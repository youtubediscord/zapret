from __future__ import annotations

from PyQt6.QtCore import QTimer

from ui.page_names import PageName
from ui.router import resolve_strategy_page_for_method


def get_active_strategy_page_name(window) -> PageName | None:
    return resolve_strategy_page_for_method(window._get_launch_method())


def call_loaded_strategy_page_method(window, method_name: str) -> bool:
    page_name = get_active_strategy_page_name(window)
    if page_name is None:
        return False
    return call_loaded_page_method(window, page_name, method_name)


def call_loaded_page_method(
    window,
    page_name: PageName,
    method_name: str,
    *args,
    delay_ms: int = 0,
) -> bool:
    page = window.get_loaded_page(page_name)
    if page is None:
        return False

    handler = getattr(page, method_name, None)
    if not callable(handler):
        return False

    def _invoke() -> None:
        if bool(getattr(window, "_is_exiting", False) or getattr(window, "_closing_completely", False)):
            return
        try:
            handler(*args)
        except Exception:
            pass

    if int(delay_ms or 0) > 0:
        QTimer.singleShot(int(delay_ms), _invoke)
        return True

    try:
        handler(*args)
        return True
    except Exception:
        return False


def show_active_strategy_page_loading(window) -> bool:
    return call_loaded_strategy_page_method(window, "show_loading")


def show_active_strategy_page_success(window) -> bool:
    return call_loaded_strategy_page_method(window, "show_success")


def dispatch_detail_page_result(
    window,
    page_name: PageName,
    method_name: str,
    *args,
    delay_ms: int = 0,
    log_message: str | None = None,
) -> bool:
    if log_message:
        from log import log

        log(log_message, "INFO")

    return call_loaded_page_method(
        window,
        page_name,
        method_name,
        *args,
        delay_ms=delay_ms,
    )
