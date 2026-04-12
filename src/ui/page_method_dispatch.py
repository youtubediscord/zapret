from __future__ import annotations

from PyQt6.QtCore import QTimer

from ui.navigation_targets import resolve_strategy_page_for_method
from ui.page_contracts import PageMethodName, get_page_method
from ui.page_names import PageName

def call_loaded_page_method(
    window,
    page_name: PageName,
    method_name: str,
    *args,
    delay_ms: int = 0,
) -> bool:
    page_host = getattr(window, "_page_host", None)
    if page_host is None:
        return False

    page = page_host.get_loaded_page(page_name)
    if page is None:
        return False

    handler = get_page_method(page, method_name)
    if handler is None:
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
    page_name = resolve_strategy_page_for_method(window._get_launch_method())
    if page_name is None:
        return False
    return call_loaded_page_method(window, page_name, PageMethodName.SHOW_LOADING)


def show_active_strategy_page_success(window) -> bool:
    page_name = resolve_strategy_page_for_method(window._get_launch_method())
    if page_name is None:
        return False
    return call_loaded_page_method(window, page_name, PageMethodName.SHOW_SUCCESS)


def switch_page_tab(window, page_name: PageName, tab_key: str) -> bool:
    return call_loaded_page_method(
        window,
        page_name,
        PageMethodName.SWITCH_TO_TAB,
        tab_key,
    )


def request_blockcheck_diagnostics_focus(window) -> bool:
    return call_loaded_page_method(
        window,
        PageName.BLOCKCHECK,
        PageMethodName.REQUEST_DIAGNOSTICS_START_FOCUS,
    )


def close_page_transient_overlays(window, page_name: PageName) -> bool:
    return call_loaded_page_method(
        window,
        page_name,
        PageMethodName.CLOSE_TRANSIENT_OVERLAYS,
    )


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
