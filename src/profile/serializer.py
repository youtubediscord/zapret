from __future__ import annotations

from copy import deepcopy

from .models import EngineName, Preset, Profile, ProfileSegment
from .parser import parse_preset_text


_STRATEGY_KINDS = {"strategy", "strategy_filter"}


def serialize_preset(preset: Preset) -> str:
    lines: list[str] = []
    lines.extend(preset.header_lines)
    lines.extend(preset.preamble_lines)

    for profile in preset.profiles:
        if profile.new_line:
            lines.append(profile.new_line)
        for segment in profile.segments:
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
    profile.segments = [*kept[:insert_at], *replacement_segments, *kept[insert_at:]]
    return _reparse(updated)


def _preserve_missing_winws2_strategy_filters(engine: EngineName, profile: Profile, strategy_lines: list[str]) -> list[str]:
    if engine != "winws2":
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


def append_profile_from_template(preset: Preset, template: Profile, *, enabled: bool = True) -> Preset:
    updated = deepcopy(preset)
    if getattr(updated, "footer_lines", None):
        updated.footer_lines = []
    if updated.profiles and updated.profiles[-1].segments and updated.profiles[-1].segments[-1].text.strip():
        updated.profiles[-1].segments.append(ProfileSegment(kind="blank", text=""))
    profile = deepcopy(template)
    profile.index = len(updated.profiles)
    profile.engine = updated.engine
    profile.new_line = "--new"
    profile.segments = [
        segment
        for segment in profile.segments
        if not (segment.kind == "directive" and segment.text.strip().lower() == "--skip")
    ]
    if not enabled:
        profile.segments.insert(_directive_insert_index(profile), ProfileSegment(kind="directive", text="--skip", name="--skip"))
    updated.profiles.append(profile)
    return _reparse(updated)


def _segment_for_strategy_line(engine: EngineName, line: str) -> ProfileSegment:
    lowered = line.lower()
    if engine == "winws2" and (
        lowered.startswith("--payload=")
        or lowered.startswith("--in-range")
        or lowered.startswith("--out-range")
    ):
        name, value = _split_option(line)
        return ProfileSegment(kind="strategy_filter", text=line, name=name, value=value)
    name, value = _split_option(line)
    return ProfileSegment(kind="strategy", text=line, name=name, value=value)


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


def _reparse(preset: Preset) -> Preset:
    return parse_preset_text(serialize_preset(preset), engine=preset.engine, source_name=preset.source_name)
