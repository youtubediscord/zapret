# telegram_proxy/socks5.py
"""Minimal SOCKS5 server implementation (RFC 1928).

Supports only what Telegram needs:
- No authentication (METHOD 0x00)
- CONNECT command (CMD 0x01)
- IPv4 (ATYP 0x01) and Domain (ATYP 0x03) address types
"""

import asyncio
import struct
import logging
import ssl
from ipaddress import IPv4Address, IPv6Address, ip_address
from typing import Optional

log = logging.getLogger("tg_proxy.socks5")

# SOCKS5 constants
SOCKS_VER = 0x05
AUTH_NONE = 0x00
AUTH_USERPASS = 0x02
CMD_CONNECT = 0x01
ATYP_IPV4 = 0x01
ATYP_DOMAIN = 0x03
ATYP_IPV6 = 0x04
REP_SUCCESS = 0x00
REP_GENERAL_FAILURE = 0x01
REP_CONN_REFUSED = 0x05
REP_CMD_NOT_SUPPORTED = 0x07
REP_ATYP_NOT_SUPPORTED = 0x08


class Socks5Error(Exception):
    """SOCKS5 protocol error."""


async def handshake(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
) -> Optional[tuple[str, int]]:
    """Perform SOCKS5 handshake. Returns (target_host, target_port) or None on error.

    Protocol flow:
    1. Client greeting -> Server method selection
    2. Client request (CONNECT) -> Server reply
    """
    try:
        return await _do_handshake(reader, writer)
    except (
        Socks5Error,
        asyncio.IncompleteReadError,
        asyncio.TimeoutError,
        ConnectionError,
        struct.error,
    ) as e:
        log.debug("SOCKS5 handshake failed: %s", e)
        return None
    except Exception:
        log.exception("Unexpected SOCKS5 error")
        return None


async def _do_handshake(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
) -> Optional[tuple[str, int]]:
    # --- Phase 1: Greeting ---
    header = await asyncio.wait_for(reader.readexactly(2), timeout=10.0)
    ver, nmethods = struct.unpack("!BB", header)
    if ver != SOCKS_VER:
        raise Socks5Error(f"Bad SOCKS version: {ver}")

    methods = await reader.readexactly(nmethods)
    if AUTH_NONE not in methods:
        # No acceptable auth method
        writer.write(struct.pack("!BB", SOCKS_VER, 0xFF))
        await writer.drain()
        raise Socks5Error("Client doesn't support no-auth")

    # Accept no-auth
    writer.write(struct.pack("!BB", SOCKS_VER, AUTH_NONE))
    await writer.drain()

    # --- Phase 2: Request ---
    req_header = await asyncio.wait_for(reader.readexactly(4), timeout=10.0)
    ver, cmd, _rsv, atyp = struct.unpack("!BBBB", req_header)

    if ver != SOCKS_VER:
        raise Socks5Error(f"Bad version in request: {ver}")

    if cmd != CMD_CONNECT:
        _send_reply(writer, REP_CMD_NOT_SUPPORTED)
        await writer.drain()
        raise Socks5Error(f"Unsupported command: {cmd}")

    # Parse target address
    if atyp == ATYP_IPV4:
        raw_addr = await reader.readexactly(4)
        target_host = ".".join(str(b) for b in raw_addr)
    elif atyp == ATYP_DOMAIN:
        domain_len = (await reader.readexactly(1))[0]
        domain = await reader.readexactly(domain_len)
        target_host = domain.decode("ascii", errors="replace")
    elif atyp == ATYP_IPV6:
        raw_addr = await reader.readexactly(16)
        # Format as standard IPv6 string
        parts = struct.unpack("!8H", raw_addr)
        target_host = ":".join(f"{p:x}" for p in parts)
    else:
        _send_reply(writer, REP_ATYP_NOT_SUPPORTED)
        await writer.drain()
        raise Socks5Error(f"Unknown ATYP: {atyp}")

    raw_port = await reader.readexactly(2)
    target_port = struct.unpack("!H", raw_port)[0]

    # Send success reply (bound address 0.0.0.0:0)
    _send_reply(writer, REP_SUCCESS)
    await writer.drain()

    return (target_host, target_port)


def _send_reply(writer: asyncio.StreamWriter, rep: int) -> None:
    """Send SOCKS5 reply with bound address 0.0.0.0:0."""
    writer.write(struct.pack(
        "!BBBBIH",
        SOCKS_VER,  # VER
        rep,        # REP
        0x00,       # RSV
        ATYP_IPV4,  # ATYP
        0,          # BND.ADDR (0.0.0.0)
        0,          # BND.PORT (0)
    ))


def send_failure(writer: asyncio.StreamWriter, rep: int = REP_GENERAL_FAILURE) -> None:
    """Send failure reply. For use after handshake if tunnel setup fails."""
    _send_reply(writer, rep)


# ---- SOCKS5 client (outbound connect through upstream proxy) ----


