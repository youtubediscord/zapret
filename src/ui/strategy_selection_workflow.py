from __future__ import annotations

from PyQt6.QtWidgets import QWidget

from ui.window_display_state import (
    get_direct_strategy_summary,
    update_current_strategy_display,
)
from ui.navigation_targets import resolve_strategy_page_for_method
from ui.window_adapter import get_loaded_page


def get_strategy_selection_source_page(window, launch_method: str | None) -> QWidget | None:
    page_name = resolve_strategy_page_for_method(launch_method)
    if page_name is None:
        return None
    return get_loaded_page(window, page_name)


def resolve_strategy_selection_display_name(
    window,
    launch_method: str | None,
    sender,
    strategy_name: str,
) -> str:
    normalized = str(launch_method or "").strip().lower()
    if normalized == "direct_zapret2" and sender is get_strategy_selection_source_page(window, normalized):
        return get_direct_strategy_summary(window)
    return strategy_name


def on_strategy_selected_from_page(window, strategy_id: str, strategy_name: str) -> None:
    from log.log import log


    launch_method = window._get_launch_method()

    sender = None
    try:
        sender = window.sender()
    except Exception:
        sender = None

    display_name = resolve_strategy_selection_display_name(
        window,
        launch_method,
        sender,
        strategy_name,
    )
    if display_name != strategy_name:
        update_current_strategy_display(window, display_name)
        return

    log(f"Стратегия выбрана из страницы: {strategy_id} - {strategy_name}", "INFO")
    update_current_strategy_display(window, strategy_name)
