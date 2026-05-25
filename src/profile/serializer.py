from __future__ import annotations

from copy import deepcopy
import re

from settings.mode import ENGINE_WINWS2

from .models import EngineName, Preset, Profile, ProfileSegment
from .parser import parse_preset_text


_STRATEGY_KINDS = {"strategy", "strategy_filter"}


def serialize_preset(preset: Preset) -> str:
    lines: list[str] = []
    lines.extend(preset.header_lines)
    lines.extend(preset.preamble_lines)

    for profile in preset.profiles:
        skip_leading_blanks = False
        if profile.new_line:
            while lines and not lines[-1].strip():
                lines.pop()
            if lines:
                lines.append("")
            lines.append(profile.new_line)
            lines.append("")
            skip_leading_blanks = True
        for segment in profile.segments:
            if segment.kind == "blank":
                continue
            skip_leading_blanks = False
            lines.append(segment.text)
    lines.extend(getattr(preset, "footer_lines", []) or [])

    while lines and not lines[-1].strip():
        lines.pop()
    return "\n".join(lines) + "\n"


def with_profile_enabled(preset: Preset, profile_index: int, enabled: bool) -> Preset:
    updated = deepcopy(preset)
    profile = updated.profiles[int(profile_index)]
    profile.enabled = bool(enabled)
    has_skip = any(segment.kind == "directive" and segment.text.strip().lower() == "--skip" for segment in profile.segments)
    if profile.enabled:
        profile.segments = [
            segment
            for segment in profile.segments
            if not (segment.kind == "directive" and segment.text.strip().lower() == "--skip")
        ]
        return _reparse(updated)

    if not has_skip:
        insert_at = _directive_insert_index(profile)
        profile.segments.insert(insert_at, ProfileSegment(kind="directive", text="--skip", name="--skip"))
    return _reparse(updated)


def with_profile_strategy_lines(preset: Preset, profile_index: int, strategy_lines: list[str]) -> Preset:
    updated = deepcopy(preset)
    profile = updated.profiles[int(profile_index)]
    normalized_lines = [str(line or "").strip() for line in strategy_lines or [] if str(line or "").strip()]
    normalized_lines = _preserve_missing_winws2_strategy_filters(updated.engine, profile, normalized_lines)
    replacement_segments = [
        _segment_for_strategy_line(updated.engine, line)
        for line in normalized_lines
    ]

    first_strategy_index = None
    kept: list[ProfileSegment] = []
    for index, segment in enumerate(profile.segments):
        if segment.kind in _STRATEGY_KINDS:
            if first_strategy_index is None:
                first_strategy_index = len(kept)
            continue
        kept.append(segment)

    insert_at = first_strategy_index if first_strategy_index is not None else len(kept)
    if replacement_segments:
        while insert_at > 0 and kept[insert_at - 1].kind == "blank":
            del kept[insert_at - 1]
            insert_at -= 1
    profile.segments = [*kept[:insert_at], *replacement_segments, *kept[insert_at:]]
    return _reparse(updated)


def with_profile_user_match(
    preset: Preset,
    profile_index: int,
    *,
    name: str,
    protocol: str,
    ports: str,
    hostlist: str,
    ipset: str,
) -> Preset:
    updated = deepcopy(preset)
    profile = updated.profiles[int(profile_index)]
    clean_name = str(name or "").strip()
    clean_protocol = str(protocol or "").strip().lower()
    clean_ports = str(ports or "").strip()
    hostlist = str(hostlist or "").strip()
    ipset = str(ipset or "").strip()
    if clean_protocol not in {"tcp", "udp", "l7"}:
        raise ValueError("protocol must be tcp, udp or l7")
    if not clean_name or not clean_ports:
        raise ValueError("name and ports are required")

    filter_line = f"--filter-{clean_protocol}={clean_ports}"
    name_written = False
    filter_written = False
    list_written = False
    insert_at: int | None = None
    result: list[ProfileSegment] = []

    for segment in profile.segments:
        segment_name = str(segment.name or "").strip().lower()
        if segment.kind == "directive" and segment_name == "--name":
            result.append(ProfileSegment(kind="directive", text=f"--name={clean_name}", name="--name", value=clean_name))
            name_written = True
            continue
        if segment.kind == "match" and segment_name.startswith("--filter-"):
            if not filter_written:
                result.append(_segment_for_match_line(filter_line))
                filter_written = True
            continue
        if segment.kind == "match" and segment_name in {"--hostlist", "--ipset"}:
            if segment_name == "--ipset":
                if ipset:
                    result.append(_segment_for_match_line(f"--ipset={ipset}"))
                    list_written = True
                continue
            if hostlist:
                result.append(_segment_for_match_line(f"--hostlist={hostlist}"))
                list_written = True
            continue
        if insert_at is None and segment.kind in {"match", "strategy_filter", "strategy"}:
            insert_at = len(result)
        result.append(segment)

    if not name_written:
        result.insert(_directive_insert_index_for_segments(result), ProfileSegment(kind="directive", text=f"--name={clean_name}", name="--name", value=clean_name))
    if not filter_written:
        insert = _first_strategy_or_end_index(result)
        result.insert(insert, _segment_for_match_line(filter_line))
    if not list_written and hostlist:
        insert = _first_strategy_or_end_index(result)
        result.insert(insert, _segment_for_match_line(f"--hostlist={hostlist}"))

    profile.segments = result
    return _reparse(updated)


