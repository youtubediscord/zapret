from __future__ import annotations

from ui.navigation.search import route_search_result, update_titlebar_search_width
from ui.page_names import PageName
from ui.window_display_state import update_current_strategy_display


def show_page(window, page_name: PageName, *, allow_internal: bool = False) -> bool:
    page_host = getattr(window, "_page_host", None)
    if page_host is None:
        return False
    return page_host.show_page(page_name, allow_internal=allow_internal)


def ensure_page(window, page_name: PageName):
    page_host = getattr(window, "_page_host", None)
    if page_host is None:
        return None
    return page_host.ensure_page(page_name)


def get_loaded_page(window, page_name: PageName):
    page_host = getattr(window, "_page_host", None)
    if page_host is None:
        return None
    return page_host.get_loaded_page(page_name)


def sync_titlebar_search_width(window) -> None:
    update_titlebar_search_width(window)


def route_window_search_result(window, page_name: PageName, tab_key: str = "") -> bool:
    return route_search_result(window, page_name, tab_key)


def persist_window_geometry(window) -> None:
    controller = getattr(window, "window_geometry_controller", None)
    if controller is not None:
        controller.persist_now(force=True)


def release_input_interaction_states(window) -> None:
    releaser = getattr(window, "_release_input_interaction_states", None)
    if callable(releaser):
        releaser()


def hide_window(window) -> None:
    window.hide()


def show_window(window) -> None:
    controller = getattr(window, "window_geometry_controller", None)
    window.show()
    window.showNormal()
    if controller is not None:
        controller.request_zoom_state(controller.remembered_zoom_state())
    window.raise_()
    window.activateWindow()


def request_exit(window, *, stop_dpi: bool) -> None:
    requester = getattr(window, "request_exit", None)
    if callable(requester):
        requester(stop_dpi=bool(stop_dpi))


def update_window_current_strategy_display(window, strategy_name: str) -> None:
    update_current_strategy_display(window, strategy_name)


__all__ = [
    "ensure_page",
    "get_loaded_page",
    "hide_window",
    "persist_window_geometry",
    "release_input_interaction_states",
    "request_exit",
    "route_window_search_result",
    "show_page",
    "show_window",
    "sync_titlebar_search_width",
    "update_window_current_strategy_display",
]
