"""BlockCheck runner — orchestrates all tests with callback progress and cancellation."""

from __future__ import annotations

import logging
import re
import socket
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from blockcheck.config import (
    DEFAULT_PARALLEL,
    HTTPS_TIMEOUT,
    STUN_TIMEOUT,
    TCP_HEALTH_MAX_CANDIDATES,
    TCP_HEALTH_TIMEOUT,
    TCP_TARGET_MAX_COUNT,
    TCP_TARGETS_PER_PROVIDER,
)
from blockcheck.dpi_classifier import DPIClassifier
from blockcheck.dns_integrity import check_dns_integrity
from blockcheck.preflight import run_preflight
from blockcheck.isp_page_detector import check_http_injection, detect_isp_page
from blockcheck.models import (
    BlockcheckReport,
    DPIClassification,
    DNSIntegrityResult,
    PreflightVerdict,
    SingleTestResult,
    TargetResult,
    TestStatus,
    TestType,
)
from blockcheck.ping_tester import ping_host
from blockcheck.stun_tester import test_stun
from blockcheck.targets import (
    build_targets_with_user_domains,
    load_domains_with_source,
    load_tcp_targets_with_source,
    select_tcp_targets,
)
from blockcheck.tcp_test import check_tcp_16_20, probe_tcp_target_health
from blockcheck.tls_tester import test_https

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Callback protocol
# ---------------------------------------------------------------------------

@runtime_checkable
class BlockcheckCallback(Protocol):
    def on_target_started(self, name: str, index: int, total: int) -> None: ...
    def on_test_result(self, result: SingleTestResult) -> None: ...
    def on_target_complete(self, result: TargetResult) -> None: ...
    def on_progress(self, current: int, total: int, message: str) -> None: ...
    def on_phase_change(self, phase: str) -> None: ...
    def on_log(self, message: str) -> None: ...
    def is_cancelled(self) -> bool: ...


class _NullCallback:
    """No-op callback for headless usage."""
    def on_target_started(self, name, index, total): pass
    def on_test_result(self, result): pass
    def on_target_complete(self, result): pass
    def on_progress(self, current, total, message): pass
    def on_phase_change(self, phase): pass
    def on_log(self, message): pass
    def is_cancelled(self): return False


# ---------------------------------------------------------------------------
# Run modes
# ---------------------------------------------------------------------------

class RunMode:
    QUICK = "quick"       # HTTPS + Ping only (fastest)
    FULL = "full"         # All tests
    DPI_ONLY = "dpi_only" # TLS + DPI + DNS + ISP (no ping/stun)


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