def _preserve_missing_winws2_strategy_filters(engine: EngineName, profile: Profile, strategy_lines: list[str]) -> list[str]:
    if engine != ENGINE_WINWS2:
        return strategy_lines

    wanted_names = ("--payload", "--in-range", "--out-range")
    provided = {
        _split_option(line)[0].strip().lower()
        for line in strategy_lines
    }
    preserved: list[str] = []
    for segment in profile.segments:
        if segment.kind != "strategy_filter":
            continue
        name = str(segment.name or "").strip().lower()
        if name not in wanted_names or name in provided:
            continue
        text = str(segment.text or "").strip()
        if text:
            preserved.append(text)
            provided.add(name)
    return [*preserved, *strategy_lines]


def append_profile_from_template(
    preset: Preset,
    template: Profile,
    *,
    enabled: bool = True,
    position: str = "bottom",
) -> Preset:
    updated = deepcopy(preset)
    if getattr(updated, "footer_lines", None):
        updated.footer_lines = []
    insert_at = 0 if str(position or "").strip().lower() == "top" else len(updated.profiles)
    if (
        updated.profiles
        and insert_at == len(updated.profiles)
        and updated.profiles[-1].segments
        and updated.profiles[-1].segments[-1].text.strip()
    ):
        updated.profiles[-1].segments.append(ProfileSegment(kind="blank", text=""))
    profile = deepcopy(template)
    profile.index = insert_at
    profile.engine = updated.engine
    profile.new_line = "" if insert_at == 0 else "--new"
    profile.segments = [
        segment
        for segment in profile.segments
        if not (segment.kind == "directive" and segment.text.strip().lower() == "--skip")
    ]
    if not enabled:
        profile.segments.insert(_directive_insert_index(profile), ProfileSegment(kind="directive", text="--skip", name="--skip"))
    _ensure_safe_default_strategy(profile)
    updated.profiles.insert(insert_at, profile)
    _ensure_profile_boundaries(updated)
    return _reparse(updated)


def with_profile_deleted(preset: Preset, profile_index: int) -> Preset:
    updated = deepcopy(preset)
    index = int(profile_index)
    if index < 0 or index >= len(updated.profiles):
        raise IndexError(f"Profile index out of range: {profile_index}")
    del updated.profiles[index]
    _ensure_profile_boundaries(updated)
    return _reparse(updated)


def with_profile_duplicated(preset: Preset, profile_index: int) -> Preset:
    updated = deepcopy(preset)
    index = int(profile_index)
    if index < 0 or index >= len(updated.profiles):
        raise IndexError(f"Profile index out of range: {profile_index}")

    source = updated.profiles[index]
    profile = deepcopy(source)
    profile.index = index + 1
    _rename_profile_copy(profile, _unique_copy_name(updated, source))

    updated.profiles.insert(index + 1, profile)
    _ensure_profile_boundaries(updated)
    return _reparse(updated)


def with_profile_moved(preset: Preset, source_index: int, destination_index: int) -> Preset:
    updated = deepcopy(preset)
    source = int(source_index)
    destination = int(destination_index)
    if source < 0 or source >= len(updated.profiles):
        raise IndexError(f"Profile index out of range: {source_index}")
    if destination < 0:
        destination = 0
    if destination > len(updated.profiles):
        destination = len(updated.profiles)
    if source == destination or source + 1 == destination:
        return updated

    profile = updated.profiles.pop(source)
    if source < destination:
        destination -= 1
    updated.profiles.insert(destination, profile)
    _ensure_profile_boundaries(updated)
    return _reparse(updated)


