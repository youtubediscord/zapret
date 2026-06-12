from __future__ import annotations

from pathlib import PureWindowsPath

from settings.mode import ENGINE_WINWS1, ENGINE_WINWS2

from .models import EngineName, Preset, Profile, ProfileMatch, ProfileSegment, build_profile_persistent_key
from .winws1 import parse_winws1_strategy
from .winws2 import parse_winws2_strategy


_DIRECTIVE_PREFIXES = (
    "--name",
    "--template",
    "--import",
    "--skip",
    "--comment",
    "--cookie",
)

_MATCH_PREFIXES = (
    "--filter-",
    "--hostlist=",
    "--hostlist-domains=",
    "--hostlist-exclude=",
    "--hostlist-exclude-domains=",
    "--hostlist-auto=",
    "--ipset=",
    "--ipset-exclude=",
    "--ipset-exclude-ip=",
    "--ipset-ip=",
)

_WINWS1_STRATEGY_PREFIXES = (
    "--dpi-desync",
    "--dup",
    "--wssize",
    "--ip-id",
)


def normalize_text(text: str) -> str:
    return str(text or "").replace("\r\n", "\n").replace("\r", "\n")


def parse_preset_text(text: str, *, engine: str, source_name: str = "") -> Preset:
    normalized_engine = _normalize_engine(engine)
    header_lines, body_lines = _split_header_and_body(text)
    preamble_lines, raw_profiles, footer_lines = _split_preamble_and_profile_lines(body_lines)
    profiles = [
        _parse_profile(lines, engine=normalized_engine, index=index, new_line=new_line)
        for index, (new_line, lines) in enumerate(raw_profiles)
    ]
    _assign_profile_keys(profiles)
    return Preset(
        engine=normalized_engine,
        header_lines=header_lines,
        preamble_lines=preamble_lines,
        profiles=profiles,
        source_name=str(source_name or ""),
        footer_lines=footer_lines,
    )


def _normalize_engine(engine: str) -> EngineName:
    normalized = str(engine or "").strip().lower()
    if normalized not in {ENGINE_WINWS1, ENGINE_WINWS2}:
        raise ValueError(f"Unsupported profile preset engine: {engine}")
    return normalized  # type: ignore[return-value]


def _split_header_and_body(text: str) -> tuple[list[str], list[str]]:
    header_lines: list[str] = []
    body_lines: list[str] = []
    in_header = True
    for raw in normalize_text(text).split("\n"):
        stripped = raw.strip()
        if in_header and (stripped.startswith("#") or not stripped):
            header_lines.append(raw)
            continue
        in_header = False
        body_lines.append(raw)
    return header_lines, body_lines


def _split_preamble_and_profile_lines(body_lines: list[str]) -> tuple[list[str], list[tuple[str, list[str]]], list[str]]:
    preamble: list[str] = []
    profiles: list[tuple[str, list[str]]] = []
    footer: list[str] = []
    current: list[str] = []
    current_new_line = ""
    saw_profile = False

    def _push_profile(new_line: str, raw_lines: list[str]) -> None:
        if raw_lines:
            profiles.append((new_line, list(raw_lines)))

    for raw in body_lines:
        stripped = raw.strip()
        if _is_new_profile_line(stripped):
            if saw_profile:
                _push_profile(current_new_line, current)
                current = []
            elif current:
                preamble.extend(current)
                current = []
            saw_profile = True
            current_new_line = stripped
            continue

        if not saw_profile and not _looks_like_profile_line(stripped):
            preamble.append(raw)
            continue

        if not saw_profile and _looks_like_profile_line(stripped):
            saw_profile = True
            current_new_line = ""
        current.append(raw)

    if current:
        if saw_profile:
            if current_new_line and not _has_profile_content(current):
                footer.extend(current)
            else:
                _push_profile(current_new_line, current)
        else:
            preamble.extend(current)
    return preamble, profiles, footer


def _has_profile_content(lines: list[str]) -> bool:
    for line in lines:
        stripped = str(line or "").strip()
        if not stripped or stripped.startswith("#"):
            continue
        return True
    return False


def _is_new_profile_line(stripped: str) -> bool:
    lowered = str(stripped or "").strip().lower()
    return lowered == "--new" or lowered.startswith("--new=")


def _looks_like_profile_line(stripped: str) -> bool:
    return any(
        str(stripped or "").startswith(prefix)
        for prefix in (
            *_MATCH_PREFIXES,
            *_DIRECTIVE_PREFIXES,
            "--payload=",
            "--in-range",
            "--out-range",
            "--lua-desync=",
            *_WINWS1_STRATEGY_PREFIXES,
        )
    )


