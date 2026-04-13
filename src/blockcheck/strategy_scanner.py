"""Strategy brute-force scanner — tests DPI bypass strategies via winws2 + protocol probes.

Lifecycle per strategy:
  1. Write temp preset file
  2. Launch winws2.exe @preset
  3. Wait for startup, verify process alive
  4. Probe target (HTTPS for TCP mode, STUN for UDP mode)
  5. Kill winws2
  6. Record result
"""

from __future__ import annotations

import concurrent.futures
import logging
import os
import secrets
import socket
import ssl
import struct
import subprocess
import threading
import time
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from blockcheck.config import (
    ISP_BODY_MARKERS,
    PROBE_TEMP_HOSTLIST,
    PROBE_TEMP_PRESET,
    STRATEGY_KILL_TIMEOUT,
    STRATEGY_PROBE_TIMEOUT,
    STRATEGY_RESPONSE_TIMEOUT,
    STRATEGY_STARTUP_WAIT,
    TCP_BLOCK_RANGE_MIN,
    TCP_BLOCK_RANGE_MAX,
)
from blockcheck.models import TestStatus
from blockcheck.scan_models import StrategyProbeResult, StrategyScanReport
from blockcheck.stun_tester import test_stun

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Callback protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class StrategyScanCallback(Protocol):
    def on_strategy_started(self, name: str, index: int, total: int) -> None: ...
    def on_strategy_result(self, result: StrategyProbeResult) -> None: ...
    def on_log(self, message: str) -> None: ...
    def on_phase(self, phase: str) -> None: ...
    def is_cancelled(self) -> bool: ...


# ---------------------------------------------------------------------------
# Null callback (for headless usage)
# ---------------------------------------------------------------------------


class _NullCallback:
    def on_strategy_started(self, name: str, index: int, total: int) -> None:
        pass

    def on_strategy_result(self, result: StrategyProbeResult) -> None:
        pass

    def on_log(self, message: str) -> None:
        pass

    def on_phase(self, phase: str) -> None:
        pass

    def is_cancelled(self) -> bool:
        return False


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_LUA_INITS = [
    "--lua-init=@lua/zapret-lib.lua",
    "--lua-init=@lua/zapret-antidpi.lua",
    "--lua-init=@lua/zapret-auto.lua",
    "--lua-init=@lua/custom_funcs.lua",
    "--lua-init=@lua/zapret-multishake.lua",
]

_PROTOCOL_TCP_HTTPS = "tcp_https"
_PROTOCOL_STUN_VOICE = "stun_voice"
_PROTOCOL_UDP_GAMES = "udp_games"
_UDP_GAMES_SCOPE_ALL = "all"
_UDP_GAMES_SCOPE_GAMES_ONLY = "games_only"
_UDP_GAMES_PORT_FILTER = "443,50000-65535"
_GAMES_IPSET_FILENAMES = (
    "ipset-roblox.txt",
    "ipset-amazon.txt",
    "ipset-steam.txt",
    "ipset-epicgames.txt",
    "ipset-epic.txt",
    "ipset-lol-ru.txt",
    "ipset-lol-euw.txt",
    "ipset-tankix.txt",
)
_PROBE_TEMP_GAMES_IPSET = "blockcheck_probe_games_ipset.txt"
_UDP_POOL_MAX_WORKERS = 6
_UDP_GAMES_CANARY_PROBES: tuple[dict[str, Any], ...] = (
    {"name": "Rust A2S", "kind": "source_a2s", "host": "205.178.168.170", "port": 28015},
    {"name": "CS A2S", "kind": "source_a2s", "host": "46.174.55.234", "port": 27015},
    {"name": "Bedrock CubeCraft", "kind": "bedrock_ping", "host": "play.cubecraft.net", "port": 19132},
)

# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------


