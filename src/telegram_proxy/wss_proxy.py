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
import base64
import logging
import os
import socket as _socket
import ssl
import struct
import time
from dataclasses import dataclass, field
from typing import Optional, Callable

from telegram_proxy.dc_map import (
    ip_to_dc,
    ip_to_dc_media,
    dc_to_tcp_endpoint,
    is_telegram_ip,
    ws_domains_for_dc,
    # transparent_port_to_dc,  # Transparent mode removed (WinDivert loopback limitation)
    IP_TO_DC,
    WSS_DOMAINS,
    WSS_RELAY_IP,
    WSS_RELAY_IPS,
    WSS_PATH,
    # TRANSPARENT_PORT_BASE,  # Transparent mode removed
)
from telegram_proxy import socks5

log = logging.getLogger("tg_proxy")

# Buffer size for relay (128 KB)
RELAY_BUFFER = 131072

# WebSocket / TCP connect timeout
CONNECT_TIMEOUT = 10.0

# Max retry attempts for WSS connection per domain
MAX_RETRIES = 1

# WebSocket connection pool settings
_WS_POOL_SIZE = 4        # connections per (dc, is_media) key
_WS_POOL_MAX_AGE = 120.0  # seconds before evicting idle connections

# DC fail cooldown (seconds)
DC_FAIL_COOLDOWN = 10.0

# How long to wait for first server response before declaring DC blocked
_RECV_ZERO_TIMEOUT = 8.0

# Max concurrent WSS handshakes — prevents TLS flood that kills the network
_MAX_CONCURRENT_WSS = 4
_wss_semaphore: Optional[asyncio.Semaphore] = None


def _get_wss_semaphore() -> asyncio.Semaphore:
    """Lazy-init semaphore (must be created inside an event loop)."""
    global _wss_semaphore
    if _wss_semaphore is None:
        _wss_semaphore = asyncio.Semaphore(_MAX_CONCURRENT_WSS)
    return _wss_semaphore

# SSL context: no hostname verification (we connect to IP, not hostname)
_ssl_ctx = ssl.create_default_context()
_ssl_ctx.check_hostname = False
_ssl_ctx.verify_mode = ssl.CERT_NONE


# ---- Raw WebSocket client ----
# We cannot use the `websockets` library because:
# 1. It resolves DNS for the URI hostname -- we need to connect to a specific IP
# 2. In v16+ it has proxy auto-detection that causes loops
# 3. We need binary subprotocol negotiation
# Instead, we implement a minimal WebSocket client that connects directly
# to a target IP via TCP+TLS with a chosen SNI hostname.


class WsHandshakeError(Exception):
    """WebSocket HTTP upgrade failed."""
    def __init__(self, status_code: int, status_line: str,
                 headers: dict = None, location: str = None):
        self.status_code = status_code
        self.status_line = status_line
        self.headers = headers or {}
        self.location = location
        super().__init__(f"HTTP {status_code}: {status_line}")

    @property
    def is_redirect(self) -> bool:
        return self.status_code in (301, 302, 303, 307, 308)


