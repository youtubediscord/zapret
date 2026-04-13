from __future__ import annotations

from ui.page_contracts import PageMethodName, get_page_method
from ui.page_names import PageName
from ui.window_adapter import ensure_page, show_page

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


def get_current_launch_method(*, default: str = "") -> str:
    try:
        from settings.dpi.strategy_settings import get_strategy_launch_method

        return str(get_strategy_launch_method() or "").strip().lower()
    except Exception:
        return str(default or "").strip().lower()


def open_preset_detail_page(window, page_name: PageName, preset_name: str, *, allow_internal: bool) -> None:
    page = ensure_page(window, page_name)
    if page is None:
        return
    call_page_method(page, PageMethodName.SET_PRESET_FILE_NAME, preset_name)
    show_page(window, page_name, allow_internal=allow_internal)


__all__ = [
    "call_page_method",
    "get_current_launch_method",
    "open_preset_detail_page",
]
