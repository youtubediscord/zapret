from __future__ import annotations

import asyncio
import inspect
from dataclasses import dataclass
from urllib.parse import urlencode


@dataclass(frozen=True, slots=True)
class CloudflareFallbackConfig:
    enabled: bool = False
    domains: tuple[str, ...] = ()
    worker_enabled: bool = False
    worker_domains: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class CloudflareDnsRecord:
    dc: int
    host: str
    ip: str


@dataclass(frozen=True, slots=True)
class CloudflareCheckEntry:
    kind: str
    host: str
    path: str
    ok: bool
    error: str = ""


@dataclass(frozen=True, slots=True)
class CloudflareCheckResult:
    kind: str
    entries: tuple[CloudflareCheckEntry, ...]

    @property
    def ok(self) -> bool:
        return any(entry.ok for entry in self.entries)

    @property
    def checked(self) -> int:
        return len(self.entries)

    @property
    def working(self) -> int:
        return sum(1 for entry in self.entries if entry.ok)

    @property
    def failed(self) -> int:
        return self.checked - self.working

    def summary(self) -> str:
        if self.checked <= 0:
            return "Нет доменов для проверки."
        if self.ok:
            return f"Работает: {self.working} из {self.checked}."
        return f"Не отвечает: 0 из {self.checked}."


CLOUDFLARE_DNS_RECORDS: tuple[CloudflareDnsRecord, ...] = (
    CloudflareDnsRecord(1, "kws1", "149.154.175.50"),
    CloudflareDnsRecord(2, "kws2", "149.154.167.51"),
    CloudflareDnsRecord(3, "kws3", "149.154.175.100"),
    CloudflareDnsRecord(4, "kws4", "149.154.167.91"),
    CloudflareDnsRecord(5, "kws5", "149.154.171.5"),
    CloudflareDnsRecord(203, "kws203", "91.105.192.100"),
)

AUTO_CLOUDFLARE_DOMAINS: tuple[str, ...] = (
    "sorokdva.co.uk",
    "sorokodin.co.uk",
    "lovetrue.co.uk",
    "pyatdesyatdva.co.uk",
    "noskomnadzor.co.uk",
    "pomogite.co.uk",
    "cakeisalie.co.uk",
    "havegreatday.co.uk",
    "pclead.co.uk",
    "offshor.co.uk",
    "kartoshka.co.uk",
    "notelega.co.uk",
    "nebally.co.uk",
    "pyatdesyatodin.co.uk",
    "ebally.co.uk",
)

_DNS_RECORD_BY_DC = {record.dc: record for record in CLOUDFLARE_DNS_RECORDS}

_CFWORKER_CODE = """\
import { connect } from "cloudflare:sockets";

function toBytes(data) {
  if (data instanceof ArrayBuffer) {
    return new Uint8Array(data);
  }
  if (typeof data === "string") {
    return new TextEncoder().encode(data);
  }
  if (data && typeof data.arrayBuffer === "function") {
    return data.arrayBuffer().then((ab) => new Uint8Array(ab));
  }
  return new Uint8Array();
}

export default {
  async fetch(request) {
    if ((request.headers.get("Upgrade") || "").toLowerCase() !== "websocket") {
      return new Response("Expected websocket", { status: 426 });
    }

    const url = new URL(request.url);
    if (url.pathname !== "/apiws") {
      return new Response("Not found", { status: 404 });
    }

    const dst = url.searchParams.get("dst");
    if (!dst) {
      return new Response("dst is required", { status: 400 });
    }

    const pair = new WebSocketPair();
    const client = pair[0];
    const server = pair[1];
    server.accept();

    const socket = connect({ hostname: dst, port: 443 });
    const tcpWriter = socket.writable.getWriter();
    const tcpReader = socket.readable.getReader();

    server.addEventListener("message", async (event) => {
      try {
        await tcpWriter.write(await toBytes(event.data));
      } catch {
        try { server.close(1011, "tcp write failed"); } catch {}
      }
    });

    server.addEventListener("close", async () => {
      try { await tcpWriter.close(); } catch {}
      try { socket.close(); } catch {}
    });

    (async () => {
      try {
        for (;;) {
          const { value, done } = await tcpReader.read();
          if (done) {
            break;
          }
          if (value) {
            server.send(value);
          }
        }
      } catch {
      } finally {
        try { server.close(); } catch {}
        try { tcpReader.releaseLock(); } catch {}
        try { socket.close(); } catch {}
      }
    })();

    return new Response(null, { status: 101, webSocket: client });
  },
};
"""


