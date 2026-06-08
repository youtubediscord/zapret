# telegram_proxy/dc_map.py
"""Telegram datacenter IP mapping and WebSocket endpoint resolution.

Key insight: only DC2 and DC4 WebSocket relays accept connections.
DC1, DC3, DC5 return HTTP 302 redirects. All traffic is routed through
DC2/DC4 WSS relays which read the real DC id from the MTProto init packet.
"""

import socket as _socket
import struct
from ipaddress import IPv4Network, IPv4Address, IPv6Network, IPv6Address
from typing import Optional


# ---- WebSocket relay configuration ----

# The IP that hosts the proven working WebSocket relays.
# Hardcoded by Flowseal reference implementation — do NOT change to DNS result.
WSS_RELAY_IP = "149.154.167.220"

# Per-domain IP overrides (empty = all use WSS_RELAY_IP).
# Only add entries here after manually verifying that a domain works at a
# specific IP.  Unverified IPs from DNS can break media downloads.
WSS_RELAY_IPS: dict[str, str] = {}

# WSS domains that accept WebSocket upgrades (return 101).
# Only DC2 and DC4 relays are proven to work.  All DCs are routed through
# them — the relay reads the real DC from the MTProto init packet.
WSS_DOMAINS = {
    2: ["kws2.web.telegram.org", "kws2-1.web.telegram.org"],
    4: ["kws4.web.telegram.org", "kws4-1.web.telegram.org"],
}

# For DCs without their own relay, try these (cross-DC routing via init).
WSS_FALLBACK_ORDER = [2, 4]

WSS_PATH = "/apiws"

# Mapping: IP -> (dc_id, is_media)
# Used to determine DC when MTProto init packet parsing fails
# (e.g., Android clients with useSecret=0 that have random dc_id bytes)
IP_TO_DC: dict[str, tuple[int, bool]] = {
    # DC1
    "149.154.175.50": (1, False), "149.154.175.51": (1, False),
    "149.154.175.53": (1, False), "149.154.175.54": (1, False),
    "149.154.175.52": (1, True),
    # DC2
    "149.154.167.41": (2, False), "149.154.167.50": (2, False),
    "149.154.167.51": (2, False), "149.154.167.220": (2, False),
    "95.161.76.100": (2, False),
    "149.154.167.151": (2, True), "149.154.167.222": (2, True),
    "149.154.167.223": (2, True), "149.154.162.123": (2, True),
    # DC3
    "149.154.175.100": (3, False), "149.154.175.101": (3, False),
    "149.154.175.102": (3, True),
    # DC4
    "149.154.167.91": (4, False), "149.154.167.92": (4, False),
    "149.154.164.250": (4, True), "149.154.166.120": (4, True),
    "149.154.166.121": (4, True), "149.154.167.118": (4, True),
    "149.154.165.111": (4, True),
    # DC5
    "91.108.56.100": (5, False), "91.108.56.101": (5, False),
    "91.108.56.116": (5, False), "91.108.56.126": (5, False),
    "149.154.171.5": (5, False),
    "91.108.56.102": (5, True), "91.108.56.128": (5, True),
    "91.108.56.151": (5, True),
    # DC203
    "91.105.192.100": (203, False),
}

# Direct TCP fallback endpoints (same DCs, raw TCP)
TCP_ENDPOINTS = {
    1: ("149.154.175.50", 443),
    2: ("149.154.167.51", 443),
    3: ("149.154.175.100", 443),
    4: ("149.154.167.91", 443),
    5: ("91.108.56.100", 443),
    203: ("91.105.192.100", 443),
}

# Telegram CIDR ranges -> DC mapping
# Source: https://core.telegram.org/resources/cidr.txt + known DC assignments
_SUBNET_TO_DC: list[tuple[IPv4Network, int]] = [
    # DC2 subnets
    (IPv4Network("91.108.4.0/22"), 2),
    (IPv4Network("91.105.192.0/23"), 2),
    (IPv4Network("185.76.151.0/24"), 2),
    # DC1 subnets
    (IPv4Network("91.108.20.0/22"), 1),
    # DC4 subnets
    (IPv4Network("91.108.8.0/22"), 4),
    (IPv4Network("91.108.12.0/22"), 4),
    # DC5 subnets
    (IPv4Network("91.108.16.0/22"), 5),
    (IPv4Network("91.108.56.0/22"), 5),
    # Large block covering DC1-DC5 (149.154.160.0/20)
    # Most specific /24 ranges first (known DC assignments):
    (IPv4Network("149.154.175.0/24"), 1),   # DC1 primary (175.50-54)
    (IPv4Network("149.154.167.0/24"), 2),   # DC2 primary (167.50-54)
    # Broader /22 ranges:
    (IPv4Network("149.154.160.0/22"), 1),   # DC1
    (IPv4Network("149.154.164.0/22"), 4),   # DC4 (164-167, but 167 overridden above)
    (IPv4Network("149.154.168.0/22"), 2),   # DC2
    (IPv4Network("149.154.172.0/22"), 1),   # DC1/DC3 range, default DC1
    # Fallback for entire /20 block
    (IPv4Network("149.154.160.0/20"), 2),
]

