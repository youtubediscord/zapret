from __future__ import annotations

from log.log import log
from settings.mode import is_preset_launch_method


def get_profile_strategy_summary_for_context(app_context, max_items: int = 2) -> str:
    try:
        from settings.dpi.strategy_settings import get_strategy_launch_method

        method = (get_strategy_launch_method() or "").strip().lower()
        if not is_preset_launch_method(method):
            return "Профили"

        from profile.public import list_profiles

        payload = list_profiles(app_context, method)
        active_names = [
            item.display_name
            for item in payload.items
            if item.in_preset and item.enabled and item.strategy_id != "none"
        ]

        if not active_names:
            return "Не выбрана"
        if len(active_names) <= max_items:
            return " • ".join(active_names)
        return " • ".join(active_names[:max_items]) + f" +{len(active_names) - max_items} ещё"
    except Exception:
        return "Профили"


def update_current_strategy_display_in_store(ui_state_store, strategy_name: str) -> None:
    if ui_state_store is not None:
        ui_state_store.set_current_strategy_summary(strategy_name)


def update_autostart_display_state(app_runtime_state, ui_state_store, enabled: bool, strategy_name: str = None) -> None:
    if app_runtime_state is not None:
        app_runtime_state.set_autostart(bool(enabled))
    if ui_state_store is not None and strategy_name:
        ui_state_store.set_current_strategy_summary(strategy_name)


def update_subscription_display_in_store(ui_state_store, is_premium: bool, days: int = None) -> None:
    if ui_state_store is not None:
        ui_state_store.set_subscription(is_premium, days)


def on_profile_ui_mode_changed_in_store(ui_state_store, mode: str) -> None:
    """Сообщает UI-слою, что profile UI mode изменился и нужно обновить revision."""
    _ = mode
    try:
        if ui_state_store is not None:
            ui_state_store.bump_mode_revision()
    except Exception:
        pass


def refresh_pages_after_preset_switch_state(app_context, ui_state_store) -> None:
    """Обновляет краткое отображение активной стратегии после смены source preset."""
    try:
        display_name = get_profile_strategy_summary_for_context(app_context)
        if display_name:
            update_current_strategy_display_in_store(ui_state_store, display_name)
    except Exception as e:
        log(f"Ошибка обновления display стратегии после смены пресета: {e}", "DEBUG")