async def connect_via_socks5(
    proxy_host: str,
    proxy_port: int,
    target_host: str,
    target_port: int,
    username: str = "",
    password: str = "",
    timeout: float = 10.0,
    tls: bool = False,
    tls_server_name: str = "",
    tls_verify: bool = False,
) -> tuple[asyncio.StreamReader, asyncio.StreamWriter]:
    """Connect to target through a SOCKS5 proxy. Returns (reader, writer) to target.

    Supports IPv4, IPv6 and domain names as target_host.
    Supports no-auth (0x00) and username/password auth (0x02, RFC 1929).
    Raises Socks5Error on any SOCKS5 protocol failure.
    """
    ssl_context = None
    server_hostname = None
    if tls:
        ssl_context = ssl.create_default_context()
        if not tls_verify:
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
        server_hostname = str(tls_server_name or proxy_host or "").strip() or None

    reader, writer = await asyncio.wait_for(
        asyncio.open_connection(
            proxy_host,
            proxy_port,
            ssl=ssl_context,
            server_hostname=server_hostname,
        ),
        timeout=timeout,
    )

    try:
        # Phase 1: Greeting — offer available auth methods
        has_creds = bool(username)
        if has_creds:
            writer.write(struct.pack("!BBBB", SOCKS_VER, 2, AUTH_NONE, AUTH_USERPASS))
        else:
            writer.write(struct.pack("!BBB", SOCKS_VER, 1, AUTH_NONE))
        await writer.drain()

        reply = await asyncio.wait_for(reader.readexactly(2), timeout=timeout)
        ver, method = struct.unpack("!BB", reply)
        if ver != SOCKS_VER:
            raise Socks5Error(f"Upstream proxy bad SOCKS version: {ver}")

        if method == AUTH_USERPASS:
            if not has_creds:
                raise Socks5Error("Upstream proxy requires auth but no credentials provided")
            # RFC 1929: VER=1, ULEN, USERNAME, PLEN, PASSWORD
            uname = username.encode("utf-8")
            passwd = password.encode("utf-8")
            auth_req = struct.pack("!BB", 0x01, len(uname)) + uname
            auth_req += struct.pack("!B", len(passwd)) + passwd
            writer.write(auth_req)
            await writer.drain()
            auth_reply = await asyncio.wait_for(reader.readexactly(2), timeout=timeout)
            auth_ver, auth_status = struct.unpack("!BB", auth_reply)
            if auth_status != 0x00:
                raise Socks5Error(f"Upstream proxy auth failed (status=0x{auth_status:02X})")
        elif method == AUTH_NONE:
            pass  # No auth needed
        elif method == 0xFF:
            raise Socks5Error("Upstream proxy rejected all auth methods")
        else:
            raise Socks5Error(f"Upstream proxy selected unsupported method 0x{method:02X}")

        # Phase 2: CONNECT request
        try:
            target_addr = ip_address(str(target_host))
        except ValueError:
            target_addr = None

        if isinstance(target_addr, IPv4Address):
            req = struct.pack("!BBB", SOCKS_VER, CMD_CONNECT, 0x00)
            req += struct.pack("!B", ATYP_IPV4) + target_addr.packed
        elif isinstance(target_addr, IPv6Address):
            req = struct.pack("!BBB", SOCKS_VER, CMD_CONNECT, 0x00)
            req += struct.pack("!B", ATYP_IPV6) + target_addr.packed
        else:
            # Domain name
            domain_bytes = target_host.encode("ascii")
            req = struct.pack("!BBB", SOCKS_VER, CMD_CONNECT, 0x00)
            req += struct.pack("!BB", ATYP_DOMAIN, len(domain_bytes)) + domain_bytes

        req += struct.pack("!H", target_port)
        writer.write(req)
        await writer.drain()

        # Read CONNECT reply header (VER + REP + RSV + ATYP)
        resp = await asyncio.wait_for(reader.readexactly(4), timeout=timeout)
        ver, rep, _rsv, atyp = struct.unpack("!BBBB", resp)

        if ver != SOCKS_VER:
            raise Socks5Error(f"Upstream proxy bad reply version: {ver}")
        if rep != REP_SUCCESS:
            raise Socks5Error(f"Upstream proxy CONNECT failed (REP=0x{rep:02X})")

        # Consume bound address (we don't need it but must read it)
        if atyp == ATYP_IPV4:
            await reader.readexactly(4 + 2)  # 4-byte addr + 2-byte port
        elif atyp == ATYP_DOMAIN:
            domain_len = (await reader.readexactly(1))[0]
            await reader.readexactly(domain_len + 2)  # domain + 2-byte port
        elif atyp == ATYP_IPV6:
            await reader.readexactly(16 + 2)  # 16-byte addr + 2-byte port
        else:
            # Unknown ATYP — try to read 4+2 as fallback
            await reader.readexactly(4 + 2)

        return reader, writer

    except Exception:
        try:
            writer.close()
            await writer.wait_closed()
        except Exception:
            pass
        raise
