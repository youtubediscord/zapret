from __future__ import annotations

from app.page_names import PageName
from ui.window_ui_session import get_window_ui_session


def _get_loaded_page(window, page_name: PageName):
    session = get_window_ui_session(window)
    if session is None:
        return None
    return session.page_host.get_loaded_page(page_name)


def switch_page_tab(window, page_name: PageName, tab_key: str) -> bool:
    page = _get_loaded_page(window, page_name)
    if page is None:
        return False
    try:
        page.switch_to_tab(tab_key)
        return True
    except Exception:
        return False


def request_blockcheck_diagnostics_focus(window) -> bool:
    page = _get_loaded_page(window, PageName.BLOCKCHECK)
    if page is None:
        return False
    try:
        page.request_diagnostics_start_focus()
        return True
    except Exception:
        return False


__all__ = [
    "request_blockcheck_diagnostics_focus",
    "switch_page_tab",
]