def _parse_profile(lines: list[str], *, engine: EngineName, index: int, new_line: str) -> Profile:
    segments: list[ProfileSegment] = []
    match = ProfileMatch()
    strategy_lines: list[str] = []
    name = _name_from_new_line(new_line)
    enabled = True
    saw_strategy = False

    for raw in lines:
        stripped = raw.strip()
        if not stripped:
            segments.append(ProfileSegment(kind="blank", text=raw))
            continue
        if stripped.startswith("#"):
            segments.append(ProfileSegment(kind="comment", text=raw))
            continue
        if _is_directive(stripped):
            directive_name, directive_value = _split_option(stripped)
            if _is_profile_name_directive(engine, directive_name):
                name = directive_value or name
            if directive_name == "--skip":
                enabled = False
            segments.append(ProfileSegment(kind="directive", text=stripped, name=directive_name, value=directive_value))
            continue
        if _is_match_line(stripped):
            _add_match_line(match, stripped)
            option_name, option_value = _split_option(stripped)
            segments.append(ProfileSegment(kind="match", text=stripped, name=option_name, value=option_value))
            continue
        if _is_strategy_filter_line(stripped, engine):
            strategy_lines.append(stripped)
            saw_strategy = True
            option_name, option_value = _split_option(stripped)
            segments.append(ProfileSegment(kind="strategy_filter", text=stripped, name=option_name, value=option_value))
            continue
        if _is_strategy_line(stripped, engine):
            strategy_lines.append(stripped)
            saw_strategy = True
            option_name, option_value = _split_option(stripped)
            segments.append(ProfileSegment(kind="strategy", text=stripped, name=option_name, value=option_value))
            continue
        if engine == ENGINE_WINWS1 and saw_strategy:
            strategy_lines.append(stripped)
            option_name, option_value = _split_option(stripped)
            segments.append(ProfileSegment(kind="strategy", text=stripped, name=option_name, value=option_value))
            continue

        _add_match_line(match, stripped)
        option_name, option_value = _split_option(stripped)
        segments.append(ProfileSegment(kind="match", text=stripped, name=option_name, value=option_value))

    strategy = parse_winws2_strategy(strategy_lines) if engine == ENGINE_WINWS2 else parse_winws1_strategy(strategy_lines)
    display_name = name or infer_profile_display_name(match, index)
    return Profile(
        id=f"profile:{index}",
        index=index,
        engine=engine,
        display_name=display_name,
        enabled=enabled,
        match=match,
        strategy=strategy,
        segments=segments,
        new_line=new_line,
        name=name,
        match_signature=build_match_signature(match),
    )


def _assign_profile_keys(profiles: list[Profile]) -> None:
    for profile in profiles:
        profile.persistent_key = build_profile_persistent_key(profile.name, profile.match_signature)


def _name_from_new_line(new_line: str) -> str:
    stripped = str(new_line or "").strip()
    if stripped.lower().startswith("--new="):
        return stripped.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


def _is_directive(stripped: str) -> bool:
    return any(stripped.startswith(prefix) for prefix in _DIRECTIVE_PREFIXES)


def _is_profile_name_directive(engine: EngineName, directive_name: str) -> bool:
    name = str(directive_name or "").strip().lower()
    if engine == ENGINE_WINWS1:
        return name == "--comment"
    return name == "--name"


def _is_match_line(stripped: str) -> bool:
    return any(stripped.startswith(prefix) for prefix in _MATCH_PREFIXES)


def _is_strategy_filter_line(stripped: str, engine: EngineName) -> bool:
    if engine != ENGINE_WINWS2:
        return False
    lowered = stripped.lower()
    return lowered.startswith("--payload=") or lowered.startswith("--in-range") or lowered.startswith("--out-range")


def _is_strategy_line(stripped: str, engine: EngineName) -> bool:
    lowered = stripped.lower()
    if engine == ENGINE_WINWS2:
        return lowered.startswith("--lua-desync=")
    return any(lowered.startswith(prefix) for prefix in _WINWS1_STRATEGY_PREFIXES)


def _split_option(line: str) -> tuple[str, str]:
    stripped = str(line or "").strip()
    if "=" not in stripped:
        return stripped, ""
    name, _, value = stripped.partition("=")
    return name.strip(), value.strip()


