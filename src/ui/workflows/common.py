from __future__ import annotations

from app.page_names import PageName
from ui.window_adapter import ensure_page, show_page


def get_current_launch_method(*, default: str = "") -> str:
    from settings.dpi.launch_method import get_current_launch_method as _get_current_launch_method

    return _get_current_launch_method(default=default)


def open_preset_raw_editor_page(window, page_name: PageName, preset_name: str, *, allow_internal: bool) -> None:
    page = ensure_page(window, page_name)
    if page is None:
        return
    try:
        page.set_preset_file_name(preset_name)
    except Exception:
        return
    show_page(window, page_name, allow_internal=allow_internal)


__all__ = [
    "get_current_launch_method",
    "open_preset_raw_editor_page",
]
