from __future__ import annotations

from ui.navigation.sidebar_builder import init_navigation
from ui.window_ui_session import get_window_ui_session
from ui.window_bootstrap_runtime import (
    create_preset_runtime_coordinator,
    ensure_session_memory_defaults,
    finalize_page_stack_bootstrap,
    finish_ui_bootstrap,
    initialize_build_ui_state,
)
from ui.navigation.schema import get_eager_page_names_for_method
from app.page_names import PageName


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
        session = get_window_ui_session(self._window)
        if session is not None:
            session.preset_runtime_coordinator = create_preset_runtime_coordinator(self._window)
            session.page_host.mark_stack_bootstrap_pending()

        try:
            launch_method = self._window.get_launch_method()
        except Exception:
            launch_method = ""

        if session is not None:
            session.page_host.create_eager_pages(get_eager_page_names_for_method(launch_method))

        init_navigation(self._window)
        finalize_page_stack_bootstrap(self._window)
        ensure_session_memory_defaults(self._window)

    def finish_bootstrap(self) -> None:
        finish_ui_bootstrap(self._window)

    def get_loaded_page(self, page_name: PageName):
        session = get_window_ui_session(self._window)
        if session is None:
            return None
        return session.page_host.get_loaded_page(page_name)

    def show_page(self, page_name: PageName) -> bool:
        session = get_window_ui_session(self._window)
        if session is None:
            return False
        return session.page_host.show_page(page_name)


__all__ = ["WindowUiRoot"]
