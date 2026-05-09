from __future__ import annotations

from log.log import log



def get_profile_strategy_summary(window, max_items: int = 2) -> str:
    try:
        from settings.dpi.strategy_settings import get_strategy_launch_method

        method = (get_strategy_launch_method() or "").strip().lower()
        if method not in ("zapret1_mode", "zapret2_mode"):
            return "Профили"

        from profile.service import ProfilePresetService

        payload = ProfilePresetService(window.app_context, method).list_profiles()
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


def update_current_strategy_display(window, strategy_name: str) -> None:
    store = getattr(window, "ui_state_store", None)
    if store is not None:
        store.set_current_strategy_summary(strategy_name)


def update_autostart_display(window, enabled: bool, strategy_name: str = None) -> None:
    app_runtime_state = getattr(window, "app_runtime_state", None)
    store = getattr(window, "ui_state_store", None)
    if app_runtime_state is not None:
        app_runtime_state.set_autostart(bool(enabled))
    if store is not None:
        if strategy_name:
            store.set_current_strategy_summary(strategy_name)


def update_subscription_display(window, is_premium: bool, days: int = None) -> None:
    store = getattr(window, "ui_state_store", None)
    if store is not None:
        store.set_subscription(is_premium, days)


def on_profile_ui_mode_changed(window, mode: str) -> None:
    """Сообщает UI-слою, что profile UI mode изменился и нужно обновить revision."""
    _ = mode
    try:
        if getattr(window, "ui_state_store", None) is not None:
            window.ui_state_store.bump_mode_revision()
    except Exception:
        pass


def refresh_pages_after_preset_switch(window) -> None:
    """Обновляет краткое отображение активной стратегии после смены source preset."""
    try:
        display_name = get_profile_strategy_summary(window)
        if display_name:
            update_current_strategy_display(window, display_name)
    except Exception as e:
        log(f"Ошибка обновления display стратегии после смены пресета: {e}", "DEBUG")