class BlockcheckRunner:
    """Orchestrates all blockcheck tests. Sync — call from QThread."""

    QUICK_TIMEOUT = 5   # seconds — shorter for quick mode

    def __init__(
        self,
        mode: str = RunMode.FULL,
        timeout: int | None = None,
        parallel: int = DEFAULT_PARALLEL,
        callback: BlockcheckCallback | None = None,
        extra_domains: list[str] | None = None,
        skip_preflight_failed: bool = False,
    ):
        self.mode = mode
        if timeout is not None:
            self.timeout = timeout
        elif mode == RunMode.QUICK:
            self.timeout = self.QUICK_TIMEOUT
        else:
            self.timeout = HTTPS_TIMEOUT
        self.parallel = parallel
        self.cb = callback or _NullCallback()
        self._cancelled = threading.Event()
        self._extra_domains = extra_domains
        self._skip_preflight_failed = skip_preflight_failed

    def cancel(self) -> None:
        """Thread-safe cancellation."""
        self._cancelled.set()

    @property
    def cancelled(self) -> bool:
        return self._cancelled.is_set() or self.cb.is_cancelled()

    def run(self) -> BlockcheckReport:
        """Run all test phases sequentially, return report."""
        start_time = time.time()
        report = BlockcheckReport()
        targets = build_targets_with_user_domains(self._extra_domains)

        phase_count = self._count_phases()
        current_phase = 0

        # ── Phase 0: Preflight ──
        if not self.cancelled:
            current_phase += 1
            self.cb.on_phase_change(f"Фаза {current_phase}/{phase_count}: Preflight проверка")
            self.cb.on_log("=== Preflight — предварительная проверка доменов ===")
            preflight_domains = self._extract_unique_hosts(targets)
            report.preflight = run_preflight(
                preflight_domains,
                callback=self.cb,
                parallel=self.parallel,
                cancelled=lambda: self.cancelled,
            )
            if self._skip_preflight_failed and report.preflight:
                failed_domains = {
                    p.domain for p in report.preflight
                    if p.verdict == PreflightVerdict.FAILED
                }
                if failed_domains:
                    before = len(targets)
                    targets = [
                        t for t in targets
                        if self._extract_host_from_target(t) not in failed_domains
                    ]
                    skipped = before - len(targets)
                    self.cb.on_log(
                        f"Preflight: пропущено {skipped} целей "
                        f"({len(failed_domains)} проблемных доменов)"
                    )

        # ── Phase 1: DNS integrity ──
        if self.mode in (RunMode.FULL, RunMode.DPI_ONLY) and not self.cancelled:
            current_phase += 1
            self.cb.on_phase_change(f"Фаза {current_phase}/{phase_count}: DNS проверка")
            self.cb.on_log("=== DNS Integrity Check ===")
            dns_domains, dns_source = load_domains_with_source()
            self.cb.on_log(f"DNS domains source: {dns_source} ({len(dns_domains)} total)")
            if dns_source.startswith("fallback"):
                self.cb.on_log("WARNING: DNS domains list fallback is in use (reduced coverage)")
            report.dns_integrity = check_dns_integrity(
                dns_domains,
                callback=lambda msg: self.cb.on_log(msg),
                cancelled=lambda: self.cancelled,
            )
            for d in report.dns_integrity:
                status = self._dns_status_text(d)
                sys_v4, sys_v6 = self._resolve_host_ips(d.domain)
                self.cb.on_log(
                    f"  {d.domain}: UDP={d.udp_ips}, DoH={d.doh_ips}, "
                    f"SYSv4={sys_v4 or ['-']}, SYSv6={sys_v6 or ['-']} → {status}"
                )

        # ── Phase 2: TLS tests ──
        if not self.cancelled:
            current_phase += 1
            self.cb.on_phase_change(f"Фаза {current_phase}/{phase_count}: TLS тесты")
            self.cb.on_log("\n=== TLS / HTTPS Tests ===")
            https_targets = [t for t in targets if not t["value"].startswith(("PING:", "STUN:"))]
            report.targets = self._run_https_phase(https_targets)

        # ── Phase 3: ISP page detection ──
        if self.mode in (RunMode.FULL, RunMode.DPI_ONLY) and not self.cancelled:
            current_phase += 1
            self.cb.on_phase_change(f"Фаза {current_phase}/{phase_count}: ISP детекция")
            self.cb.on_log("\n=== ISP Page Detection ===")
            self._run_isp_phase(report.targets)

        # ── Phase 4: TCP 16-20KB ──
        if self.mode in (RunMode.FULL, RunMode.DPI_ONLY) and not self.cancelled:
            current_phase += 1
            self.cb.on_phase_change(f"Фаза {current_phase}/{phase_count}: TCP 16-20KB")
            self.cb.on_log("\n=== TCP 16-20KB Block Test ===")
            tcp_results = self._run_tcp_phase()
            if tcp_results:
                tcp_target = TargetResult(
                    name="TCP 16-20KB",
                    value="TCP:16-20KB",
                    tests=tcp_results,
                )
                report.targets.append(tcp_target)
                self.cb.on_target_complete(tcp_target)

        # ── Phase 5: STUN/UDP ──
        if self.mode == RunMode.FULL and not self.cancelled:
            current_phase += 1
            self.cb.on_phase_change(f"Фаза {current_phase}/{phase_count}: STUN/UDP")
            self.cb.on_log("\n=== STUN/UDP Tests ===")
            stun_targets = [t for t in targets if t["value"].startswith("STUN:")]
            stun_results = self._run_stun_phase(stun_targets)
            report.targets.extend(stun_results)

        # ── Phase 6: Ping ──
        if self.mode in (RunMode.FULL, RunMode.QUICK) and not self.cancelled:
            current_phase += 1
            self.cb.on_phase_change(f"Фаза {current_phase}/{phase_count}: Ping")
            self.cb.on_log("\n=== Ping Tests ===")
            self._run_ping_phase(report.targets, targets)

        # ── Phase 7: DPI Classification ──
        if not self.cancelled:
            self.cb.on_phase_change("Классификация DPI...")
            self.cb.on_log("\n=== DPI Classification ===")
            self._attach_dns_stub_tests(report.targets, report.dns_integrity)
            for tr in report.targets:
                classification, detail = DPIClassifier.classify(tr)
                tr.classification = classification
                tr.classification_detail = detail
                self.cb.on_log(f"  {tr.name}: {classification.value} — {detail}")

        # ── Summary ──
        was_cancelled = self.cancelled
        report.elapsed_seconds = time.time() - start_time
        report.cancelled = was_cancelled
        report.summary = self._build_summary(report)
        if was_cancelled:
            self.cb.on_phase_change("Отменено")
            self.cb.on_log(f"\nCancelled after {report.elapsed_seconds:.1f}s")
        else:
            self.cb.on_phase_change("Готово")
            self.cb.on_log(f"\nCompleted in {report.elapsed_seconds:.1f}s")
        return report

    # ------------------------------------------------------------------
    # Phase implementations
    # ------------------------------------------------------------------

    def _run_https_phase(self, https_targets: list[dict]) -> list[TargetResult]:
        """Run HTTP, TLS 1.2, TLS 1.3 tests for each HTTPS target (parallel)."""
        total = len(https_targets)
        # Pre-build TargetResult list to preserve order
        results: list[TargetResult] = []
        target_map: dict[str, dict[str, Any]] = {}

        for i, target in enumerate(https_targets):
            name = target["name"]
            value = target["value"]
            host = re.sub(r"^https?://", "", value).rstrip("/").split("/")[0]
            tr = TargetResult(name=name, value=value)
            results.append(tr)

            ipv4, ipv6 = self._resolve_host_ips(host)
            families: list[str] = []
            if ipv4:
                families.append("ipv4")
            if ipv6:
                families.append("ipv6")
            if not families:
                # Keep at least one probe path for diagnostics.
                families = ["ipv4"]

            target_map[name] = {
                "index": i,
                "target": tr,
                "host": host,
                "families": families,
                "expected": len(families) * 3,
            }

            self.cb.on_log(
                f"  DNS {name}: IPv4={ipv4 or ['-']}, IPv6={ipv6 or ['-']}, test_families={families}"
            )

        # Submit all jobs to thread pool: 3 tests per target
        def _run_one(name: str, host: str, tls_version: str | None, ip_family: str):
            """Run a single TLS test — called in a pool thread."""
            return name, tls_version, ip_family, test_https(
                host,
                timeout=self.timeout,
                tls_version=tls_version,
                ip_family=ip_family,
            )

        completed_targets = set()
        cancelled_during_phase = False
        pool = ThreadPoolExecutor(max_workers=self.parallel)
        try:
            futures = []
            for name, data in target_map.items():
                if self.cancelled:
                    cancelled_during_phase = True
                    break
                idx = int(data["index"])
                host = str(data["host"])
                families = list(data["families"])
                self.cb.on_target_started(name, idx, total)
                for tls_v in (None, "1.2", "1.3"):
                    for ip_family in families:
                        futures.append(pool.submit(_run_one, name, host, tls_v, ip_family))

            for future in as_completed(futures):
                if self.cancelled:
                    cancelled_during_phase = True
                    break
                name, tls_v, ip_family, r = future.result()
                target_data = target_map[name]
                tr = target_data["target"]
                r.target_name = name
                r.raw_data.setdefault("ip_family", ip_family)
                tr.tests.append(r)

                label = {None: "HTTP", "1.2": "TLS1.2", "1.3": "TLS1.3"}[tls_v]
                family_label = "IPv6" if ip_family == "ipv6" else "IPv4"
                self.cb.on_test_result(r)
                self.cb.on_log(f"  {name} {label} [{family_label}]: {r.status.value} {r.detail}")
                self.cb.on_progress(len(completed_targets), total, f"{name} {label} [{family_label}]")

                expected = int(target_data["expected"])
                if len(tr.tests) >= expected and name not in completed_targets:
                    completed_targets.add(name)
                    self.cb.on_target_complete(tr)
        finally:
            pool.shutdown(wait=not cancelled_during_phase, cancel_futures=cancelled_during_phase)

        # Emit for targets that finished partially (cancelled)
        for name, data in target_map.items():
            tr = data["target"]
            if name not in completed_targets and tr.tests:
                self.cb.on_target_complete(tr)

        return results

    def _run_isp_phase(self, target_results: list[TargetResult]) -> None:
        """Run ISP page detection for existing HTTPS targets (parallel)."""
        if not target_results:
            return

        def _isp_one(tr):
            host = re.sub(r"^https?://", "", tr.value).rstrip("/").split("/")[0]
            http_result = check_http_injection(host)
            http_result.target_name = tr.name

            if http_result.status == TestStatus.FAIL and http_result.error_code == "HTTP_INJECT":
                return tr, http_result, "http"

            https_result = detect_isp_page(host)
            https_result.target_name = tr.name

            if https_result.status == TestStatus.FAIL and https_result.error_code == "ISP_PAGE":
                return tr, https_result, "https"

            if http_result.status != TestStatus.OK and https_result.status == TestStatus.OK:
                return tr, https_result, "https"

            return tr, http_result, "http"

        cancelled_during_phase = False
        pool = ThreadPoolExecutor(max_workers=self.parallel)
        try:
            futures = [pool.submit(_isp_one, tr) for tr in target_results]
            for future in as_completed(futures):
                if self.cancelled:
                    cancelled_during_phase = True
                    break
                tr, r, source = future.result()
                tr.tests.append(r)
                self.cb.on_test_result(r)
                self.cb.on_log(f"  ISP {tr.name} ({source.upper()}): {r.status.value} {r.detail}")
        finally:
            pool.shutdown(wait=not cancelled_during_phase, cancel_futures=cancelled_during_phase)

    def _run_tcp_phase(self) -> list[SingleTestResult]:
        """Run TCP 16-20KB tests (parallel, diverse provider subset)."""
        all_tcp, source = load_tcp_targets_with_source()
        self.cb.on_log(f"TCP targets source: {source} ({len(all_tcp)} total)")
        if source.startswith("fallback"):
            self.cb.on_log("WARNING: TCP target list fallback is in use (reduced coverage)")

        candidate_targets = select_tcp_targets(
            all_tcp,
            max_count=TCP_HEALTH_MAX_CANDIDATES,
            per_provider_cap=max(TCP_TARGETS_PER_PROVIDER + 1, 3),
        )
        health_map = self._probe_tcp_targets_health(candidate_targets)

        healthy_count = sum(1 for ok, _detail, _elapsed in health_map.values() if ok)
        self.cb.on_log(
            f"TCP health probe: {healthy_count}/{len(candidate_targets)} reachable "
            f"(timeout={TCP_HEALTH_TIMEOUT}s)"
        )

        tcp_targets = self._select_rotated_tcp_targets(candidate_targets, health_map)
        if not tcp_targets:
            self.cb.on_log("WARNING: No TCP targets selected for 16-20KB phase")
            return []

        selected_providers = sorted({str(t.get("provider") or "unknown") for t in tcp_targets})
        self.cb.on_log(
            f"TCP targets selected: {len(tcp_targets)} across {len(selected_providers)} providers "
            f"(up to {TCP_TARGETS_PER_PROVIDER} per provider)"
        )
        selected_ids = ", ".join(
            str(t.get("id") or t.get("name") or t.get("url") or "?") for t in tcp_targets
        )
        self.cb.on_log(f"TCP selected IDs: {selected_ids}")
        if healthy_count == 0:
            self.cb.on_log("WARNING: TCP health probe found no reachable URLs; results may be noisy")

        tcp_results: list[SingleTestResult] = []

        def _tcp_one(tcp_t):
            target_name = str(tcp_t.get("name") or tcp_t.get("id") or tcp_t.get("url", "unknown"))
            provider = str(tcp_t.get("provider") or "unknown")
            asn = str(tcp_t.get("asn") or "")
            url = str(tcp_t.get("url") or "")
            r = check_tcp_16_20(tcp_t["url"])
            r.target_name = target_name
            r.raw_data.setdefault("target_id", target_name)
            r.raw_data.setdefault("provider", provider)
            if asn:
                r.raw_data.setdefault("asn", asn)
            if url:
                r.raw_data.setdefault("url", url)
            return target_name, r

        cancelled_during_phase = False
        pool = ThreadPoolExecutor(max_workers=self.parallel)
        try:
            futures = [pool.submit(_tcp_one, t) for t in tcp_targets]
            for future in as_completed(futures):
                if self.cancelled:
                    cancelled_during_phase = True
                    break
                target_name, r = future.result()
                tcp_results.append(r)
                self.cb.on_test_result(r)
                self.cb.on_log(f"  TCP 16-20KB {target_name}: {r.status.value} {r.detail}")
        finally:
            pool.shutdown(wait=not cancelled_during_phase, cancel_futures=cancelled_during_phase)

        return tcp_results

    @staticmethod
    def _tcp_scan_key(target: dict) -> str:
        return str(target.get("id") or target.get("url") or "")

    def _probe_tcp_targets_health(
        self,
        targets: list[dict],
    ) -> dict[str, tuple[bool, str, float]]:
        """Probe candidate TCP target URLs and return health map."""
        if not targets:
            return {}

        health: dict[str, tuple[bool, str, float]] = {}

        def _probe_one(target: dict) -> tuple[str, tuple[bool, str, float]]:
            key = self._tcp_scan_key(target)
            ok, detail, elapsed = probe_tcp_target_health(
                str(target.get("url") or ""),
                timeout=TCP_HEALTH_TIMEOUT,
            )
            return key, (ok, detail, elapsed)

        workers = min(max(2, self.parallel * 2), 16)
        cancelled_during_phase = False
        pool = ThreadPoolExecutor(max_workers=workers)
        try:
            futures = [pool.submit(_probe_one, t) for t in targets]
            for future in as_completed(futures):
                if self.cancelled:
                    cancelled_during_phase = True
                    break
                key, result = future.result()
                health[key] = result
        finally:
            pool.shutdown(wait=not cancelled_during_phase, cancel_futures=cancelled_during_phase)

        return health

    def _select_rotated_tcp_targets(
        self,
        candidates: list[dict],
        health_map: dict[str, tuple[bool, str, float]],
    ) -> list[dict]:
        """Select up to N targets with provider diversity and health-based rotation."""
        if not candidates:
            return []

        provider_buckets: dict[str, dict[str, Any]] = {}
        provider_order: list[str] = []

        for target in candidates:
            provider = str(target.get("provider") or "unknown")
            key = self._tcp_scan_key(target)
            is_healthy = health_map.get(key, (False, "", 0.0))[0]

            if provider not in provider_buckets:
                provider_buckets[provider] = {
                    "healthy": [],
                    "fallback": [],
                    "healthy_idx": 0,
                    "fallback_idx": 0,
                    "taken": 0,
                }
                provider_order.append(provider)

            if is_healthy:
                provider_buckets[provider]["healthy"].append(target)
            else:
                provider_buckets[provider]["fallback"].append(target)

        selected: list[dict] = []
        picked_keys: set[str] = set()

        def _round_robin(stage: str) -> bool:
            added_any = False

            for provider in provider_order:
                bucket = provider_buckets[provider]
                if bucket["taken"] >= TCP_TARGETS_PER_PROVIDER:
                    continue

                if stage == "healthy":
                    idx = int(bucket["healthy_idx"])
                    pool = bucket["healthy"]
                else:
                    idx = int(bucket["fallback_idx"])
                    pool = bucket["fallback"]

                if idx >= len(pool):
                    continue

                candidate = pool[idx]
                key = self._tcp_scan_key(candidate)

                if stage == "healthy":
                    bucket["healthy_idx"] = idx + 1
                else:
                    bucket["fallback_idx"] = idx + 1

                if key in picked_keys:
                    continue

                selected.append(candidate)
                picked_keys.add(key)
                bucket["taken"] = int(bucket["taken"]) + 1
                added_any = True

                if len(selected) >= TCP_TARGET_MAX_COUNT:
                    break

            return added_any

        # Stage 1: prioritize healthy URLs.
        while len(selected) < TCP_TARGET_MAX_COUNT and _round_robin("healthy"):
            pass

        # Stage 2: fill remaining slots with fallback URLs if needed.
        while len(selected) < TCP_TARGET_MAX_COUNT and _round_robin("fallback"):
            pass

        if not selected:
            return candidates[:TCP_TARGET_MAX_COUNT]

        return selected

    def _run_stun_phase(self, stun_targets: list[dict]) -> list[TargetResult]:
        """Run STUN/UDP tests (parallel)."""
        results: list[TargetResult] = []
        if not stun_targets:
            return results

        def _parse_stun_endpoint(value: str) -> tuple[str, int]:
            raw = str(value or "").strip()
            if raw.upper().startswith("STUN:"):
                raw = raw[5:].strip()
            if not raw:
                return "", 3478

            if raw.startswith("["):
                right = raw.find("]")
                if right > 1:
                    host = raw[1:right].strip()
                    rest = raw[right + 1 :].strip()
                    if rest.startswith(":"):
                        try:
                            port = int(rest[1:])
                            if 1 <= port <= 65535:
                                return host, port
                        except ValueError:
                            pass
                    return host, 3478

            if raw.count(":") == 1:
                host, port_str = raw.rsplit(":", 1)
                host = host.strip()
                if host:
                    try:
                        port = int(port_str)
                        if 1 <= port <= 65535:
                            return host, port
                    except ValueError:
                        pass
                    return host, 3478

            return raw, 3478

        def _test_one_stun(target):
            value = target["value"]
            host, port = _parse_stun_endpoint(value)
            r = test_stun(host, port, timeout=STUN_TIMEOUT)
            r.target_name = target["name"]
            return target, r

        cancelled_during_phase = False
        pool = ThreadPoolExecutor(max_workers=self.parallel)
        try:
            futures = [pool.submit(_test_one_stun, t) for t in stun_targets]
            for future in as_completed(futures):
                if self.cancelled:
                    cancelled_during_phase = True
                    break
                target, r = future.result()
                tr = TargetResult(name=target["name"], value=target["value"], tests=[r])
                self.cb.on_test_result(r)
                self.cb.on_target_complete(tr)
                self.cb.on_log(f"  STUN {target['name']}: {r.status.value} {r.detail}")
                results.append(tr)
        finally:
            pool.shutdown(wait=not cancelled_during_phase, cancel_futures=cancelled_during_phase)

        return results

    def _run_ping_phase(self, target_results: list[TargetResult], all_targets: list[dict]) -> None:
        """Run ping tests for all targets (parallel)."""
        # Build jobs: (target_name, host, existing_tr_or_None)
        jobs: list[tuple[str, str, TargetResult | None]] = []

        ping_targets = [t for t in all_targets if t["value"].startswith("PING:")]
        for target in ping_targets:
            host = target["value"].replace("PING:", "").strip()
            jobs.append((target["name"], host, None))

        for tr in target_results:
            if tr.value.startswith(("PING:", "STUN:", "TCP:")):
                continue
            host = re.sub(r"^https?://", "", tr.value).rstrip("/").split("/")[0]
            jobs.append((tr.name, host, tr))

        if not jobs:
            return

        def _ping_one(name, host):
            r = ping_host(host)
            r.target_name = name
            return name, r

        cancelled_during_phase = False
        pool = ThreadPoolExecutor(max_workers=self.parallel)
        try:
            futures = {pool.submit(_ping_one, name, host): (name, host, tr_ref) for name, host, tr_ref in jobs}
            for future in as_completed(futures):
                if self.cancelled:
                    cancelled_during_phase = True
                    break
                name, host, tr_ref = futures[future]
                _name, r = future.result()
                self.cb.on_test_result(r)
                self.cb.on_log(f"  Ping {name}: {r.detail}")

                if tr_ref is not None:
                    tr_ref.tests.append(r)
                else:
                    # Ping-only target
                    ping_t = next((t for t in ping_targets if t["name"] == name), None)
                    value = ping_t["value"] if ping_t else f"PING:{host}"
                    tr = TargetResult(name=name, value=value, tests=[r])
                    target_results.append(tr)
        finally:
            pool.shutdown(wait=not cancelled_during_phase, cancel_futures=cancelled_during_phase)

    def _attach_dns_stub_tests(
        self,
        target_results: list[TargetResult],
        dns_results: list[DNSIntegrityResult],
    ) -> None:
        """Attach DNS stub/inconsistency evidence to matching HTTPS targets."""
        if not dns_results or not target_results:
            return

        public_suffix_2level = {
            "co.uk", "org.uk", "ac.uk", "gov.uk",
            "com.au", "net.au", "org.au",
            "co.jp", "ne.jp", "or.jp",
            "com.br", "com.mx", "com.tr", "co.id",
            "com.ua", "co.kr", "co.in",
        }

        def _host_candidates(raw_host: str) -> set[str]:
            host = raw_host.strip().lower().rstrip(".")
            if not host:
                return set()

            candidates = {host}
            if host.startswith("www."):
                candidates.add(host[4:])

            parts = host.split(".")
            if len(parts) >= 2:
                base2 = ".".join(parts[-2:])
                candidates.add(base2)
                if len(parts) >= 3 and base2 in public_suffix_2level:
                    candidates.add(".".join(parts[-3:]))

            return {c for c in candidates if c and "." in c}

        fake_domains: set[str] = set()
        for dns_result in dns_results:
            comparable = dns_result.is_comparable or bool(dns_result.udp_ips and dns_result.doh_ips)
            is_fake = dns_result.is_stub or (comparable and not dns_result.is_consistent)
            if not is_fake:
                continue
            fake_domains.update(_host_candidates(dns_result.domain))

        if not fake_domains:
            return

        for tr in target_results:
            if tr.value.startswith(("PING:", "STUN:", "TCP:")):
                continue

            host = re.sub(r"^https?://", "", tr.value).rstrip("/").split("/")[0]
            host = host.lower().split(":", 1)[0]
            host_variants = _host_candidates(host)
            if not host_variants:
                continue

            matched = any(
                host_variant == fake_domain or host_variant.endswith(f".{fake_domain}")
                for host_variant in host_variants
                for fake_domain in fake_domains
            )
            if not matched:
                continue

            has_dns_stub = any(
                t.test_type in (TestType.DNS_UDP, TestType.DNS_DOH) and t.error_code == "STUB"
                for t in tr.tests
            )
            if has_dns_stub:
                continue

            tr.tests.append(
                SingleTestResult(
                    target_name=tr.name,
                    test_type=TestType.DNS_UDP,
                    status=TestStatus.FAIL,
                    error_code="STUB",
                    detail="DNS integrity check detected stub/inconsistent response",
                )
            )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_unique_hosts(targets: list[dict]) -> list[str]:
        """Extract unique domain names from HTTPS targets (skip PING/STUN/TCP)."""
        seen: set[str] = set()
        result: list[str] = []
        for t in targets:
            v = t["value"]
            if v.startswith(("PING:", "STUN:", "TCP:")):
                continue
            host = re.sub(r"^https?://", "", v).rstrip("/").split("/")[0].lower()
            if host and host not in seen:
                seen.add(host)
                result.append(host)
        return result

    @staticmethod
    def _extract_host_from_target(target: dict) -> str:
        """Extract host from a single target dict."""
        v = target["value"]
        if v.startswith(("PING:", "STUN:", "TCP:")):
            return v
        return re.sub(r"^https?://", "", v).rstrip("/").split("/")[0].lower()

    @staticmethod
    def _resolve_host_ips(host: str) -> tuple[list[str], list[str]]:
        """Resolve host and return (ipv4_list, ipv6_list)."""
        host = str(host or "").strip()
        if not host:
            return [], []

        ipv4: list[str] = []
        ipv6: list[str] = []

        try:
            infos = socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP)
        except Exception:
            return [], []

        for family, _socktype, _proto, _canonname, sockaddr in infos:
            ip_raw = sockaddr[0]
            if not isinstance(ip_raw, str):
                continue
            ip = ip_raw
            if family == socket.AF_INET:
                if ip not in ipv4:
                    ipv4.append(ip)
            elif family == socket.AF_INET6:
                if ip not in ipv6:
                    ipv6.append(ip)

        return ipv4, ipv6

    @staticmethod
    def _dns_status_text(result: DNSIntegrityResult) -> str:
        """Human status for DNS log lines."""
        if result.is_stub:
            return "FAKE(STUB)"
        comparable = result.is_comparable or bool(result.udp_ips and result.doh_ips)
        if comparable:
            return "OK" if result.is_consistent else "FAKE"
        if result.udp_ips and not result.doh_ips:
            return "NO_DOH"
        if result.doh_ips and not result.udp_ips:
            return "NO_UDP"
        return "NO_DNS"

    def _count_phases(self) -> int:
        if self.mode == RunMode.QUICK:
            return 3  # Preflight + TLS + Ping
        if self.mode == RunMode.DPI_ONLY:
            return 5  # Preflight + DNS + TLS + ISP + TCP
        return 7  # Preflight + Full: DNS + TLS + ISP + TCP + STUN + Ping

    @staticmethod
    def _build_summary(report: BlockcheckReport) -> dict:
        """Build summary statistics from the report."""
        stats: dict[str, Any] = {
            "http_ok": 0, "http_fail": 0,
            "tls12_ok": 0, "tls12_fail": 0, "tls12_unsup": 0,
            "tls13_ok": 0, "tls13_fail": 0, "tls13_unsup": 0,
            "stun_ok": 0, "stun_fail": 0,
            "ping_ok": 0, "ping_fail": 0,
            "dns_ok": 0, "dns_fake": 0,
            "dns_unknown": 0,
            "isp_ok": 0, "isp_inject": 0,
            "tcp_ok": 0, "tcp_block": 0,
            "dpi_types": [],
            "dpi_count": 0,
        }

        for tr in report.targets:
            for t in tr.tests:
                if t.test_type == TestType.HTTP:
                    if t.status == TestStatus.OK:
                        stats["http_ok"] += 1
                    else:
                        stats["http_fail"] += 1
                elif t.test_type == TestType.TLS_12:
                    if t.status == TestStatus.OK:
                        stats["tls12_ok"] += 1
                    elif t.status == TestStatus.UNSUPPORTED:
                        stats["tls12_unsup"] += 1
                    else:
                        stats["tls12_fail"] += 1
                elif t.test_type == TestType.TLS_13:
                    if t.status == TestStatus.OK:
                        stats["tls13_ok"] += 1
                    elif t.status == TestStatus.UNSUPPORTED:
                        stats["tls13_unsup"] += 1
                    else:
                        stats["tls13_fail"] += 1
                elif t.test_type == TestType.STUN:
                    if t.status == TestStatus.OK:
                        stats["stun_ok"] += 1
                    else:
                        stats["stun_fail"] += 1
                elif t.test_type == TestType.PING:
                    if t.status == TestStatus.OK:
                        stats["ping_ok"] += 1
                    else:
                        stats["ping_fail"] += 1
                elif t.test_type == TestType.ISP_PAGE:
                    if t.status == TestStatus.OK:
                        stats["isp_ok"] += 1
                    else:
                        stats["isp_inject"] += 1
                elif t.test_type == TestType.TCP_16_20:
                    if t.status == TestStatus.OK:
                        stats["tcp_ok"] += 1
                    else:
                        stats["tcp_block"] += 1

        for d in report.dns_integrity:
            comparable = d.is_comparable or bool(d.udp_ips and d.doh_ips)
            if d.is_stub:
                stats["dns_fake"] += 1
            elif comparable:
                if d.is_consistent:
                    stats["dns_ok"] += 1
                else:
                    stats["dns_fake"] += 1
            else:
                stats["dns_unknown"] += 1

        # DPI classifications
        classifications = [tr.classification for tr in report.targets]
        dpi_detected = [c for c in classifications if c != DPIClassification.NONE]
        stats["dpi_types"] = sorted({c.value for c in dpi_detected})
        stats["dpi_count"] = len(dpi_detected)

        # Preflight
        stats["preflight_passed"] = sum(
            1 for p in report.preflight if p.verdict == PreflightVerdict.PASSED
        )
        stats["preflight_warned"] = sum(
            1 for p in report.preflight if p.verdict == PreflightVerdict.WARNING
        )
        stats["preflight_failed"] = sum(
            1 for p in report.preflight if p.verdict == PreflightVerdict.FAILED
        )

        return stats
