from __future__ import annotations

from dataclasses import dataclass

from .models import Profile, build_profile_logical_key


@dataclass(frozen=True)
class ProfileListSource:
    key: str
    profile: Profile
    in_preset: bool
    order: int


def build_profile_list_sources(
    preset_profiles: tuple[Profile, ...],
    templates: dict[str, Profile],
) -> tuple[ProfileListSource, ...]:
    groups: dict[str, list[ProfileListSource]] = {}

    for profile in preset_profiles:
        source = ProfileListSource(
            key=profile.key,
            profile=profile,
            in_preset=True,
            order=profile.index,
        )
        groups.setdefault(_logical_profile_key(profile), []).append(source)

    template_order = len(preset_profiles)
    for template_id, profile in templates.items():
        source = ProfileListSource(
            key=f"template:{template_id}",
            profile=profile,
            in_preset=False,
            order=template_order + profile.index,
        )
        groups.setdefault(_logical_profile_key(profile), []).append(source)

    selected = [_select_source(candidates) for candidates in groups.values()]
    selected.sort(key=lambda source: (source.order, source.profile.display_name.lower(), source.key))
    return tuple(selected)


def _logical_profile_key(profile: Profile) -> str:
    key = build_profile_logical_key(profile.match_signature)
    return key or str(profile.match_signature or profile.key)


def _select_source(candidates: list[ProfileListSource]) -> ProfileListSource:
    preset_sources = [source for source in candidates if source.in_preset]
    if preset_sources:
        preset_sources.sort(key=lambda source: (not source.profile.enabled, source.profile.index))
        return preset_sources[0]

    candidates.sort(key=lambda source: (_template_kind_rank(source.profile), source.order))
    return candidates[0]


def _template_kind_rank(profile: Profile) -> int:
    if profile.match.hostlist_lines:
        return 0
    if profile.match.ipset_lines:
        return 1
    return 2
