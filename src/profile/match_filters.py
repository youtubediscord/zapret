from __future__ import annotations


def strategy_catalog_from_match_lines(match_lines: tuple[str, ...]) -> str:
    if is_voice_match(match_lines):
        return "voice"
    if filter_values(match_lines, "--filter-l7"):
        return "udp"
    if filter_values(match_lines, "--filter-udp") and not filter_values(match_lines, "--filter-tcp"):
        return "udp"
    if is_http80_match(match_lines):
        return "http80"
    return "tcp"


def protocol_label_from_match_lines(match_lines: tuple[str, ...]) -> str:
    has_l7 = bool(filter_values(match_lines, "--filter-l7"))
    has_udp = bool(filter_values(match_lines, "--filter-udp"))
    has_tcp = bool(filter_values(match_lines, "--filter-tcp"))
    if is_voice_match(match_lines):
        return "Voice"
    if has_tcp and (has_udp or has_l7):
        return "TCP/UDP"
    if has_l7:
        return "L7"
    if has_udp:
        return "UDP"
    if is_http80_match(match_lines):
        return "TCP/HTTP"
    return "TCP"


def ports_label_from_match_lines(match_lines: tuple[str, ...]) -> str:
    parts: list[str] = []
    for label, option_name in (("TCP", "--filter-tcp"), ("UDP", "--filter-udp")):
        values = filter_values(match_lines, option_name)
        if values:
            parts.append(f"{label} {', '.join(values)}")
    return "; ".join(parts)


def filter_values(match_lines: tuple[str, ...], option_name: str) -> tuple[str, ...]:
    prefix = option_name.lower().rstrip("=") + "="
    return tuple(
        line.split("=", 1)[1].strip()
        for line in match_lines
        if line.lower().startswith(prefix) and "=" in line
    )


def is_voice_match(match_lines: tuple[str, ...]) -> bool:
    l7_values = ",".join(filter_values(match_lines, "--filter-l7")).lower()
    if any(token in l7_values for token in ("stun", "discord", "wireguard")):
        return True
    udp_values = filter_values(match_lines, "--filter-udp")
    match_text = " ".join(match_lines).lower()
    if not any(token in match_text for token in ("discord", "stun", "voice", "голос")):
        return False
    return any(_ports_overlap(value, 50000, 59000) for value in udp_values)


def is_http80_match(match_lines: tuple[str, ...]) -> bool:
    tcp_values = filter_values(match_lines, "--filter-tcp")
    if not tcp_values or filter_values(match_lines, "--filter-udp") or filter_values(match_lines, "--filter-l7"):
        return False
    ports = _parse_ports(",".join(tcp_values))
    return bool(ports) and ports == {80}


def _ports_overlap(raw_ports: str, start: int, end: int) -> bool:
    for token in str(raw_ports or "").split(","):
        bounds = _parse_port_token(token)
        if bounds is None:
            continue
        token_start, token_end = bounds
        if token_start <= end and token_end >= start:
            return True
    return False


def _parse_ports(raw_ports: str) -> set[int]:
    ports: set[int] = set()
    for token in str(raw_ports or "").split(","):
        bounds = _parse_port_token(token)
        if bounds is None:
            continue
        start, end = bounds
        if start == end:
            ports.add(start)
            continue
        if end - start <= 512:
            ports.update(range(start, end + 1))
        else:
            ports.add(start)
            ports.add(end)
    return ports


def _parse_port_token(token: str) -> tuple[int, int] | None:
    stripped = str(token or "").strip()
    if not stripped:
        return None
    if "-" in stripped:
        left, _, right = stripped.partition("-")
        if not left.strip().isdigit() or not right.strip().isdigit():
            return None
        start = int(left.strip())
        end = int(right.strip())
        if start > end:
            start, end = end, start
        return start, end
    if not stripped.isdigit():
        return None
    port = int(stripped)
    return port, port