def _add_match_line(match: ProfileMatch, line: str) -> None:
    lowered = line.lower()
    if lowered.startswith("--filter-"):
        match.filter_lines.append(line)
    elif lowered.startswith("--hostlist="):
        match.hostlist_lines.append(line)
    elif lowered.startswith("--ipset="):
        match.ipset_lines.append(line)
    elif lowered.startswith("--hostlist-exclude=") or lowered.startswith("--hostlist-exclude-domains="):
        match.hostlist_exclude_lines.append(line)
    elif lowered.startswith("--hostlist-auto="):
        match.hostlist_auto_lines.append(line)
    elif lowered.startswith("--ipset-exclude=") or lowered.startswith("--ipset-exclude-ip="):
        match.ipset_exclude_lines.append(line)
    elif lowered.startswith("--hostlist-domains="):
        match.hostlist_domains_lines.append(line)
    elif lowered.startswith("--ipset-ip="):
        match.inline_ipset_lines.append(line)
    else:
        match.other_lines.append(line)


def build_match_signature(match: ProfileMatch) -> str:
    normalized: list[str] = []
    primary_lines = [
        *match.hostlist_lines,
        *match.ipset_lines,
        *match.hostlist_domains_lines,
        *match.inline_ipset_lines,
    ]
    identity_lines = [
        *match.filter_lines,
        *primary_lines,
    ]
    if not primary_lines:
        identity_lines.extend(match.hostlist_exclude_lines)
        identity_lines.extend(match.ipset_exclude_lines)
    for line in identity_lines:
        stripped = str(line or "").strip().lower()
        if not stripped:
            continue
        if "=" in stripped:
            name, _, value = stripped.partition("=")
            name = name.strip()
            if name in {"--hostlist", "--hostlist-exclude", "--hostlist-auto", "--ipset", "--ipset-exclude"}:
                value = PureWindowsPath(value.lstrip("@").strip('"').strip("'")).name.lower()
            elif name in {"--hostlist-domains", "--hostlist-exclude-domains", "--ipset-ip", "--ipset-exclude-ip"}:
                value = ",".join(sorted(token.strip().lower() for token in value.split(",") if token.strip()))
            stripped = f"{_signature_option_name(name)}={value}"
        normalized.append(stripped)
    return "|".join(sorted(normalized))


def _signature_option_name(name: str) -> str:
    clean = str(name or "").strip().lower()
    if clean.startswith("--filter-"):
        return clean.removeprefix("--filter-")
    return clean.removeprefix("--")


def infer_profile_display_name(match: ProfileMatch, index: int) -> str:
    base_parts: list[str] = []
    for label, option_name in (("TCP", "--filter-tcp"), ("UDP", "--filter-udp"), ("L7", "--filter-l7")):
        values = _match_values(match.filter_lines, option_name)
        if values:
            base_parts.append(f"{label} {','.join(values)}")
    base = " / ".join(base_parts) if base_parts else "Без фильтра"

    suffixes: list[str] = []
    simple_hostlist = _single_file_name(match.hostlist_lines)
    simple_ipset = _single_file_name(match.ipset_lines)
    complex_match = _is_complex_match(match)

    if simple_hostlist:
        suffixes.append(f"hostlist {simple_hostlist}")
    if simple_ipset:
        suffixes.append(f"ipset {simple_ipset}")
    if complex_match:
        suffixes.append("сложный match")

    if suffixes:
        return f"{base} • {' • '.join(suffixes)}"
    return base or f"profile {index + 1}"


def _match_values(lines: list[str], option_name: str) -> list[str]:
    prefix = f"{option_name.lower()}="
    values: list[str] = []
    for line in lines:
        stripped = str(line or "").strip()
        if stripped.lower().startswith(prefix) and "=" in stripped:
            values.append(stripped.split("=", 1)[1].strip())
    return values


def _single_file_name(lines: list[str]) -> str:
    if len(lines) != 1:
        return ""
    value = lines[0].split("=", 1)[1].strip() if "=" in lines[0] else ""
    name = PureWindowsPath(value.lstrip("@").strip('"').strip("'")).name
    return name


def _is_complex_match(match: ProfileMatch) -> bool:
    list_line_count = (
        len(match.hostlist_lines)
        + len(match.ipset_lines)
        + len(match.hostlist_domains_lines)
        + len(match.inline_ipset_lines)
    )
    if list_line_count > 1:
        return True
    if match.hostlist_exclude_lines or match.ipset_exclude_lines:
        return True
    if match.hostlist_auto_lines:
        return True
    if match.other_lines:
        return True
    return False
