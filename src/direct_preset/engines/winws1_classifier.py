from __future__ import annotations

from ..common.source_preset_models import FilterProfile


def classify(profile: FilterProfile) -> tuple[str, ...]:
    return tuple(profile.canonical_target_keys or ())
