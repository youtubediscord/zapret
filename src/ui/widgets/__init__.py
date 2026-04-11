"""Ленивые экспорты UI-виджетов.

Важно: пакет `ui.widgets` не должен eagerly импортировать все виджеты сразу.
Некоторые из них тянут дополнительные Fluent/Qt зависимости и сложные helper-модули,
поэтому безопаснее отдавать конкретный виджет только по запросу.
"""

from __future__ import annotations

from importlib import import_module


_WIDGET_EXPORTS: dict[str, tuple[str, str]] = {
    "strategies_tooltip_manager": (".strategies_tooltip", "strategies_tooltip_manager"),
    "StrategiesListTooltip": (".strategies_tooltip", "StrategiesListTooltip"),
    "NotificationBanner": (".notification_banner", "NotificationBanner"),
    "Win11Spinner": (".win11_spinner", "Win11Spinner"),
    "FilterButtonGroup": (".filter_chip_button", "FilterButtonGroup"),
    "CollapsibleGroup": (".collapsible_group", "CollapsibleGroup"),
    "StrategyRadioItem": (".strategy_radio_item", "StrategyRadioItem"),
    "PresetTargetsList": (".preset_targets_list", "PresetTargetsList"),
    "UnifiedStrategiesList": (".unified_strategies_list", "UnifiedStrategiesList"),
}

__all__ = list(_WIDGET_EXPORTS)


def __getattr__(name: str):
    spec = _WIDGET_EXPORTS.get(name)
    if spec is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    module_name, attr_name = spec
    module = import_module(module_name, __name__)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
