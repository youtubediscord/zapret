from __future__ import annotations

from log.log import log



def get_direct_strategy_summary(window, max_items: int = 2) -> str:
    try:
        from settings.dpi.strategy_settings import get_strategy_launch_method
        from direct_preset.facade import DirectPresetFacade

        method = (get_strategy_launch_method() or "").strip().lower()
        if method not in ("direct_zapret1", "direct_zapret2"):
            return "Прямой запуск"

        facade = DirectPresetFacade.from_launch_method(method, app_context=window.app_context)
        selections = facade.get_strategy_selections() or {}
        target_items = facade.get_target_ui_items() or {}
        ordered_targets = sorted(
            target_items.items(),
            key=lambda item: (
                getattr(item[1], "order", 999),
                str(getattr(item[1], "full_name", item[0]) or item[0]).lower(),
                item[0],
            ),
        )

        active_names: list[str] = []
        for target_key, target_info in ordered_targets:
            sid = selections.get(target_key, "none") or "none"
            if sid == "none":
                continue
            active_names.append(getattr(target_info, "full_name", None) or target_key)

        if not active_names:
            return "Не выбрана"
        if len(active_names) <= max_items:
            return " • ".join(active_names)
        return " • ".join(active_names[:max_items]) + f" +{len(active_names) - max_items} ещё"
    except Exception:
        return "Прямой запуск"


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


def on_direct_mode_changed(window, mode: str) -> None:
    """Сообщает UI-слою, что direct mode изменился и нужно обновить revision."""
    _ = mode
    try:
        if getattr(window, "ui_state_store", None) is not None:
            window.ui_state_store.bump_mode_revision()
    except Exception:
        pass


def refresh_pages_after_preset_switch(window) -> None:
    """Обновляет краткое отображение активной стратегии после смены source preset."""
    try:
        display_name = get_direct_strategy_summary(window)
        if display_name:
            update_current_strategy_display(window, display_name)
    except Exception as e:
        log(f"Ошибка обновления display стратегии после смены пресета: {e}", "DEBUG")
