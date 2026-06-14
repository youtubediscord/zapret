from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from pathlib import PureWindowsPath

from settings.mode import ENGINE_WINWS1, ENGINE_WINWS2

from .models import Preset, Profile, ProfileSegment
from .parser import parse_preset_text
from .serializer import serialize_preset
from .winws2_transport import parse_out_range_expression


_SERVICE_EXCLUDE_LIST_NAMES = frozenset(
    {
        "ipset-ru.txt",
        "ipset-dns.txt",
        "ipset-exclude.txt",
        "netrogat.txt",
    }
)


@dataclass(frozen=True)
class EditableProfileSettings:
    filter_kind: str = "hostlist"
    filter_value: str = ""
    filter_editable: bool = True
    filter_role: str = "primary"
    in_range: str = "x"
    out_range: str = "a"


def read_editable_profile_settings(profile: Profile) -> EditableProfileSettings:
    return EditableProfileSettings(
        filter_kind=_editable_filter_kind(profile),
        filter_value=_editable_filter_value(profile),
        filter_editable=_editable_filter_is_file_based(profile),
        filter_role=_editable_filter_role(profile),
        in_range=_range_value(profile, "--in-range", default="x"),
        out_range=_range_value(profile, "--out-range", default="a"),
    )


def with_editable_profile_settings(
    preset: Preset,
    profile_index: int,
    settings: EditableProfileSettings,
) -> Preset:
    if preset.engine not in {ENGINE_WINWS1, ENGINE_WINWS2}:
        raise ValueError(f"Unsupported profile preset engine: {preset.engine}")

    updated = deepcopy(preset)
    profile = updated.profiles[int(profile_index)]
    filter_kind = str(settings.filter_kind or "").strip().lower()
    if filter_kind not in {"hostlist", "ipset"}:
        raise ValueError("filter_kind must be hostlist or ipset")
    filter_role = str(settings.filter_role or "primary").strip().lower()
    if filter_role not in {"primary", "exclude"}:
        filter_role = _editable_filter_role(profile)

    if _editable_filter_is_file_based(profile):
        filter_value = normalize_filter_value(settings.filter_value, filter_kind, filter_role=filter_role)
        if not filter_value:
            raise ValueError("filter_value must not be empty")
        filter_lines = [f"--{_filter_option_name(filter_kind, filter_role)}={value}" for value in _split_filter_values(filter_value)]
        if filter_role == "exclude":
            profile.segments = _replace_exclude_match_filters(profile.segments, filter_lines)
        else:
            profile.segments = _replace_primary_match_filter(profile.segments, filter_lines[0])

    if preset.engine == ENGINE_WINWS2:
        range_lines = _canonical_range_lines(settings.in_range, settings.out_range)
        profile.segments = _replace_range_filters(profile.segments, range_lines)

    return _reparse(updated)


def with_editable_profile(profile: Profile, settings: EditableProfileSettings) -> Profile:
    preset = Preset(
        engine=profile.engine,
        header_lines=[],
        preamble_lines=[],
        profiles=[deepcopy(profile)],
    )
    return with_editable_profile_settings(preset, 0, settings).profiles[0]


def _editable_filter_kind(profile: Profile) -> str:
    if profile.match.hostlist_lines:
        return "hostlist"
    if profile.match.ipset_lines:
        return "ipset"
    if profile.match.hostlist_exclude_lines:
        return "hostlist"
    if profile.match.ipset_exclude_lines:
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
        profile.match.hostlist_exclude_lines,
        profile.match.ipset_exclude_lines,
    ):
        values = [line.split("=", 1)[1].strip() for line in lines if "=" in line]
        if values:
            return ",".join(values)
    return ""


def _editable_filter_is_file_based(profile: Profile) -> bool:
    if _editable_filter_role(profile) == "exclude":
        return True
    for segment in profile.segments:
        name = str(segment.name or "").strip().lower()
        if segment.kind == "match" and name in {"--hostlist", "--ipset", "--hostlist-exclude", "--ipset-exclude"}:
            return True
        if segment.kind == "match" and name in {
            "--hostlist-domains",
            "--ipset-ip",
            "--hostlist-exclude-domains",
            "--ipset-exclude-ip",
        }:
            return False
    return False


def _editable_filter_role(profile: Profile) -> str:
    if _is_service_exclusion_profile(profile):
        return "exclude"
    return "primary"


