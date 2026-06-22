from __future__ import annotations

import asyncio
import base64
import os
import socket as _socket
import ssl
import struct
from typing import Optional


_ssl_ctx = ssl.create_default_context()
_ssl_ctx.check_hostname = False
_ssl_ctx.verify_mode = ssl.CERT_NONE


class WsHandshakeError(Exception):
    """WebSocket HTTP upgrade failed."""

    def __init__(self, status_code: int, status_line: str, headers: dict = None, location: str = None):
        self.status_code = status_code
        self.status_line = status_line
        self.headers = headers or {}
        self.location = location
        super().__init__(f"HTTP {status_code}: {status_line}")

    @property
    def is_redirect(self) -> bool:
        return self.status_code in (301, 302, 303, 307, 308)


def apply_socket_options(transport, buffer_size: int = 256 * 1024) -> None:
    sock = transport.get_extra_info("socket") if transport is not None else None
    if sock is None:
        return
    try:
        sock.setsockopt(_socket.IPPROTO_TCP, _socket.TCP_NODELAY, 1)
    except (OSError, AttributeError):
        pass
    try:
        size = max(4 * 1024, int(buffer_size))
        sock.setsockopt(_socket.SOL_SOCKET, _socket.SO_RCVBUF, size)
        sock.setsockopt(_socket.SOL_SOCKET, _socket.SO_SNDBUF, size)
    except (OSError, AttributeError, TypeError, ValueError):
        pass


def _xor_mask(data: bytes, mask: bytes) -> bytes:
    """XOR data with a 4-byte WebSocket mask key."""
    if not data:
        return data
    n = len(data)
    mask_rep = (mask * (n // 4 + 1))[:n]
    return (int.from_bytes(data, "big") ^ int.from_bytes(mask_rep, "big")).to_bytes(n, "big")


class RawWebSocket:
    """Lightweight WebSocket client over asyncio reader/writer."""

    OP_TEXT = 0x1
    OP_BINARY = 0x2
    OP_CLOSE = 0x8
    OP_PING = 0x9
    OP_PONG = 0xA

    def __init__(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        *,
        domain: str = "",
        path: str = "/apiws",
    ):
        self.reader = reader
        self.writer = writer
        self.domain = str(domain or "")
        self.path = str(path or "")
        self._closed = False

    @staticmethod
    async def connect(
        ip: str,
        domain: str,
        path: str = "/apiws",
        timeout: float = 10.0,
        buffer_size: int = 256 * 1024,
    ) -> "RawWebSocket":
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(ip, 443, ssl=_ssl_ctx, server_hostname=domain),
            timeout=min(timeout, 10),
        )

        apply_socket_options(writer.transport, buffer_size)

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

        response_lines: list[str] = []
        try:
            while True:
                line = await asyncio.wait_for(reader.readline(), timeout=timeout)
                if line in (b"\r\n", b"\n", b""):
                    break
                response_lines.append(line.decode("utf-8", errors="replace").strip())
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
            return RawWebSocket(reader, writer, domain=domain, path=path)

        headers: dict[str, str] = {}
        for hl in response_lines[1:]:
            if ":" in hl:
                k, v = hl.split(":", 1)
                headers[k.strip().lower()] = v.strip()

        writer.close()
        raise WsHandshakeError(status_code, first_line, headers, location=headers.get("location"))

    async def send(self, data: bytes) -> None:
        if self._closed:
            raise ConnectionError("WebSocket closed")
        frame = self._build_frame(self.OP_BINARY, data, mask=True)
        self.writer.write(frame)
        await self.writer.drain()

    async def send_batch(self, parts: list[bytes]) -> None:
        if self._closed:
            raise ConnectionError("WebSocket closed")
        for part in parts:
            frame = self._build_frame(self.OP_BINARY, part, mask=True)
            self.writer.write(frame)
        await self.writer.drain()

    async def recv(self) -> Optional[bytes]:
        while not self._closed:
            opcode, payload = await self._read_frame()

            if opcode == self.OP_CLOSE:
                self._closed = True
                try:
                    reply = self._build_frame(self.OP_CLOSE, payload[:2] if payload else b"", mask=True)
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

            continue

        return None

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            self.writer.write(self._build_frame(self.OP_CLOSE, b"", mask=True))
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
        header.append(0x80 | opcode)
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
            length = struct.unpack(">H", await self.reader.readexactly(2))[0]
        elif length == 127:
            length = struct.unpack(">Q", await self.reader.readexactly(8))[0]

        if is_masked:
            mask_key = await self.reader.readexactly(4)
            payload = await self.reader.readexactly(length)
            return opcode, _xor_mask(payload, mask_key)

        payload = await self.reader.readexactly(length)
        return opcode, payload


__all__ = ["RawWebSocket", "WsHandshakeError"]
