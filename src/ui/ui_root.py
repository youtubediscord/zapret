from __future__ import annotations

import time

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

    def __init__(self, window, page_deps_sources, runtime_bootstrap_deps):
        self._window = window
        self._page_deps_sources = page_deps_sources
        self._runtime_bootstrap_deps = runtime_bootstrap_deps

    def build(
        self,
        *,
        width: int,
        height: int,
        nav_icons,
        nav_labels,
        default_nav_icon,
        nav_scroll_position,
        sidebar_search_widget_cls,
    ) -> None:
        _ = width
        _ = height

        def _metric(marker: str, started_at: float) -> None:
            try:
                self._window.log_startup_metric(marker, f"{(time.perf_counter() - started_at) * 1000:.0f}ms")
            except Exception:
                pass

        started_at = time.perf_counter()
        initialize_build_ui_state(
            self._window,
            runtime_deps=self._runtime_bootstrap_deps,
            page_deps_sources=self._page_deps_sources,
            nav_icons=nav_icons,
            nav_labels=nav_labels,
            default_nav_icon=default_nav_icon,
            nav_scroll_position=nav_scroll_position,
            sidebar_search_widget_cls=sidebar_search_widget_cls,
        )
        _metric("StartupWindowUiRootInitialize", started_at)
        session = get_window_ui_session(self._window)
        if session is not None:
            started_at = time.perf_counter()
            session.preset_runtime_coordinator = create_preset_runtime_coordinator(
                self._window,
                self._runtime_bootstrap_deps,
            )
            session.page_host.mark_stack_bootstrap_pending()
            _metric("StartupWindowUiRootRuntimeCoordinator", started_at)

        launch_method = self._initial_launch_method()

        if session is not None:
            started_at = time.perf_counter()
            session.page_host.create_eager_pages(get_eager_page_names_for_method(launch_method))
            _metric("StartupWindowUiRootEagerPages", started_at)

        started_at = time.perf_counter()
        init_navigation(self._window)
        _metric("StartupWindowUiRootNavigation", started_at)
        started_at = time.perf_counter()
        finalize_page_stack_bootstrap(self._window)
        _metric("StartupWindowUiRootStack", started_at)
        ensure_session_memory_defaults(self._window)

    def finish_bootstrap(self) -> None:
        finish_ui_bootstrap(self._window, self._runtime_bootstrap_deps)

    def _initial_launch_method(self) -> str:
        try:
            snapshot = self._runtime_bootstrap_deps.ui_state_store.snapshot()
            return str(getattr(snapshot, "launch_method", "") or "").strip().lower()
        except Exception:
            return ""

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
