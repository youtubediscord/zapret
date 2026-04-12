from __future__ import annotations

from ui.page_contracts import PageMethodName, get_page_method
from ui.page_names import PageName
from ui.window_adapter import ensure_window_adapter

def call_page_method(page, method_name: str, *args) -> bool:
    if page is None:
        return False
    handler = get_page_method(page, method_name)
    if handler is None:
        return False
    try:
        handler(*args)
        return True
    except Exception:
        return False


def refresh_page_if_possible(window, page_name: PageName) -> None:
    page = ensure_window_adapter(window).ensure_page(page_name)
    if page is None:
        return
    call_page_method(page, PageMethodName.REFRESH_PRESETS_VIEW)


def refresh_or_show_page_after_refresh_if_possible(
    window,
    page_name: PageName,
    *,
    show_page_after_refresh: bool,
    allow_internal: bool,
) -> None:
    refresh_page_if_possible(window, page_name)
    if show_page_after_refresh:
        ensure_window_adapter(window).show_page(page_name, allow_internal=allow_internal)


def get_current_launch_method(*, default: str = "") -> str:
    try:
        from settings.dpi.strategy_settings import get_strategy_launch_method

        return str(get_strategy_launch_method() or "").strip().lower()
    except Exception:
        return str(default or "").strip().lower()


def open_preset_detail_page(window, page_name: PageName, preset_name: str, *, allow_internal: bool) -> None:
    page = ensure_window_adapter(window).ensure_page(page_name)
    if page is None:
        return
    call_page_method(page, PageMethodName.SET_PRESET_FILE_NAME, preset_name)
    ensure_window_adapter(window).show_page(page_name, allow_internal=allow_internal)


__all__ = [
    "call_page_method",
    "get_current_launch_method",
    "open_preset_detail_page",
    "refresh_or_show_page_after_refresh_if_possible",
    "refresh_page_if_possible",
]
