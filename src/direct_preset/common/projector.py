from __future__ import annotations

from .source_preset_models import PresetTargetView, TargetContext


def build_target_views(contexts: dict[str, TargetContext]) -> list[PresetTargetView]:
    views = [
        PresetTargetView(target_key=ctx.target_key, display_name=ctx.display_name)
        for ctx in contexts.values()
    ]
    return sorted(views, key=lambda item: (item.display_name.lower(), item.target_key))