class StrategyScanner:
    """Sequential strategy prober for TCP/HTTPS or UDP/STUN."""

    def __init__(
        self,
        target: str,
        mode: str = "quick",
        start_index: int = 0,
        callback: StrategyScanCallback | None = None,
        scan_protocol: str = _PROTOCOL_TCP_HTTPS,
        udp_games_scope: str = _UDP_GAMES_SCOPE_ALL,
    ):
        self._scan_protocol = self._normalize_scan_protocol(scan_protocol)
        self._udp_games_scope = self._normalize_udp_games_scope(udp_games_scope)
        if self._scan_protocol != _PROTOCOL_UDP_GAMES:
            self._udp_games_scope = _UDP_GAMES_SCOPE_ALL
        raw_target = (target or "").strip()
        if self._scan_protocol in {_PROTOCOL_STUN_VOICE, _PROTOCOL_UDP_GAMES}:
            host, port = self._parse_stun_target(raw_target)
            self._target_host = host or "stun.l.google.com"
            self._target_port = int(port)
            self._target = self._format_endpoint(self._target_host, self._target_port)
        else:
            self._target_host = raw_target or "discord.com"
            self._target_port = 443
            self._target = self._target_host

        self._mode = mode
        try:
            self._start_index = max(0, int(start_index))
        except Exception:
            self._start_index = 0
        self._cb: StrategyScanCallback = callback or _NullCallback()
        self._cancelled = False
        self._process: subprocess.Popen | None = None
        self._process_lock = threading.Lock()
        self._games_ipset_sources: list[str] = []
        self._games_ipset_compiled_path: str | None = None
        self._games_ipset_entries_count: int = 0
        self._baseline_by_af: dict[int, bool | None] = {
            socket.AF_INET: None,
            socket.AF_INET6: None,
        }
        self._probe_families: list[int] = [socket.AF_INET]

        # Resolve paths
        self._work_dir = self._find_work_dir()
        self._winws2_exe = self._find_winws2()

    @property
    def cancelled(self) -> bool:
        return bool(self._cancelled or self._cb.is_cancelled())

    @staticmethod
    def _normalize_scan_protocol(scan_protocol: str) -> str:
        """Normalize protocol aliases to scanner-supported values."""
        key = (scan_protocol or "").strip().lower()
        if key in {"stun", "udp_stun", "udp/stun", "stun_voice", "discord_stun", "voice_stun"}:
            return _PROTOCOL_STUN_VOICE
        if key in {"udp_games", "games_udp", "roblox_udp", "games"}:
            return _PROTOCOL_UDP_GAMES
        return _PROTOCOL_TCP_HTTPS

    @staticmethod
    def _normalize_udp_games_scope(scope: str) -> str:
        """Normalize UDP games coverage scope selector."""
        key = (scope or "").strip().lower()
        if key in {"games_only", "games", "only_games", "targeted"}:
            return _UDP_GAMES_SCOPE_GAMES_ONLY
        return _UDP_GAMES_SCOPE_ALL

    @staticmethod
    def _parse_stun_target(target: str, default_port: int = 3478) -> tuple[str, int]:
        """Parse STUN target into (host, port). Supports [IPv6]:port."""
        raw = (target or "").strip()
        if not raw:
            return "", default_port

        if raw.upper().startswith("STUN:"):
            raw = raw[5:].strip()

        raw = raw.split("/", 1)[0].split("?", 1)[0].split("#", 1)[0].strip()
        if not raw:
            return "", default_port

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
                return host, default_port

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
                return host, default_port

        # Likely IPv6 literal without brackets, or plain host without explicit port.
        return raw, default_port

    @staticmethod
    def _format_endpoint(host: str, port: int) -> str:
        """Format endpoint as host:port, brackets for IPv6 literals."""
        host = (host or "").strip()
        if ":" in host and not host.startswith("["):
            return f"[{host}]:{int(port)}"
        return f"{host}:{int(port)}"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self) -> StrategyScanReport:
        """Run the scan. Blocking — call from a background thread."""
        t0 = time.monotonic()

        strategies, start_index, total_available = self._select_strategies(self._mode, self._start_index)
        batch_size = len(strategies)
        if self._scan_protocol == _PROTOCOL_STUN_VOICE:
            protocol_label = "STUN Voice (Discord/Telegram)"
        elif self._scan_protocol == _PROTOCOL_UDP_GAMES:
            protocol_label = "UDP Games (multi-ipset profile)"
        else:
            protocol_label = "TCP/HTTPS"
        self._cb.on_log(
            f"Scan mode: {self._mode}, protocol: {protocol_label}, total: {total_available}, "
            f"batch: {batch_size}, target: {self._target}"
        )
        if self._scan_protocol == _PROTOCOL_UDP_GAMES:
            scope_label = "all ipsets" if self._udp_games_scope == _UDP_GAMES_SCOPE_ALL else "games-only ipsets"
            self._cb.on_log(f"UDP games scope: {scope_label}")
        if self._scan_protocol in {_PROTOCOL_STUN_VOICE, _PROTOCOL_UDP_GAMES}:
            pool_size = len(self._build_udp_probe_pool())
            self._cb.on_log(f"UDP probe pool targets: {pool_size}")
        if start_index > 0:
            self._cb.on_log(f"Resume enabled: starting from strategy {start_index + 1}/{total_available}")
        self._cb.on_phase(f"Подготовка ({total_available} стратегий)")

        working: list[StrategyProbeResult] = []
        failed: list[StrategyProbeResult] = []

        # Pre-scan: kill any running winws and clean WinDivert
        self._pre_scan_cleanup()

        # Preflight — быстрая проверка целевого хоста перед сканированием
        if not self.cancelled:
            preflight_ok = self._run_preflight_check()
            if not preflight_ok:
                self._cb.on_log("Preflight: обнаружены проблемы, но сканирование продолжится")

        # Baseline test: check if target is already accessible without winws2
        baseline_accessible = False if self.cancelled else self._run_baseline_test()

        for idx, strat in enumerate(strategies, start=start_index):
            if self.cancelled:
                break

            name = strat.get("name", f"strategy_{idx}")
            args = strat.get("args", "")
            strat_id = strat.get("id", name)

            self._cb.on_strategy_started(name, idx, total_available)
            self._cb.on_phase(f"[{idx + 1}/{total_available}] {name}")
            self._cb.on_log(f"\n--- [{idx + 1}/{total_available}] {name} ---")
            self._cb.on_log(f"  args: {args}")

            result = self._probe_one_strategy(
                name=name,
                strat_id=strat_id,
                args=args,
                target=self._target,
            )

            if self.cancelled and (not result.success and result.error == "Cancelled"):
                break

            self._cb.on_strategy_result(result)
            if result.success:
                working.append(result)
                self._cb.on_log(f"  SUCCESS ({result.time_ms:.0f} ms)")
            else:
                failed.append(result)
                self._cb.on_log(f"  FAIL: {result.error}")

        tested_now = len(working) + len(failed)
        tested_total = start_index + tested_now
        elapsed = time.monotonic() - t0
        was_cancelled = self.cancelled
        report = StrategyScanReport(
            target=self._target,
            total_tested=tested_total,
            total_available=total_available,
            working_strategies=working,
            failed_strategies=failed,
            elapsed_seconds=elapsed,
            cancelled=was_cancelled,
            baseline_accessible=baseline_accessible,
            scan_protocol=self._scan_protocol,
        )

        if was_cancelled:
            self._cb.on_phase("Отменено")
            self._cb.on_log(f"\nСканирование отменено. Протестировано: {report.total_tested}/{total_available}")
        else:
            self._cb.on_phase("Завершено")
            self._cb.on_log(
                f"\nГотово: {report.total_tested}/{total_available} протестировано, "
                f"{len(working)} рабочих, {elapsed:.1f}s"
            )

        # Post-scan cleanup
        self._kill_current_process()
        self._cleanup_temp_files()

        return report

    def cancel(self) -> None:
        """Request cancellation (thread-safe)."""
        self._cancelled = True
        self._kill_current_process()

    # ------------------------------------------------------------------
    # Baseline test
    # ------------------------------------------------------------------

    def _run_baseline_test(self) -> bool:
        """Run baseline probe without winws2 for selected protocol."""
        if self.cancelled:
            return False
        if self._scan_protocol in {_PROTOCOL_STUN_VOICE, _PROTOCOL_UDP_GAMES}:
            return self._run_baseline_stun()
        return self._run_baseline_https()

    @staticmethod
    def _af_label(af: int) -> str:
        return "IPv6" if af == socket.AF_INET6 else "IPv4"

    @staticmethod
    def _target_has_family(host: str, port: int, af: int, socktype: int) -> bool:
        """Check whether host resolves for a specific address family."""
        try:
            infos = socket.getaddrinfo(host, port, af, socktype)
            return bool(infos)
        except (socket.gaierror, OSError):
            return False

    def _run_baseline_https(self) -> bool:
        """Baseline HTTPS check on IPv4/IPv6."""
        if self.cancelled:
            return False
        self._cb.on_phase("Baseline-тест (без обхода)")
        self._cb.on_log("\n--- Baseline HTTPS test (без winws2) ---")

        available_families: list[int] = []
        blocked_families: list[int] = []

        for af in (socket.AF_INET, socket.AF_INET6):
            if self.cancelled:
                return False
            label = self._af_label(af)
            if not self._target_has_family(self._target_host, 443, af, socket.SOCK_STREAM):
                self._baseline_by_af[af] = None
                self._cb.on_log(f"  {label}: нет DNS записи")
                continue

            available_families.append(af)
            ok, elapsed_ms, detail = self._test_https(self._target_host, af=af)
            self._baseline_by_af[af] = ok

            if ok:
                self._cb.on_log(
                    f"  {label}: ДОСТУПЕН без обхода ({elapsed_ms:.0f} ms) — "
                    f"результаты сканирования могут быть ложноположительными"
                )
            else:
                blocked_families.append(af)
                self._cb.on_log(f"  {label}: Заблокирован — {detail}")

        if blocked_families:
            self._probe_families = blocked_families
            families_label = "/".join(self._af_label(af) for af in blocked_families)
            self._cb.on_log(f"  Сканирование стратегий — {families_label}")
            return False

        if not available_families:
            self._probe_families = [socket.AF_INET]
            self._cb.on_log("  DNS не вернул IPv4/IPv6 адреса; сканирование продолжится с IPv4 fallback")
            return False

        self._probe_families = [available_families[0]]
        self._cb.on_log("  IPv4/IPv6 уже доступны без обхода")
        return True

    def _run_baseline_stun(self) -> bool:
        """Baseline STUN check on IPv4/IPv6."""
        if self.cancelled:
            return False
        self._cb.on_phase("Baseline-тест (без обхода)")
        self._cb.on_log("\n--- Baseline STUN test (без winws2) ---")

        available_families: list[int] = []
        blocked_families: list[int] = []

        for af in (socket.AF_INET, socket.AF_INET6):
            if self.cancelled:
                return False
            label = self._af_label(af)
            if not self._target_has_family(self._target_host, self._target_port, af, socket.SOCK_DGRAM):
                self._baseline_by_af[af] = None
                self._cb.on_log(f"  {label}: нет DNS записи для STUN")
                continue

            available_families.append(af)
            ok, elapsed_ms, detail = self._test_stun_probe(self._target_host, self._target_port, af=af)
            self._baseline_by_af[af] = ok

            if ok:
                self._cb.on_log(
                    f"  {label}: STUN доступен без обхода ({elapsed_ms:.0f} ms) — "
                    f"результаты сканирования могут быть ложноположительными"
                )
            else:
                blocked_families.append(af)
                self._cb.on_log(f"  {label}: STUN заблокирован — {detail}")

        if blocked_families:
            self._probe_families = blocked_families
            families_label = "/".join(self._af_label(af) for af in blocked_families)
            self._cb.on_log(f"  Сканирование стратегий — {families_label}")
            return False

        if not available_families:
            self._probe_families = [socket.AF_INET]
            self._cb.on_log("  DNS не вернул IPv4/IPv6 адреса для STUN")
            return False

        self._probe_families = [available_families[0]]
        self._cb.on_log("  STUN по IPv4/IPv6 уже доступен без обхода")
        return True

    # ------------------------------------------------------------------
    # Strategy selection
    # ------------------------------------------------------------------

    def _select_strategies(self, mode: str, start_index: int = 0) -> tuple[list[dict], int, int]:
        """Select strategy batch for mode and resume cursor.

        All modes load from the canonical direct-preset catalog for the selected
        protocol. The scanner works with the same strategy definitions as the
        direct preset editor instead of the removed legacy z2 catalog layer.
        - quick:    30 strategies from cursor
        - standard: 80 strategies from cursor
        - full:     all remaining strategies from cursor

        Returns: (selected_batch, safe_start_index, total_available)
        """
        catalog_strategies = self._load_catalog_strategies()
        total_available = len(catalog_strategies)
        safe_start = min(max(0, int(start_index)), total_available)

        if not catalog_strategies:
            logger.warning("Catalog is empty — no strategies to scan")
            return [], 0, 0

        if mode == "quick":
            end_index = min(safe_start + 30, total_available)
            return catalog_strategies[safe_start:end_index], safe_start, total_available

        if mode == "standard":
            end_index = min(safe_start + 80, total_available)
            return catalog_strategies[safe_start:end_index], safe_start, total_available

        # mode == "full"
        return catalog_strategies[safe_start:], safe_start, total_available

    def _load_catalog_strategies(self) -> list[dict]:
        """Load catalog strategies for current scan protocol."""
        try:
            from config.config import MAIN_DIRECTORY, get_zapret_userdata_dir
            from core.paths import AppPaths
            from direct_preset.catalog_provider import load_strategy_catalogs

            if self._scan_protocol == _PROTOCOL_STUN_VOICE:
                catalog_name = "voice"
            elif self._scan_protocol == _PROTOCOL_UDP_GAMES:
                catalog_name = "udp"
            else:
                catalog_name = "tcp"

            user_root = Path((get_zapret_userdata_dir() or "").strip() or self._work_dir)
            local_root = Path((MAIN_DIRECTORY or "").strip() or self._work_dir)
            app_paths = AppPaths(user_root=user_root, local_root=local_root)
            catalogs = load_strategy_catalogs(app_paths, "winws2")
            entries = catalogs.get(catalog_name, {})

            result = []
            for strat_id, entry in entries.items():
                result.append({
                    "name": getattr(entry, "name", strat_id) or strat_id,
                    "id": strat_id,
                    "args": getattr(entry, "args", "") or "",
                })
            return result
        except Exception as e:
            logger.debug("Failed to load catalog strategies: %s", e)
            return []

    # ------------------------------------------------------------------
    # Probe lifecycle
    # ------------------------------------------------------------------

    _WINWS2_CRASH_RETRIES = 2  # retry up to 2 times on winws2 crash (WinDivert race)

    def _make_probe_result(
        self,
        *,
        strategy_name: str,
        strategy_id: str,
        strategy_args: str,
        target: str,
        success: bool,
        time_ms: float,
        error: str = "",
        http_code: int = 0,
        raw_data: dict | None = None,
    ) -> StrategyProbeResult:
        """Create StrategyProbeResult with protocol metadata."""
        probe_type = "stun" if self._scan_protocol in {_PROTOCOL_STUN_VOICE, _PROTOCOL_UDP_GAMES} else "https"
        return StrategyProbeResult(
            strategy_name=strategy_name,
            strategy_id=strategy_id,
            strategy_args=strategy_args,
            target=target,
            success=success,
            time_ms=time_ms,
            error=error,
            http_code=http_code,
            scan_protocol=self._scan_protocol,
            probe_type=probe_type,
            target_port=self._target_port,
            raw_data=raw_data or {},
        )

    def _make_cancelled_probe_result(
        self,
        *,
        strategy_name: str,
        strategy_id: str,
        strategy_args: str,
        target: str,
    ) -> StrategyProbeResult:
        return self._make_probe_result(
            strategy_name=strategy_name,
            strategy_id=strategy_id,
            strategy_args=strategy_args,
            target=target,
            success=False,
            time_ms=0,
            error="Cancelled",
        )

    def _probe_one_strategy(
        self, name: str, strat_id: str, args: str, target: str,
    ) -> StrategyProbeResult:
        """Test one strategy: write preset -> launch winws2 -> probe -> kill."""
        if self.cancelled:
            return self._make_cancelled_probe_result(
                strategy_name=name,
                strategy_id=strat_id,
                strategy_args=args,
                target=target,
            )
        last_error = ""
        for attempt in range(1 + self._WINWS2_CRASH_RETRIES):
            if self.cancelled:
                return self._make_cancelled_probe_result(
                    strategy_name=name,
                    strategy_id=strat_id,
                    strategy_args=args,
                    target=target,
                )
            try:
                result = self._probe_one_attempt(name, strat_id, args, target)
                # If winws2 crashed, retry (WinDivert may not have released yet)
                if not result.success and "winws2 crashed" in result.error:
                    last_error = result.error
                    if attempt < self._WINWS2_CRASH_RETRIES and not self.cancelled:
                        self._cb.on_log(f"  winws2 crashed, retrying ({attempt + 1})...")
                        time.sleep(1.0)
                        continue
                return result
            except Exception as e:
                last_error = str(e)
                if attempt < self._WINWS2_CRASH_RETRIES and not self.cancelled:
                    time.sleep(1.0)
                    continue
                break

        return self._make_probe_result(
            strategy_name=name,
            strategy_id=strat_id,
            strategy_args=args,
            target=target,
            success=False,
            time_ms=0,
            error=last_error,
        )

    def _probe_one_attempt(
        self, name: str, strat_id: str, args: str, target: str,
    ) -> StrategyProbeResult:
        """Single attempt: write preset -> launch winws2 -> protocol probe -> kill."""
        if self.cancelled:
            return self._make_cancelled_probe_result(
                strategy_name=name,
                strategy_id=strat_id,
                strategy_args=args,
                target=target,
            )
        try:
            # 1. Write temp files
            preset_path = self._write_temp_preset(args, self._target_host)
            if self.cancelled:
                return self._make_cancelled_probe_result(
                    strategy_name=name,
                    strategy_id=strat_id,
                    strategy_args=args,
                    target=target,
                )
            self._cb.on_log(f"  preset: {preset_path}")
            if self._scan_protocol == _PROTOCOL_UDP_GAMES:
                if self._games_ipset_sources:
                    shown = ", ".join(os.path.basename(p) for p in self._games_ipset_sources[:4])
                    if len(self._games_ipset_sources) > 4:
                        shown += f", ... (+{len(self._games_ipset_sources) - 4})"
                    if self._games_ipset_entries_count > 0:
                        self._cb.on_log(
                            f"  game ipsets: {shown} (entries: {self._games_ipset_entries_count})"
                        )
                    else:
                        self._cb.on_log(f"  game ipsets: {shown}")
                else:
                    self._cb.on_log("  game ipsets: fallback lists/ipset-all.txt")
            elif self._scan_protocol == _PROTOCOL_STUN_VOICE:
                self._cb.on_log("  filter profile: Discord/Telegram voice (STUN + discord_ip_discovery)")

            # 2. Launch winws2
            proc = self._launch_winws2(preset_path)
            with self._process_lock:
                self._process = proc

            # 3. Wait for startup
            time.sleep(STRATEGY_STARTUP_WAIT)
            if self.cancelled:
                return self._make_cancelled_probe_result(
                    strategy_name=name,
                    strategy_id=strat_id,
                    strategy_args=args,
                    target=target,
                )

            # 4. Check process alive
            if proc.poll() is not None:
                output = ""
                try:
                    raw_err = proc.stderr.read() if proc.stderr else b""
                    raw_out = proc.stdout.read() if proc.stdout else b""
                    raw = raw_err or raw_out
                    output = raw.decode("utf-8", errors="replace").strip() if raw else ""
                except Exception:
                    pass
                return self._make_probe_result(
                    strategy_name=name,
                    strategy_id=strat_id,
                    strategy_args=args,
                    target=target,
                    success=False,
                    time_ms=0,
                    error=f"winws2 crashed (exit={proc.returncode}): {output[:300]}",
                )

            # 5. Protocol probe test (one or more address families)
            family_results: list[tuple[int, bool, float, str]] = []
            udp_pool_by_family: dict[str, list[dict[str, Any]]] = {}
            for af in (self._probe_families or [socket.AF_INET]):
                if self.cancelled:
                    return self._make_cancelled_probe_result(
                        strategy_name=name,
                        strategy_id=strat_id,
                        strategy_args=args,
                        target=target,
                    )
                if self._scan_protocol in {_PROTOCOL_STUN_VOICE, _PROTOCOL_UDP_GAMES}:
                    af_success, af_time_ms, af_detail, af_probes = self._test_udp_probe_pool(af)
                    udp_pool_by_family[self._af_label(af)] = af_probes
                else:
                    af_success, af_time_ms, af_detail = self._test_https(self._target_host, af=af)
                family_results.append((af, af_success, af_time_ms, af_detail))
                if self.cancelled:
                    return self._make_cancelled_probe_result(
                        strategy_name=name,
                        strategy_id=strat_id,
                        strategy_args=args,
                        target=target,
                    )
                af_label = "IPv6" if af == socket.AF_INET6 else "IPv4"
                if af_success:
                    self._cb.on_log(f"  {af_label}: OK ({af_time_ms:.0f} ms)")
                else:
                    self._cb.on_log(f"  {af_label}: FAIL ({af_detail})")

            considered_results = [
                item for item in family_results if self._baseline_by_af.get(item[0]) is False
            ]
            if not considered_results:
                considered_results = family_results

            successful = [item for item in considered_results if item[1]]
            if successful:
                best = min(successful, key=lambda item: item[2])
                success = True
                time_ms = best[2]
                detail = ""
            else:
                success = False
                time_ms = max((item[2] for item in considered_results), default=0.0)
                detail_parts = []
                for af, _ok, _ms, af_detail in considered_results:
                    af_label = "IPv6" if af == socket.AF_INET6 else "IPv4"
                    detail_parts.append(f"{af_label}: {af_detail}")
                detail = "; ".join(detail_parts) if detail_parts else "No response"

            is_https_probe = self._scan_protocol == _PROTOCOL_TCP_HTTPS
            raw_data: dict[str, Any] = {
                "families": [self._af_label(af) for af, _ok, _ms, _detail in family_results],
            }
            if udp_pool_by_family:
                raw_data["udp_probe_pool"] = udp_pool_by_family

            return self._make_probe_result(
                strategy_name=name,
                strategy_id=strat_id,
                strategy_args=args,
                target=target,
                success=success,
                time_ms=time_ms,
                error="" if success else detail,
                http_code=200 if (success and is_https_probe) else 0,
                raw_data=raw_data,
            )

        except Exception as e:
            logger.debug("Probe error for %s: %s", name, e)
            return self._make_probe_result(
                strategy_name=name,
                strategy_id=strat_id,
                strategy_args=args,
                target=target,
                success=False,
                time_ms=0,
                error=str(e),
            )
        finally:
            self._kill_current_process()
            # Pause to let WinDivert driver release the filter handle.
            # Without enough time, next winws2 fails to acquire WinDivert.
            if not self.cancelled:
                time.sleep(0.5)

    # ------------------------------------------------------------------
    # Probe tests
    # ------------------------------------------------------------------

    def _build_udp_probe_pool(self) -> list[dict[str, Any]]:
        """Build UDP probe pool for current scan protocol."""
        if self._scan_protocol not in {_PROTOCOL_STUN_VOICE, _PROTOCOL_UDP_GAMES}:
            return []

        pool: list[dict[str, Any]] = []
        seen: set[tuple[str, str, int]] = set()

        def _add_probe(name: str, kind: str, host: str, port: int, required: bool = False) -> None:
            host = str(host or "").strip()
            try:
                port_num = int(port)
            except (TypeError, ValueError):
                return
            if not host or not (1 <= port_num <= 65535):
                return

            key = (kind, host.lower(), port_num)
            if key in seen:
                return
            seen.add(key)
            pool.append(
                {
                    "name": name,
                    "kind": kind,
                    "host": host,
                    "port": port_num,
                    "required": bool(required),
                }
            )

        # Primary target probe is always present; strict requirement for voice mode.
        _add_probe(
            "Primary target",
            "stun",
            self._target_host,
            self._target_port,
            required=self._scan_protocol == _PROTOCOL_STUN_VOICE,
        )

        # Add default STUN canaries.
        try:
            from blockcheck.targets import get_default_stun_targets

            for target in get_default_stun_targets():
                host, port = self._parse_stun_target(str(target.get("value", "")))
                if not host:
                    continue
                _add_probe(str(target.get("name", "STUN")), "stun", host, port)
        except Exception:
            pass

        # Add game-specific canaries for udp_games profile.
        if self._scan_protocol == _PROTOCOL_UDP_GAMES:
            for probe in _UDP_GAMES_CANARY_PROBES:
                _add_probe(
                    str(probe.get("name", "Game canary")),
                    str(probe.get("kind", "stun")),
                    str(probe.get("host", "")),
                    int(probe.get("port", 0)),
                    required=False,
                )

        return pool

    def _resolve_udp_probe_pool_ips(self) -> list[str]:
        """Resolve all UDP probe-pool hosts to concrete IPs."""
        resolved: list[str] = []
        seen: set[str] = set()

        for probe in self._build_udp_probe_pool():
            host = str(probe.get("host", "")).strip()
            port = int(probe.get("port", 0) or 0)
            if not host or not (1 <= port <= 65535):
                continue

            try:
                infos = socket.getaddrinfo(
                    host,
                    port,
                    socket.AF_UNSPEC,
                    socket.SOCK_DGRAM,
                    socket.IPPROTO_UDP,
                )
            except (socket.gaierror, OSError):
                continue

            for af, _socktype, _proto, _canonname, sockaddr in infos:
                if af not in (socket.AF_INET, socket.AF_INET6):
                    continue
                ip = str(sockaddr[0]).strip()
                if not ip or ip in seen:
                    continue
                seen.add(ip)
                resolved.append(ip)

        return resolved

    def _test_source_a2s_probe(
        self,
        host: str,
        port: int,
        timeout: float = STRATEGY_PROBE_TIMEOUT,
        af: int = socket.AF_INET,
    ) -> tuple[bool, float, str]:
        """Probe Source/GoldSrc-like server with A2S_INFO query."""
        start = time.monotonic()
        query = b"\xff\xff\xff\xffTSource Engine Query\x00"

        try:
            infos = socket.getaddrinfo(host, port, af, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        except OSError as e:
            return False, (time.monotonic() - start) * 1000, f"resolve error: {e}"

        if not infos:
            return False, (time.monotonic() - start) * 1000, "no address"

        seen_addrs: set[tuple[int, str, int]] = set()
        errors: list[str] = []
        for family, socktype, proto, _canonname, target_addr in infos:
            if family not in (socket.AF_INET, socket.AF_INET6):
                continue

            addr_ip = str(target_addr[0])
            key = (family, addr_ip, int(target_addr[1]))
            if key in seen_addrs:
                continue
            seen_addrs.add(key)

            sock = None
            try:
                sock = socket.socket(family, socktype, proto)
                sock.settimeout(timeout)
                sock.sendto(query, target_addr)
                response, _addr = sock.recvfrom(4096)
                elapsed_ms = (time.monotonic() - start) * 1000
                if len(response) >= 5 and response[:4] == b"\xff\xff\xff\xff" and response[4] in (0x49, 0x41, 0x44, 0x45):
                    return True, elapsed_ms, f"A2S reply type=0x{response[4]:02x}"
                errors.append(f"{addr_ip}: unexpected response")
            except socket.timeout:
                errors.append(f"{addr_ip}: timeout")
            except OSError as e:
                errors.append(f"{addr_ip}: {e}")
            finally:
                if sock is not None:
                    try:
                        sock.close()
                    except Exception:
                        pass

        elapsed_ms = (time.monotonic() - start) * 1000
        detail = "; ".join(errors[:3]) if errors else "no response"
        if len(errors) > 3:
            detail += f"; ... (+{len(errors) - 3} more)"
        return False, elapsed_ms, detail

    def _test_bedrock_probe(
        self,
        host: str,
        port: int,
        timeout: float = STRATEGY_PROBE_TIMEOUT,
        af: int = socket.AF_INET,
    ) -> tuple[bool, float, str]:
        """Probe Minecraft Bedrock server via RakNet unconnected ping."""
        start = time.monotonic()
        timestamp = int(time.time() * 1000) & 0xFFFFFFFFFFFFFFFF
        magic = bytes.fromhex("00ffff00fefefefefdfdfdfd12345678")
        request = b"\x01" + struct.pack(">Q", timestamp) + magic + secrets.token_bytes(8)

        try:
            infos = socket.getaddrinfo(host, port, af, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        except OSError as e:
            return False, (time.monotonic() - start) * 1000, f"resolve error: {e}"

        if not infos:
            return False, (time.monotonic() - start) * 1000, "no address"

        seen_addrs: set[tuple[int, str, int]] = set()
        errors: list[str] = []
        for family, socktype, proto, _canonname, target_addr in infos:
            if family not in (socket.AF_INET, socket.AF_INET6):
                continue

            addr_ip = str(target_addr[0])
            key = (family, addr_ip, int(target_addr[1]))
            if key in seen_addrs:
                continue
            seen_addrs.add(key)

            sock = None
            try:
                sock = socket.socket(family, socktype, proto)
                sock.settimeout(timeout)
                sock.sendto(request, target_addr)
                response, _addr = sock.recvfrom(4096)
                elapsed_ms = (time.monotonic() - start) * 1000
                if response and response[0] == 0x1C and magic in response:
                    return True, elapsed_ms, "Bedrock pong"
                errors.append(f"{addr_ip}: unexpected response")
            except socket.timeout:
                errors.append(f"{addr_ip}: timeout")
            except OSError as e:
                errors.append(f"{addr_ip}: {e}")
            finally:
                if sock is not None:
                    try:
                        sock.close()
                    except Exception:
                        pass

        elapsed_ms = (time.monotonic() - start) * 1000
        detail = "; ".join(errors[:3]) if errors else "no response"
        if len(errors) > 3:
            detail += f"; ... (+{len(errors) - 3} more)"
        return False, elapsed_ms, detail

    def _run_udp_probe_target(
        self,
        probe: dict[str, Any],
        af: int,
    ) -> tuple[bool, float, str]:
        """Run a single UDP probe target by kind."""
        kind = str(probe.get("kind", "stun"))
        host = str(probe.get("host", "")).strip()
        port = int(probe.get("port", 0) or 0)
        if not host or not (1 <= port <= 65535):
            return False, 0.0, "invalid probe target"

        timeout = min(float(STRATEGY_PROBE_TIMEOUT), 4.0)
        if kind == "source_a2s":
            return self._test_source_a2s_probe(host, port=port, timeout=timeout, af=af)
        if kind == "bedrock_ping":
            return self._test_bedrock_probe(host, port=port, timeout=timeout, af=af)
        return self._test_stun_probe(host, port=port, timeout=timeout, af=af)

    def _test_udp_probe_pool(
        self,
        af: int,
    ) -> tuple[bool, float, str, list[dict[str, Any]]]:
        """Run UDP probe pool in parallel and aggregate verdict."""
        if self.cancelled:
            return False, 0.0, "Cancelled", []
        pool = self._build_udp_probe_pool()
        if not pool:
            ok, time_ms, detail = self._test_stun_probe(self._target_host, self._target_port, af=af)
            return ok, time_ms, detail, []

        max_workers = min(_UDP_POOL_MAX_WORKERS, max(1, len(pool)))

        raw_results: list[tuple[bool, float, str] | None] = [None] * len(pool)
        cancelled_during_pool = False
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=max_workers)
        try:
            futures = {
                executor.submit(self._run_udp_probe_target, spec, af): idx
                for idx, spec in enumerate(pool)
            }
            for future in concurrent.futures.as_completed(futures):
                if self.cancelled:
                    cancelled_during_pool = True
                    break
                idx = futures[future]
                raw_results[idx] = future.result()
        finally:
            executor.shutdown(wait=not cancelled_during_pool, cancel_futures=cancelled_during_pool)

        if self.cancelled:
            return False, 0.0, "Cancelled", []

        probes: list[dict[str, Any]] = []
        for spec, result in zip(pool, raw_results):
            if result is None:
                continue
            ok, elapsed_ms, detail = result
            probes.append(
                {
                    "name": str(spec.get("name", "probe")),
                    "kind": str(spec.get("kind", "stun")),
                    "host": str(spec.get("host", "")),
                    "port": int(spec.get("port", 0) or 0),
                    "required": bool(spec.get("required", False)),
                    "success": bool(ok),
                    "time_ms": float(elapsed_ms),
                    "detail": str(detail or ""),
                }
            )

        successes = [item for item in probes if item["success"]]
        required = [item for item in probes if item["required"]]

        if self._scan_protocol == _PROTOCOL_STUN_VOICE:
            success = bool(required) and all(item["success"] for item in required)
        else:
            success = bool(successes)

        if success:
            time_ms = min(float(item["time_ms"]) for item in successes)
            detail = f"pool OK {len(successes)}/{len(probes)}"
        else:
            time_ms = max((float(item["time_ms"]) for item in probes), default=0.0)
            failed = [item for item in probes if not item["success"]]
            fail_parts = [
                f"{item['name']}: {item['detail']}" for item in failed[:3]
            ]
            detail = "; ".join(fail_parts) if fail_parts else "No response"
            if len(failed) > 3:
                detail += f"; ... (+{len(failed) - 3} more)"

        return success, time_ms, detail, probes

    def _test_stun_probe(
        self,
        host: str,
        port: int,
        timeout: float = STRATEGY_PROBE_TIMEOUT,
        af: int = socket.AF_INET,
    ) -> tuple[bool, float, str]:
        """Run STUN probe and normalize to (success, time_ms, detail)."""
        family = socket.AF_INET6 if af == socket.AF_INET6 else socket.AF_INET
        result = test_stun(
            host,
            port=port,
            timeout=max(int(timeout), 1),
            retries=2,
            family=family,
        )

        elapsed_ms = float(result.time_ms or 0.0)
        if result.status == TestStatus.OK:
            return True, elapsed_ms, result.detail or "OK"

        detail = result.detail or result.error_code or result.status.value
        return False, elapsed_ms, detail

    def _test_https(
        self,
        host: str,
        timeout: float = STRATEGY_PROBE_TIMEOUT,
        af: int = socket.AF_INET,
    ) -> tuple[bool, float, str]:
        """Pure Python HTTPS test with browser-like request and address retries.

        Args:
            host: Target hostname.
            timeout: Connection timeout in seconds.
            af: Address family — AF_INET (IPv4) or AF_INET6 (IPv6).

        Returns: (success, time_ms, detail)
        Checks response body against ISP_BODY_MARKERS to detect block pages.
        """
        af_label = "IPv6" if af == socket.AF_INET6 else "IPv4"
        overall_t0 = time.monotonic()

        try:
            addr_info = socket.getaddrinfo(host, 443, af, socket.SOCK_STREAM)
        except OSError as e:
            elapsed_ms = (time.monotonic() - overall_t0) * 1000
            return False, elapsed_ms, f"resolve error: {e}"

        if not addr_info:
            elapsed_ms = (time.monotonic() - overall_t0) * 1000
            return False, elapsed_ms, f"No {af_label} address found for {host}"

        # Keep unique IPs only; retry each one (helps with CDN anycast edges).
        resolved_addrs: list[tuple[int, int, int, tuple]] = []
        seen_addrs: set[tuple[str, int]] = set()
        for family, socktype, proto, _canonname, target_addr in addr_info:
            ip = str(target_addr[0])
            key = (ip, family)
            if key in seen_addrs:
                continue
            seen_addrs.add(key)
            resolved_addrs.append((family, socktype, proto, target_addr))

        browser_headers = (
            f"GET / HTTP/1.1\r\n"
            f"Host: {host}\r\n"
            f"Connection: close\r\n"
            f"User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            f"AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36\r\n"
            f"Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8\r\n"
            f"Accept-Language: en-US,en;q=0.9\r\n"
            f"Accept-Encoding: identity\r\n"
            f"Cache-Control: no-cache\r\n"
            f"Pragma: no-cache\r\n"
            f"\r\n"
        ).encode("ascii", errors="ignore")

        attempt_errors: list[str] = []

        for attempt_idx, (family, socktype, proto, target_addr) in enumerate(resolved_addrs, start=1):
            sock = None
            ssl_sock = None
            stage = "connect"
            addr_label = str(target_addr[0])

            try:
                self._cb.on_log(
                    f"  {af_label}: try {attempt_idx}/{len(resolved_addrs)} {addr_label} "
                    f"(connect->tls->read)"
                )

                sock = socket.socket(family, socktype, proto)
                sock.settimeout(timeout)

                stage = "connect"
                sock.connect(target_addr)

                ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
                ctx.check_hostname = True
                ctx.verify_mode = ssl.CERT_REQUIRED
                ctx.load_default_certs()
                try:
                    ctx.set_alpn_protocols(["http/1.1"])
                except (NotImplementedError, ssl.SSLError):
                    pass

                stage = "tls"
                ssl_sock = ctx.wrap_socket(sock, server_hostname=host, do_handshake_on_connect=False)
                ssl_sock.settimeout(timeout)
                ssl_sock.do_handshake()

                stage = "write"
                ssl_sock.sendall(browser_headers)

                # Read response — up to 32 KB to detect 16 KB TCP block
                stage = "read"
                response = b""
                recv_timed_out = False
                try:
                    ssl_sock.settimeout(STRATEGY_RESPONSE_TIMEOUT)
                    while True:
                        chunk = ssl_sock.recv(4096)
                        if not chunk:
                            break
                        response += chunk
                        if len(response) > 32768:
                            break
                except socket.timeout:
                    recv_timed_out = True

                elapsed_ms = (time.monotonic() - overall_t0) * 1000

                if not response:
                    if recv_timed_out:
                        attempt_errors.append(f"{addr_label}: read timeout (no response)")
                    else:
                        attempt_errors.append(f"{addr_label}: read empty response")
                    continue

                # Check for ISP block page markers in response body
                if b"HTTP/" in response:
                    body_text = response.decode("utf-8", errors="replace").lower()
                    for marker in ISP_BODY_MARKERS:
                        if marker.lower() in body_text:
                            attempt_errors.append(f"{addr_label}: ISP block page detected ({marker})")
                            break
                    else:
                        # Detect 16 KB TCP block: recv timed out and total size
                        # falls in the DPI block range (15-21 KB)
                        if recv_timed_out and TCP_BLOCK_RANGE_MIN <= len(response) <= TCP_BLOCK_RANGE_MAX:
                            attempt_errors.append(
                                f"{addr_label}: read timeout after {len(response)} bytes (16KB TCP block)"
                            )
                            continue

                        return True, elapsed_ms, "OK"

                    # Marker matched and appended to attempt_errors
                    continue

                return True, elapsed_ms, f"Got {len(response)} bytes (no HTTP header)"

            except ssl.SSLCertVerificationError as e:
                attempt_errors.append(f"{addr_label}: tls cert error ({e})")
            except ssl.SSLError as e:
                attempt_errors.append(f"{addr_label}: tls error ({e})")
            except socket.timeout:
                attempt_errors.append(f"{addr_label}: {stage} timeout")
            except ConnectionResetError:
                attempt_errors.append(f"{addr_label}: connect reset (DPI RST)")
            except OSError as e:
                attempt_errors.append(f"{addr_label}: {stage} os error ({e})")
            finally:
                for s in (ssl_sock, sock):
                    if s is not None:
                        try:
                            s.close()
                        except Exception:
                            pass

        elapsed_ms = (time.monotonic() - overall_t0) * 1000
        if not attempt_errors:
            return False, elapsed_ms, "no usable addresses"

        if len(attempt_errors) > 3:
            shown = "; ".join(attempt_errors[:3])
            return False, elapsed_ms, f"{shown}; ... (+{len(attempt_errors) - 3} more)"
        return False, elapsed_ms, "; ".join(attempt_errors)

    # ------------------------------------------------------------------
    # Temp preset generation
    # ------------------------------------------------------------------

    def _game_lists_directories(self) -> list[str]:
        """Collect candidate directories where ipset game lists can live."""
        dirs: list[str] = []

        appdata = (os.environ.get("APPDATA") or "").strip()
        if appdata:
            dirs.extend(
                [
                    os.path.join(appdata, "ZapretTwoDev", "lists"),
                    os.path.join(appdata, "ZapretTwo", "lists"),
                ]
            )

        try:
            from config.config import APPDATA_DIR, get_zapret_userdata_dir

            app_channel_dir = (APPDATA_DIR or "").strip()
            if app_channel_dir:
                dirs.append(os.path.join(app_channel_dir, "lists"))

            user_data_dir = (get_zapret_userdata_dir() or "").strip()
            if user_data_dir:
                dirs.append(os.path.join(user_data_dir, "lists"))
        except Exception:
            pass

        dirs.append(os.path.join(self._work_dir, "lists"))

        result: list[str] = []
        seen: set[str] = set()
        for raw in dirs:
            path = os.path.normpath(raw)
            if path in seen:
                continue
            seen.add(path)
            result.append(path)
        return result

    def _resolve_games_ipset_sources(self) -> list[str]:
        """Resolve available UDP game/ipset files for selected coverage scope."""
        found: list[str] = []
        seen: set[str] = set()

        for base_dir in self._game_lists_directories():
            # Prefer explicit game ipset names first.
            for filename in _GAMES_IPSET_FILENAMES:
                candidate = os.path.normpath(os.path.join(base_dir, filename))
                if candidate in seen:
                    continue
                seen.add(candidate)
                if os.path.exists(candidate):
                    found.append(candidate)

            if self._udp_games_scope == _UDP_GAMES_SCOPE_GAMES_ONLY:
                continue

            # Then include any ipset-*.txt file as broad default coverage.
            try:
                for filename in sorted(os.listdir(base_dir)):
                    name = filename.lower()
                    if not (name.startswith("ipset-") and name.endswith(".txt")):
                        continue
                    candidate = os.path.normpath(os.path.join(base_dir, filename))
                    if candidate in seen:
                        continue
                    seen.add(candidate)
                    if os.path.exists(candidate):
                        found.append(candidate)
            except OSError:
                continue

        return found

    def _build_games_ipset_temp_file(self) -> str:
        """Build merged temporary game ipset file and return path to use."""
        if self._games_ipset_compiled_path and os.path.exists(self._games_ipset_compiled_path):
            return self._games_ipset_compiled_path

        sources = self._resolve_games_ipset_sources()
        self._games_ipset_sources = list(sources)

        if not sources:
            if self._udp_games_scope == _UDP_GAMES_SCOPE_GAMES_ONLY:
                fallback = "lists/ipset-roblox.txt"
            else:
                fallback = "lists/ipset-all.txt"
            self._games_ipset_compiled_path = fallback
            self._games_ipset_entries_count = 0
            return fallback

        merged_lines: list[str] = []
        seen_entries: set[str] = set()
        for source in sources:
            try:
                with open(source, "r", encoding="utf-8") as f:
                    for raw_line in f:
                        line = raw_line.strip()
                        if not line or line.startswith("#"):
                            continue
                        if line in seen_entries:
                            continue
                        seen_entries.add(line)
                        merged_lines.append(line)
            except OSError:
                continue

        # Ensure all UDP probe-pool targets are covered by ipset filter.
        for ip in self._resolve_udp_probe_pool_ips():
            if ip in seen_entries:
                continue
            seen_entries.add(ip)
            merged_lines.append(ip)

        if not merged_lines:
            self._games_ipset_compiled_path = sources[0]
            self._games_ipset_entries_count = 0
            return sources[0]

        path = os.path.join(self._work_dir, _PROBE_TEMP_GAMES_IPSET)
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write("\n".join(merged_lines) + "\n")
            self._games_ipset_compiled_path = path
            self._games_ipset_entries_count = len(merged_lines)
            return path
        except OSError:
            self._games_ipset_compiled_path = sources[0]
            self._games_ipset_entries_count = 0
            return sources[0]

    def _write_temp_preset(self, strategy_args: str, target_domain: str) -> str:
        """Generate a minimal preset file for probing one strategy."""
        preset_path = os.path.join(self._work_dir, PROBE_TEMP_PRESET)
        hostlist_path = os.path.join(self._work_dir, PROBE_TEMP_HOSTLIST)

        # Write single-domain hostlist
        with open(hostlist_path, "w", encoding="utf-8") as f:
            f.write(target_domain + "\n")

        lines: list[str] = []

        # Lua inits
        lines.extend(_LUA_INITS)
        lines.append("")

        # Blob definitions — only what the strategy uses
        blob_defs = self._generate_blob_lines(strategy_args)
        if blob_defs:
            lines.extend(blob_defs)
            lines.append("")

        if self._scan_protocol == _PROTOCOL_STUN_VOICE:
            lines.append("--wf-udp-out=443-65535")
            lines.append("")

            lines.append("--filter-l7=stun,discord")
            lines.append("--payload=stun,discord_ip_discovery")
            lines.append("")
        elif self._scan_protocol == _PROTOCOL_UDP_GAMES:
            games_ipset_path = self._build_games_ipset_temp_file()

            lines.append(f"--wf-udp-out={_UDP_GAMES_PORT_FILTER}")
            lines.append("")

            lines.append(f"--filter-udp={_UDP_GAMES_PORT_FILTER}")
            lines.append(f"--ipset={games_ipset_path}")
            lines.append("")
        else:
            # WinDivert filter
            lines.append("--wf-tcp-out=443")
            lines.append("")

            # Filter + hostlist + range
            lines.append("--filter-tcp=443")
            lines.append(f"--hostlist={hostlist_path}")
            lines.append("--out-range=-d8")
            lines.append("")

        # Strategy arguments (may contain multiple --lua-desync= lines joined by \n)
        for arg_line in strategy_args.split("\n"):
            arg_line = arg_line.strip()
            if arg_line:
                lines.append(arg_line)

        with open(preset_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")

        return preset_path

    def _generate_blob_lines(self, strategy_args: str) -> list[str]:
        """Generate --blob= lines for blobs used in the strategy."""
        try:
            from blobs.service import find_used_blobs, get_blobs
            used = find_used_blobs(strategy_args)
            if not used:
                return []
            blobs = get_blobs()
            result = []
            for name in sorted(used):
                if name in blobs:
                    result.append(f"--blob={name}:{blobs[name]}")
            return result
        except Exception as e:
            logger.debug("Failed to generate blob definitions: %s", e)
            return []

    # ------------------------------------------------------------------
    # Process management
    # ------------------------------------------------------------------

    def _launch_winws2(self, preset_path: str) -> subprocess.Popen:
        """Launch winws2.exe with the given preset file."""
        cmd = [self._winws2_exe, f"@{preset_path}"]

        startupinfo = subprocess.STARTUPINFO()
        try:
            from winws_runtime.runners.constants import STARTF_USESHOWWINDOW, SW_HIDE
            startupinfo.dwFlags = STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = SW_HIDE
        except ImportError:
            startupinfo.dwFlags = 0x00000001
            startupinfo.wShowWindow = 0

        try:
            from winws_runtime.runners.constants import CREATE_NO_WINDOW
            creation_flags = CREATE_NO_WINDOW
        except ImportError:
            creation_flags = 0x08000000

        return subprocess.Popen(
            cmd,
            cwd=self._work_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            startupinfo=startupinfo,
            creationflags=creation_flags,
        )

    def _kill_current_process(self) -> None:
        """Terminate the current winws2 process if running (thread-safe)."""
        with self._process_lock:
            proc = self._process
            self._process = None

        if proc is None:
            return

        killed_cleanly = False
        try:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=STRATEGY_KILL_TIMEOUT)
                    killed_cleanly = True
                except subprocess.TimeoutExpired:
                    proc.kill()
                    try:
                        proc.wait(timeout=2)
                        killed_cleanly = True
                    except subprocess.TimeoutExpired:
                        logger.warning("winws2 process %s did not die after kill(), using force kill", proc.pid)
            else:
                killed_cleanly = True
        except OSError as e:
            logger.warning("Error killing winws2 process: %s", e)

        # Fallback: force-kill all winws processes if graceful kill failed
        if not killed_cleanly:
            try:
                from winws_runtime.runtime.sync_shutdown import shutdown_runtime_sync

                shutdown_runtime_sync(reason="blockcheck_kill_fallback", include_cleanup=True)
            except Exception as e:
                logger.debug("canonical runtime shutdown fallback failed: %s", e)

    def _pre_scan_cleanup(self) -> None:
        """Kill any running winws and clean WinDivert before scanning."""
        self._cb.on_log("Pre-scan cleanup...")
        errors = []

        try:
            from winws_runtime.runtime.sync_shutdown import shutdown_runtime_sync

            result = shutdown_runtime_sync(reason="blockcheck_pre_scan", include_cleanup=True)
            if result.still_running:
                errors.append("runtime still running after canonical shutdown")
        except Exception as e:
            errors.append(f"canonical_runtime_shutdown: {e}")
            logger.debug("canonical runtime shutdown failed: %s", e)

        # Clean stale temp files from a previous crashed scan
        self._cleanup_temp_files()

        if errors:
            self._cb.on_log(f"Cleanup finished with warnings: {'; '.join(errors)}")
        else:
            self._cb.on_log("Cleanup done")

    def _run_preflight_check(self) -> bool:
        """Быстрая preflight-проверка целевого хоста перед сканированием стратегий."""
        if self._scan_protocol != _PROTOCOL_TCP_HTTPS:
            return True  # Preflight только для HTTPS-целей

        try:
            from blockcheck.preflight import check_one_domain, format_domain_log
            from blockcheck.models import PreflightVerdict
        except ImportError:
            self._cb.on_log("Preflight: модуль недоступен, пропускаем")
            return True

        self._cb.on_phase("Preflight проверка")
        self._cb.on_log(f"\n--- Preflight: {self._target_host} ---")

        result = check_one_domain(self._target_host, cancelled=lambda: self.cancelled)

        # Подробный лог каждой проверки
        self._cb.on_log(format_domain_log(result))

        if result.is_block_ip:
            self._cb.on_log(
                f"\n  DNS возвращает IP-заглушку провайдера ({result.block_ip_detail}).\n"
                "  Стратегии будут тестироваться на заглушке, а не на реальном сервере.\n"
                "  Рекомендация: используйте DoH/DoT или измените системный DNS."
            )

        return result.verdict != PreflightVerdict.FAILED

    def _cleanup_temp_files(self) -> None:
        """Remove temp preset and hostlist files."""
        for fname in (PROBE_TEMP_PRESET, PROBE_TEMP_HOSTLIST, _PROBE_TEMP_GAMES_IPSET):
            path = os.path.join(self._work_dir, fname)
            try:
                if os.path.exists(path):
                    os.remove(path)
            except OSError:
                pass

        self._games_ipset_compiled_path = None
        self._games_ipset_entries_count = 0
        self._games_ipset_sources = []

    # ------------------------------------------------------------------
    # Path resolution
    # ------------------------------------------------------------------

    def _find_work_dir(self) -> str:
        """Find the working directory (where exe/ folder is)."""
        try:
            from config.config import MAIN_DIRECTORY
            return MAIN_DIRECTORY
        except ImportError:
            return os.getcwd()

    def _find_winws2(self) -> str:
        """Find the winws2.exe path."""
        try:
            from config.config import WINWS2_EXE
            if os.path.exists(WINWS2_EXE):
                return WINWS2_EXE
        except ImportError:
            pass

        # Fallback: relative to working directory
        fallback = os.path.join(self._work_dir, "exe", "winws2.exe")
        if os.path.exists(fallback):
            return fallback

        raise FileNotFoundError(
            "winws2.exe not found. Ensure zapret2 is installed."
        )
