from __future__ import annotations

import re
from pathlib import Path

from config.config import MAIN_DIRECTORY
from blockcheck.strategy_scan_state import StrategyScanSelectionState

_quick_domains_cache: list[str] | None = None
_quick_stun_targets_cache: list[str] | None = None


def scan_protocol_from_value(value) -> str:
    raw = str(value or "").strip().lower()
    if raw == "stun_voice":
        return "stun_voice"
    if raw == "udp_games":
        return "udp_games"
    return "tcp_https"


def mode_from_index(index: int) -> str:
    mode_map = {0: "quick", 1: "standard", 2: "full"}
    return mode_map.get(int(index), "quick")


def build_selection_state(
    *,
    protocol_value,
    udp_scope_value,
    mode_index: int,
) -> StrategyScanSelectionState:
    scan_protocol = scan_protocol_from_value(protocol_value)
    udp_games_scope = (
        normalize_udp_games_scope(udp_scope_value)
        if scan_protocol == "udp_games"
        else "all"
    )
    return StrategyScanSelectionState(
        scan_protocol=scan_protocol,
        udp_games_scope=udp_games_scope,
        mode=mode_from_index(mode_index),
    )


def normalize_udp_games_scope(scope: str) -> str:
    raw = (scope or "").strip().lower()
    if raw in {"games_only", "games", "only_games", "targeted"}:
        return "games_only"
    return "all"


def default_target_for_protocol(scan_protocol: str) -> str:
    protocol = (scan_protocol or "").strip().lower()
    if protocol == "stun_voice":
        return "stun.l.google.com:19302"
    if protocol == "udp_games":
        return "stun.cloudflare.com:3478"
    return "discord.com"


def stun_target_parts(value: str, default_port: int = 3478) -> tuple[str, int]:
    raw = (value or "").strip()
    if not raw:
        return "", default_port

    if raw.upper().startswith("STUN:"):
        raw = raw[5:].strip()

    raw = re.sub(r"^https?://", "", raw, flags=re.IGNORECASE)
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

    return raw, default_port


def format_stun_target(host: str, port: int) -> str:
    host = (host or "").strip()
    if not host:
        return ""
    if ":" in host and not host.startswith("["):
        return f"[{host}]:{int(port)}"
    return f"{host}:{int(port)}"


def normalize_target_domain(value: str) -> str:
    raw = (value or "").strip()
    if not raw:
        return ""
    try:
        from blockcheck.targets import _normalize_domain

        return _normalize_domain(raw)
    except Exception:
        return raw.lower()


def normalize_target_input(value: str, scan_protocol: str) -> str:
    protocol = (scan_protocol or "").strip().lower()
    if protocol in {"stun_voice", "udp_games"}:
        host, port = stun_target_parts(value)
        if not host:
            return ""
        return format_stun_target(host, port)
    return normalize_target_domain(value)


def resolve_games_ipset_paths(udp_games_scope: str = "all") -> list[str]:
    scope = normalize_udp_games_scope(udp_games_scope)

    explicit_game_files = (
        "ipset-roblox.txt",
        "ipset-amazon.txt",
        "ipset-steam.txt",
        "ipset-epicgames.txt",
        "ipset-epic.txt",
        "ipset-lol-ru.txt",
        "ipset-lol-euw.txt",
        "ipset-tankix.txt",
    )

    list_dirs: list[Path] = []

    list_dirs.append(Path(MAIN_DIRECTORY) / "lists")

    files: list[str] = []
    seen: set[str] = set()
    for base_dir in list_dirs:
        if scope == "all":
            ipset_all = base_dir / "ipset-all.txt"
            key_all = str(ipset_all)
            if key_all not in seen:
                seen.add(key_all)
                if ipset_all.exists():
                    return [str(ipset_all)]

        for filename in explicit_game_files:
            candidate = base_dir / filename
            key = str(candidate)
            if key in seen:
                continue
            seen.add(key)
            if candidate.exists():
                files.append(str(candidate))

        if scope == "games_only":
            continue

        try:
            for candidate in sorted(base_dir.glob("ipset-*.txt")):
                key = str(candidate)
                if key in seen:
                    continue
                seen.add(key)
                if candidate.exists():
                    files.append(str(candidate))
        except OSError:
            continue

    if files:
        return files

    if scope == "games_only":
        return ["lists/ipset-roblox.txt"]
    return ["lists/ipset-all.txt"]


def load_quick_domains() -> list[str]:
    if _quick_domains_cache is not None:
        return list(_quick_domains_cache)

    try:
        from blockcheck.targets import load_domains

        raw_domains = load_domains()
    except Exception:
        raw_domains = []

    normalized_domains: list[str] = []
    seen: set[str] = set()
    for raw in raw_domains:
        domain = normalize_target_domain(str(raw))
        if not domain or domain in seen:
            continue
        seen.add(domain)
        normalized_domains.append(domain)

    _quick_domains_cache = normalized_domains
    return list(_quick_domains_cache)


def load_quick_stun_targets() -> list[str]:
    if _quick_stun_targets_cache is not None:
        return list(_quick_stun_targets_cache)

    try:
        from blockcheck.targets import get_default_stun_targets

        raw_targets = get_default_stun_targets()
    except Exception:
        raw_targets = []

    targets: list[str] = []
    seen: set[str] = set()
    for item in raw_targets:
        value = str(item.get("value", ""))
        normalized = normalize_target_input(value, "stun_voice")
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        targets.append(normalized)

    _quick_stun_targets_cache = targets
    return list(_quick_stun_targets_cache)
