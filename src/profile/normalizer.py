from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass

from .models import Preset, Profile, ProfileSegment
from .parser import parse_preset_text
from .serializer import serialize_preset


_PRIMARY_LIST_NAMES = {"--hostlist", "--ipset"}
_EXCLUDE_LIST_NAMES = {
    "--hostlist-exclude",
    "--hostlist-exclude-domains",
    "--ipset-exclude",
    "--ipset-exclude-ip",
}
_NAME_DIRECTIVE_NAMES = {"--name", "--comment"}


@dataclass(frozen=True)
class ProfileNormalizationResult:
    preset: Preset
    changed: bool = False
    split_profile_count: int = 0
    created_profile_count: int = 0


def normalize_preset_profiles(preset: Preset) -> ProfileNormalizationResult:
    """Разделяет profile-ы, где несколько обычных hostlist/ipset.

    Исключения не копируются в разрезанные profile-ы: после появления обычного
    hostlist/ipset profile и так применяется только к выбранному списку.
    """

    profiles: list[Profile] = []
    split_profile_count = 0
    created_profile_count = 0

    for profile in tuple(preset.profiles or ()):
        primary_segments = _primary_list_segments(profile)
        if len(primary_segments) <= 1:
            profiles.append(profile)
            continue

        split_profile_count += 1
        created_profile_count += len(primary_segments) - 1
        for primary_index, primary_segment in enumerate(primary_segments):
            profiles.append(_profile_with_single_primary_list(profile, primary_segment, is_first=primary_index == 0))

    if split_profile_count <= 0:
        return ProfileNormalizationResult(preset=preset)

    updated = deepcopy(preset)
    updated.profiles = profiles
    reparsed = parse_preset_text(
        serialize_preset(updated),
        engine=updated.engine,
        source_name=updated.source_name,
    )
    return ProfileNormalizationResult(
        preset=reparsed,
        changed=True,
        split_profile_count=split_profile_count,
        created_profile_count=created_profile_count,
    )


def _profile_with_single_primary_list(profile: Profile, primary_segment: ProfileSegment, *, is_first: bool) -> Profile:
    updated = deepcopy(profile)
    updated.new_line = "" if is_first and not str(profile.new_line or "").strip() else "--new"
    updated.name = ""
    updated.display_name = ""
    updated.segments = _segments_with_single_primary_list(profile.segments, primary_segment)
    return updated


def _segments_with_single_primary_list(
    segments: list[ProfileSegment],
    primary_segment: ProfileSegment,
) -> list[ProfileSegment]:
    result: list[ProfileSegment] = []
    insert_at: int | None = None

    for segment in segments:
        name = _segment_name(segment)
        if segment.kind == "directive" and name in _NAME_DIRECTIVE_NAMES:
            continue
        if segment.kind == "match" and name in _EXCLUDE_LIST_NAMES:
            continue
        if segment.kind == "match" and name in _PRIMARY_LIST_NAMES:
            if insert_at is None:
                insert_at = len(result)
            continue
        result.append(segment)

    if insert_at is None:
        insert_at = len(result)
    result.insert(insert_at, deepcopy(primary_segment))
    return result


def _primary_list_segments(profile: Profile) -> list[ProfileSegment]:
    return [
        segment
        for segment in tuple(profile.segments or ())
        if segment.kind == "match" and _segment_name(segment) in _PRIMARY_LIST_NAMES
    ]


def _segment_name(segment: ProfileSegment) -> str:
    return str(getattr(segment, "name", "") or "").strip().lower()