def _xor_mask(data: bytes, mask: bytes) -> bytes:
    """XOR data with a 4-byte WebSocket mask key."""
    if not data:
        return data
    n = len(data)
    mask_rep = (mask * (n // 4 + 1))[:n]
    return (int.from_bytes(data, "big") ^ int.from_bytes(mask_rep, "big")).to_bytes(n, "big")


class RawWebSocket:
    """Lightweight WebSocket client over asyncio reader/writer.

    Connects DIRECTLY to a target IP via TCP+TLS (bypassing DNS),
    performs the HTTP Upgrade handshake with the correct Host/SNI,
    and provides send/recv for binary frames with proper masking.
    """

    OP_TEXT = 0x1
    OP_BINARY = 0x2
    OP_CLOSE = 0x8
    OP_PING = 0x9
    OP_PONG = 0xA

    def __init__(self, reader: asyncio.StreamReader,
                 writer: asyncio.StreamWriter):
        self.reader = reader
        self.writer = writer
        self._closed = False

    @staticmethod
    async def connect(ip: str, domain: str, path: str = "/apiws",
                      timeout: float = 10.0) -> "RawWebSocket":
        """Connect via TLS to the given IP with SNI=domain,
        perform WebSocket upgrade, return a RawWebSocket.

        Raises WsHandshakeError on non-101 response.
        """
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(
                ip, 443, ssl=_ssl_ctx, server_hostname=domain,
            ),
            timeout=min(timeout, 10),
        )

        # Set TCP_NODELAY for lower latency
        sock = writer.transport.get_extra_info("socket")
        if sock is not None:
            try:
                sock.setsockopt(_socket.IPPROTO_TCP, _socket.TCP_NODELAY, 1)
            except (OSError, AttributeError):
                pass

        ws_key = base64.b64encode(os.urandom(16)).decode()
        req = (
            f"GET {path} HTTP/1.1\r\n"
            f"Host: {domain}\r\n"
            f"Upgrade: websocket\r\n"
            f"Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {ws_key}\r\n"
            f"Sec-WebSocket-Version: 13\r\n"
            f"Sec-WebSocket-Protocol: binary\r\n"
            f"Origin: https://web.telegram.org\r\n"
            f"User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            f"AppleWebKit/537.36 (KHTML, like Gecko) "
            f"Chrome/131.0.0.0 Safari/537.36\r\n"
            f"\r\n"
        )
        writer.write(req.encode())
        await writer.drain()

        # Read HTTP response line by line
        response_lines: list[str] = []
        try:
            while True:
                line = await asyncio.wait_for(
                    reader.readline(), timeout=timeout,
                )
                if line in (b"\r\n", b"\n", b""):
                    break
                response_lines.append(
                    line.decode("utf-8", errors="replace").strip())
        except asyncio.TimeoutError:
            writer.close()
            raise

        if not response_lines:
            writer.close()
            raise WsHandshakeError(0, "empty response")

        first_line = response_lines[0]
        parts = first_line.split(" ", 2)
        try:
            status_code = int(parts[1]) if len(parts) >= 2 else 0
        except ValueError:
            status_code = 0

        if status_code == 101:
            return RawWebSocket(reader, writer)

        # Parse response headers for error reporting
        headers: dict[str, str] = {}
        for hl in response_lines[1:]:
            if ":" in hl:
                k, v = hl.split(":", 1)
                headers[k.strip().lower()] = v.strip()

        writer.close()
        raise WsHandshakeError(
            status_code, first_line, headers,
            location=headers.get("location"),
        )

    async def send(self, data: bytes) -> None:
        """Send a masked binary WebSocket frame."""
        if self._closed:
            raise ConnectionError("WebSocket closed")
        frame = self._build_frame(self.OP_BINARY, data, mask=True)
        self.writer.write(frame)
        await self.writer.drain()

    async def send_batch(self, parts: list[bytes]) -> None:
        """Send multiple binary frames with a single drain."""
        if self._closed:
            raise ConnectionError("WebSocket closed")
        for part in parts:
            frame = self._build_frame(self.OP_BINARY, part, mask=True)
            self.writer.write(frame)
        await self.writer.drain()

    async def recv(self) -> Optional[bytes]:
        """Receive the next data frame. Handles ping/pong/close internally.

        Returns payload bytes, or None on clean close.
        """
        while not self._closed:
            opcode, payload = await self._read_frame()

            if opcode == self.OP_CLOSE:
                self._closed = True
                try:
                    reply = self._build_frame(
                        self.OP_CLOSE,
                        payload[:2] if payload else b"",
                        mask=True,
                    )
                    self.writer.write(reply)
                    await self.writer.drain()
                except Exception:
                    pass
                return None

            if opcode == self.OP_PING:
                try:
                    pong = self._build_frame(self.OP_PONG, payload, mask=True)
                    self.writer.write(pong)
                    await self.writer.drain()
                except Exception:
                    pass
                continue

            if opcode == self.OP_PONG:
                continue

            if opcode in (self.OP_TEXT, self.OP_BINARY):
                return payload

            continue  # Unknown opcode -- skip

        return None

    async def close(self) -> None:
        """Send close frame and shut down the transport."""
        if self._closed:
            return
        self._closed = True
        try:
            self.writer.write(
                self._build_frame(self.OP_CLOSE, b"", mask=True))
            await self.writer.drain()
        except Exception:
            pass
        try:
            self.writer.close()
            await self.writer.wait_closed()
        except Exception:
            pass

    @staticmethod
    def _build_frame(opcode: int, data: bytes, mask: bool = False) -> bytes:
        header = bytearray()
        header.append(0x80 | opcode)  # FIN=1 + opcode
        length = len(data)
        mask_bit = 0x80 if mask else 0x00

        if length < 126:
            header.append(mask_bit | length)
        elif length < 65536:
            header.append(mask_bit | 126)
            header.extend(struct.pack(">H", length))
        else:
            header.append(mask_bit | 127)
            header.extend(struct.pack(">Q", length))

        if mask:
            mask_key = os.urandom(4)
            header.extend(mask_key)
            return bytes(header) + _xor_mask(data, mask_key)
        return bytes(header) + data

    async def _read_frame(self) -> tuple[int, bytes]:
        hdr = await self.reader.readexactly(2)
        opcode = hdr[0] & 0x0F
        is_masked = bool(hdr[1] & 0x80)
        length = hdr[1] & 0x7F

        if length == 126:
            length = struct.unpack(">H",
                                   await self.reader.readexactly(2))[0]
        elif length == 127:
            length = struct.unpack(">Q",
                                   await self.reader.readexactly(8))[0]

        if is_masked:
            mask_key = await self.reader.readexactly(4)
            payload = await self.reader.readexactly(length)
            return opcode, _xor_mask(payload, mask_key)

        payload = await self.reader.readexactly(length)
        return opcode, payload


# ---- MTProto init packet parsing ----


def _dc_from_init(data: bytes) -> tuple[Optional[int], bool]:
    """Extract DC id from the 64-byte MTProto obfuscation init packet.

    The init packet structure:
    - bytes 0-7: random padding
    - bytes 8-39: AES-CTR encryption key (32 bytes)
    - bytes 40-55: AES-CTR IV (16 bytes)
    - bytes 56-63: encrypted payload containing protocol + dc_id

    We derive the AES-CTR keystream and decrypt bytes 56-63 to read:
    - bytes 0-3 of decrypted: protocol id (0xEFEFEFEF, 0xEEEEEEEE, 0xDDDDDDDD)
    - bytes 4-5 of decrypted: dc_id (signed int16, negative = media DC)

    Returns (dc_id, is_media). dc_id is None if extraction fails.
    """
    if len(data) < 64:
        return None, False

    try:
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        key = bytes(data[8:40])
        iv = bytes(data[40:56])
        cipher = Cipher(algorithms.AES(key), modes.CTR(iv))
        encryptor = cipher.encryptor()
        keystream = encryptor.update(b"\x00" * 64) + encryptor.finalize()
        plain = bytes(a ^ b for a, b in zip(data[56:64], keystream[56:64]))

        proto = struct.unpack("<I", plain[0:4])[0]
        dc_raw = struct.unpack("<h", plain[4:6])[0]

        log.debug("dc_from_init: proto=0x%08X dc_raw=%d", proto, dc_raw)

        if proto in (0xEFEFEFEF, 0xEEEEEEEE, 0xDDDDDDDD):
            dc = abs(dc_raw)
            if 1 <= dc <= 1000:
                return dc, (dc_raw < 0)
    except ImportError:
        log.warning("cryptography library not installed -- cannot parse MTProto init")
    except Exception as exc:
        log.debug("DC extraction failed: %s", exc)

    return None, False


def _patch_init_dc(data: bytes, dc: int) -> bytes:
    """Patch dc_id in the 64-byte MTProto init packet.

    Some clients (Android with useSecret=0) leave bytes 60-61 as random.
    The WS relay needs a valid dc_id to route correctly.
    """
    if len(data) < 64:
        return data
    try:
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        new_dc = struct.pack("<h", dc)
        key_raw = bytes(data[8:40])
        iv = bytes(data[40:56])
        cipher = Cipher(algorithms.AES(key_raw), modes.CTR(iv))
        enc = cipher.encryptor()
        ks = enc.update(b"\x00" * 64) + enc.finalize()
        patched = bytearray(data[:64])
        patched[60] = ks[60] ^ new_dc[0]
        patched[61] = ks[61] ^ new_dc[1]
        log.debug("init patched: dc_id -> %d", dc)
        if len(data) > 64:
            return bytes(patched) + data[64:]
        return bytes(patched)
    except Exception:
        return data


# ---- MTProto message splitter ----


class _MsgSplitter:
    """Splits client TCP data into individual MTProto abridged-protocol
    messages so each can be sent as a separate WebSocket frame.

    The Telegram WS relay processes one MTProto message per WS frame.
    Mobile clients batch multiple messages in a single TCP write (e.g.,
    msgs_ack + req_DH_params). If sent as one WS frame, the relay
    only processes the first message and the DH handshake never completes.

    IMPORTANT: buffers trailing incomplete messages. If a TCP chunk ends
    mid-message, the tail is prepended to the next chunk. Sending a
    partial message as a WS frame causes the relay to drop the connection.
    """

    def __init__(self, init_data: bytes):
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        key_raw = bytes(init_data[8:40])
        iv = bytes(init_data[40:56])
        cipher = Cipher(algorithms.AES(key_raw), modes.CTR(iv))
        self._dec = cipher.encryptor()
        self._dec.update(b"\x00" * 64)  # Skip the init packet itself

    def split(self, chunk: bytes) -> list[bytes]:
        """Find message boundaries, split into separate WS frames.

        If only 0 or 1 complete message found, returns [chunk] as-is.
        If multiple messages found, splits at boundaries.
        Trailing data (partial message) is appended to the LAST
        complete message frame — the relay handles this correctly.
        """
        plain = self._dec.update(chunk)
        boundaries: list[int] = []
        pos = 0
        while pos < len(plain):
            first = plain[pos]
            if first == 0x7F:
                if pos + 4 > len(plain):
                    break
                msg_len = (
                    struct.unpack_from("<I", plain, pos + 1)[0] & 0xFFFFFF
                ) * 4
                pos += 4
            else:
                msg_len = first * 4
                pos += 1
            if msg_len == 0 or pos + msg_len > len(plain):
                break
            pos += msg_len
            boundaries.append(pos)

        if len(boundaries) <= 1:
            return [chunk]

        # Multiple messages: split, trailing data goes with last frame
        parts: list[bytes] = []
        prev = 0
        for i, b in enumerate(boundaries):
            if i == len(boundaries) - 1:
                # Last boundary: include any trailing data
                parts.append(chunk[prev:])
            else:
                parts.append(chunk[prev:b])
            prev = b
        return parts


def _relay_ip_for_domain(domain: str) -> str:
    """Get the relay IP for a WSS domain, with fallback."""
    return WSS_RELAY_IPS.get(domain, WSS_RELAY_IP)


# ---- HTTP transport detection ----


def _is_http_transport(data: bytes) -> bool:
    """Check if data looks like HTTP (not MTProto)."""
    return (data[:5] == b"POST " or data[:4] == b"GET " or
            data[:5] == b"HEAD " or data[:8] == b"OPTIONS ")


# ---- Upstream proxy config ----


@dataclass
class UpstreamProxyConfig:
    """Configuration for an external SOCKS5 proxy used as last-resort fallback.

    Modes:
      - "fallback": route through upstream only when WSS+TCP both fail
      - "always":   route all traffic through upstream proxy
    """
    enabled: bool = False
    host: str = ""
    port: int = 0
    mode: str = "always"
    username: str = ""
    password: str = ""



# ---- Relay reachability check ----


def check_relay_reachable(
    relay_ip: str = "149.154.167.220",
    timeout: float = 5.0,
) -> dict:
    """Synchronous TCP+TLS check of WSS relay reachability.

    Called from UI diagnostics thread (ThreadPoolExecutor) — must be sync.
    Tests: TCP connect to relay_ip:443 → TLS handshake with SNI=kws2.web.telegram.org.

    Returns dict with keys:
        reachable (bool): True if TLS handshake succeeded
        error (str): error description on failure, empty on success
        ms (float): elapsed time in milliseconds
    """
    t0 = time.monotonic()
    try:
        sock = _socket.create_connection((relay_ip, 443), timeout=timeout)
        try:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            tls_sock = ctx.wrap_socket(sock, server_hostname="kws2.web.telegram.org")
            tls_sock.close()
        except Exception:
            sock.close()
            raise
        ms = (time.monotonic() - t0) * 1000
        return {"reachable": True, "error": "", "ms": round(ms, 1)}
    except _socket.timeout:
        ms = (time.monotonic() - t0) * 1000
        return {"reachable": False, "error": f"TCP timeout ({timeout}s)", "ms": round(ms, 1)}
    except ConnectionRefusedError:
        ms = (time.monotonic() - t0) * 1000
        return {"reachable": False, "error": "Connection refused", "ms": round(ms, 1)}
    except OSError as e:
        ms = (time.monotonic() - t0) * 1000
        return {"reachable": False, "error": f"Network error: {e}", "ms": round(ms, 1)}
    except Exception as e:
        ms = (time.monotonic() - t0) * 1000
        return {"reachable": False, "error": str(e), "ms": round(ms, 1)}


# ---- Stats ----


@dataclass
class ProxyStats:
    """Live proxy statistics."""
    total_connections: int = 0
    active_connections: int = 0
    bytes_sent: int = 0
    bytes_received: int = 0
    wss_connections: int = 0
    tcp_fallback_connections: int = 0
    failed_connections: int = 0
    pool_hits: int = 0
    pool_misses: int = 0
    passthrough_connections: int = 0
    upstream_connections: int = 0
    # Per-DC recv=0 counter (connection established but no data received)
    recv_zero_count: int = 0
    http_rejected: int = 0
    start_time: float = field(default_factory=time.monotonic)

    @property
    def uptime_seconds(self) -> float:
        return time.monotonic() - self.start_time


# ---- WebSocket connection pool ----


class _WsPool:
    """Pre-opened WebSocket connection pool.

    Maintains up to _WS_POOL_SIZE idle connections per (dc, is_media) key.
    When a connection is taken, a background refill task replenishes the pool.
    Stale (older than _WS_POOL_MAX_AGE) or closed connections are evicted on get().
    """

    def __init__(self, stats: ProxyStats):
        # {(dc, is_media): [(RawWebSocket, created_timestamp), ...]}
        self._idle: dict[tuple[int, bool], list[tuple[RawWebSocket, float]]] = {}
        self._refilling: set[tuple[int, bool]] = set()
        self._stats = stats

    async def get(
        self, dc: int, is_media: bool,
        target_ip: str, domains: list[str],
    ) -> Optional[RawWebSocket]:
        """Return a pooled WebSocket or None if pool is empty.

        Evicts stale/closed entries. Triggers background refill.
        """
        key = (dc, is_media)
        now = time.monotonic()

        bucket = self._idle.get(key, [])
        while bucket:
            ws, created = bucket.pop(0)
            age = now - created
            if age > _WS_POOL_MAX_AGE or ws._closed:
                asyncio.create_task(self._quiet_close(ws))
                continue
            self._stats.pool_hits += 1
            media_tag = "m" if is_media else ""
            log.debug("WS pool hit for DC%d%s (age=%.1fs, left=%d)",
                      dc, media_tag, age, len(bucket))
            self._schedule_refill(key, target_ip, domains)
            return ws

        self._stats.pool_misses += 1
        self._schedule_refill(key, target_ip, domains)
        return None

    def _schedule_refill(
        self, key: tuple[int, bool],
        target_ip: str, domains: list[str],
    ) -> None:
        """Start a background refill if one isn't already running for this key."""
        if key in self._refilling:
            return
        self._refilling.add(key)
        asyncio.create_task(self._refill(key, target_ip, domains))

    async def _refill(
        self, key: tuple[int, bool],
        target_ip: str, domains: list[str],
    ) -> None:
        """Open new WebSocket connections until the bucket is full."""
        dc, is_media = key
        try:
            bucket = self._idle.setdefault(key, [])
            needed = _WS_POOL_SIZE - len(bucket)
            if needed <= 0:
                return
            tasks = [
                asyncio.create_task(self._connect_one(target_ip, domains))
                for _ in range(needed)
            ]
            for t in tasks:
                try:
                    ws = await t
                    if ws is not None:
                        bucket.append((ws, time.monotonic()))
                except Exception:
                    pass
            media_tag = "m" if is_media else ""
            log.debug("WS pool refilled DC%d%s: %d ready",
                      dc, media_tag, len(bucket))
        finally:
            self._refilling.discard(key)

    @staticmethod
    async def _connect_one(
        target_ip: str, domains: list[str],
    ) -> Optional[RawWebSocket]:
        """Try to open one WebSocket connection, cycling through domains."""
        sem = _get_wss_semaphore()
        async with sem:
            for domain in domains:
                relay_ip = _relay_ip_for_domain(domain)
                try:
                    ws = await RawWebSocket.connect(
                        relay_ip, domain, WSS_PATH, timeout=8.0,
                    )
                    return ws
                except WsHandshakeError as exc:
                    if exc.is_redirect:
                        continue
                    return None
                except Exception:
                    return None
        return None

    @staticmethod
    async def _quiet_close(ws: RawWebSocket) -> None:
        """Close a WebSocket without raising."""
        try:
            await ws.close()
        except Exception:
            pass

    async def warmup(self) -> None:
        """Pre-fill pool for all DCs that have working WSS relays."""
        for dc, domain_list in WSS_DOMAINS.items():
            for is_media in (False, True):
                key = (dc, is_media)
                domains = ws_domains_for_dc(dc, is_media)
                self._schedule_refill(key, WSS_RELAY_IP, domains)
        log.info("WS pool warmup started for %d DC(s)", len(WSS_DOMAINS))

    async def close_all(self) -> None:
        """Close all idle pooled connections (for shutdown)."""
        for bucket in self._idle.values():
            for ws, _ in bucket:
                asyncio.create_task(self._quiet_close(ws))
        self._idle.clear()


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
    ):
        self._port = port
        self._mode = mode
        self._host = host
        self._on_log = on_log
        self._upstream = upstream_config or UpstreamProxyConfig()
        self._servers: list[asyncio.Server] = []
        self._tasks: set[asyncio.Task] = set()
        self._running = False
        self.stats = ProxyStats()
        self._ws_pool = _WsPool(self.stats)
        # WS blacklist: set of (dc, is_media) where ALL domains returned 302
        self._ws_blacklist: set[tuple[int, bool]] = set()
        # Cooldown for failed DCs: {(dc, is_media): fail_until_timestamp}
        self._dc_cooldown: dict[tuple[int, bool], float] = {}
        # DCs that should use upstream (learned from consecutive recv=0 failures)
        self._dc_upstream_required: set[int] = set()

    def _log(self, msg: str) -> None:
        log.info(msg)
        if self._on_log:
            try:
                self._on_log(msg)
            except Exception:
                pass

    @property
    def is_running(self) -> bool:
        return self._running

    async def start(self) -> None:
        """Start the proxy server(s)."""
        if self._running:
            return

        self.stats = ProxyStats()
        self._ws_pool = _WsPool(self.stats)
        # Reset semaphore for fresh event loop
        global _wss_semaphore
        _wss_semaphore = asyncio.Semaphore(_MAX_CONCURRENT_WSS)

        # NOTE: Transparent mode was removed. WinDivert cannot intercept
        # inbound loopback packets (kernel driver limitation), making Lua NAT
        # redirect impossible. Only SOCKS5 mode is supported.
        server = await asyncio.start_server(
            self._handle_socks5_client,
            self._host,
            self._port,
        )
        self._servers.append(server)

        for srv in self._servers:
            await srv.start_serving()

        # Mark running AFTER server is successfully bound and listening
        self._running = True
        self._log(f"SOCKS5 proxy started on {self._host}:{self._port}")

        # Pre-fill WebSocket connection pool (non-blocking)
        asyncio.create_task(self._ws_pool.warmup())

    async def stop(self) -> None:
        """Graceful shutdown."""
        if not self._running:
            return

        self._running = False
        self._log("Stopping proxy...")

        # Close all pooled WebSocket connections
        await self._ws_pool.close_all()

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
                self.stats.passthrough_connections += 1
                self._log(f"[{label}] HTTP transport -> direct TCP")
                try:
                    rr, rw = await asyncio.wait_for(
                        asyncio.open_connection(target_host, target_port),
                        timeout=CONNECT_TIMEOUT,
                    )
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
            if (self._upstream.enabled
                    and self._upstream.mode == "always"):
                self._log(f"[{label}] DC{dc} -> upstream (always mode)")
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

        sem = _get_wss_semaphore()
        for domain in domains if ws is None else []:
            relay_ip = _relay_ip_for_domain(domain)
            try:
                self._log(f"[{label}] DC{dc}{media_tag} -> wss://{domain}{WSS_PATH}")
                async with sem:
                    ws = await RawWebSocket.connect(
                        relay_ip, domain, WSS_PATH, timeout=CONNECT_TIMEOUT,
                    )
                all_redirects = False
                break
            except WsHandshakeError as exc:
                if exc.is_redirect:
                    any_redirect = True
                    log.warning("[%s] DC%d%s got %d from %s -> %s",
                                label, dc, media_tag, exc.status_code,
                                domain, exc.location or "?")
                    continue
                else:
                    all_redirects = False
                    log.warning("[%s] DC%d%s WS handshake: %s",
                                label, dc, media_tag, exc.status_line)
            except Exception as exc:
                all_redirects = False
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

            # "always" mode: skip TCP fallback, go straight to upstream
            if (self._upstream.enabled
                    and self._upstream.mode == "always"):
                await self._upstream_proxy_connect(
                    client_reader, client_writer, target_host, target_port,
                    init, label, dc, is_media,
                )
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
        await self._relay_wss(client_reader, client_writer, ws, splitter, label)

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
        if (dc in self._dc_upstream_required
                and self._upstream.enabled
                and self._upstream.mode == "fallback"):
            self._log(f"[{label}] DC{dc}{media_tag} learned-blocked -> upstream proxy")
            ok = await self._upstream_proxy_connect(
                client_reader, client_writer,
                target_host, target_port, init, label, dc, is_media,
            )
            if not ok:
                self._dc_upstream_required.discard(dc)
                self._log(f"[{label}] DC{dc} upstream failed, unmarked for re-probe")
            return

        self._log(f"[{label}] DC{dc}{media_tag} TCP fallback -> {target_host}:{target_port}")
        t_connect = time.monotonic()
        try:
            rr, rw = await asyncio.wait_for(
                asyncio.open_connection(target_host, target_port),
                timeout=CONNECT_TIMEOUT,
            )
        except Exception as exc:
            elapsed = time.monotonic() - t_connect
            self.stats.failed_connections += 1
            self._log(f"[{label}] TCP fallback failed ({elapsed:.1f}s): {type(exc).__name__}")
            # TCP connect failed — try upstream if available
            if self._upstream.enabled:
                self._dc_upstream_required.add(dc)
                self._log(f"[{label}] DC{dc}{media_tag} TCP failed -> trying upstream")
                await self._upstream_proxy_connect(
                    client_reader, client_writer,
                    target_host, target_port, init, label, dc, is_media,
                )
            return

        elapsed = time.monotonic() - t_connect
        self._log(f"[{label}] DC{dc}{media_tag} TCP connected ({elapsed:.1f}s)")
        self.stats.tcp_fallback_connections += 1
        # Forward the buffered init packet
        rw.write(init)
        await rw.drain()
        recv_total, watchdog_fired = await self._relay_tcp(
            client_reader, client_writer, rr, rw, label,
            recv_zero_timeout=_RECV_ZERO_TIMEOUT,
        )

        # Learn from watchdog timeout: server silence = DC is blocked by DPI.
        # Only mark on watchdog — client disconnect with recv=0 is NOT blocking evidence.
        if watchdog_fired and recv_total == 0 and self._upstream.enabled:
            self._dc_upstream_required.add(dc)
            self._log(f"[{label}] DC{dc} recv=0 (watchdog) -> marked for upstream routing")

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
        except Exception as exc:
            elapsed = time.monotonic() - t_connect
            self.stats.failed_connections += 1
            self._log(
                f"[{label}] DC{dc}{media_tag} upstream connect failed "
                f"({elapsed:.1f}s): {type(exc).__name__}: {exc}"
            )
            return False

        elapsed = time.monotonic() - t_connect
        self._log(f"[{label}] DC{dc}{media_tag} upstream connected ({elapsed:.1f}s)")
        self.stats.upstream_connections += 1
        # Forward the buffered init packet
        rw.write(init)
        await rw.drain()
        await self._relay_tcp(client_reader, client_writer, rr, rw, label)
        return True

    async def _relay_wss(
        self,
        client_reader: asyncio.StreamReader,
        client_writer: asyncio.StreamWriter,
        ws: RawWebSocket,
        splitter: Optional[_MsgSplitter],
        label: str,
    ) -> None:
        """Bidirectional relay between TCP client and WebSocket."""
        t0 = time.monotonic()
        sent_total = 0
        recv_total = 0

        async def tcp_to_ws():
            nonlocal sent_total
            try:
                while True:
                    data = await client_reader.read(RELAY_BUFFER)
                    if not data:
                        break
                    sent_total += len(data)
                    self.stats.bytes_sent += len(data)
                    if splitter:
                        parts = splitter.split(data)
                        if not parts:
                            continue  # All data buffered, no complete messages yet
                        if len(parts) > 1:
                            await ws.send_batch(parts)
                        else:
                            await ws.send(parts[0])
                    else:
                        await ws.send(data)
            except (asyncio.CancelledError, ConnectionError, OSError):
                pass
            except Exception as e:
                self._log(f"[{label}] tcp->ws error: {type(e).__name__}: {e}")

        async def ws_to_tcp():
            nonlocal recv_total
            try:
                while True:
                    data = await ws.recv()
                    if data is None:
                        self._log(f"[{label}] WS closed by server (recv_total={recv_total})")
                        break
                    recv_total += len(data)
                    self.stats.bytes_received += len(data)
                    client_writer.write(data)
                    # Only drain when kernel buffer is filling up (matches reference)
                    buf = client_writer.transport.get_write_buffer_size()
                    if buf > RELAY_BUFFER:
                        await client_writer.drain()
            except (asyncio.CancelledError, ConnectionError, OSError):
                pass
            except Exception as e:
                self._log(f"[{label}] ws->tcp error: {type(e).__name__}: {e}")

        tasks = [asyncio.create_task(tcp_to_ws()),
                 asyncio.create_task(ws_to_tcp())]
        try:
            await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        finally:
            for t in tasks:
                t.cancel()
            for t in tasks:
                try:
                    await t
                except BaseException:
                    pass
            try:
                await ws.close()
            except BaseException:
                pass
            elapsed = time.monotonic() - t0
            if recv_total == 0 and sent_total > 0:
                self.stats.recv_zero_count += 1
            self._log(f"[{label}] relay done: sent={sent_total} recv={recv_total} ({elapsed:.1f}s)")

    async def _relay_tcp(
        self,
        client_reader: asyncio.StreamReader,
        client_writer: asyncio.StreamWriter,
        remote_reader: asyncio.StreamReader,
        remote_writer: asyncio.StreamWriter,
        label: str = "",
        recv_zero_timeout: float = 0,
    ) -> tuple[int, bool]:
        """Bidirectional TCP relay (fallback or passthrough).

        Returns (recv_total, watchdog_fired):
            recv_total: bytes received from remote
            watchdog_fired: True if relay ended due to recv=0 watchdog timeout
        """
        t0 = time.monotonic()
        sent_total = 0
        recv_total = 0
        watchdog_fired = False

        async def forward(src: asyncio.StreamReader, dst: asyncio.StreamWriter, is_upload: bool):
            nonlocal sent_total, recv_total
            try:
                while True:
                    data = await src.read(RELAY_BUFFER)
                    if not data:
                        break
                    dst.write(data)
                    await dst.drain()
                    if is_upload:
                        sent_total += len(data)
                        self.stats.bytes_sent += len(data)
                    else:
                        recv_total += len(data)
                        self.stats.bytes_received += len(data)
            except (asyncio.CancelledError, ConnectionError, OSError):
                pass

        task_c2r = asyncio.create_task(forward(client_reader, remote_writer, True))
        task_r2c = asyncio.create_task(forward(remote_reader, client_writer, False))
        all_tasks = {task_c2r, task_r2c}
        watchdog_task = None

        if recv_zero_timeout > 0:
            async def _recv_watchdog():
                await asyncio.sleep(recv_zero_timeout)
                if recv_total == 0:
                    return  # Completes task -> triggers FIRST_COMPLETED
                # Data flowing — wait until relay ends naturally
                try:
                    await asyncio.Event().wait()
                except asyncio.CancelledError:
                    pass
            watchdog_task = asyncio.create_task(_recv_watchdog())
            all_tasks.add(watchdog_task)

        try:
            done, _pending = await asyncio.wait(
                all_tasks,
                return_when=asyncio.FIRST_COMPLETED,
            )
            # Check if watchdog was the task that completed (= server silence)
            if watchdog_task is not None and watchdog_task in done:
                watchdog_fired = True
        finally:
            for t in all_tasks:
                t.cancel()
            for t in all_tasks:
                try:
                    await t
                except BaseException:
                    pass
            try:
                remote_writer.close()
                await remote_writer.wait_closed()
            except Exception:
                pass
            if label:
                elapsed = time.monotonic() - t0
                if recv_total == 0 and sent_total > 0:
                    self.stats.recv_zero_count += 1
                tag = " [watchdog]" if watchdog_fired else ""
                self._log(f"[{label}] tcp relay done: sent={sent_total} recv={recv_total} ({elapsed:.1f}s){tag}")
        return recv_total, watchdog_fired


def _is_domain(host: str) -> bool:
    """Check if host is a domain name (not an IP address)."""
    if ":" in host:
        return False  # IPv6 address
    return not all(c.isdigit() or c == "." for c in host)