def with_profile_raw_text(preset: Preset, profile_index: int, raw_text: str) -> Preset:
    updated = deepcopy(preset)
    index = int(profile_index)
    if index < 0 or index >= len(updated.profiles):
        raise IndexError(f"Profile index out of range: {profile_index}")

    text = str(raw_text or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not text:
        raise ValueError("profile text must not be empty")

    parsed = parse_preset_text(text, engine=updated.engine, source_name=updated.source_name)
    if len(parsed.profiles) != 1:
        raise ValueError("profile text must contain exactly one profile")

    replacement = deepcopy(parsed.profiles[0])
    current_new_line = str(updated.profiles[index].new_line or "")
    replacement.index = index
    replacement.engine = updated.engine
    replacement.new_line = str(replacement.new_line or current_new_line)
    updated.profiles[index] = replacement
    _ensure_profile_boundaries(updated)
    return _reparse(updated)


def _segment_for_strategy_line(engine: EngineName, line: str) -> ProfileSegment:
    lowered = line.lower()
    if engine == ENGINE_WINWS2 and (
        lowered.startswith("--payload=")
        or lowered.startswith("--in-range")
        or lowered.startswith("--out-range")
    ):
        name, value = _split_option(line)
        return ProfileSegment(kind="strategy_filter", text=line, name=name, value=value)
    name, value = _split_option(line)
    return ProfileSegment(kind="strategy", text=line, name=name, value=value)


def _segment_for_match_line(line: str) -> ProfileSegment:
    name, value = _split_option(line)
    return ProfileSegment(kind="match", text=line, name=name, value=value)


def _directive_insert_index_for_segments(segments: list[ProfileSegment]) -> int:
    for index, segment in enumerate(segments):
        if segment.kind not in {"blank", "comment", "directive"}:
            return index
    return len(segments)


def _first_strategy_or_end_index(segments: list[ProfileSegment]) -> int:
    for index, segment in enumerate(segments):
        if segment.kind in {"strategy_filter", "strategy"}:
            return index
    return len(segments)


def _split_option(line: str) -> tuple[str, str]:
    if "=" not in line:
        return line, ""
    name, _, value = line.partition("=")
    return name.strip(), value.strip()


def _directive_insert_index(profile: Profile) -> int:
    for index, segment in enumerate(profile.segments):
        if segment.kind not in {"blank", "comment", "directive"}:
            return index
    return len(profile.segments)


def _unique_copy_name(preset: Preset, source: Profile) -> str:
    base = str(source.name or source.display_name or f"profile {source.index + 1}").strip() or "profile"
    base = re.sub(r"\s+копия(?:\s+\d+)?$", "", base, flags=re.IGNORECASE).strip() or base
    existing = {
        str(profile.name or profile.display_name or "").strip().casefold()
        for profile in preset.profiles
        if str(profile.name or profile.display_name or "").strip()
    }
    candidate = f"{base} копия"
    if candidate.casefold() not in existing:
        return candidate
    counter = 2
    while True:
        candidate = f"{base} копия {counter}"
        if candidate.casefold() not in existing:
            return candidate
        counter += 1


def _ensure_profile_boundaries(preset: Preset) -> None:
    for index, profile in enumerate(preset.profiles):
        if index == 0:
            _remove_leading_blank_segments(profile)
            profile.new_line = ""
            continue
        if _profile_has_name_directive(profile):
            profile.new_line = "--new"
            continue
        name = str(profile.name or profile.display_name or f"profile {index + 1}").strip() or f"profile {index + 1}"
        profile.new_line = f"--new={name}"


def _profile_has_name_directive(profile: Profile) -> bool:
    return any(
        segment.kind == "directive" and str(segment.name or "").strip().lower() == "--name"
        for segment in profile.segments
    )


def _ensure_safe_default_strategy(profile: Profile) -> None:
    if profile.engine != ENGINE_WINWS2:
        return
    if any(segment.kind == "strategy" for segment in profile.segments):
        return
    insert_at = len(profile.segments)
    while insert_at > 0 and profile.segments[insert_at - 1].kind == "blank":
        insert_at -= 1
    profile.segments.insert(
        insert_at,
        ProfileSegment(kind="strategy", text="--lua-desync=pass", name="--lua-desync", value="pass"),
    )


def _remove_leading_blank_segments(profile: Profile) -> None:
    while profile.segments and profile.segments[0].kind == "blank":
        del profile.segments[0]


def _rename_profile_copy(profile: Profile, name: str) -> None:
    clean_name = str(name or "").strip() or "profile копия"
    renamed_new_line = False
    current_new_line = str(profile.new_line or "").strip()
    if current_new_line.lower().startswith("--new="):
        profile.new_line = f"--new={clean_name}"
        renamed_new_line = True

    for segment in profile.segments:
        if segment.kind == "directive" and str(segment.name or "").strip().lower() == "--name":
            segment.value = clean_name
            segment.text = f"--name={clean_name}"
            profile.name = clean_name
            profile.display_name = clean_name
            return

    if renamed_new_line:
        profile.name = clean_name
        profile.display_name = clean_name
        return
    profile.new_line = f"--new={clean_name}"
    if current_new_line.lower() not in {"--new"}:
        profile.segments.insert(
            _directive_insert_index(profile),
            ProfileSegment(kind="directive", text=f"--name={clean_name}", name="--name", value=clean_name),
        )
    profile.name = clean_name
    profile.display_name = clean_name


def _reparse(preset: Preset) -> Preset:
    return parse_preset_text(serialize_preset(preset), engine=preset.engine, source_name=preset.source_name)
