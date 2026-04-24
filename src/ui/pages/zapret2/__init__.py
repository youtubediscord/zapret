"""Ленивые экспорты Zapret2 UI pages."""

from __future__ import annotations

from importlib import import_module


_PAGE_EXPORTS: dict[str, tuple[str, str]] = {
    "Zapret2DirectControlPage": ("direct_preset.ui.control.zapret2.page", "Zapret2DirectControlPage"),
    "Zapret2StrategiesPageNew": ("filters.ui.filter_list.zapret2.targets_page", "Zapret2StrategiesPageNew"),
    "StrategyDetailPage": ("filters.ui.filter_list.zapret2.strategy_detail_page", "StrategyDetailPage"),
    "Zapret2PresetDetailPage": ("direct_preset.ui.zapret2.preset_detail_page", "Zapret2PresetDetailPage"),
    "Zapret2UserPresetsPage": ("direct_preset.ui.zapret2.user_presets_page", "Zapret2UserPresetsPage"),
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
