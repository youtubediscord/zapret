from __future__ import annotations

import asyncio
import hashlib
import os
import secrets
import struct
import time
from collections.abc import Callable
from dataclasses import dataclass
from urllib.parse import urlencode

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from telegram_proxy.proxy.stats import ProxyStats
from telegram_proxy.proxy.transport import RawWebSocket
from telegram_proxy.proxy.fake_tls import build_fake_tls_secret


HANDSHAKE_LEN = 64
SKIP_LEN = 8
PREKEY_LEN = 32
IV_LEN = 16
PROTO_TAG_POS = 56
DC_IDX_POS = 60

PROTO_TAG_ABRIDGED = b"\xef\xef\xef\xef"
PROTO_TAG_INTERMEDIATE = b"\xee\xee\xee\xee"
PROTO_TAG_SECURE = b"\xdd\xdd\xdd\xdd"
VALID_PROTO_TAGS = frozenset({PROTO_TAG_ABRIDGED, PROTO_TAG_INTERMEDIATE, PROTO_TAG_SECURE})
ZERO_64 = b"\x00" * 64
RELAY_BUFFER = 131072


@dataclass(frozen=True, slots=True)
class MTProxyClientInit:
    dc: int
    is_media: bool
    proto_tag: bytes
    client_prekey_iv: bytes


@dataclass(slots=True)
class MTProxyCryptoContext:
    client_decryptor: object
    client_encryptor: object
    telegram_encryptor: object
    telegram_decryptor: object

    def client_to_telegram(self, data: bytes) -> bytes:
        plain = self.client_decryptor.update(bytes(data or b""))
        return self.telegram_encryptor.update(plain)

    def telegram_to_client(self, data: bytes) -> bytes:
        plain = self.telegram_decryptor.update(bytes(data or b""))
        return self.client_encryptor.update(plain)


class MTProxyMsgSplitter:
    """Делит MTProxy-поток на отдельные MTProto-пакеты для WebSocket."""

    def __init__(self, relay_init: bytes, proto_tag: bytes):
        self._decryptor = _cipher(
            bytes(relay_init[SKIP_LEN:SKIP_LEN + PREKEY_LEN]),
            bytes(relay_init[SKIP_LEN + PREKEY_LEN:SKIP_LEN + PREKEY_LEN + IV_LEN]),
        )
        self._decryptor.update(ZERO_64)
        self._proto_tag = bytes(proto_tag or b"")
        self._cipher_buf = bytearray()
        self._plain_buf = bytearray()
        self._disabled = False

    def split(self, chunk: bytes) -> list[bytes]:
        if not chunk:
            return []
        if self._disabled:
            return [chunk]

        self._cipher_buf.extend(chunk)
        self._plain_buf.extend(self._decryptor.update(chunk))
        parts: list[bytes] = []
        offset = 0

        while offset < len(self._cipher_buf):
            packet_len = self._next_packet_len(offset, len(self._cipher_buf) - offset)
            if packet_len is None:
                break
            if packet_len <= 0:
                parts.append(bytes(self._cipher_buf[offset:]))
                offset = len(self._cipher_buf)
                self._disabled = True
                break
            parts.append(bytes(self._cipher_buf[offset:offset + packet_len]))
            offset += packet_len

        if offset:
            del self._cipher_buf[:offset]
            del self._plain_buf[:offset]
        return parts

    def flush(self) -> list[bytes]:
        if not self._cipher_buf:
            return []
        tail = bytes(self._cipher_buf)
        self._cipher_buf.clear()
        self._plain_buf.clear()
        return [tail]

    def _next_packet_len(self, offset: int, available: int) -> int | None:
        if available <= 0:
            return None
        if self._proto_tag == PROTO_TAG_ABRIDGED:
            return self._next_abridged_len(offset, available)
        if self._proto_tag in (PROTO_TAG_INTERMEDIATE, PROTO_TAG_SECURE):
            return self._next_intermediate_len(offset, available)
        return 0

    def _next_abridged_len(self, offset: int, available: int) -> int | None:
        first = self._plain_buf[offset]
        if first in (0x7F, 0xFF):
            if available < 4:
                return None
            payload_len = int.from_bytes(self._plain_buf[offset + 1:offset + 4], "little") * 4
            header_len = 4
        else:
            payload_len = (first & 0x7F) * 4
            header_len = 1
        if payload_len <= 0:
            return 0
        packet_len = header_len + payload_len
        if available < packet_len:
            return None
        return packet_len

    def _next_intermediate_len(self, offset: int, available: int) -> int | None:
        if available < 4:
            return None
        payload_len = struct.unpack_from("<I", self._plain_buf, offset)[0] & 0x7FFFFFFF
        if payload_len <= 0:
            return 0
        packet_len = 4 + payload_len
        if available < packet_len:
            return None
        return packet_len