def _is_service_exclusion_profile(profile: Profile) -> bool:
    if not (profile.match.hostlist_exclude_lines or profile.match.ipset_exclude_lines):
        return False
    if profile.match.hostlist_lines or profile.match.ipset_lines:
        return False

    text_parts = [
        str(getattr(profile, "name", "") or ""),
        str(getattr(profile, "display_name", "") or ""),
    ]
    if "исключ" in " ".join(text_parts).casefold():
        return True

    for line in (*profile.match.hostlist_exclude_lines, *profile.match.ipset_exclude_lines):
        _option, _separator, value = str(line or "").partition("=")
        for part in value.split(","):
            file_name = PureWindowsPath(part.strip().strip('"').strip("'").lstrip("@")).name.lower()
            if file_name in _SERVICE_EXCLUDE_LIST_NAMES:
                return True
    return False


def _range_value(profile: Profile, option_name: str, *, default: str) -> str:
    if profile.engine != ENGINE_WINWS2:
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
    strategy_insert_at: int | None = None

    for segment in segments:
        name = str(segment.name or "").strip().lower()
        if segment.kind == "match" and name in primary_names:
            if not inserted:
                result.append(ProfileSegment(kind="match", text=filter_line, name=filter_name, value=filter_value))
                inserted = True
            continue
        if strategy_insert_at is None and segment.kind in {"strategy_filter", "strategy"}:
            strategy_insert_at = len(result)
        result.append(segment)

    if not inserted:
        insert_at = strategy_insert_at if strategy_insert_at is not None else len(result)
        result.insert(insert_at, ProfileSegment(kind="match", text=filter_line, name=filter_name, value=filter_value))
    return result


def _replace_exclude_match_filters(segments: list[ProfileSegment], filter_lines: list[str]) -> list[ProfileSegment]:
    exclude_names = {"--hostlist-exclude", "--hostlist-exclude-domains", "--ipset-exclude", "--ipset-exclude-ip"}
    inserted = False
    result: list[ProfileSegment] = []
    strategy_insert_at: int | None = None

    replacement_segments = []
    for line in filter_lines:
        name, value = _split_option(line)
        replacement_segments.append(ProfileSegment(kind="match", text=line, name=name, value=value))

    for segment in segments:
        name = str(segment.name or "").strip().lower()
        if segment.kind == "match" and name in exclude_names:
            if not inserted:
                result.extend(replacement_segments)
                inserted = True
            continue
        if strategy_insert_at is None and segment.kind in {"strategy_filter", "strategy"}:
            strategy_insert_at = len(result)
        result.append(segment)

    if not inserted:
        insert_at = strategy_insert_at if strategy_insert_at is not None else len(result)
        result[insert_at:insert_at] = replacement_segments
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


def _canonical_range_line(option_name: str, value: str) -> str:
    parsed = parse_out_range_expression(value, raw_line=f"{option_name}={value}")
    if parsed is None:
        raise ValueError(f"Invalid {ENGINE_WINWS2} packet range value: {value}")
    return f"{option_name}={parsed.expression}"


def _canonical_range_lines(in_range: str, out_range: str) -> list[str]:
    in_line = _canonical_range_line("--in-range", in_range)
    out_line = _canonical_range_line("--out-range", out_range)

    lines: list[str] = []
    if _range_expression(in_line) != "x":
        lines.append(in_line)
    if _range_expression(out_line) != "a":
        lines.append(out_line)
    return lines


def _range_expression(line: str) -> str:
    _name, _sep, value = str(line or "").partition("=")
    return value.strip().lower()


def normalize_filter_value(value: str, filter_kind: str, *, filter_role: str = "primary") -> str:
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


def _filter_option_name(filter_kind: str, filter_role: str) -> str:
    if filter_role == "exclude":
        return f"{filter_kind}-exclude"
    return filter_kind


def _split_filter_values(filter_value: str) -> list[str]:
    return [part.strip() for part in str(filter_value or "").split(",") if part.strip()]


def _normalize_single_filter_value_for_kind(value: str, filter_kind: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""

    return raw


def _split_option(line: str) -> tuple[str, str]:
    if "=" not in line:
        return line, ""
    name, _, value = line.partition("=")
    return name.strip(), value.strip()


def _reparse(preset: Preset) -> Preset:
    return parse_preset_text(serialize_preset(preset), engine=preset.engine, source_name=preset.source_name)
