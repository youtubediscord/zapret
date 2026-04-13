from __future__ import annotations

from ui.navigation.sidebar_builder import init_navigation
from ui.window_bootstrap_runtime import (
    create_preset_runtime_coordinator,
    ensure_session_memory_defaults,
    finalize_page_signal_bootstrap,
    finish_ui_bootstrap,
    initialize_build_ui_state,
)
from ui.navigation.schema import get_eager_page_names_for_method
from ui.page_names import PageName


class WindowUiRoot:
    """Центральная точка сборки fluent UI-каркаса окна."""

    def __init__(self, window):
        self._window = window

    def build(
        self,
        *,
        width: int,
        height: int,
        nav_icons,
        nav_labels,
        has_fluent: bool,
        default_nav_icon,
        nav_scroll_position,
        sidebar_search_widget_cls,
    ) -> None:
        _ = width
        _ = height

        initialize_build_ui_state(
            self._window,
            nav_icons=nav_icons,
            nav_labels=nav_labels,
            has_fluent=has_fluent,
            default_nav_icon=default_nav_icon,
            nav_scroll_position=nav_scroll_position,
            sidebar_search_widget_cls=sidebar_search_widget_cls,
        )
        self._window._preset_runtime_coordinator = create_preset_runtime_coordinator(self._window)
        self._window._page_signal_bootstrap_complete = False

        launch_method = ""
        getter = getattr(self._window, "_get_launch_method", None)
        if callable(getter):
            try:
                launch_method = getter()
            except Exception:
                launch_method = ""

        page_host = getattr(self._window, "_page_host", None)
        if page_host is not None:
            page_host.create_eager_pages(get_eager_page_names_for_method(launch_method))

        init_navigation(self._window)
        finalize_page_signal_bootstrap(self._window)
        ensure_session_memory_defaults(self._window)

    def finish_bootstrap(self) -> None:
        finish_ui_bootstrap(self._window)

    def get_loaded_page(self, page_name: PageName):
        page_host = getattr(self._window, "_page_host", None)
        if page_host is None:
            return None
        return page_host.get_loaded_page(page_name)

    def show_page(self, page_name: PageName) -> bool:
        page_host = getattr(self._window, "_page_host", None)
        if page_host is None:
            return False
        return page_host.show_page(page_name)


__all__ = ["WindowUiRoot"]