def _is_valid_domain(value: str) -> bool:
    if not value or len(value) > 253:
        return False
    if value.startswith(".") or value.endswith("."):
        return False
    labels = value.split(".")
    if len(labels) < 2:
        return False
    for label in labels:
        if not label or len(label) > 63:
            return False
        if label[0] == "-" or label[-1] == "-":
            return False
        if not all(ch.isalnum() or ch == "-" for ch in label):
            return False
    return len(labels[-1]) >= 2 and any(ch.isalpha() for ch in labels[-1])


def normalize_domain_list(value: object) -> tuple[str, ...]:
    if isinstance(value, str):
        raw_items = value.replace(",", " ").replace(";", " ").split()
    elif isinstance(value, (list, tuple, set)):
        raw_items: list[str] = []
        for entry in value:
            if isinstance(entry, str):
                raw_items.extend(entry.replace(",", " ").replace(";", " ").split())
    else:
        raw_items = []

    result: list[str] = []
    seen: set[str] = set()
    for item in raw_items:
        domain = item.strip().lower()
        if domain in seen or not _is_valid_domain(domain):
            continue
        seen.add(domain)
        result.append(domain)
    return tuple(result)


def should_try_cloudflare(config: CloudflareFallbackConfig | None) -> bool:
    if config is None:
        return False
    if config.enabled and (config.domains or AUTO_CLOUDFLARE_DOMAINS):
        return True
    return bool(config.worker_enabled and config.worker_domains)


class CloudflareDomainBalancer:
    """Keeps the last working Cloudflare base domain first for each Telegram DC."""

    __slots__ = ("_active_by_dc", "_domains")

    def __init__(self) -> None:
        self._active_by_dc: dict[int, str] = {}
        self._domains: tuple[str, ...] = ()

    def reset(self) -> None:
        self._active_by_dc.clear()
        self._domains = ()

    def ordered_domains(self, dc: int, domains: tuple[str, ...]) -> list[str]:
        self._sync_domains(domains)
        active = self._active_by_dc.get(int(dc))
        if active not in self._domains:
            active = None
        if active is None:
            return list(self._domains)
        return [active, *(domain for domain in self._domains if domain != active)]

    def record_success(self, dc: int, domain: str) -> bool:
        normalized = str(domain or "").strip().lower()
        prefix = f"kws{int(dc)}."
        base_domain = normalized[len(prefix):] if normalized.startswith(prefix) else normalized
        if base_domain not in self._domains:
            return False
        previous = self._active_by_dc.get(int(dc))
        self._active_by_dc[int(dc)] = base_domain
        return previous != base_domain

    def _sync_domains(self, domains: tuple[str, ...]) -> None:
        if self._domains == domains:
            return
        self._domains = domains
        valid = set(domains)
        self._active_by_dc = {
            dc: domain
            for dc, domain in self._active_by_dc.items()
            if domain in valid
        }


def build_cloudflare_domains(
    dc: int,
    config: CloudflareFallbackConfig,
    *,
    balancer: CloudflareDomainBalancer | None = None,
) -> list[str]:
    result: list[str] = []
    domains = config.domains or AUTO_CLOUDFLARE_DOMAINS
    ordered_domains = balancer.ordered_domains(dc, domains) if balancer is not None else list(domains)
    for base_domain in ordered_domains:
        result.append(f"kws{int(dc)}.{base_domain}")
    return result