def normalize_secret(value: object) -> str:
    text = str(value or "").strip().lower()
    if len(text) != 32:
        return ""
    if not all(ch in "0123456789abcdef" for ch in text):
        return ""
    return text


def generate_secret() -> str:
    return secrets.token_hex(16)


def build_mtproxy_link(host: str, port: int, secret: str, *, fake_tls_domain: str = "") -> str:
    normalized_secret = normalize_secret(secret)
    link_secret = f"dd{normalized_secret}"
    if fake_tls_domain:
        fake_tls_secret = build_fake_tls_secret(normalized_secret, fake_tls_domain)
        if fake_tls_secret.startswith("ee"):
            link_secret = fake_tls_secret
    query = urlencode(
        {
            "server": str(host or "127.0.0.1").strip() or "127.0.0.1",
            "port": str(int(port or 0)),
            "secret": link_secret,
        }
    )
    return f"tg://proxy?{query}"


def _cipher(key: bytes, iv: bytes):
    return Cipher(algorithms.AES(key), modes.CTR(iv)).encryptor()


def _keystream(key: bytes, iv: bytes, size: int = HANDSHAKE_LEN) -> bytes:
    return _cipher(key, iv).update(b"\x00" * int(size))


def generate_relay_init(proto_tag: bytes, dc: int, is_media: bool) -> bytes:
    if proto_tag not in VALID_PROTO_TAGS:
        proto_tag = PROTO_TAG_INTERMEDIATE

    dc_idx = -int(dc) if is_media else int(dc)
    while True:
        init = bytearray(os.urandom(HANDSHAKE_LEN))
        if init[0] == 0xEF:
            continue
        if bytes(init[:4]) in {b"HEAD", b"POST", b"GET ", PROTO_TAG_INTERMEDIATE, PROTO_TAG_SECURE}:
            continue
        if bytes(init[4:8]) == b"\x00\x00\x00\x00":
            continue
        break

    key = bytes(init[SKIP_LEN:SKIP_LEN + PREKEY_LEN])
    iv = bytes(init[SKIP_LEN + PREKEY_LEN:SKIP_LEN + PREKEY_LEN + IV_LEN])
    tail_plain = bytes(proto_tag) + struct.pack("<h", dc_idx) + os.urandom(2)
    tail_cipher = bytes(a ^ b for a, b in zip(tail_plain, _keystream(key, iv)[PROTO_TAG_POS:HANDSHAKE_LEN]))
    init[PROTO_TAG_POS:HANDSHAKE_LEN] = tail_cipher
    return bytes(init)


