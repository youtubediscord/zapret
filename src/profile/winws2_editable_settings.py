from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from pathlib import PureWindowsPath

from .models import Preset, Profile, ProfileSegment
from .parser import parse_preset_text
from .serializer import serialize_preset
from .winws2_transport import parse_out_range_expression


@dataclass(frozen=True)
class Winws2EditableSettings:
    filter_kind: str = "hostlist"
    filter_value: str = ""
    filter_editable: bool = True
    in_range: str = "x"
    out_range: str = "a"


def read_winws2_editable_settings(profile: Profile) -> Winws2EditableSettings:
    return Winws2EditableSettings(
        filter_kind=_editable_filter_kind(profile),
        filter_value=_editable_filter_value(profile),
        filter_editable=_editable_filter_is_file_based(profile),
        in_range=_range_value(profile, "--in-range", default="x"),
        out_range=_range_value(profile, "--out-range", default="a"),
    )


def with_winws2_editable_settings(
    preset: Preset,
    profile_index: int,
    settings: Winws2EditableSettings,
) -> Preset:
    if preset.engine != "winws2":
        raise ValueError("winws2 editable settings are available only for winws2 presets")

    updated = deepcopy(preset)
    profile = updated.profiles[int(profile_index)]
    filter_kind = str(settings.filter_kind or "").strip().lower()
    if filter_kind not in {"hostlist", "ipset"}:
        raise ValueError("filter_kind must be hostlist or ipset")

    in_line = _canonical_range_line("--in-range", settings.in_range, default_value="x")
    out_line = _canonical_range_line("--out-range", settings.out_range, default_value="a")

    if _editable_filter_is_file_based(profile):
        filter_value = normalize_winws2_filter_value(settings.filter_value, filter_kind)
        if not filter_value:
            raise ValueError("filter_value must not be empty")
        filter_line = f"--{filter_kind}={filter_value}"
        profile.segments = _replace_primary_match_filter(profile.segments, filter_line)
    profile.segments = _replace_range_filters(profile.segments, [in_line, out_line])
    return _reparse(updated)


def _editable_filter_kind(profile: Profile) -> str:
    if profile.match.hostlist_lines:
        return "hostlist"
    if profile.match.ipset_lines:
        return "ipset"
    if profile.match.hostlist_domains_lines:
        return "hostlist-domains"
    if profile.match.inline_ipset_lines:
        return "ipset-ip"
    return "hostlist"


def _editable_filter_value(profile: Profile) -> str:
    for lines in (
        profile.match.hostlist_lines,
        profile.match.hostlist_domains_lines,
        profile.match.ipset_lines,
        profile.match.inline_ipset_lines,
    ):
        for line in lines:
            if "=" in line:
                return line.split("=", 1)[1].strip()
    return ""


def _editable_filter_is_file_based(profile: Profile) -> bool:
    for segment in profile.segments:
        name = str(segment.name or "").strip().lower()
        if segment.kind == "match" and name in {"--hostlist", "--ipset"}:
            return True
        if segment.kind == "match" and name in {"--hostlist-domains", "--ipset-ip"}:
            return False
    return True


def _range_value(profile: Profile, option_name: str, *, default: str) -> str:
    if profile.engine != "winws2":
        return default
    wanted = str(option_name or "").strip().lower()
    for segment in profile.segments:
        name = str(segment.name or "").strip().lower()
        if segment.kind == "strategy_filter" and name == wanted:
            return str(segment.value or "").strip() or default
    return default


def _replace_primary_match_filter(segments: list[ProfileSegment], filter_line: str) -> list[ProfileSegment]:
    filter_name, filter_value = _split_option(filter_line)
    primary_names = {"--hostlist", "--hostlist-domains", "--ipset", "--ipset-ip"}
    inserted = False
    result: list[ProfileSegment] = []
    fallback_insert_at: int | None = None

    for segment in segments:
        name = str(segment.name or "").strip().lower()
        if segment.kind == "match" and name in primary_names:
            if not inserted:
                result.append(ProfileSegment(kind="match", text=filter_line, name=filter_name, value=filter_value))
                inserted = True
            continue
        if fallback_insert_at is None and segment.kind in {"strategy_filter", "strategy"}:
            fallback_insert_at = len(result)
        result.append(segment)

    if not inserted:
        insert_at = fallback_insert_at if fallback_insert_at is not None else len(result)
        result.insert(insert_at, ProfileSegment(kind="match", text=filter_line, name=filter_name, value=filter_value))
    return result


def _replace_range_filters(segments: list[ProfileSegment], range_lines: list[str]) -> list[ProfileSegment]:
    range_names = {"--in-range", "--out-range"}
    range_segments = []
    for line in range_lines:
        name, value = _split_option(line)
        range_segments.append(ProfileSegment(kind="strategy_filter", text=line, name=name, value=value))

    result: list[ProfileSegment] = []
    insert_at: int | None = None
    for segment in segments:
        name = str(segment.name or "").strip().lower()
        if segment.kind == "strategy_filter" and name in range_names:
            if insert_at is None:
                insert_at = len(result)
            continue
        if insert_at is None and segment.kind == "strategy":
            insert_at = len(result)
        result.append(segment)

    if insert_at is None:
        insert_at = len(result)
    return [*result[:insert_at], *range_segments, *result[insert_at:]]


def _canonical_range_line(option_name: str, value: str, *, default_value: str) -> str:
    parsed = parse_out_range_expression(value, raw_line=f"{option_name}={value}")
    if parsed is None:
        parsed = parse_out_range_expression(default_value, raw_line=f"{option_name}={default_value}")
    if parsed is None:
        raise ValueError(f"Invalid winws2 packet range value: {value}")
    return f"{option_name}={parsed.expression}"


def normalize_winws2_filter_value(value: str, filter_kind: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    if "," in raw:
        return ",".join(
            part
            for part in (_normalize_single_filter_value_for_kind(item, filter_kind) for item in raw.split(","))
            if part
        )
    return _normalize_single_filter_value_for_kind(raw, filter_kind)


def _normalize_single_filter_value_for_kind(value: str, filter_kind: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""

    path = PureWindowsPath(raw)
    name = path.name
    if not name:
        return raw

    suffix = "".join(path.suffixes)
    stem = name[: -len(suffix)] if suffix else name
    normalized_stem = stem.lower()

    if filter_kind == "ipset":
        if normalized_stem.startswith(("ipset-", "ipset_")):
            return raw
        new_name = f"ipset-{stem}{suffix}"
    else:
        if normalized_stem.startswith(("ipset-", "ipset_")):
            new_name = f"{stem[6:]}{suffix}"
        else:
            return raw

    parent = str(path.parent)
    if not parent or parent == ".":
        return new_name
    separator = "\\" if "\\" in raw else "/"
    return f"{parent}{separator}{new_name}"


def _split_option(line: str) -> tuple[str, str]:
    if "=" not in line:
        return line, ""
    name, _, value = line.partition("=")
    return name.strip(), value.strip()


def _reparse(preset: Preset) -> Preset:
    return parse_preset_text(serialize_preset(preset), engine=preset.engine, source_name=preset.source_name)
