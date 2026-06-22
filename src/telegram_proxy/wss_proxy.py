# telegram_proxy/wss_proxy.py
"""Core Telegram WebSocket proxy server.

Tunnels TCP connections to Telegram through WSS endpoints
(kws{N}.web.telegram.org) to bypass IP-based blocking by ISPs.

Architecture (matching the proven Flowseal/tg-ws-proxy approach):
1. Accept SOCKS5 connection from Telegram Desktop
2. Complete SOCKS5 handshake, note target IP
3. Read the 64-byte MTProto obfuscation init packet
4. Decrypt the init packet to extract (dc_id, is_media)
5. Connect to WSS relay IP via raw TCP+TLS with SNI hostname
6. Perform WebSocket upgrade handshake manually
7. Forward the init packet as the first WS binary frame
8. Bridge TCP <-> WS bidirectionally, splitting MTProto messages

Only DC2 and DC4 have working WebSocket relays.
The relay reads the DC id from the init packet and routes internally.
"""

import asyncio
import logging
import time
from typing import Optional, Callable

from telegram_proxy.proxy.dc_map import (
    ip_to_dc,
    is_telegram_ip,
    ws_domains_for_dc,
    IP_TO_DC,
    WSS_DOMAINS,
    WSS_RELAY_IP,
    WSS_PATH,
    dc_to_tcp_endpoint,
)
from telegram_proxy.proxy import socks5
from telegram_proxy.proxy.cloudflare import (
    CloudflareDomainBalancer,
    CloudflareFallbackConfig,
    build_cloudflare_domains,
    build_worker_path,
    should_try_cloudflare,
)
from telegram_proxy.proxy.mtproto import (
    MsgSplitter as _MsgSplitter,
    dc_from_init as _dc_from_init,
    is_http_transport as _is_http_transport,
    patch_init_dc as _patch_init_dc,
)
from telegram_proxy.proxy.mtproxy import (
    MTProxyMsgSplitter,
    build_crypto_context,
    generate_relay_init,
    normalize_secret,
    parse_client_init,
    relay_mtproxy_tcp,
    relay_mtproxy_wss,
)
from telegram_proxy.proxy.fake_tls import normalize_fake_tls_domain, read_mtproxy_client_init
from telegram_proxy.proxy.pool import (
    CloudflareWorkerPool,
    WsPool as _WsPool,
    get_wss_semaphore as _get_wss_semaphore,
    relay_ip_for_domain as _relay_ip_for_domain,
    reset_wss_semaphore,
)
from telegram_proxy.proxy.relay import RELAY_BUFFER, relay_tcp, relay_wss
from telegram_proxy.proxy.routing import (
    UpstreamProxyConfig,
    UpstreamProxyEndpoint,
    check_relay_reachable,
    should_route_upstream,
)
from telegram_proxy.proxy.stats import ProxyStats
from telegram_proxy.proxy.transport import RawWebSocket, WsHandshakeError, apply_socket_options

log = logging.getLogger("tg_proxy")

# WebSocket / TCP connect timeout
CONNECT_TIMEOUT = 10.0

# Direct TCP fallback is only a quick probe before external SOCKS.
TCP_FALLBACK_CONNECT_TIMEOUT = 3.0

# External SOCKS should still fail over faster than direct TCP, but real client
# paths to bundled VPS nodes can occasionally need more than 3 seconds.
UPSTREAM_CONNECT_TIMEOUT = 5.0

# DC fail cooldown (seconds)
DC_FAIL_COOLDOWN = 10.0

# How long to wait for first server response before declaring DC blocked
_RECV_ZERO_TIMEOUT = 8.0

# How many empty upstream relays are enough to try the next bundled proxy first
_UPSTREAM_ZERO_RECV_FAILS = 2
_UPSTREAM_PENALTY_SECONDS = 60.0
_UPSTREAM_CONNECT_FAILURE_PENALTIES = (60.0, 180.0, 300.0)
_WSS_ZERO_RECV_FAILS = 1
_WSS_DOMAIN_PENALTY_SECONDS = 60.0


class _Socks5UdpRelayProtocol(asyncio.DatagramProtocol):
    def __init__(self, *, label: str, side: str, log_callback: Callable[[str], None]):
        self.label = label
        self.side = side
        self.log_callback = log_callback
        self.transport: asyncio.DatagramTransport | None = None
        self.peer: "_Socks5UdpRelayProtocol | None" = None
        self.fixed_target: tuple[str, int] | None = None
        self.client_addr: tuple[str, int] | None = None

    def connection_made(self, transport) -> None:
        self.transport = transport

    def datagram_received(self, data: bytes, addr) -> None:
        peer = self.peer
        if peer is None or peer.transport is None:
            return
        if self.side == "client":
            self.client_addr = addr
            try:
                packet = socks5.parse_udp_packet(data)
                self.log_callback(
                    f"[{self.label}] UDP -> {packet.target_host}:{packet.target_port} via upstream SOCKS5"
                )
            except Exception as exc:
                self.log_callback(f"[{self.label}] UDP packet rejected: {type(exc).__name__}: {exc}")
                return
            target = peer.fixed_target
            if target is not None:
                peer.transport.sendto(data, target)
            return

        client_addr = peer.client_addr
        if client_addr is not None:
            peer.transport.sendto(data, client_addr)


class _Socks5UdpRelay:
    def __init__(
        self,
        *,
        local_transport,
        upstream_transport,
        upstream_session: socks5.UdpAssociateSession,
        local_host: str,
        local_port: int,
    ):
        self.local_transport = local_transport
        self.upstream_transport = upstream_transport
        self.upstream_session = upstream_session
        self.local_host = local_host
        self.local_port = local_port

    def close(self) -> None:
        try:
            self.local_transport.close()
        except Exception:
            pass
        try:
            self.upstream_transport.close()
        except Exception:
            pass
        try:
            self.upstream_session.writer.close()
        except Exception:
            pass


# ---- Main proxy class ----


