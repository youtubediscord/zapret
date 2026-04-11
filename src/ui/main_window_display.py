from __future__ import annotations

from log import log
from ui.page_names import PageName


def get_direct_strategy_summary(window, max_items: int = 2) -> str:
    try:
        from strategy_menu import get_strategy_launch_method
        from core.presets.direct_facade import DirectPresetFacade

        method = (get_strategy_launch_method() or "").strip().lower()
        if method == "direct_zapret2_orchestra":
            from preset_orchestra_zapret2 import PresetManager

            selections = PresetManager().get_strategy_selections() or {}
            active_names = [
                str(target_key or "").strip()
                for target_key, strategy_id in selections.items()
                if str(target_key or "").strip() and (strategy_id or "none") != "none"
            ]

            if not active_names:
                return "Не выбрана"
            if len(active_names) <= max_items:
                return " • ".join(active_names)
            return " • ".join(active_names[:max_items]) + f" +{len(active_names) - max_items} ещё"

        if method not in ("direct_zapret1", "direct_zapret2"):
            return "Прямой запуск"

        facade = DirectPresetFacade.from_launch_method(method)
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


def set_status_text(window, text: str, status: str = "neutral") -> None:
    store = getattr(window, "ui_state_store", None)
    if store is not None:
        store.set_status_message(text, status)


def open_subscription_dialog(window) -> None:
    window.show_page(PageName.PREMIUM)


def on_autostart_enabled(window) -> None:
    log("Автозапуск включён через страницу настроек", "INFO")
    update_autostart_display(window, True)


def on_autostart_disabled(window) -> None:
    log("Автозапуск отключён через страницу настроек", "INFO")
    update_autostart_display(window, False)


def on_subscription_updated(window, is_premium: bool, days_remaining: int) -> None:
    log(f"Статус подписки обновлён: premium={is_premium}, days={days_remaining}", "INFO")
    update_subscription_display(window, is_premium, days_remaining)
