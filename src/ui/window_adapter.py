from __future__ import annotations

from ui.window_display_state import update_current_strategy_display
from ui.page_names import PageName


class WindowUiAdapter:
    """Временный совместимый facade для window-level UI API.

    Это не второй источник истины и не новая архитектура сам по себе.
    Он только даёт внешним use-site'ам стабильную точку входа, пока реальным
    владельцем поведения становятся ui_root/page_host/navigation_controller.
    """

    def __init__(self, window):
        self._window = window

    def show_page(self, page_name: PageName, *, allow_internal: bool = False) -> bool:
        page_host = getattr(self._window, "_page_host", None)
        if page_host is None:
            return False
        return page_host.show_page(page_name, allow_internal=allow_internal)

    def ensure_page(self, page_name: PageName):
        page_host = getattr(self._window, "_page_host", None)
        if page_host is None:
            return None
        return page_host.ensure_page(page_name)

    def get_loaded_page(self, page_name: PageName):
        page_host = getattr(self._window, "_page_host", None)
        if page_host is None:
            return None
        return page_host.get_loaded_page(page_name)

    @property
    def pages(self):
        page_host = getattr(self._window, "_page_host", None)
        if page_host is None:
            return {}
        return page_host.pages

    def update_titlebar_search_width(self) -> None:
        from ui.navigation.navigation_controller import ensure_navigation_controller

        ensure_navigation_controller(self._window).update_titlebar_search_width()

    def route_search_result(self, page_name: PageName, tab_key: str = "") -> bool:
        from ui.navigation.navigation_controller import ensure_navigation_controller

        return ensure_navigation_controller(self._window).route_search_result(page_name, tab_key)

    def persist_window_geometry(self) -> None:
        controller = getattr(self._window, "window_geometry_controller", None)
        if controller is not None:
            controller.persist_now(force=True)

    def release_input_interaction_states(self) -> None:
        releaser = getattr(self._window, "_release_input_interaction_states", None)
        if callable(releaser):
            releaser()

    def hide_window(self) -> None:
        self._window.hide()

    def show_window(self) -> None:
        controller = getattr(self._window, "window_geometry_controller", None)
        self._window.show()
        self._window.showNormal()
        if controller is not None:
            controller.request_zoom_state(controller.remembered_zoom_state())
        self._window.raise_()
        self._window.activateWindow()

    def request_exit(self, *, stop_dpi: bool) -> None:
        requester = getattr(self._window, "request_exit", None)
        if callable(requester):
            requester(stop_dpi=bool(stop_dpi))

    def update_current_strategy_display(self, strategy_name: str) -> None:
        update_current_strategy_display(self._window, strategy_name)


def ensure_window_adapter(window) -> WindowUiAdapter:
    adapter = getattr(window, "_window_ui_adapter", None)
    if adapter is None:
        adapter = WindowUiAdapter(window)
        window._window_ui_adapter = adapter
    return adapter


__all__ = ["WindowUiAdapter", "ensure_window_adapter"]
