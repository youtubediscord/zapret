"""Ленивые экспорты Zapret1 UI pages."""

from __future__ import annotations

from importlib import import_module


_PAGE_EXPORTS: dict[str, tuple[str, str]] = {
    "Zapret1DirectControlPage": ("direct_control.zapret1.page", "Zapret1DirectControlPage"),
    "Zapret1StrategiesPage": ("filters.pages.direct_zapret1_targets_page", "Zapret1StrategiesPage"),
    "Zapret1UserPresetsPage": ("preset_zapret1.ui.user_presets_page", "Zapret1UserPresetsPage"),
    "Zapret1StrategyDetailPage": ("filters.strategy_detail.zapret1.page", "Zapret1StrategyDetailPage"),
    "Zapret1PresetDetailPage": ("preset_zapret1.ui.preset_detail_page", "Zapret1PresetDetailPage"),
}

__all__ = list(_PAGE_EXPORTS)


def __getattr__(name: str):
    spec = _PAGE_EXPORTS.get(name)
    if spec is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    module_name, attr_name = spec
    module = import_module(module_name, __name__)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