def build_worker_path(dst: str, dc: int) -> str:
    return "/apiws?" + urlencode({"dst": str(dst or ""), "dc": str(int(dc or 0))})


def build_cfproxy_dns_records_text() -> str:
    lines = [
        "DNS-записи Cloudflare для своего домена:",
        "",
        "Тип: A",
        "Статус прокси: включён (Proxied)",
        "",
    ]
    for record in CLOUDFLARE_DNS_RECORDS:
        lines.append(f"{record.host} A {record.ip}")
    return "\n".join(lines)


def build_cfworker_code() -> str:
    return _CFWORKER_CODE


async def _close_ws(ws) -> None:
    close = getattr(ws, "close", None)
    if close is None:
        return
    result = close()
    if inspect.isawaitable(result):
        await result


async def _check_entry(
    *,
    kind: str,
    host: str,
    path: str,
    timeout: float,
    connect,
) -> CloudflareCheckEntry:
    try:
        ws = await connect(host, host, path=path, timeout=float(timeout))
        await _close_ws(ws)
        return CloudflareCheckEntry(kind=kind, host=host, path=path, ok=True)
    except Exception as exc:
        return CloudflareCheckEntry(kind=kind, host=host, path=path, ok=False, error=str(exc))


def _probe_targets(kind: str, domains: object, dcs: tuple[int, ...]) -> tuple[tuple[str, str], ...]:
    normalized_kind = str(kind or "").strip().lower()
    normalized_domains = normalize_domain_list(domains)
    if normalized_kind == "domain" and not normalized_domains:
        normalized_domains = AUTO_CLOUDFLARE_DOMAINS
    if not normalized_domains:
        return ()

    targets: list[tuple[str, str]] = []
    for domain in normalized_domains:
        if normalized_kind == "worker":
            for dc in dcs:
                record = _DNS_RECORD_BY_DC.get(int(dc))
                if record is None:
                    continue
                targets.append((domain, build_worker_path(record.ip, record.dc)))
            continue

        for dc in dcs:
            record = _DNS_RECORD_BY_DC.get(int(dc))
            if record is None:
                continue
            targets.append((f"{record.host}.{domain}", "/apiws"))
    return tuple(targets)


async def check_cloudflare_connectivity(
    kind: str,
    domains: object,
    *,
    dcs: tuple[int, ...] = (1, 2, 3, 4, 5, 203),
    timeout: float = 6.0,
    connect=None,
) -> CloudflareCheckResult:
    from telegram_proxy.proxy.transport import RawWebSocket

    normalized_kind = str(kind or "").strip().lower()
    if normalized_kind not in {"domain", "worker"}:
        normalized_kind = "domain"
    connect_fn = connect or RawWebSocket.connect
    tasks = [
        _check_entry(kind=normalized_kind, host=host, path=path, timeout=timeout, connect=connect_fn)
        for host, path in _probe_targets(normalized_kind, domains, tuple(int(dc) for dc in dcs))
    ]
    if not tasks:
        return CloudflareCheckResult(kind=normalized_kind, entries=())
    return CloudflareCheckResult(kind=normalized_kind, entries=tuple(await asyncio.gather(*tasks)))


def run_cloudflare_connectivity_check(
    kind: str,
    domains: object,
    *,
    timeout: float = 6.0,
) -> CloudflareCheckResult:
    return asyncio.run(check_cloudflare_connectivity(kind, domains, timeout=timeout))


__all__ = [
    "AUTO_CLOUDFLARE_DOMAINS",
    "CLOUDFLARE_DNS_RECORDS",
    "CloudflareCheckEntry",
    "CloudflareCheckResult",
    "CloudflareDnsRecord",
    "CloudflareDomainBalancer",
    "CloudflareFallbackConfig",
    "build_cfproxy_dns_records_text",
    "build_cfworker_code",
    "build_cloudflare_domains",
    "build_worker_path",
    "check_cloudflare_connectivity",
    "normalize_domain_list",
    "run_cloudflare_connectivity_check",
    "should_try_cloudflare",
]
