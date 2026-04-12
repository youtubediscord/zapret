from __future__ import annotations

from PyQt6.QtWidgets import QWidget

from log import log
from ui.navigation.navigation_controller import ensure_navigation_controller
from ui.page_dependencies import inject_page_dependencies
from ui.navigation.schema import (
    get_page_route_key,
    is_page_allowed_for_method,
    is_page_direct_open_allowed,
)
from ui.page_names import PageName
from ui.page_performance import log_page_metric
from ui.page_registry import get_page_performance_profile
from ui.startup_ui_metrics import (
    pump_startup_ui,
    record_startup_page_init_metric,
)


class WindowPageHost:
    """Единая точка lifecycle для страниц окна.

    Хранит уже созданные страницы, создаёт новые через factory и управляет
    показом через stackedWidget/navigationInterface.
    """

    def __init__(self, window, page_factory, *, connect_page_signals):
        self._window = window
        self._page_factory = page_factory
        self._connect_page_signals = connect_page_signals
        self.pages: dict[PageName, QWidget] = {}

    def create_eager_pages(self, page_names: tuple[PageName, ...]) -> None:
        import time as _time

        started_at = _time.perf_counter()
        for page_name in page_names:
            self.ensure_page(page_name)
            pump_startup_ui(self._window)

        log(
            f"⏱ Startup: _create_pages core {(_time.perf_counter() - started_at) * 1000:.0f}ms",
            "DEBUG",
        )
        pump_startup_ui(self._window, force=True)

    def get_loaded_page(self, page_name: PageName) -> QWidget | None:
        return self.pages.get(page_name)

    def has_nav_item(self, page_name: PageName) -> bool:
        nav_items = getattr(self._window, "_nav_items", None)
        if not isinstance(nav_items, dict):
            return False
        return page_name in nav_items

    def set_stacked_widget_current_page(self, page: QWidget | None, *, animate: bool = True) -> bool:
        stack = getattr(self._window, "stackedWidget", None)
        if page is None or stack is None:
            return False

        if animate:
            switch_to = getattr(self._window, "switchTo", None)
            if callable(switch_to):
                try:
                    switch_to(page)
                    return True
                except Exception:
                    pass

        view = getattr(stack, "view", None)
        set_animation_enabled = getattr(view, "setAnimationEnabled", None)
        previous_animation_enabled = getattr(view, "isAnimationEnabled", None)
        animation_flag_known = isinstance(previous_animation_enabled, bool)

        if callable(set_animation_enabled):
            try:
                set_animation_enabled(False)
            except Exception:
                pass

        try:
            try:
                stack.setCurrentWidget(page, False)
            except TypeError:
                stack.setCurrentWidget(page)
            return True
        except Exception:
            return False
        finally:
            if callable(set_animation_enabled) and animation_flag_known:
                try:
                    set_animation_enabled(bool(previous_animation_enabled))
                except Exception:
                    pass

    def ensure_page_in_stacked_widget(self, page: QWidget | None) -> None:
        stack = getattr(self._window, "stackedWidget", None)
        if page is None or stack is None:
            return
        try:
            if stack.indexOf(page) < 0:
                stack.addWidget(page)
        except Exception:
            pass

    def bind_page_ui_state(self, page: QWidget | None) -> None:
        store = getattr(self._window, "ui_state_store", None)
        binder = getattr(page, "bind_ui_state_store", None)
        if store is None or page is None or not callable(binder):
            return

        try:
            binder(store)
        except Exception:
            pass

    def _current_launch_method(self) -> str:
        getter = getattr(self._window, "_get_launch_method", None)
        if callable(getter):
            try:
                return str(getter() or "").strip().lower()
            except Exception:
                return ""
        return ""

    def _is_page_allowed(self, page_name: PageName) -> bool:
        return is_page_allowed_for_method(page_name, self._current_launch_method())

    def ensure_page(self, page_name: PageName) -> QWidget | None:
        if not self._is_page_allowed(page_name):
            log(f"[PAGE_HOST] skip ensure_page for disallowed page {page_name.name}", "DEBUG")
            return None

        page = self.pages.get(page_name)
        if page is not None:
            inject_page_dependencies(page, self._window)
            ensure_navigation_controller(self._window).apply_ui_language_to_page(page)
            self.bind_page_ui_state(page)
            if bool(getattr(self._window, "_page_signal_bootstrap_complete", False)):
                self.ensure_page_in_stacked_widget(page)
            return page

        created_page = self._page_factory.create_page(page_name)
        if created_page is None:
            return None

        page = created_page.page
        self.pages[page_name] = page
        setattr(self._window, created_page.attr_name, page)

        inject_page_dependencies(page, self._window)
        ensure_navigation_controller(self._window).apply_ui_language_to_page(page)
        self.bind_page_ui_state(page)

        if bool(getattr(self._window, "_page_signal_bootstrap_complete", False)):
            self._connect_page_signals(self._window, page_name, page)
            self.ensure_page_in_stacked_widget(page)

        record_startup_page_init_metric(self._window, page_name, created_page.elapsed_ms)
        log_page_metric(
            page_name,
            "constructor",
            created_page.elapsed_ms,
            budget_ms=get_page_performance_profile(page_name).first_show_budget_ms,
        )
        return page

    def show_page(self, page_name: PageName, *, allow_internal: bool = False) -> bool:
        if not self._is_page_allowed(page_name):
            log(f"[PAGE_HOST] reject show_page for disallowed page {page_name.name}", "WARNING")
            return False

        if not allow_internal and not is_page_direct_open_allowed(page_name):
            log(f"[PAGE_HOST] reject direct-open for internal/detail page {page_name.name}", "WARNING")
            return False

        page = self.ensure_page(page_name)
        if page is None:
            return False

        self.ensure_page_in_stacked_widget(page)
        use_nav_route = self.has_nav_item(page_name)
        switched = self.set_stacked_widget_current_page(page, animate=use_nav_route)
        if not switched:
            return False

        try:
            route_key = get_page_route_key(page_name)
            if route_key and use_nav_route:
                self._window.navigationInterface.setCurrentItem(route_key)
        except Exception:
            pass
        return True


__all__ = ["WindowPageHost"]