# All Telegram IPv4 CIDR ranges (for checking if IP is Telegram)
TELEGRAM_CIDRS: list[IPv4Network] = [
    IPv4Network("91.108.56.0/22"),
    IPv4Network("91.108.4.0/22"),
    IPv4Network("91.108.8.0/22"),
    IPv4Network("91.108.16.0/22"),
    IPv4Network("91.108.12.0/22"),
    IPv4Network("149.154.160.0/20"),
    IPv4Network("91.105.192.0/23"),
    IPv4Network("91.108.20.0/22"),
    IPv4Network("185.76.151.0/24"),
]

# Telegram IPv6 CIDR ranges
TELEGRAM_V6_CIDRS: list[IPv6Network] = [
    IPv6Network("2001:67c:4e8::/48"),
    IPv6Network("2001:b28:f23c::/46"),
    IPv6Network("2a0a:f280::/32"),
]

# IPv6 DC mapping (prefix -> dc)
_V6_SUBNET_TO_DC: list[tuple[IPv6Network, int]] = [
    (IPv6Network("2001:67c:4e8:f002::/64"), 2),   # DC2
    (IPv6Network("2001:67c:4e8:f003::/64"), 3),   # DC3
    (IPv6Network("2001:67c:4e8:f004::/64"), 4),   # DC4
    (IPv6Network("2001:67c:4e8:f001::/64"), 1),   # DC1
    (IPv6Network("2001:67c:4e8:f005::/64"), 5),   # DC5
    (IPv6Network("2001:b28:f23d:f003::/64"), 3),   # DC3 alt
    (IPv6Network("2001:b28:f23f:f005::/64"), 5),   # DC5 alt
    (IPv6Network("2a0a:f280:203::/48"), 203),       # CDN DC203
    # Fallback for entire ranges
    (IPv6Network("2001:67c:4e8::/48"), 2),
    (IPv6Network("2001:b28:f23c::/46"), 2),
    (IPv6Network("2a0a:f280::/32"), 2),
]

# Telegram IP ranges as integer tuples for fast lookup
_TG_RANGES = [
    # 185.76.151.0/24
    (struct.unpack("!I", _socket.inet_aton("185.76.151.0"))[0],
     struct.unpack("!I", _socket.inet_aton("185.76.151.255"))[0]),
    # 149.154.160.0/20
    (struct.unpack("!I", _socket.inet_aton("149.154.160.0"))[0],
     struct.unpack("!I", _socket.inet_aton("149.154.175.255"))[0]),
    # 91.105.192.0/23
    (struct.unpack("!I", _socket.inet_aton("91.105.192.0"))[0],
     struct.unpack("!I", _socket.inet_aton("91.105.193.255"))[0]),
    # 91.108.0.0/16
    (struct.unpack("!I", _socket.inet_aton("91.108.0.0"))[0],
     struct.unpack("!I", _socket.inet_aton("91.108.255.255"))[0]),
]

# Pre-compiled set of (network_int, mask) for fast lookup
_COMPILED_NETS: list[tuple[int, int, int]] = []  # (net_addr, mask, dc)
_COMPILED_TG_RANGES: list[tuple[int, int]] = []  # (net_addr, mask)


def _compile() -> None:
    """Pre-compile CIDR ranges for fast integer matching."""
    global _COMPILED_NETS, _COMPILED_TG_RANGES
    if _COMPILED_NETS:
        return
    # Sort by prefix length descending (most specific first)
    sorted_subnets = sorted(_SUBNET_TO_DC, key=lambda x: x[0].prefixlen, reverse=True)
    for net, dc in sorted_subnets:
        net_int = int(net.network_address)
        mask = int(net.netmask)
        _COMPILED_NETS.append((net_int, mask, dc))
    for net in TELEGRAM_CIDRS:
        net_int = int(net.network_address)
        mask = int(net.netmask)
        _COMPILED_TG_RANGES.append((net_int, mask))


