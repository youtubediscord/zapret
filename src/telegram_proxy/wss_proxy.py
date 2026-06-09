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
from telegram_proxy.proxy.routing import UpstreamProxyConfig, check_relay_reachable, should_route_upstream
from telegram_proxy.proxy.stats import ProxyStats
from telegram_proxy.proxy.transport import RawWebSocket, WsHandshakeError, apply_socket_options

log = logging.getLogger("tg_proxy")

# WebSocket / TCP connect timeout
CONNECT_TIMEOUT = 10.0

# DC fail cooldown (seconds)
DC_FAIL_COOLDOWN = 10.0

# How long to wait for first server response before declaring DC blocked
_RECV_ZERO_TIMEOUT = 8.0

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
        self._upstream = upstream_config or UpstreamProxyConfig()
        self._cloudflare = cloudflare_config or CloudflareFallbackConfig()
        self._cloudflare_domain_balancer = CloudflareDomainBalancer()
        self._mtproxy_secret = normalize_secret(mtproxy_secret)
        self._dc_endpoint_overrides = dict(dc_endpoint_overrides or {})
        self._pool_size = max(0, min(32, int(pool_size or 4)))
        self._buffer_size = max(4, min(4096, int(buffer_kb or 256))) * 1024
        self._fake_tls_domain = normalize_fake_tls_domain(fake_tls_domain)
        self._proxy_protocol = bool(proxy_protocol)
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

    @staticmethod
    def _route_error(exc: Exception) -> str:
        text = str(exc)
        if text:
            return f"{type(exc).__name__}: {text}"
        return type(exc).__name__

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
        self._ws_blacklist = set()
        self._dc_cooldown = {}
        self._cloudflare_domain_balancer.reset()
        # Reset semaphore for fresh event loop
        reset_wss_semaphore()

        handler = self._handle_mtproxy_client if self._mode == "mtproxy" else self._handle_socks5_client
        server = await asyncio.start_server(
            handler,
            self._host,
            self._port,
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

        try:
            result = await socks5.handshake(reader, writer)
            if result is None:
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
                        reason="HTTP transport, режим весь трафик",
                    )
                    await self._upstream_proxy_connect(
                        reader, writer, target_host, target_port,
                        init, label, dc=0, is_media=False,
                    )
                    return
                self.stats.passthrough_connections += 1
                self._log(f"[{label}] HTTP transport -> direct TCP")
                try:
                    rr, rw = await asyncio.wait_for(
                        asyncio.open_connection(target_host, target_port),
                        timeout=CONNECT_TIMEOUT,
                    )
                    apply_socket_options(rw.transport, self._buffer_size)
                except Exception as exc:
                    self._log(f"[{label}] HTTP TCP failed: {type(exc).__name__}")
                    return
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

            # "always" mode: route ALL Telegram traffic through upstream,
            # skip WSS entirely. This is the "Весь трафик через прокси" toggle.
            if should_route_upstream(self._upstream, mode="always"):
                self._log(f"[{label}] DC{dc} -> upstream (always mode)")
                self._record_route(
                    dc=dc,
                    is_media=is_media,
                    route="WSS",
                    status="пропуск",
                    reason="весь трафик через внешний SOCKS5",
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
                self._log(f"[{label}] no MTProxy init packet")
                return
            client_init = client.init
            client_reader = client.reader
            client_writer = client.writer
            label = client.label

            parsed = parse_client_init(client_init, self._mtproxy_secret)
            if parsed is None:
                self.stats.failed_connections += 1
                self._log(f"[{label}] bad MTProxy handshake")
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
        domains = ws_domains_for_dc(dc, is_media)
        ws = None

        # Try the connection pool first
        ws = await self._ws_pool.get(dc, is_media, WSS_RELAY_IP, domains)
        if ws is not None:
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
                break
            except WsHandshakeError as exc:
                if exc.is_redirect:
                    any_redirect = True
                    ws_failure_reason = f"{domain}: HTTP {exc.status_code} redirect"
                    log.warning("[%s] DC%d%s got %d from %s -> %s",
                                label, dc, media_tag, exc.status_code,
                                domain, exc.location or "?")
                    continue
                else:
                    all_redirects = False
                    ws_failure_reason = f"{domain}: {exc.status_line}"
                    log.warning("[%s] DC%d%s WS handshake: %s",
                                label, dc, media_tag, exc.status_line)
            except Exception as exc:
                all_redirects = False
                ws_failure_reason = f"{domain}: {self._route_error(exc)}"
                log.warning("[%s] DC%d%s WS connect failed: %s",
                            label, dc, media_tag, exc)

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
        self._record_route(dc=dc, is_media=is_media, route="WSS", status="OK")
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
        await self._relay_wss(client_reader, client_writer, ws, splitter, label, dc=dc)

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
                reason="весь трафик через внешний SOCKS5",
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

        domains = ws_domains_for_dc(dc, is_media)
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
                break
            except WsHandshakeError as exc:
                if exc.is_redirect:
                    any_redirect = True
                    ws_failure_reason = f"{domain}: HTTP {exc.status_code} redirect"
                    continue
                all_redirects = False
                ws_failure_reason = f"{domain}: {exc.status_line}"
            except Exception:
                all_redirects = False
                ws_failure_reason = f"{domain}: WSS connect failed"

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
                try:
                    self._log(f"[{label}] DC{dc}{media_tag} -> Cloudflare wss://{domain}{WSS_PATH}")
                    ws = await RawWebSocket.connect(
                        domain,
                        domain,
                        path=WSS_PATH,
                        timeout=CONNECT_TIMEOUT,
                        buffer_size=self._buffer_size,
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
        self._log(
            f"[{label}] MTProxy DC{dc}{media_tag} upstream proxy "
            f"-> {self._upstream.host}:{self._upstream.port}"
        )
        t_connect = time.monotonic()
        try:
            rr, rw = await socks5.connect_via_socks5(
                self._upstream.host,
                self._upstream.port,
                target_host,
                target_port,
                username=self._upstream.username,
                password=self._upstream.password,
                timeout=CONNECT_TIMEOUT,
            )
            apply_socket_options(rw.transport, self._buffer_size)
        except Exception as exc:
            elapsed = time.monotonic() - t_connect
            self.stats.failed_connections += 1
            self._log(
                f"[{label}] MTProxy DC{dc}{media_tag} upstream connect failed "
                f"({elapsed:.1f}s): {type(exc).__name__}: {exc}"
            )
            self._record_route(
                dc=dc,
                is_media=is_media,
                route="внешний SOCKS5",
                status="ошибка",
                reason=self._route_error(exc),
            )
            return False

        elapsed = time.monotonic() - t_connect
        self._log(f"[{label}] MTProxy DC{dc}{media_tag} upstream connected ({elapsed:.1f}s)")
        self.stats.upstream_connections += 1
        self._record_route(dc=dc, is_media=is_media, route="внешний SOCKS5", status="OK")
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

        self._log(f"[{label}] DC{dc}{media_tag} TCP fallback -> {target_host}:{target_port}")
        t_connect = time.monotonic()
        try:
            rr, rw = await asyncio.wait_for(
                asyncio.open_connection(target_host, target_port),
                timeout=CONNECT_TIMEOUT,
            )
            apply_socket_options(rw.transport, self._buffer_size)
        except Exception as exc:
            elapsed = time.monotonic() - t_connect
            self.stats.failed_connections += 1
            self._log(f"[{label}] TCP fallback failed ({elapsed:.1f}s): {type(exc).__name__}")
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

        media_tag = " media" if is_media else ""
        self._log(
            f"[{label}] DC{dc}{media_tag} upstream proxy "
            f"-> {self._upstream.host}:{self._upstream.port}"
        )
        t_connect = time.monotonic()
        try:
            rr, rw = await socks5.connect_via_socks5(
                self._upstream.host,
                self._upstream.port,
                target_host,
                target_port,
                username=self._upstream.username,
                password=self._upstream.password,
                timeout=CONNECT_TIMEOUT,
            )
            apply_socket_options(rw.transport, self._buffer_size)
        except Exception as exc:
            elapsed = time.monotonic() - t_connect
            self.stats.failed_connections += 1
            self._log(
                f"[{label}] DC{dc}{media_tag} upstream connect failed "
                f"({elapsed:.1f}s): {type(exc).__name__}: {exc}"
            )
            self._record_route(
                dc=dc,
                is_media=is_media,
                route="внешний SOCKS5",
                status="ошибка",
                reason=self._route_error(exc),
            )
            return False

        elapsed = time.monotonic() - t_connect
        self._log(f"[{label}] DC{dc}{media_tag} upstream connected ({elapsed:.1f}s)")
        self.stats.upstream_connections += 1
        self._record_route(dc=dc, is_media=is_media, route="внешний SOCKS5", status="OK")
        # Forward the buffered init packet
        rw.write(init)
        await rw.drain()
        await self._relay_tcp(client_reader, client_writer, rr, rw, label, dc=dc)
        return True

    async def _relay_wss(
        self,
        client_reader: asyncio.StreamReader,
        client_writer: asyncio.StreamWriter,
        ws: RawWebSocket,
        splitter: Optional[_MsgSplitter],
        label: str,
        dc: int = 0,
    ) -> None:
        await relay_wss(
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
        )


def _is_domain(host: str) -> bool:
    """Check if host is a domain name (not an IP address)."""
    if ":" in host:
        return False  # IPv6 address
    return not all(c.isdigit() or c == "." for c in host)