def build_crypto_context(
    client_prekey_iv: bytes,
    secret: str,
    relay_init: bytes,
) -> MTProxyCryptoContext:
    normalized_secret = normalize_secret(secret)
    if not normalized_secret:
        raise ValueError("MTProxy secret must be 32 hex characters")

    secret_bytes = bytes.fromhex(normalized_secret)
    client_prekey_iv = bytes(client_prekey_iv)
    client_prekey = client_prekey_iv[:PREKEY_LEN]
    client_iv = client_prekey_iv[PREKEY_LEN:PREKEY_LEN + IV_LEN]
    client_decryptor = _cipher(hashlib.sha256(client_prekey + secret_bytes).digest(), client_iv)
    client_decryptor.update(ZERO_64)

    reverse_client = client_prekey_iv[::-1]
    client_encryptor = _cipher(
        hashlib.sha256(reverse_client[:PREKEY_LEN] + secret_bytes).digest(),
        reverse_client[PREKEY_LEN:PREKEY_LEN + IV_LEN],
    )

    relay_prekey_iv = bytes(relay_init[SKIP_LEN:SKIP_LEN + PREKEY_LEN + IV_LEN])
    telegram_encryptor = _cipher(
        relay_prekey_iv[:PREKEY_LEN],
        relay_prekey_iv[PREKEY_LEN:PREKEY_LEN + IV_LEN],
    )
    telegram_encryptor.update(ZERO_64)

    reverse_relay = relay_prekey_iv[::-1]
    telegram_decryptor = _cipher(
        reverse_relay[:PREKEY_LEN],
        reverse_relay[PREKEY_LEN:PREKEY_LEN + IV_LEN],
    )

    return MTProxyCryptoContext(
        client_decryptor=client_decryptor,
        client_encryptor=client_encryptor,
        telegram_encryptor=telegram_encryptor,
        telegram_decryptor=telegram_decryptor,
    )


def parse_client_init(init: bytes, secret: str) -> MTProxyClientInit | None:
    normalized_secret = normalize_secret(secret)
    if len(init or b"") < HANDSHAKE_LEN or not normalized_secret:
        return None

    secret_bytes = bytes.fromhex(normalized_secret)
    client_prekey_iv = bytes(init[SKIP_LEN:SKIP_LEN + PREKEY_LEN + IV_LEN])
    prekey = client_prekey_iv[:PREKEY_LEN]
    iv = client_prekey_iv[PREKEY_LEN:]
    key = hashlib.sha256(prekey + secret_bytes).digest()

    cipher = Cipher(algorithms.AES(key), modes.CTR(iv))
    decrypted = cipher.encryptor().update(bytes(init[:HANDSHAKE_LEN]))

    proto_tag = decrypted[PROTO_TAG_POS:PROTO_TAG_POS + 4]
    if proto_tag not in VALID_PROTO_TAGS:
        return None

    dc_idx = struct.unpack("<h", decrypted[DC_IDX_POS:DC_IDX_POS + 2])[0]
    dc = abs(dc_idx)
    if dc <= 0:
        return None

    return MTProxyClientInit(
        dc=dc,
        is_media=dc_idx < 0,
        proto_tag=proto_tag,
        client_prekey_iv=client_prekey_iv,
    )