def ip_to_dc(ip: str) -> int:
    """Map a Telegram IP address to its datacenter number.

    Returns DC number (1-5). Falls back to DC2 (most common) if unknown.
    Supports both IPv4 and IPv6.
    """
    if ":" in ip:
        try:
            addr = IPv6Address(ip)
            for net, dc in _V6_SUBNET_TO_DC:
                if addr in net:
                    return dc
        except ValueError:
            pass
        return 2
    _compile()
    try:
        ip_int = int(IPv4Address(ip))
    except ValueError:
        return 2
    for net_addr, mask, dc in _COMPILED_NETS:
        if (ip_int & mask) == net_addr:
            return dc
    return 2  # Default DC


def ip_to_dc_media(ip: str) -> tuple[int, bool]:
    """Map IP to (dc_id, is_media) using the exact IP table.

    Falls back to CIDR-based lookup if IP not in table.
    """
    entry = IP_TO_DC.get(ip)
    if entry is not None:
        return entry
    return (ip_to_dc(ip), False)


def is_telegram_ip(ip: str) -> bool:
    """Check if an IP address belongs to Telegram's known ranges.

    Uses fast integer comparison against precomputed ranges.
    Supports both IPv4 and IPv6.
    """
    if ":" in ip:
        # IPv6
        try:
            addr = IPv6Address(ip)
            return any(addr in net for net in TELEGRAM_V6_CIDRS)
        except ValueError:
            return False
    try:
        n = struct.unpack("!I", _socket.inet_aton(ip))[0]
        return any(lo <= n <= hi for lo, hi in _TG_RANGES)
    except OSError:
        return False


def ws_domains_for_dc(dc: int, is_media: bool = False) -> list[str]:
    """Get WebSocket domain names to try for a datacenter.

    Only DC2 and DC4 have proven working WSS relays.  For other DCs,
    returns DC2/DC4 domains — the relay routes based on the DC id in the
    MTProto init packet (cross-DC routing).

    For media connections, tries the -1 variant first.
    """
    if dc in WSS_DOMAINS:
        domains = WSS_DOMAINS[dc]
        if is_media:
            return list(reversed(domains))  # -1 variant first for media
        return list(domains)

    # DC doesn't have its own relay -- use fallback DCs
    result = []
    for fallback_dc in WSS_FALLBACK_ORDER:
        domains = WSS_DOMAINS[fallback_dc]
        if is_media:
            result.extend(reversed(domains))
        else:
            result.extend(domains)
    return result


def parse_dc_endpoint_overrides(value: object) -> dict[int, str]:
    """Parse user DC -> IP overrides like "2:149.154.167.220"."""
    if isinstance(value, str):
        raw_items = value.replace(",", " ").replace(";", " ").split()
    elif isinstance(value, (list, tuple, set)):
        raw_items = []
        for item in value:
            if isinstance(item, str):
                raw_items.extend(item.replace(",", " ").replace(";", " ").split())
    else:
        raw_items = []

    overrides: dict[int, str] = {}
    for item in raw_items:
        text = item.strip()
        if ":" not in text:
            continue
        dc_text, ip_text = text.split(":", 1)
        try:
            dc = int(dc_text.strip())
            ip = str(IPv4Address(ip_text.strip()))
        except Exception:
            continue
        if dc not in {1, 2, 3, 4, 5, 203}:
            continue
        overrides[dc] = ip
    return overrides


def dc_to_tcp_endpoint(dc: int, overrides: dict[int, str] | None = None) -> tuple[str, int]:
    """Get direct TCP endpoint for a datacenter (fallback)."""
    override_ip = (overrides or {}).get(int(dc))
    if override_ip:
        return override_ip, 443
    return TCP_ENDPOINTS.get(dc, TCP_ENDPOINTS[2])


# Transparent mode: port encoding
# DC1 -> port 1351, DC2 -> 1352, ..., DC5 -> 1355
TRANSPARENT_PORT_BASE = 1350

def dc_to_transparent_port(dc: int) -> int:
    """Get local port for transparent mode per-DC listener."""
    return TRANSPARENT_PORT_BASE + dc

def transparent_port_to_dc(port: int) -> Optional[int]:
    """Get DC number from transparent mode port. Returns None if not a DC port."""
    dc = port - TRANSPARENT_PORT_BASE
    if 1 <= dc <= 5:
        return dc
    return None
