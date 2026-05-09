from __future__ import annotations

from .models import ProfileAction, ProfileActionArg, Winws2Strategy


def parse_winws2_strategy(lines: list[str]) -> Winws2Strategy:
    payload = "all"
    in_range = "x"
    out_range = "a"
    actions: list[ProfileAction] = []
    other_lines: list[str] = []

    for raw in lines or []:
        line = str(raw or "").strip()
        lowered = line.lower()
        if not line:
            continue
        if lowered.startswith("--payload="):
            payload = line.split("=", 1)[1].strip() or "all"
            continue
        if lowered.startswith("--in-range"):
            in_range = line.split("=", 1)[1].strip() if "=" in line else "x"
            in_range = in_range or "x"
            continue
        if lowered.startswith("--out-range"):
            out_range = line.split("=", 1)[1].strip() if "=" in line else "a"
            out_range = out_range or "a"
            continue
        if lowered.startswith("--lua-desync="):
            actions.extend(
                _parse_lua_desync(action_line, payload=payload, in_range=in_range, out_range=out_range)
                for action_line in _split_lua_desync_lines(line)
            )
            continue
        other_lines.append(line)

    return Winws2Strategy(actions=actions, strategy_lines=[str(line or "").strip() for line in lines or [] if str(line or "").strip()], other_lines=other_lines)


def _split_lua_desync_lines(line: str) -> list[str]:
    stripped = str(line or "").strip()
    if not stripped:
        return []
    marker = "--lua-desync="
    positions: list[int] = []
    search_from = 0
    lowered = stripped.lower()
    while True:
        index = lowered.find(marker, search_from)
        if index < 0:
            break
        positions.append(index)
        search_from = index + len(marker)
    result: list[str] = []
    for idx, start in enumerate(positions):
        end = positions[idx + 1] if idx + 1 < len(positions) else len(stripped)
        action = stripped[start:end].strip()
        if action:
            result.append(action)
    return result


def _parse_lua_desync(line: str, *, payload: str, in_range: str, out_range: str) -> ProfileAction:
    value = line.split("=", 1)[1].strip() if "=" in line else ""
    parts = [part for part in _split_unescaped(value, ":") if part != ""]
    func_name = parts[0].strip() if parts else ""
    args: list[ProfileActionArg] = []
    flags: list[str] = []
    for token in parts[1:]:
        token = _unescape_lua_token(token.strip())
        if not token:
            continue
        if "=" in token:
            key, _, val = token.partition("=")
            key = key.strip()
            if key:
                args.append(ProfileActionArg(raw=token, key=key, value=val.strip(), is_flag=False))
        else:
            args.append(ProfileActionArg(raw=token, is_flag=True))
            flags.append(token.strip())
    return ProfileAction(
        raw_line=line,
        func_name=_unescape_lua_token(func_name),
        args=args,
        flags=[flag for flag in flags if flag],
        payload=payload,
        in_range=in_range,
        out_range=out_range,
    )


def _split_unescaped(value: str, separator: str) -> list[str]:
    parts: list[str] = []
    current: list[str] = []
    escaped = False
    for char in str(value or ""):
        if escaped:
            current.append("\\" + char if char != separator else char)
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if char == separator:
            parts.append("".join(current))
            current = []
            continue
        current.append(char)
    if escaped:
        current.append("\\")
    parts.append("".join(current))
    return parts


def _unescape_lua_token(value: str) -> str:
    return str(value or "").replace("\\:", ":")