class TelegramWSProxy:
    """Async TCP server that tunnels Telegram traffic through WebSocket.

    Usage:
        proxy = TelegramWSProxy(port=1353, mode="socks5")
        await proxy.start()
        # ... proxy is running ...
        await proxy.stop()
    """

    def __init__(
        self,
        port: int = 1353,
        mode: str = "socks5",
        on_log: Optional[Callable[[str], None]] = None,
        on_upstream_selected: Optional[Callable[[str, str], None]] = None,
        host: str = "127.0.0.1",
        upstream_config: Optional[UpstreamProxyConfig] = None,
        cloudflare_config: Optional[CloudflareFallbackConfig] = None,
        mtproxy_secret: str = "",
        dc_endpoint_overrides: Optional[dict[int, str]] = None,
        pool_size: int = 4,
        buffer_kb: int = 256,
        fake_tls_domain: str = "",
        proxy_protocol: bool = False,
    ):
        self._port = port
        self._mode = mode
        self._host = host
        self._on_log = on_log
        self._on_upstream_selected = on_upstream_selected
        self._upstream = upstream_config or UpstreamProxyConfig()
        self._cloudflare = cloudflare_config or CloudflareFallbackConfig()
        self._cloudflare_domain_balancer = CloudflareDomainBalancer()
        self._mtproxy_secret = normalize_secret(mtproxy_secret)
        self._dc_endpoint_overrides = dict(dc_endpoint_overrides or {})
        self._pool_size = max(0, min(32, int(pool_size or 4)))
        self._buffer_size = max(4, min(4096, int(buffer_kb or 256))) * 1024
        self._fake_tls_domain = normalize_fake_tls_domain(fake_tls_domain)
        self._proxy_protocol = bool(proxy_protocol)
        self._upstream_connect_semaphore: asyncio.Semaphore | None = None
        self._http_upstream_connect_semaphore: asyncio.Semaphore | None = None
        self._upstream_zero_recv_counts: dict[tuple[str, int, str, str, bool, str, bool], int] = {}
        self._upstream_connect_failure_counts: dict[tuple[str, int, str, str, bool, str, bool], int] = {}
        self._upstream_penalty_until: dict[tuple[str, int, str, str, bool, str, bool], float] = {}
        self._upstream_active_counts: dict[tuple[str, int, str, str, bool, str, bool], int] = {}
        self._wss_domain_penalty_until: dict[tuple[int, bool, str], float] = {}
        self._wss_zero_recv_counts: dict[tuple[int, bool, str], int] = {}
        self._active_upstream_selected_key: tuple[str, tuple[str, int, str, str, bool, str, bool]] | None = None
        self._servers: list[asyncio.Server] = []
        self._tasks: set[asyncio.Task] = set()
        self._running = False
        self.stats = ProxyStats()
        self._ws_pool = _WsPool(self.stats, pool_size=self._pool_size, buffer_size=self._buffer_size)
        self._cloudflare_worker_pool = CloudflareWorkerPool(
            self.stats,
            pool_size=self._pool_size,
            buffer_size=self._buffer_size,
        )
        # WS blacklist: set of (dc, is_media) where ALL domains returned 302
        self._ws_blacklist: set[tuple[int, bool]] = set()
        # Cooldown for failed DCs: {(dc, is_media): fail_until_timestamp}
        self._dc_cooldown: dict[tuple[int, bool], float] = {}
        # DCs that should use upstream (learned from consecutive recv=0 failures)
        self._dc_upstream_required: set[tuple[int, bool]] = set()
        # HTTP transport cannot use WSS. If direct HTTP/80 is blocked once,
        # skip the repeated 10s direct timeout while this proxy session runs.
        self._http_upstream_required = False
        self._mtproxy_invalid_init_log_marks = {1, 5, 20, 50}
        self._mtproxy_bad_handshake_log_marks = {1, 5, 20, 50}

    def _log(self, msg: str) -> None:
        log.info(msg)
        if self._on_log:
            try:
                self._on_log(msg)
            except Exception:
                pass

    def _record_route(
        self,
        *,
        dc: int,
        is_media: bool,
        route: str,
        status: str,
        reason: str = "",
    ) -> None:
        self.stats.record_route_event(
            dc=dc,
            is_media=is_media,
            route=route,
            status=status,
            reason=reason,
        )

    def _wss_domains_for(self, dc: int, is_media: bool) -> list[str]:
        domains = ws_domains_for_dc(dc, is_media)
        now = time.monotonic()
        ready: list[str] = []
        penalized: list[str] = []
        for domain in domains:
            key = (int(dc), bool(is_media), domain)
            until = self._wss_domain_penalty_until.get(key, 0.0)
            if until <= now:
                self._wss_domain_penalty_until.pop(key, None)
                self._wss_zero_recv_counts.pop(key, None)
                ready.append(domain)
            else:
                penalized.append(domain)
        if ready:
            return ready
        return []

    def _mark_wss_domain_timeout(self, dc: int, is_media: bool, domain: str, label: str, exc: Exception) -> None:
        if not isinstance(exc, TimeoutError):
            return
        key = (int(dc), bool(is_media), domain)
        self._wss_domain_penalty_until[key] = time.monotonic() + _WSS_DOMAIN_PENALTY_SECONDS
        self._log(
            f"[{label}] WSS domain {domain} temporarily deprioritized after TimeoutError "
            f"for {_WSS_DOMAIN_PENALTY_SECONDS:.0f}s"
        )

    def _mark_wss_domain_zero_recv(self, dc: int, is_media: bool, domain: str, label: str) -> None:
        domain = str(domain or "").strip()
        if not domain:
            return
        key = (int(dc), bool(is_media), domain)
        count = self._wss_zero_recv_counts.get(key, 0) + 1
        self._wss_zero_recv_counts[key] = count
        if count < _WSS_ZERO_RECV_FAILS:
            return
        self._wss_domain_penalty_until[key] = time.monotonic() + _WSS_DOMAIN_PENALTY_SECONDS
        self._log(
            f"[{label}] WSS domain {domain} temporarily deprioritized after recv=0 "
            f"({count}/{_WSS_ZERO_RECV_FAILS}) for {_WSS_DOMAIN_PENALTY_SECONDS:.0f}s"
        )

    def _mark_wss_domain_recv_ok(self, dc: int, is_media: bool, domain: str) -> None:
        domain = str(domain or "").strip()
        if not domain:
            return
        key = (int(dc), bool(is_media), domain)
        self._wss_zero_recv_counts.pop(key, None)
        self._wss_domain_penalty_until.pop(key, None)

    @staticmethod
    def _should_log_mtproxy_problem(count: int, marks: set[int]) -> bool:
        return int(count) in marks or (int(count) > 0 and int(count) % 100 == 0)

    def _record_mtproxy_invalid_init(self, label: str) -> None:
        self.stats.mtproxy_invalid_init_count += 1
        count = int(self.stats.mtproxy_invalid_init_count)
        self.stats.mtproxy_last_problem = (
            "нет MTProxy init packet: проверьте тип прокси, старые записи, "
            "Fake TLS/secret или авто-проверку Telegram"
        )
        if not self._should_log_mtproxy_problem(count, self._mtproxy_invalid_init_log_marks):
            return
        self._log(
            f"[{label}] MTProxy init packet не получен; повторов: {count}. "
            "Что это значит: Telegram подключился к MTProxy-порту, но не прислал "
            "первый MTProxy-пакет. Что делать: проверьте тип прокси в Telegram, "
            "удалите старые записи 127.0.0.1, проверьте secret/Fake TLS; "
            "одиночные проверки клиента могут закрываться сами."
        )

    def _record_mtproxy_bad_handshake(self, label: str) -> None:
        self.stats.mtproxy_bad_handshake_count += 1
        count = int(self.stats.mtproxy_bad_handshake_count)
        self.stats.mtproxy_last_problem = (
            "init есть, но secret или тип secret dd/ee не подошёл"
        )
        if not self._should_log_mtproxy_problem(count, self._mtproxy_bad_handshake_log_marks):
            return
        self._log(
            f"[{label}] MTProxy init получен, но не расшифровался; повторов: {count}. "
            "Чаще всего это неверный secret, старый прокси в Telegram или mismatch "
            "типа secret dd/ee."
        )

    @staticmethod
    def _route_error(exc: Exception) -> str:
        text = str(exc)
        if text:
            return f"{type(exc).__name__}: {text}"
        return type(exc).__name__

    def _log_route_detail(
        self,
        label: str,
        *,
        route: str,
        dc: int,
        is_media: bool,
        target: str = "",
        result: str,
        reason: str = "",
        next_step: str = "",
        elapsed: float | None = None,
    ) -> None:
        parts = [
            f"[{label}] route={route}",
            f"mode={'MTProxy' if self._mode == 'mtproxy' else 'SOCKS5'}",
            f"dc={int(dc)}",
            f"media={'yes' if is_media else 'no'}",
        ]
        if target:
            parts.append(f"target={target}")
        parts.append(f"result={result}")
        if reason:
            parts.append(f"reason={reason}")
        if next_step:
            parts.append(f"next={next_step}")
        if elapsed is not None:
            parts.append(f"elapsed={elapsed:.1f}s")
        self._log(" ".join(parts))

    def _get_upstream_connect_semaphore(self) -> asyncio.Semaphore:
        semaphore = self._upstream_connect_semaphore
        if semaphore is None:
            semaphore = asyncio.Semaphore(max(1, self._pool_size or 1))
            self._upstream_connect_semaphore = semaphore
        return semaphore

    def _get_http_upstream_connect_semaphore(self) -> asyncio.Semaphore:
        semaphore = self._http_upstream_connect_semaphore
        if semaphore is None:
            semaphore = asyncio.Semaphore(max(1, min(2, self._pool_size or 1)))
            self._http_upstream_connect_semaphore = semaphore
        return semaphore

    def _get_upstream_semaphore_for_target(self, upstream_port: int) -> asyncio.Semaphore:
        if int(upstream_port or 0) == 80:
            return self._get_http_upstream_connect_semaphore()
        return self._get_upstream_connect_semaphore()

    @staticmethod
    def _upstream_endpoint_key(endpoint: UpstreamProxyEndpoint) -> tuple[str, int, str, str, bool, str, bool]:
        return (
            str(endpoint.host or "").strip().lower(),
            int(endpoint.port or 0),
            str(endpoint.username or ""),
            str(endpoint.password or ""),
            bool(endpoint.tls),
            str(endpoint.tls_server_name or "").strip().lower(),
            bool(endpoint.tls_verify),
        )

    def _upstream_penalty_active(self, endpoint: UpstreamProxyEndpoint, now: float | None = None) -> bool:
        key = self._upstream_endpoint_key(endpoint)
        until = self._upstream_penalty_until.get(key, 0.0)
        if until <= 0:
            return False
        if until <= (time.monotonic() if now is None else now):
            self._upstream_penalty_until.pop(key, None)
            self._upstream_zero_recv_counts.pop(key, None)
            return False
        return True

    def _upstream_candidate_order_key(
        self,
        index: int,
        endpoint: UpstreamProxyEndpoint,
        now: float,
    ) -> tuple[int, int, int, int]:
        penalty = self._upstream_penalty_active(endpoint, now)
        if not penalty and (index == 0 or endpoint.tls):
            group = 0
        elif penalty and endpoint.tls:
            group = 1
        elif not penalty:
            group = 2
        else:
            group = 3
        key = self._upstream_endpoint_key(endpoint)
        failures = self._upstream_connect_failure_counts.get(key, 0)
        active = self._upstream_active_counts.get(key, 0)
        return group, failures, active, index

    def _mark_upstream_active(self, endpoint: UpstreamProxyEndpoint) -> None:
        key = self._upstream_endpoint_key(endpoint)
        self._upstream_active_counts[key] = self._upstream_active_counts.get(key, 0) + 1

    def _unmark_upstream_active(self, endpoint: UpstreamProxyEndpoint) -> None:
        key = self._upstream_endpoint_key(endpoint)
        count = self._upstream_active_counts.get(key, 0)
        if count <= 1:
            self._upstream_active_counts.pop(key, None)
        else:
            self._upstream_active_counts[key] = count - 1

    def _mark_upstream_connect_failure(
        self,
        endpoint: UpstreamProxyEndpoint,
        label: str,
        exc: Exception,
    ) -> None:
        key = self._upstream_endpoint_key(endpoint)
        count = self._upstream_connect_failure_counts.get(key, 0) + 1
        self._upstream_connect_failure_counts[key] = count
        penalty = _UPSTREAM_CONNECT_FAILURE_PENALTIES[min(count - 1, len(_UPSTREAM_CONNECT_FAILURE_PENALTIES) - 1)]
        self._upstream_penalty_until[key] = time.monotonic() + penalty
        self._log(
            f"[{label}] upstream {endpoint.host}:{endpoint.port} temporarily deprioritized "
            f"after connect {type(exc).__name__}"
        )

    def _mark_upstream_zero_recv(self, endpoint: UpstreamProxyEndpoint, label: str) -> None:
        key = self._upstream_endpoint_key(endpoint)
        count = self._upstream_zero_recv_counts.get(key, 0) + 1
        self._upstream_zero_recv_counts[key] = count
        if count < _UPSTREAM_ZERO_RECV_FAILS:
            return
        self._upstream_penalty_until[key] = time.monotonic() + _UPSTREAM_PENALTY_SECONDS
        self._log(
            f"[{label}] upstream {endpoint.host}:{endpoint.port} temporarily deprioritized "
            f"after recv=0 ({count}/{_UPSTREAM_ZERO_RECV_FAILS})"
        )

    def _mark_upstream_recv_ok(self, endpoint: UpstreamProxyEndpoint) -> None:
        key = self._upstream_endpoint_key(endpoint)
        self._upstream_zero_recv_counts.pop(key, None)
        self._upstream_connect_failure_counts.pop(key, None)
        self._upstream_penalty_until.pop(key, None)

    @staticmethod
    def _upstream_display_name(endpoint: UpstreamProxyEndpoint) -> str:
        name = str(endpoint.preset_name or "").strip()
        if name:
            return name
        host = str(endpoint.host or "").strip()
        port = int(endpoint.port or 0)
        return f"{host}:{port}" if host and port > 0 else "внешний прокси"

    def _notify_working_upstream(self, endpoint: UpstreamProxyEndpoint, label: str) -> None:
        endpoint_key = self._upstream_endpoint_key(endpoint)
        preset_id = str(endpoint.preset_id or "").strip()
        preset_name = self._upstream_display_name(endpoint)
        self.stats.active_upstream_preset_id = preset_id
        self.stats.active_upstream_name = preset_name
        self.stats.active_upstream_host = str(endpoint.host or "").strip()
        if not preset_id:
            return
        selected_key = (preset_id, endpoint_key)
        if selected_key == self._active_upstream_selected_key:
            return
        self._active_upstream_selected_key = selected_key
        self._log(f"[{label}] working upstream proxy selected: {preset_name}")
        if self._on_upstream_selected is None:
            return
        try:
            self._on_upstream_selected(preset_id, preset_name)
        except Exception:
            pass

    def _upstream_proxy_candidates(self) -> tuple[UpstreamProxyEndpoint, ...]:
        primary = UpstreamProxyEndpoint(
            host=self._upstream.host,
            port=self._upstream.port,
            username=self._upstream.username,
            password=self._upstream.password,
            tls=self._upstream.tls,
            tls_server_name=self._upstream.tls_server_name,
            tls_verify=self._upstream.tls_verify,
            preset_id=self._upstream.preset_id,
            preset_name=self._upstream.preset_name,
        )
        candidates = (primary, *tuple(self._upstream.fallback_proxies or ()))
        result: list[UpstreamProxyEndpoint] = []
        seen: set[tuple[str, int, str, str, bool, str, bool]] = set()
        for endpoint in candidates:
            host = str(endpoint.host or "").strip()
            try:
                port = int(endpoint.port)
            except (TypeError, ValueError):
                port = 0
            if not host or port <= 0:
                continue
            key = (
                host.lower(),
                port,
                str(endpoint.username or ""),
                str(endpoint.password or ""),
                bool(endpoint.tls),
                str(endpoint.tls_server_name or "").strip().lower(),
                bool(endpoint.tls_verify),
            )
            if key in seen:
                continue
            seen.add(key)
            result.append(
                UpstreamProxyEndpoint(
                    host=host,
                    port=port,
                    username=str(endpoint.username or ""),
                    password=str(endpoint.password or ""),
                    tls=bool(endpoint.tls),
                    tls_server_name=str(endpoint.tls_server_name or "").strip(),
                    tls_verify=bool(endpoint.tls_verify),
                    preset_id=str(endpoint.preset_id or "").strip(),
                    preset_name=str(endpoint.preset_name or "").strip(),
                )
            )
        if any(endpoint.tls for endpoint in result):
            result = [endpoint for endpoint in result if endpoint.tls]
        if len(result) <= 1:
            return tuple(result)
        now = time.monotonic()
        return tuple(
            endpoint for _, endpoint in sorted(
                enumerate(result),
                key=lambda item: self._upstream_candidate_order_key(item[0], item[1], now),
            )
        )

    def _has_healthy_upstream_proxy(self) -> bool:
        candidates = self._upstream_proxy_candidates()
        return any(not self._upstream_penalty_active(endpoint) for endpoint in candidates)

    async def _open_upstream_proxy(
        self,
        *,
        upstream_host: str,
        upstream_port: int,
        label: str,
        dc: int,
        is_media: bool,
        mtproxy: bool = False,
        allow_penalized: bool = True,
    ) -> tuple[asyncio.StreamReader, asyncio.StreamWriter, UpstreamProxyEndpoint] | None:
        media_tag = " media" if is_media else ""
        prefix = "MTProxy " if mtproxy else ""
        attempted: set[tuple[str, int, str, str, bool, str, bool]] = set()
        attempt_index = 0
        while True:
            remaining_candidates = tuple(
                endpoint
                for endpoint in self._upstream_proxy_candidates()
                if self._upstream_endpoint_key(endpoint) not in attempted
            )
            if not remaining_candidates:
                return None

            healthy_candidates = tuple(
                endpoint for endpoint in remaining_candidates
                if not self._upstream_penalty_active(endpoint)
            )
            if healthy_candidates:
                candidates = healthy_candidates
            elif not allow_penalized:
                self._log(f"[{label}] upstream temporarily unavailable; skip penalized fallback")
                return None
            else:
                candidates = remaining_candidates
            if not candidates:
                return None
            endpoint = candidates[0]
            endpoint_key = self._upstream_endpoint_key(endpoint)
            next_step = "try next bundled SOCKS5" if len(candidates) > 1 else "none"
            fallback_tag = "backup " if attempt_index > 0 else ""
            attempt_index += 1
            tls_tag = "yes" if endpoint.tls else "no"
            self._log(
                f"[{label}] {prefix}DC{dc}{media_tag} {fallback_tag}upstream proxy "
                f"-> {endpoint.host}:{endpoint.port} tls={tls_tag}"
            )
            t_connect = time.monotonic()
            self._mark_upstream_active(endpoint)
            try:
                rr, rw = await asyncio.wait_for(
                    socks5.connect_via_socks5(
                        endpoint.host,
                        endpoint.port,
                        upstream_host,
                        upstream_port,
                        username=endpoint.username,
                        password=endpoint.password,
                        timeout=UPSTREAM_CONNECT_TIMEOUT,
                        tls=endpoint.tls,
                        tls_server_name=endpoint.tls_server_name,
                        tls_verify=endpoint.tls_verify,
                    ),
                    timeout=UPSTREAM_CONNECT_TIMEOUT,
                )
                apply_socket_options(rw.transport, self._buffer_size)
            except Exception as exc:
                elapsed = time.monotonic() - t_connect
                self.stats.failed_connections += 1
                self._log(
                    f"[{label}] {prefix}DC{dc}{media_tag} upstream connect failed "
                    f"({elapsed:.1f}s): {type(exc).__name__}: {exc}"
                )
                self._log_route_detail(
                    label,
                    route="upstream SOCKS5",
                    dc=dc,
                    is_media=is_media,
                    target=f"{upstream_host}:{upstream_port} via {endpoint.host}:{endpoint.port}",
                    result="error",
                    reason=self._route_error(exc),
                    next_step=next_step,
                    elapsed=elapsed,
                )
                self._record_route(
                    dc=dc,
                    is_media=is_media,
                    route="внешний SOCKS5",
                    status="ошибка",
                    reason=self._route_error(exc),
                )
                self._mark_upstream_connect_failure(endpoint, label, exc)
                self._unmark_upstream_active(endpoint)
                attempted.add(endpoint_key)
                continue

            elapsed = time.monotonic() - t_connect
            self._log(f"[{label}] {prefix}DC{dc}{media_tag} upstream connected ({elapsed:.1f}s)")
            self._log_route_detail(
                label,
                route="upstream SOCKS5",
                dc=dc,
                is_media=is_media,
                target=f"{upstream_host}:{upstream_port} via {endpoint.host}:{endpoint.port}",
                result="connected",
                elapsed=elapsed,
            )
            self.stats.upstream_connections += 1
            self._record_route(dc=dc, is_media=is_media, route="внешний SOCKS5", status="OK")
            return rr, rw, endpoint

    async def _open_udp_relay(self, label: str) -> _Socks5UdpRelay:
        if not self._upstream.enabled or not self._upstream.udp_enabled:
            raise socks5.Socks5Error("SOCKS5 UDP relay is disabled")

        endpoint = next(
            (
                item for item in self._upstream_proxy_candidates()
                if str(item.host or "").strip() and int(item.port or 0) > 0
            ),
            None,
        )
        if endpoint is None:
            raise socks5.Socks5Error("No upstream SOCKS5 proxy for UDP relay")

        self._log(f"[{label}] UDP ASSOCIATE -> upstream proxy {endpoint.host}:{endpoint.port}")
        upstream_session = await socks5.open_udp_associate_via_socks5(
            endpoint.host,
            endpoint.port,
            username=endpoint.username,
            password=endpoint.password,
            timeout=UPSTREAM_CONNECT_TIMEOUT,
            tls=endpoint.tls,
            tls_server_name=endpoint.tls_server_name,
            tls_verify=endpoint.tls_verify,
        )

        loop = asyncio.get_running_loop()
        local_protocol = _Socks5UdpRelayProtocol(label=label, side="client", log_callback=self._log)
        upstream_protocol = _Socks5UdpRelayProtocol(label=label, side="upstream", log_callback=self._log)
        local_protocol.peer = upstream_protocol
        upstream_protocol.peer = local_protocol
        upstream_protocol.fixed_target = (upstream_session.relay_host, upstream_session.relay_port)

        local_bind_host = self._host if self._host != "0.0.0.0" else "127.0.0.1"
        local_transport = None
        try:
            local_transport, _ = await loop.create_datagram_endpoint(
                lambda: local_protocol,
                local_addr=(local_bind_host, 0),
            )
            upstream_transport, _ = await loop.create_datagram_endpoint(
                lambda: upstream_protocol,
                local_addr=("0.0.0.0", 0),
            )
        except Exception:
            try:
                upstream_session.writer.close()
            except Exception:
                pass
            try:
                if local_transport is not None:
                    local_transport.close()
            except Exception:
                pass
            raise
        local_sock = local_transport.get_extra_info("sockname") or (local_bind_host, 0)
        self._log(
            f"[{label}] UDP relay ready: local {local_sock[0]}:{local_sock[1]} "
            f"-> {upstream_session.relay_host}:{upstream_session.relay_port}"
        )
        return _Socks5UdpRelay(
            local_transport=local_transport,
            upstream_transport=upstream_transport,
            upstream_session=upstream_session,
            local_host=str(local_sock[0]),
            local_port=int(local_sock[1]),
        )

    @property
    def is_running(self) -> bool:
        return self._running

    async def start(self) -> None:
        """Start the proxy server(s)."""
        if self._running:
            return

        self.stats = ProxyStats()
        self._ws_pool = _WsPool(self.stats, pool_size=self._pool_size, buffer_size=self._buffer_size)
        self._cloudflare_worker_pool = CloudflareWorkerPool(
            self.stats,
            pool_size=self._pool_size,
            buffer_size=self._buffer_size,
        )
        # Reset learned routing state from previous session
        self._dc_upstream_required = set()
        self._http_upstream_required = False
        self._ws_blacklist = set()
        self._dc_cooldown = {}
        self._upstream_zero_recv_counts = {}
        self._upstream_connect_failure_counts = {}
        self._upstream_penalty_until = {}
        self._upstream_active_counts = {}
        self._wss_domain_penalty_until = {}
        self._wss_zero_recv_counts = {}
        self._active_upstream_selected_key = None
        self._cloudflare_domain_balancer.reset()
        # Reset semaphore for fresh event loop
        reset_wss_semaphore()
        self._upstream_connect_semaphore = None
        self._http_upstream_connect_semaphore = None

        handler = self._handle_mtproxy_client if self._mode == "mtproxy" else self._handle_socks5_client
        server = await asyncio.start_server(
            handler,
            self._host,
            self._port,
            start_serving=False,
        )
        self._servers.append(server)

        for srv in self._servers:
            await srv.start_serving()

        # Mark running AFTER server is successfully bound and listening
        self._running = True
        mode_label = "MTProxy" if self._mode == "mtproxy" else "SOCKS5"
        self._log(f"{mode_label} proxy started on {self._host}:{self._port}")

        # Pre-fill WebSocket connection pool (non-blocking)
        asyncio.create_task(self._ws_pool.warmup())
        if self._cloudflare.worker_enabled and self._cloudflare.worker_domains:
            asyncio.create_task(
                self._cloudflare_worker_pool.warmup(
                    self._cloudflare.worker_domains,
                    self._cloudflare_worker_warmup_targets(),
                )
            )

    async def stop(self) -> None:
        """Graceful shutdown."""
        if not self._running:
            return

        self._running = False
        self._log("Stopping proxy...")

        # Close all pooled WebSocket connections
        await self._ws_pool.close_all()
        await self._cloudflare_worker_pool.close_all()

        for srv in self._servers:
            srv.close()
        for srv in self._servers:
            await srv.wait_closed()
        self._servers.clear()

        for task in list(self._tasks):
            task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()

        self._log("Proxy stopped")

    # ---- Connection handlers ----

    def _cloudflare_worker_warmup_targets(self) -> list[tuple[int, str]]:
        targets: list[tuple[int, str]] = []
        seen: set[tuple[int, str]] = set()
        for dc in (1, 2, 3, 4, 5, 203):
            if dc in WSS_DOMAINS:
                continue
            for is_media in (False, True):
                host, _port = dc_to_tcp_endpoint(
                    dc,
                    self._dc_endpoint_overrides,
                    is_media=is_media,
                )
                key = (dc, host)
                if key in seen:
                    continue
                seen.add(key)
                targets.append(key)
        return targets

    async def _handle_socks5_client(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        """Handle incoming SOCKS5 connection."""
        task = asyncio.current_task()
        if task:
            self._tasks.add(task)
        self.stats.total_connections += 1
        self.stats.active_connections += 1
        peer = writer.get_extra_info("peername", ("?", 0))
        label = f"{peer[0]}:{peer[1]}"
        udp_relay: _Socks5UdpRelay | None = None

        try:
            async def create_udp_relay() -> tuple[str, int]:
                nonlocal udp_relay
                try:
                    udp_relay = await self._open_udp_relay(label)
                    return udp_relay.local_host, udp_relay.local_port
                except Exception as exc:
                    self._log(f"[{label}] UDP relay failed: {type(exc).__name__}: {exc}")
                    raise

            result = await socks5.handshake(
                reader,
                writer,
                allow_udp_associate=bool(self._upstream.enabled and self._upstream.udp_enabled),
                on_udp_associate=create_udp_relay,
            )
            if result is None:
                return

            if isinstance(result, socks5.UdpAssociateRequest):
                self._log(
                    f"[{label}] UDP ASSOCIATE accepted; "
                    f"client hint {result.client_host}:{result.client_port}"
                )
                try:
                    await reader.read()
                finally:
                    if udp_relay is not None:
                        udp_relay.close()
                return

            target_host, target_port = result

            # Non-Telegram traffic: passthrough (domains + non-Telegram IPs)
            is_domain = _is_domain(target_host)
            is_tg = not is_domain and is_telegram_ip(target_host)
            if not is_tg:
                self.stats.passthrough_connections += 1
                log.debug("[%s] passthrough -> %s:%d", label, target_host, target_port)
                try:
                    rr, rw = await asyncio.wait_for(
                        asyncio.open_connection(target_host, target_port),
                        timeout=CONNECT_TIMEOUT,
                    )
                    apply_socket_options(rw.transport, self._buffer_size)
                except Exception as exc:
                    log.warning("[%s] passthrough connect failed: %s", label, exc)
                    return
                await self._relay_tcp(reader, writer, rr, rw)
                return

            self._log(f"[{label}] -> {target_host}:{target_port}")

            # Read the 64-byte MTProto init packet
            try:
                init = await asyncio.wait_for(
                    reader.readexactly(64), timeout=15.0,
                )
            except (asyncio.IncompleteReadError, asyncio.TimeoutError) as e:
                self._log(f"[{label}] no init packet: {type(e).__name__}")
                return

            # HTTP transport (port 80): pass through directly, can't use WSS
            if _is_http_transport(init):
                # "always" mode: even HTTP goes through upstream
                if should_route_upstream(self._upstream, mode="always"):
                    self._log(f"[{label}] HTTP transport -> upstream (always mode)")
                    self._record_route(
                        dc=0,
                        is_media=False,
                        route="внешний SOCKS5",
                        status="пропуск",
                        reason="HTTP transport, весь TCP через внешний SOCKS5",
                    )
                    await self._upstream_proxy_connect(
                        reader, writer, target_host, target_port,
                        init, label, dc=0, is_media=False,
                    )
                    return
                if should_route_upstream(self._upstream, mode="fallback") and self._http_upstream_required:
                    if self._has_healthy_upstream_proxy():
                        self._log(f"[{label}] HTTP transport -> upstream (fallback mode)")
                        self._record_route(
                            dc=0,
                            is_media=False,
                            route="внешний SOCKS5",
                            status="пропуск",
                            reason="HTTP transport, fallback SOCKS5",
                        )
                        if await self._upstream_proxy_connect(
                            reader, writer, target_host, target_port,
                            init, label, dc=0, is_media=False,
                        ):
                            return
                        self._log(f"[{label}] HTTP upstream failed -> direct TCP probe")
                    else:
                        self._log(f"[{label}] HTTP transport -> direct TCP (upstream temporarily unavailable)")
                self.stats.passthrough_connections += 1
                self._log(f"[{label}] HTTP transport -> direct TCP")
                t_connect = time.monotonic()
                try:
                    rr, rw = await asyncio.wait_for(
                        asyncio.open_connection(target_host, target_port),
                        timeout=CONNECT_TIMEOUT,
                    )
                    apply_socket_options(rw.transport, self._buffer_size)
                except Exception as exc:
                    elapsed = time.monotonic() - t_connect
                    self._log(f"[{label}] HTTP TCP failed: {type(exc).__name__}")
                    self._log_route_detail(
                        label,
                        route="HTTP direct TCP",
                        dc=0,
                        is_media=False,
                        target=f"{target_host}:{target_port}",
                        result="error",
                        reason=self._route_error(exc),
                        next_step=(
                            "upstream SOCKS5 fallback"
                            if should_route_upstream(self._upstream, mode="fallback")
                            else "none; HTTP transport cannot use WSS"
                        ),
                        elapsed=elapsed,
                    )
                    self._record_route(
                        dc=0,
                        is_media=False,
                        route="HTTP direct TCP",
                        status="ошибка",
                        reason=self._route_error(exc),
                    )
                    if should_route_upstream(self._upstream, mode="fallback"):
                        self._http_upstream_required = True
                        self._log(f"[{label}] HTTP TCP failed -> trying upstream SOCKS5 fallback")
                        await self._upstream_proxy_connect(
                            reader, writer, target_host, target_port,
                            init, label, dc=0, is_media=False,
                        )
                    return
                elapsed = time.monotonic() - t_connect
                self._http_upstream_required = False
                self._log_route_detail(
                    label,
                    route="HTTP direct TCP",
                    dc=0,
                    is_media=False,
                    target=f"{target_host}:{target_port}",
                    result="connected",
                    reason="HTTP transport cannot use WSS",
                    elapsed=elapsed,
                )
                rw.write(init)
                await rw.drain()
                await self._relay_tcp(reader, writer, rr, rw)
                return

            # Extract DC from init packet
            dc, is_media = _dc_from_init(init)
            init_patched = False

            # Fallback: if init parsing failed, use IP lookup
            if dc is None:
                entry = IP_TO_DC.get(target_host)
                if entry is not None:
                    dc, is_media = entry
                    # Patch the init packet with the correct DC
                    init = _patch_init_dc(init, -dc if is_media else dc)
                    init_patched = True
                    self._log(f"[{label}] DC from IP table: DC{dc} (patched)")
                else:
                    # Last resort: CIDR-based DC lookup
                    dc = ip_to_dc(target_host) if not _is_domain(target_host) else 2
                    self._log(f"[{label}] DC from CIDR: DC{dc}")
            else:
                self._log(f"[{label}] DC from init: DC{dc}{' media' if is_media else ''}")

            media_tag = " media" if is_media else ""
            self._log(f"[{label}] DC{dc}{media_tag} ({target_host}:{target_port})")

            # "always" mode: route all Telegram TCP traffic through upstream,
            # skip WSS entirely. UDP calls use the separate experimental toggle.
            if should_route_upstream(self._upstream, mode="always"):
                self._log(f"[{label}] DC{dc} -> upstream (always mode)")
                self._record_route(
                    dc=dc,
                    is_media=is_media,
                    route="WSS",
                    status="пропуск",
                    reason="весь TCP через внешний SOCKS5",
                )
                await self._upstream_proxy_connect(
                    reader, writer, target_host, target_port,
                    init, label, dc, is_media,
                )
                return

            # Only DC2 and DC4 have proven working WSS relays.
            # Cross-DC routing via kws2 does NOT work (recv=0, server rejects).
            # Port 80 fallback tested: DC1 partial, DC5 dead. Not reliable.
            if dc not in WSS_DOMAINS:
                self._log(f"[{label}] DC{dc} -> TCP (no WSS relay for this DC)")
                self._record_route(
                    dc=dc,
                    is_media=is_media,
                    route="WSS",
                    status="пропуск",
                    reason="для этого DC нет WSS relay",
                )
                if await self._cloudflare_fallback(
                    reader, writer, target_host, target_port,
                    init, init_patched, label, dc, is_media,
                ):
                    return
                await self._tcp_fallback(
                    reader, writer, target_host, target_port,
                    init, label, dc, is_media,
                )
                return

            await self._tunnel_via_wss(
                reader, writer, dc, is_media, init, init_patched,
                target_host, target_port, label,
            )

        except (asyncio.CancelledError, ConnectionError, OSError):
            pass
        except Exception:
            self.stats.failed_connections += 1
            log.exception("[%s] SOCKS5 handler error", label)
        finally:
            if udp_relay is not None:
                udp_relay.close()
            self.stats.active_connections -= 1
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass
            if task:
                self._tasks.discard(task)

    async def _handle_mtproxy_client(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        """Handle incoming MTProxy secret connection."""
        task = asyncio.current_task()
        if task:
            self._tasks.add(task)
        self.stats.total_connections += 1
        self.stats.active_connections += 1
        peer = writer.get_extra_info("peername", ("?", 0))
        label = f"{peer[0]}:{peer[1]}"

        try:
            if not self._mtproxy_secret:
                self.stats.failed_connections += 1
                self._log(f"[{label}] MTProxy secret is not configured")
                return

            client = await read_mtproxy_client_init(
                reader,
                writer,
                self._mtproxy_secret,
                label,
                fake_tls_domain=self._fake_tls_domain,
                proxy_protocol=self._proxy_protocol,
            )
            if client is None:
                self._record_mtproxy_invalid_init(label)
                return
            client_init = client.init
            client_reader = client.reader
            client_writer = client.writer
            label = client.label

            parsed = parse_client_init(client_init, self._mtproxy_secret)
            if parsed is None:
                self.stats.failed_connections += 1
                self._record_mtproxy_bad_handshake(label)
                return

            dc = parsed.dc
            is_media = parsed.is_media
            relay_init = generate_relay_init(parsed.proto_tag, dc=dc, is_media=is_media)
            crypto = build_crypto_context(parsed.client_prekey_iv, self._mtproxy_secret, relay_init)

            target_host, target_port = dc_to_tcp_endpoint(dc, self._dc_endpoint_overrides, is_media=is_media)
            media_tag = " media" if is_media else ""
            self._log(f"[{label}] MTProxy DC{dc}{media_tag} -> {target_host}:{target_port}")

            await self._tunnel_mtproxy_via_wss(
                client_reader,
                client_writer,
                dc,
                is_media,
                relay_init,
                crypto,
                parsed.proto_tag,
                target_host,
                target_port,
                label,
            )
        except (asyncio.CancelledError, ConnectionError, OSError):
            pass
        except Exception:
            self.stats.failed_connections += 1
            log.exception("[%s] MTProxy handler error", label)
        finally:
            self.stats.active_connections -= 1
            try:
                writer_to_close = locals().get("client_writer", writer)
                writer_to_close.close()
                await writer_to_close.wait_closed()
            except Exception:
                pass
            if task:
                self._tasks.discard(task)

    # ---- Core tunneling ----

    async def _tunnel_via_wss(
        self,
        client_reader: asyncio.StreamReader,
        client_writer: asyncio.StreamWriter,
        dc: int,
        is_media: bool,
        init: bytes,
        init_patched: bool,
        target_host: str,
        target_port: int,
        label: str,
    ) -> None:
        """Try WSS tunnel, fall back to direct TCP if WSS fails."""

        dc_key = (dc, is_media)
        now = time.monotonic()
        media_tag = " media" if is_media else ""

        # Check WS blacklist
        if dc_key in self._ws_blacklist:
            log.debug("[%s] DC%d%s WS blacklisted -> TCP", label, dc, media_tag)
            self._record_route(
                dc=dc,
                is_media=is_media,
                route="WSS",
                status="пропуск",
                reason="раньше были только 302 redirect",
            )
            if await self._cloudflare_fallback(
                client_reader, client_writer, target_host, target_port,
                init, init_patched, label, dc, is_media,
            ):
                return
            await self._tcp_fallback(
                client_reader, client_writer, target_host, target_port,
                init, label, dc, is_media,
            )
            return

        # Check cooldown
        fail_until = self._dc_cooldown.get(dc_key, 0)
        if now < fail_until:
            log.debug("[%s] DC%d%s WS cooldown (%.0fs) -> TCP",
                      label, dc, media_tag, fail_until - now)
            self._record_route(
                dc=dc,
                is_media=is_media,
                route="WSS",
                status="пропуск",
                reason=f"пауза после ошибки {fail_until - now:.0f}s",
            )
            if await self._cloudflare_fallback(
                client_reader, client_writer, target_host, target_port,
                init, init_patched, label, dc, is_media,
            ):
                return
            await self._tcp_fallback(
                client_reader, client_writer, target_host, target_port,
                init, label, dc, is_media,
            )
            return

        # Try WebSocket connection
        domains = self._wss_domains_for(dc, is_media)
        ws = None
        current_domain = ""

        # Try the connection pool first
        ws = await self._ws_pool.get(dc, is_media, WSS_RELAY_IP, domains) if domains else None
        if ws is not None:
            current_domain = str(getattr(ws, "domain", "") or "")
            self._log(f"[{label}] DC{dc}{media_tag} WSS from pool")

        # If pool miss, try fresh WebSocket connection
        all_redirects = True
        any_redirect = False
        ws_failure_reason = "нет доступного WSS"

        sem = _get_wss_semaphore()
        for domain in domains if ws is None else []:
            relay_ip = _relay_ip_for_domain(domain)
            try:
                self._log(f"[{label}] DC{dc}{media_tag} -> wss://{domain}{WSS_PATH}")
                async with sem:
                    ws = await RawWebSocket.connect(
                        relay_ip,
                        domain,
                        WSS_PATH,
                        timeout=CONNECT_TIMEOUT,
                        buffer_size=self._buffer_size,
                    )
                all_redirects = False
                self._log_route_detail(
                    label,
                    route="WSS",
                    dc=dc,
                    is_media=is_media,
                    target=f"{domain}{WSS_PATH} via {relay_ip}",
                    result="connected",
                )
                current_domain = domain
                break
            except WsHandshakeError as exc:
                if exc.is_redirect:
                    any_redirect = True
                    ws_failure_reason = f"{domain}: HTTP {exc.status_code} redirect"
                    log.warning("[%s] DC%d%s got %d from %s -> %s",
                                label, dc, media_tag, exc.status_code,
                                domain, exc.location or "?")
                    self._log_route_detail(
                        label,
                        route="WSS",
                        dc=dc,
                        is_media=is_media,
                        target=f"{domain}{WSS_PATH} via {relay_ip}",
                        result="redirect",
                        reason=f"HTTP {exc.status_code} -> {exc.location or '?'}",
                        next_step="try next WSS domain",
                    )
                    continue
                else:
                    all_redirects = False
                    ws_failure_reason = f"{domain}: {exc.status_line}"
                    log.warning("[%s] DC%d%s WS handshake: %s",
                                label, dc, media_tag, exc.status_line)
                    self._log_route_detail(
                        label,
                        route="WSS",
                        dc=dc,
                        is_media=is_media,
                        target=f"{domain}{WSS_PATH} via {relay_ip}",
                        result="error",
                        reason=exc.status_line,
                        next_step="try next WSS domain or fallback",
                    )
            except Exception as exc:
                all_redirects = False
                ws_failure_reason = f"{domain}: {self._route_error(exc)}"
                self._mark_wss_domain_timeout(dc, is_media, domain, label, exc)
                log.warning("[%s] DC%d%s WS connect failed: %s",
                            label, dc, media_tag, exc)
                self._log_route_detail(
                    label,
                    route="WSS",
                    dc=dc,
                    is_media=is_media,
                    target=f"{domain}{WSS_PATH} via {relay_ip}",
                    result="error",
                    reason=self._route_error(exc),
                    next_step="try next WSS domain or fallback",
                )

        # WS failed
        if ws is None:
            if any_redirect and all_redirects:
                self._ws_blacklist.add(dc_key)
                log.warning("[%s] DC%d%s blacklisted for WS (all 302)",
                            label, dc, media_tag)
            else:
                self._dc_cooldown[dc_key] = now + DC_FAIL_COOLDOWN
                self._log(f"[{label}] DC{dc}{media_tag} WS failed, cooldown {DC_FAIL_COOLDOWN:.0f}s")
            self._record_route(
                dc=dc,
                is_media=is_media,
                route="WSS",
                status="ошибка",
                reason=ws_failure_reason,
            )

            # "always" mode: skip TCP fallback, go straight to upstream
            if should_route_upstream(self._upstream, mode="always"):
                await self._upstream_proxy_connect(
                    client_reader, client_writer, target_host, target_port,
                    init, label, dc, is_media,
                )
                return

            if should_route_upstream(self._upstream, mode="fallback") and self._has_healthy_upstream_proxy():
                self._log(f"[{label}] DC{dc}{media_tag} WSS unavailable -> upstream proxy")
                await self._upstream_proxy_connect(
                    client_reader, client_writer, target_host, target_port,
                    init, label, dc, is_media,
                )
                return

            if await self._cloudflare_fallback(
                client_reader, client_writer, target_host, target_port,
                init, init_patched, label, dc, is_media,
            ):
                return

            await self._tcp_fallback(
                client_reader, client_writer, target_host, target_port,
                init, label, dc, is_media,
            )
            return

        # WS success
        self._dc_cooldown.pop(dc_key, None)
        self.stats.wss_connections += 1
        self._log(f"[{label}] DC{dc}{media_tag} WSS connected")

        # Create splitter ONLY for patched inits (mobile clients with random DC bytes).
        # Normal Telegram Desktop uses intermediate protocol where the splitter's
        # abridged-protocol boundary detection would produce wrong splits.
        splitter = None
        if init_patched:
            try:
                splitter = _MsgSplitter(init)
            except Exception:
                pass

        # Send the buffered init packet as the first WS frame
        await ws.send(init)

        # Bidirectional bridge
        relay_result = await self._relay_wss(client_reader, client_writer, ws, splitter, label, dc=dc)
        recv_total = 0
        sent_total = 0
        if isinstance(relay_result, tuple) and len(relay_result) >= 2:
            recv_total = int(relay_result[0] or 0)
            sent_total = int(relay_result[1] or 0)
        if recv_total > 0:
            self._mark_wss_domain_recv_ok(dc, is_media, current_domain)
            self._record_route(dc=dc, is_media=is_media, route="WSS", status="OK")
            return
        if sent_total > 0:
            self._mark_wss_domain_zero_recv(dc, is_media, current_domain, label)
            self._record_route(
                dc=dc,
                is_media=is_media,
                route="WSS",
                status="ошибка",
                reason="recv=0",
            )

    async def _tunnel_mtproxy_via_wss(
        self,
        client_reader: asyncio.StreamReader,
        client_writer: asyncio.StreamWriter,
        dc: int,
        is_media: bool,
        relay_init: bytes,
        crypto,
        proto_tag: bytes,
        target_host: str,
        target_port: int,
        label: str,
    ) -> None:
        """Try WSS tunnel for MTProxy, fall back to Cloudflare/TCP."""
        dc_key = (dc, is_media)
        now = time.monotonic()
        media_tag = " media" if is_media else ""
        try:
            splitter = MTProxyMsgSplitter(relay_init, proto_tag)
        except Exception:
            splitter = None

        if should_route_upstream(self._upstream, mode="always"):
            self._log(f"[{label}] MTProxy DC{dc}{media_tag} -> upstream (always mode)")
            self._record_route(
                dc=dc,
                is_media=is_media,
                route="WSS",
                status="пропуск",
                reason="весь TCP через внешний SOCKS5",
            )
            await self._mtproxy_upstream_proxy_connect(
                client_reader,
                client_writer,
                target_host,
                target_port,
                relay_init,
                crypto,
                label,
                dc,
                is_media,
            )
            return

        if dc not in WSS_DOMAINS:
            self._log(f"[{label}] MTProxy DC{dc}{media_tag} -> fallback (no own WSS relay)")
            self._record_route(
                dc=dc,
                is_media=is_media,
                route="WSS",
                status="пропуск",
                reason="для этого DC нет WSS relay",
            )
            if await self._cloudflare_fallback(
                client_reader,
                client_writer,
                target_host,
                target_port,
                relay_init,
                False,
                label,
                dc,
                is_media,
                relay_wss_fn=lambda **kwargs: relay_mtproxy_wss(crypto=crypto, splitter=splitter, **kwargs),
            ):
                return
            await self._mtproxy_tcp_fallback(
                client_reader, client_writer, target_host, target_port, relay_init, crypto, label, dc, is_media
            )
            return

        if dc_key in self._ws_blacklist or now < self._dc_cooldown.get(dc_key, 0):
            reason = "раньше были только 302 redirect" if dc_key in self._ws_blacklist else "пауза после ошибки"
            self._record_route(
                dc=dc,
                is_media=is_media,
                route="WSS",
                status="пропуск",
                reason=reason,
            )
            if await self._cloudflare_fallback(
                client_reader,
                client_writer,
                target_host,
                target_port,
                relay_init,
                False,
                label,
                dc,
                is_media,
                relay_wss_fn=lambda **kwargs: relay_mtproxy_wss(crypto=crypto, splitter=splitter, **kwargs),
            ):
                return
            await self._mtproxy_tcp_fallback(
                client_reader, client_writer, target_host, target_port, relay_init, crypto, label, dc, is_media
            )
            return

        domains = self._wss_domains_for(dc, is_media)
        ws = await self._ws_pool.get(dc, is_media, WSS_RELAY_IP, domains)
        if ws is not None:
            self._log(f"[{label}] MTProxy DC{dc}{media_tag} WSS from pool")

        all_redirects = True
        any_redirect = False
        ws_failure_reason = "нет доступного WSS"
        sem = _get_wss_semaphore()
        for domain in domains if ws is None else []:
            relay_ip = _relay_ip_for_domain(domain)
            try:
                self._log(f"[{label}] MTProxy DC{dc}{media_tag} -> wss://{domain}{WSS_PATH}")
                async with sem:
                    ws = await RawWebSocket.connect(
                        relay_ip,
                        domain,
                        WSS_PATH,
                        timeout=CONNECT_TIMEOUT,
                        buffer_size=self._buffer_size,
                    )
                all_redirects = False
                self._log_route_detail(
                    label,
                    route="WSS",
                    dc=dc,
                    is_media=is_media,
                    target=f"{domain}{WSS_PATH} via {relay_ip}",
                    result="connected",
                )
                self._wss_domain_penalty_until.pop((int(dc), bool(is_media), domain), None)
                break
            except WsHandshakeError as exc:
                if exc.is_redirect:
                    any_redirect = True
                    ws_failure_reason = f"{domain}: HTTP {exc.status_code} redirect"
                    self._log_route_detail(
                        label,
                        route="WSS",
                        dc=dc,
                        is_media=is_media,
                        target=f"{domain}{WSS_PATH} via {relay_ip}",
                        result="redirect",
                        reason=f"HTTP {exc.status_code} -> {exc.location or '?'}",
                        next_step="try next WSS domain",
                    )
                    continue
                all_redirects = False
                ws_failure_reason = f"{domain}: {exc.status_line}"
                self._log_route_detail(
                    label,
                    route="WSS",
                    dc=dc,
                    is_media=is_media,
                    target=f"{domain}{WSS_PATH} via {relay_ip}",
                    result="error",
                    reason=exc.status_line,
                    next_step="try next WSS domain or fallback",
                )
            except Exception as exc:
                all_redirects = False
                ws_failure_reason = f"{domain}: {self._route_error(exc)}"
                self._mark_wss_domain_timeout(dc, is_media, domain, label, exc)
                self._log_route_detail(
                    label,
                    route="WSS",
                    dc=dc,
                    is_media=is_media,
                    target=f"{domain}{WSS_PATH} via {relay_ip}",
                    result="error",
                    reason=self._route_error(exc),
                    next_step="try next WSS domain or fallback",
                )

        if ws is None:
            if any_redirect and all_redirects:
                self._ws_blacklist.add(dc_key)
            else:
                self._dc_cooldown[dc_key] = now + DC_FAIL_COOLDOWN
            self._record_route(
                dc=dc,
                is_media=is_media,
                route="WSS",
                status="ошибка",
                reason=ws_failure_reason,
            )
            if await self._cloudflare_fallback(
                client_reader,
                client_writer,
                target_host,
                target_port,
                relay_init,
                False,
                label,
                dc,
                is_media,
                relay_wss_fn=lambda **kwargs: relay_mtproxy_wss(crypto=crypto, splitter=splitter, **kwargs),
            ):
                return
            await self._mtproxy_tcp_fallback(
                client_reader, client_writer, target_host, target_port, relay_init, crypto, label, dc, is_media
            )
            return

        self._dc_cooldown.pop(dc_key, None)
        self.stats.wss_connections += 1
        self._record_route(dc=dc, is_media=is_media, route="WSS", status="OK")
        await ws.send(relay_init)
        await relay_mtproxy_wss(
            client_reader=client_reader,
            client_writer=client_writer,
            ws=ws,
            crypto=crypto,
            stats=self.stats,
            log_fn=self._log,
            label=label,
            dc=dc,
            splitter=splitter,
        )

    async def _cloudflare_fallback(
        self,
        client_reader: asyncio.StreamReader,
        client_writer: asyncio.StreamWriter,
        target_host: str,
        target_port: int,
        init: bytes,
        init_patched: bool,
        label: str,
        dc: int,
        is_media: bool,
        relay_wss_fn=None,
    ) -> bool:
        """Try Cloudflare Worker/domain fallback before plain TCP fallback."""
        if not should_try_cloudflare(self._cloudflare):
            return False

        media_tag = " media" if is_media else ""
        splitter = None
        if init_patched:
            try:
                splitter = _MsgSplitter(init)
            except Exception:
                pass

        if self._cloudflare.worker_enabled and self._cloudflare.worker_domains:
            path = build_worker_path(target_host, dc)
            for worker_domain in self._cloudflare.worker_domains:
                t_connect = time.monotonic()
                try:
                    ws = await self._cloudflare_worker_pool.get(dc, worker_domain, target_host)
                    if ws is not None:
                        self._log(
                            f"[{label}] DC{dc}{media_tag} -> Cloudflare Worker pool "
                            f"{worker_domain}{path}"
                        )
                    else:
                        self._log(
                            f"[{label}] DC{dc}{media_tag} -> Cloudflare Worker "
                            f"{worker_domain}{path}"
                        )
                        ws = await RawWebSocket.connect(
                            worker_domain,
                            worker_domain,
                            path=path,
                            timeout=CONNECT_TIMEOUT,
                            buffer_size=self._buffer_size,
                        )
                    elapsed = time.monotonic() - t_connect
                    self._log_route_detail(
                        label,
                        route="Cloudflare Worker",
                        dc=dc,
                        is_media=is_media,
                        target=f"{worker_domain}{path} -> {target_host}:{target_port}",
                        result="connected",
                        elapsed=elapsed,
                    )
                    self.stats.cloudflare_connections += 1
                    self.stats.cloudflare_worker_connections += 1
                    self._record_route(
                        dc=dc,
                        is_media=is_media,
                        route="Cloudflare Worker",
                        status="OK",
                        reason=worker_domain,
                    )
                    await ws.send(init)
                    if relay_wss_fn is None:
                        await self._relay_wss(client_reader, client_writer, ws, splitter, label, dc=dc)
                    else:
                        await relay_wss_fn(
                            client_reader=client_reader,
                            client_writer=client_writer,
                            ws=ws,
                            stats=self.stats,
                            log_fn=self._log,
                            label=label,
                            dc=dc,
                        )
                    return True
                except Exception as exc:
                    log.warning(
                        "[%s] DC%d%s Cloudflare Worker %s failed: %s",
                        label,
                        dc,
                        media_tag,
                        worker_domain,
                        exc,
                    )
                    elapsed = time.monotonic() - t_connect
                    self._log_route_detail(
                        label,
                        route="Cloudflare Worker",
                        dc=dc,
                        is_media=is_media,
                        target=f"{worker_domain}{path} -> {target_host}:{target_port}",
                        result="error",
                        reason=self._route_error(exc),
                        next_step="try next Worker domain or Cloudflare domain",
                        elapsed=elapsed,
                    )
                    self._record_route(
                        dc=dc,
                        is_media=is_media,
                        route="Cloudflare Worker",
                        status="ошибка",
                        reason=f"{worker_domain}: {self._route_error(exc)}",
                    )

        if self._cloudflare.enabled and self._cloudflare.domains:
            for domain in build_cloudflare_domains(
                dc,
                self._cloudflare,
                balancer=self._cloudflare_domain_balancer,
            ):
                t_connect = time.monotonic()
                try:
                    self._log(f"[{label}] DC{dc}{media_tag} -> Cloudflare wss://{domain}{WSS_PATH}")
                    ws = await RawWebSocket.connect(
                        domain,
                        domain,
                        path=WSS_PATH,
                        timeout=CONNECT_TIMEOUT,
                        buffer_size=self._buffer_size,
                    )
                    elapsed = time.monotonic() - t_connect
                    self._log_route_detail(
                        label,
                        route="Cloudflare",
                        dc=dc,
                        is_media=is_media,
                        target=f"{domain}{WSS_PATH} -> {target_host}:{target_port}",
                        result="connected",
                        elapsed=elapsed,
                    )
                    self.stats.cloudflare_connections += 1
                    self._cloudflare_domain_balancer.record_success(dc, domain)
                    self._record_route(
                        dc=dc,
                        is_media=is_media,
                        route="Cloudflare",
                        status="OK",
                        reason=domain,
                    )
                    await ws.send(init)
                    if relay_wss_fn is None:
                        await self._relay_wss(client_reader, client_writer, ws, splitter, label, dc=dc)
                    else:
                        await relay_wss_fn(
                            client_reader=client_reader,
                            client_writer=client_writer,
                            ws=ws,
                            stats=self.stats,
                            log_fn=self._log,
                            label=label,
                            dc=dc,
                        )
                    return True
                except Exception as exc:
                    log.warning(
                        "[%s] DC%d%s Cloudflare domain %s failed: %s",
                        label,
                        dc,
                        media_tag,
                        domain,
                        exc,
                    )
                    elapsed = time.monotonic() - t_connect
                    self._log_route_detail(
                        label,
                        route="Cloudflare",
                        dc=dc,
                        is_media=is_media,
                        target=f"{target_host}:{target_port}",
                        result="error",
                        reason=self._route_error(exc),
                        next_step="try next Cloudflare domain or TCP fallback",
                        elapsed=elapsed,
                    )
                    self._record_route(
                        dc=dc,
                        is_media=is_media,
                        route="Cloudflare",
                        status="ошибка",
                        reason=f"{domain}: {self._route_error(exc)}",
                    )

        self.stats.cloudflare_failures += 1
        self._record_route(
            dc=dc,
            is_media=is_media,
            route="Cloudflare",
            status="ошибка",
            reason="нет рабочего Worker или домена",
        )
        self._log_route_detail(
            label,
            route="Cloudflare",
            dc=dc,
            is_media=is_media,
            target=f"{target_host}:{target_port}",
            result="exhausted",
            reason="no working Worker or domain",
            next_step="TCP fallback",
        )
        return False

    async def _mtproxy_tcp_fallback(
        self,
        client_reader: asyncio.StreamReader,
        client_writer: asyncio.StreamWriter,
        target_host: str,
        target_port: int,
        relay_init: bytes,
        crypto,
        label: str,
        dc: int,
        is_media: bool,
    ) -> None:
        media_tag = " media" if is_media else ""
        self._log(f"[{label}] MTProxy DC{dc}{media_tag} TCP fallback -> {target_host}:{target_port}")
        try:
            rr, rw = await asyncio.wait_for(
                asyncio.open_connection(target_host, target_port),
                timeout=CONNECT_TIMEOUT,
            )
            apply_socket_options(rw.transport, self._buffer_size)
        except Exception as exc:
            self.stats.failed_connections += 1
            self._log(f"[{label}] MTProxy TCP fallback failed: {type(exc).__name__}")
            self._log_route_detail(
                label,
                route="TCP fallback",
                dc=dc,
                is_media=is_media,
                target=f"{target_host}:{target_port}",
                result="error",
                reason=self._route_error(exc),
                next_step="upstream SOCKS5" if self._upstream.enabled else "none",
            )
            self._record_route(
                dc=dc,
                is_media=is_media,
                route="TCP",
                status="ошибка",
                reason=self._route_error(exc),
            )
            if self._upstream.enabled:
                self._log(f"[{label}] MTProxy DC{dc}{media_tag} TCP failed -> trying upstream")
                await self._mtproxy_upstream_proxy_connect(
                    client_reader,
                    client_writer,
                    target_host,
                    target_port,
                    relay_init,
                    crypto,
                    label,
                    dc,
                    is_media,
                )
            return

        self.stats.tcp_fallback_connections += 1
        self._log_route_detail(
            label,
            route="TCP fallback",
            dc=dc,
            is_media=is_media,
            target=f"{target_host}:{target_port}",
            result="connected",
        )
        self._record_route(dc=dc, is_media=is_media, route="TCP", status="OK")
        rw.write(relay_init)
        await rw.drain()
        await relay_mtproxy_tcp(
            client_reader=client_reader,
            client_writer=client_writer,
            remote_reader=rr,
            remote_writer=rw,
            crypto=crypto,
            stats=self.stats,
            log_fn=self._log,
            label=label,
        )

    async def _mtproxy_upstream_proxy_connect(
        self,
        client_reader: asyncio.StreamReader,
        client_writer: asyncio.StreamWriter,
        target_host: str,
        target_port: int,
        relay_init: bytes,
        crypto,
        label: str,
        dc: int,
        is_media: bool,
    ) -> bool:
        """Route MTProxy relay traffic through the external SOCKS5 fallback."""
        if not self._upstream.enabled:
            return False

        media_tag = " media" if is_media else ""
        upstream_host, upstream_port = self._upstream_target(target_host, target_port, dc, is_media)
        if upstream_host != target_host or upstream_port != target_port:
            self._log(
                f"[{label}] MTProxy DC{dc}{media_tag} upstream target "
                f"{target_host}:{target_port} -> {upstream_host}:{upstream_port}"
            )
        async with self._get_upstream_connect_semaphore():
            opened = await self._open_upstream_proxy(
                upstream_host=upstream_host,
                upstream_port=upstream_port,
                label=label,
                dc=dc,
                is_media=is_media,
                mtproxy=True,
                allow_penalized=not should_route_upstream(self._upstream, mode="fallback"),
            )
            if opened is None:
                return False
            rr, rw, endpoint = opened
            try:
                rw.write(relay_init)
                await rw.drain()
                await relay_mtproxy_tcp(
                    client_reader=client_reader,
                    client_writer=client_writer,
                    remote_reader=rr,
                    remote_writer=rw,
                    crypto=crypto,
                    stats=self.stats,
                    log_fn=self._log,
                    label=label,
                )
            finally:
                self._unmark_upstream_active(endpoint)
        return True

    async def _tcp_fallback(
        self,
        client_reader: asyncio.StreamReader,
        client_writer: asyncio.StreamWriter,
        target_host: str,
        target_port: int,
        init: bytes,
        label: str,
        dc: int,
        is_media: bool,
    ) -> None:
        """Fall back to direct TCP to the original DC IP.

        If upstream proxy is configured in "fallback" mode and this DC has
        previously had recv=0 failures, routes through upstream instead.
        After a direct TCP relay with recv=0, marks the DC for future upstream routing.
        """
        media_tag = " media" if is_media else ""

        # If this DC is known-blocked and upstream is available, use upstream
        if ((dc, is_media) in self._dc_upstream_required
                and should_route_upstream(self._upstream, mode="fallback")):
            self._log(f"[{label}] DC{dc}{media_tag} learned-blocked -> upstream proxy")
            self._record_route(
                dc=dc,
                is_media=is_media,
                route="TCP",
                status="пропуск",
                reason="раньше был recv=0",
            )
            ok = await self._upstream_proxy_connect(
                client_reader, client_writer,
                target_host, target_port, init, label, dc, is_media,
            )
            if not ok:
                self._dc_upstream_required.discard((dc, is_media))
                self._log(f"[{label}] DC{dc}{media_tag} upstream failed, unmarked for re-probe")
            return

        if (
            is_media
            and dc not in WSS_DOMAINS
            and should_route_upstream(self._upstream, mode="fallback")
        ):
            self._log(f"[{label}] DC{dc}{media_tag} no WSS -> upstream proxy")
            self._record_route(
                dc=dc,
                is_media=is_media,
                route="TCP",
                status="пропуск",
                reason="медиа DC без WSS relay",
            )
            ok = await self._upstream_proxy_connect(
                client_reader, client_writer,
                target_host, target_port, init, label, dc, is_media,
            )
            if ok:
                return
            self._log(f"[{label}] DC{dc}{media_tag} upstream failed -> direct TCP probe")

        self._log(f"[{label}] DC{dc}{media_tag} TCP fallback -> {target_host}:{target_port}")
        t_connect = time.monotonic()
        try:
            rr, rw = await asyncio.wait_for(
                asyncio.open_connection(target_host, target_port),
                timeout=TCP_FALLBACK_CONNECT_TIMEOUT,
            )
            apply_socket_options(rw.transport, self._buffer_size)
        except Exception as exc:
            elapsed = time.monotonic() - t_connect
            self.stats.failed_connections += 1
            self._log(f"[{label}] TCP fallback failed ({elapsed:.1f}s): {type(exc).__name__}")
            self._log_route_detail(
                label,
                route="TCP fallback",
                dc=dc,
                is_media=is_media,
                target=f"{target_host}:{target_port}",
                result="error",
                reason=self._route_error(exc),
                next_step="upstream SOCKS5" if self._upstream.enabled else "none",
                elapsed=elapsed,
            )
            self._record_route(
                dc=dc,
                is_media=is_media,
                route="TCP",
                status="ошибка",
                reason=self._route_error(exc),
            )
            # TCP connect failed — try upstream if available
            if self._upstream.enabled:
                self._dc_upstream_required.add((dc, is_media))
                self._log(f"[{label}] DC{dc}{media_tag} TCP failed -> trying upstream")
                await self._upstream_proxy_connect(
                    client_reader, client_writer,
                    target_host, target_port, init, label, dc, is_media,
                )
            return

        elapsed = time.monotonic() - t_connect
        self._log(f"[{label}] DC{dc}{media_tag} TCP connected ({elapsed:.1f}s)")
        self._log_route_detail(
            label,
            route="TCP fallback",
            dc=dc,
            is_media=is_media,
            target=f"{target_host}:{target_port}",
            result="connected",
            elapsed=elapsed,
        )
        self.stats.tcp_fallback_connections += 1
        self._record_route(dc=dc, is_media=is_media, route="TCP", status="OK")
        # Forward the buffered init packet
        rw.write(init)
        await rw.drain()
        recv_total, watchdog_fired = await self._relay_tcp(
            client_reader, client_writer, rr, rw, label,
            dc=dc, recv_zero_timeout=_RECV_ZERO_TIMEOUT,
        )

        # Learn from watchdog timeout: server silence = DC is blocked by DPI.
        # Only mark on watchdog — client disconnect with recv=0 is NOT blocking evidence.
        if watchdog_fired and recv_total == 0 and self._upstream.enabled:
            self._dc_upstream_required.add((dc, is_media))
            self._log(f"[{label}] DC{dc}{media_tag} recv=0 (watchdog) -> marked for upstream routing")
            self._log_route_detail(
                label,
                route="TCP fallback",
                dc=dc,
                is_media=is_media,
                target=f"{target_host}:{target_port}",
                result="error",
                reason="recv=0 watchdog",
                next_step="future connections use upstream SOCKS5",
            )
            self._record_route(
                dc=dc,
                is_media=is_media,
                route="TCP",
                status="ошибка",
                reason="recv=0 watchdog",
            )

    async def _upstream_proxy_connect(
        self,
        client_reader: asyncio.StreamReader,
        client_writer: asyncio.StreamWriter,
        target_host: str,
        target_port: int,
        init: bytes,
        label: str,
        dc: int,
        is_media: bool,
    ) -> bool:
        """Route through upstream SOCKS5 proxy as last-resort fallback.
        Returns True if upstream connected, False on failure."""
        if not self._upstream.enabled:
            return False
        fallback_mode = should_route_upstream(self._upstream, mode="fallback")
        has_healthy_upstream = self._has_healthy_upstream_proxy()
        if fallback_mode and not has_healthy_upstream:
            self._log(f"[{label}] upstream temporarily unavailable; skip fallback")
            return False

        media_tag = " media" if is_media else ""
        upstream_host, upstream_port = self._upstream_target(target_host, target_port, dc, is_media)
        if upstream_host != target_host or upstream_port != target_port:
            self._log(
                f"[{label}] DC{dc}{media_tag} upstream target "
                f"{target_host}:{target_port} -> {upstream_host}:{upstream_port}"
            )
        async with self._get_upstream_semaphore_for_target(upstream_port):
            opened = await self._open_upstream_proxy(
                upstream_host=upstream_host,
                upstream_port=upstream_port,
                label=label,
                dc=dc,
                is_media=is_media,
                allow_penalized=not fallback_mode,
            )
            if opened is None:
                return False
            rr, rw, endpoint = opened
            upstream_notified = False

            def notify_on_first_response() -> None:
                nonlocal upstream_notified
                if upstream_notified:
                    return
                upstream_notified = True
                self._mark_upstream_recv_ok(endpoint)
                self._notify_working_upstream(endpoint, label)

            try:
                # Forward the buffered init packet
                rw.write(init)
                await rw.drain()
                recv_total, watchdog_fired = await self._relay_tcp(
                    client_reader,
                    client_writer,
                    rr,
                    rw,
                    label,
                    dc=dc,
                    on_first_response=notify_on_first_response,
                )
                if recv_total > 0:
                    if not upstream_notified:
                        self._mark_upstream_recv_ok(endpoint)
                        self._notify_working_upstream(endpoint, label)
                elif not fallback_mode:
                    self._mark_upstream_zero_recv(endpoint, label)
            finally:
                self._unmark_upstream_active(endpoint)
        return True

    def _upstream_target(
        self,
        target_host: str,
        target_port: int,
        dc: int,
        is_media: bool,
    ) -> tuple[str, int]:
        if ":" not in str(target_host) or int(dc or 0) <= 0 or int(target_port or 0) != 443:
            return target_host, target_port
        if not is_telegram_ip(str(target_host)):
            return target_host, target_port
        return dc_to_tcp_endpoint(dc, self._dc_endpoint_overrides, is_media=is_media)

    async def _relay_wss(
        self,
        client_reader: asyncio.StreamReader,
        client_writer: asyncio.StreamWriter,
        ws: RawWebSocket,
        splitter: Optional[_MsgSplitter],
        label: str,
        dc: int = 0,
    ) -> tuple[int, int]:
        return await relay_wss(
            client_reader=client_reader,
            client_writer=client_writer,
            ws=ws,
            splitter=splitter,
            stats=self.stats,
            log_fn=self._log,
            label=label,
            dc=dc,
        )

    async def _relay_tcp(
        self,
        client_reader: asyncio.StreamReader,
        client_writer: asyncio.StreamWriter,
        remote_reader: asyncio.StreamReader,
        remote_writer: asyncio.StreamWriter,
        label: str = "",
        dc: int = 0,
        recv_zero_timeout: float = 0,
        on_first_response: Optional[Callable[[], None]] = None,
    ) -> tuple[int, bool]:
        return await relay_tcp(
            client_reader=client_reader,
            client_writer=client_writer,
            remote_reader=remote_reader,
            remote_writer=remote_writer,
            stats=self.stats,
            log_fn=self._log,
            label=label,
            dc=dc,
            recv_zero_timeout=recv_zero_timeout,
            on_first_response=on_first_response,
        )


def _is_domain(host: str) -> bool:
    """Check if host is a domain name (not an IP address)."""
    if ":" in host:
        return False  # IPv6 address
    return not all(c.isdigit() or c == "." for c in host)