async def relay_mtproxy_wss(
    *,
    client_reader: asyncio.StreamReader,
    client_writer: asyncio.StreamWriter,
    ws: RawWebSocket,
    crypto: MTProxyCryptoContext,
    stats: ProxyStats,
    log_fn: Callable[[str], None],
    label: str,
    dc: int = 0,
    splitter: MTProxyMsgSplitter | None = None,
) -> None:
    t0 = time.monotonic()
    sent_total = 0
    recv_total = 0

    async def tcp_to_ws() -> None:
        nonlocal sent_total
        try:
            while True:
                data = await client_reader.read(RELAY_BUFFER)
                if not data:
                    break
                sent_total += len(data)
                stats.bytes_sent += len(data)
                chunk = crypto.client_to_telegram(data)
                if splitter is None:
                    await ws.send(chunk)
                    continue
                parts = splitter.split(chunk)
                if not parts:
                    continue
                if len(parts) == 1:
                    await ws.send(parts[0])
                else:
                    await ws.send_batch(parts)
            if splitter is not None:
                tail = splitter.flush()
                if tail:
                    if len(tail) == 1:
                        await ws.send(tail[0])
                    else:
                        await ws.send_batch(tail)
        except (asyncio.CancelledError, ConnectionError, OSError):
            pass
        except Exception as exc:
            log_fn(f"[{label}] mtproxy tcp->ws error: {type(exc).__name__}: {exc}")

    async def ws_to_tcp() -> None:
        nonlocal recv_total
        try:
            while True:
                data = await ws.recv()
                if data is None:
                    break
                recv_total += len(data)
                stats.bytes_received += len(data)
                client_writer.write(crypto.telegram_to_client(data))
                await client_writer.drain()
        except (asyncio.CancelledError, ConnectionError, OSError):
            pass
        except Exception as exc:
            log_fn(f"[{label}] mtproxy ws->tcp error: {type(exc).__name__}: {exc}")

    tasks = [asyncio.create_task(tcp_to_ws()), asyncio.create_task(ws_to_tcp())]
    try:
        await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    finally:
        for task in tasks:
            task.cancel()
        for task in tasks:
            try:
                await task
            except BaseException:
                pass
        try:
            await ws.close()
        except BaseException:
            pass
        elapsed = time.monotonic() - t0
        log_fn(f"[{label}] mtproxy relay done: sent={sent_total} recv={recv_total} ({elapsed:.1f}s)")


async def relay_mtproxy_tcp(
    *,
    client_reader: asyncio.StreamReader,
    client_writer: asyncio.StreamWriter,
    remote_reader: asyncio.StreamReader,
    remote_writer: asyncio.StreamWriter,
    crypto: MTProxyCryptoContext,
    stats: ProxyStats,
    log_fn: Callable[[str], None],
    label: str,
    dc: int = 0,
    on_first_response: Callable[[], None] | None = None,
) -> tuple[int, int]:
    t0 = time.monotonic()
    sent_total = 0
    recv_total = 0

    async def forward_client_to_remote() -> None:
        nonlocal sent_total
        try:
            while True:
                data = await client_reader.read(RELAY_BUFFER)
                if not data:
                    break
                sent_total += len(data)
                stats.bytes_sent += len(data)
                remote_writer.write(crypto.client_to_telegram(data))
                await remote_writer.drain()
        except (asyncio.CancelledError, ConnectionError, OSError):
            pass

    async def forward_remote_to_client() -> None:
        nonlocal recv_total
        try:
            while True:
                data = await remote_reader.read(RELAY_BUFFER)
                if not data:
                    break
                first_response = recv_total == 0
                recv_total += len(data)
                stats.bytes_received += len(data)
                client_writer.write(crypto.telegram_to_client(data))
                await client_writer.drain()
                if first_response and on_first_response is not None:
                    try:
                        on_first_response()
                    except Exception:
                        pass
        except (asyncio.CancelledError, ConnectionError, OSError):
            pass

    tasks = [asyncio.create_task(forward_client_to_remote()), asyncio.create_task(forward_remote_to_client())]
    try:
        await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    finally:
        for task in tasks:
            task.cancel()
        for task in tasks:
            try:
                await task
            except BaseException:
                pass
        for writer in (client_writer, remote_writer):
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass
        elapsed = time.monotonic() - t0
        if recv_total == 0 and sent_total > 0:
            stats.recv_zero_count += 1
            if dc > 0:
                stats.recv_zero_per_dc[dc] = stats.recv_zero_per_dc.get(dc, 0) + 1
        log_fn(f"[{label}] mtproxy tcp relay done: sent={sent_total} recv={recv_total} ({elapsed:.1f}s)")
    return recv_total, sent_total


__all__ = [
    "MTProxyClientInit",
    "MTProxyCryptoContext",
    "MTProxyMsgSplitter",
    "build_crypto_context",
    "build_mtproxy_link",
    "generate_secret",
    "generate_relay_init",
    "normalize_secret",
    "parse_client_init",
    "relay_mtproxy_tcp",
    "relay_mtproxy_wss",
]
