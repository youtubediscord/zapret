from __future__ import annotations

import time

from PyQt6.QtWidgets import QWidget

from log.log import log

from ui.navigation.text_sync import apply_ui_language_to_page
from ui.navigation.schema import (
    get_page_route_key,
    is_page_allowed_for_method,
    is_page_mode_open_allowed,
)
from app.page_names import PageName
from ui.page_performance import log_page_metric
from ui.page_registry import get_page_performance_profile
from ui.startup_ui_metrics import (
    pump_startup_ui,
    record_startup_page_init_metric,
)
from ui.window_ui_session import get_window_ui_session


class WindowPageHost:
    """Единая точка lifecycle для страниц окна.

    Хранит уже созданные страницы, создаёт новые через factory и управляет
    показом через stackedWidget/navigationInterface.
    """

    def __init__(self, window, page_factory):
        self._window = window
        self._page_factory = page_factory
        self.pages: dict[PageName, QWidget] = {}
        self._shown_pages: set[PageName] = set()

    @staticmethod
    def _log_step_timing(page_name: PageName, stage: str, started_at: float, *, threshold_ms: int = 15) -> None:
        elapsed_ms = (time.perf_counter() - started_at) * 1000
        if elapsed_ms < int(threshold_ms):
            return
        log_page_metric(page_name, stage, elapsed_ms)

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

    def send_page_command(
        self,
        page_name: PageName,
        command: str,
        payload: dict | None = None,
        *,
        ensure: bool = True,
    ) -> bool:
        page = self.ensure_page(page_name) if ensure else self.get_loaded_page(page_name)
        if page is None:
            return False
        handler = getattr(page, "handle_page_command", None)
        if not callable(handler):
            log(f"[PAGE_HOST] page {page_name.name} не принимает команды", "WARNING")
            return False
        return bool(handler(str(command or ""), dict(payload or {})))

    def current_page(self) -> QWidget | None:
        try:
            return self._window.stackedWidget.currentWidget()
        except Exception:
            return None

    def has_nav_item(self, page_name: PageName) -> bool:
        session = get_window_ui_session(self._window)
        if session is None:
            return False
        return page_name in session.nav_items

    def set_stacked_widget_current_page(self, page: QWidget | None, *, animate: bool = True) -> bool:
        stack = self._window.stackedWidget
        if page is None:
            return False

        if animate:
            try:
                self._window.switchTo(page)
                return True
            except Exception:
                pass

        previous_animation_enabled = getattr(stack, "isAnimationEnabled", None)
        animation_flag_known = isinstance(previous_animation_enabled, bool)
        if animation_flag_known:
            try:
                stack.isAnimationEnabled = False
            except Exception:
                animation_flag_known = False

        try:
            try:
                stack.setCurrentWidget(page, False)
            except TypeError:
                stack.setCurrentWidget(page)
            return True
        except Exception:
            return False
        finally:
            if animation_flag_known:
                try:
                    stack.isAnimationEnabled = bool(previous_animation_enabled)
                except Exception:
                    pass

    def ensure_page_in_stacked_widget(self, page: QWidget | None) -> None:
        stack = self._window.stackedWidget
        if page is None:
            return
        try:
            if stack.indexOf(page) < 0:
                stack.addWidget(page)
        except Exception:
            pass

    def mark_stack_bootstrap_pending(self) -> None:
        session = get_window_ui_session(self._window)
        if session is not None:
            session.page_stack_bootstrap_complete = False

    def finalize_stack_bootstrap(self) -> None:
        session = get_window_ui_session(self._window)
        if session is None:
            return
        session.page_stack_bootstrap_complete = True
        for page in list(self.pages.values()):
            self.ensure_page_in_stacked_widget(page)

    def _current_launch_method(self) -> str:
        try:
            return str(self._window.get_launch_method() or "").strip().lower()
        except Exception:
            return ""

    def _is_page_allowed(self, page_name: PageName) -> bool:
        return is_page_allowed_for_method(page_name, self._current_launch_method())

    def ensure_page(self, page_name: PageName) -> QWidget | None:
        if not self._is_page_allowed(page_name):
            log(f"[PAGE_HOST] skip ensure_page for disallowed page {page_name.name}", "DEBUG")
            return None

        page = self.pages.get(page_name)
        if page is not None:
            step_started_at = time.perf_counter()
            apply_ui_language_to_page(self._window, page)
            self._log_step_timing(page_name, "ensure.cached.language", step_started_at)
            session = get_window_ui_session(self._window)
            if session is not None and bool(session.page_stack_bootstrap_complete):
                step_started_at = time.perf_counter()
                self.ensure_page_in_stacked_widget(page)
                self._log_step_timing(page_name, "ensure.cached.stack", step_started_at)
            return page

        step_started_at = time.perf_counter()
        created_page = self._page_factory.create_page(page_name)
        self._log_step_timing(page_name, "ensure.create", step_started_at)
        if created_page is None:
            return None

        page = created_page.page
        self.pages[page_name] = page

        step_started_at = time.perf_counter()
        apply_ui_language_to_page(self._window, page)
        self._log_step_timing(page_name, "ensure.created.language", step_started_at)

        session = get_window_ui_session(self._window)
        if session is not None and bool(session.page_stack_bootstrap_complete):
            step_started_at = time.perf_counter()
            self.ensure_page_in_stacked_widget(page)
            self._log_step_timing(page_name, "ensure.created.stack", step_started_at)

        record_startup_page_init_metric(self._window, page_name, created_page.elapsed_ms)
        log_page_metric(
            page_name,
            "constructor",
            created_page.elapsed_ms,
            budget_ms=get_page_performance_profile(page_name).first_show_budget_ms,
        )
        return page

    def show_page(self, page_name: PageName, *, allow_internal: bool = False) -> bool:
        import time as _time

        started_at = _time.perf_counter()
        first_show = page_name not in self._shown_pages
        if not self._is_page_allowed(page_name):
            log(f"[PAGE_HOST] reject show_page for disallowed page {page_name.name}", "WARNING")
            return False

        if not allow_internal and not is_page_mode_open_allowed(page_name):
            log(f"[PAGE_HOST] reject direct-open for inner page {page_name.name}", "WARNING")
            return False

        step_started_at = _time.perf_counter()
        page = self.ensure_page(page_name)
        self._log_step_timing(page_name, "show.ensure_page", step_started_at)
        if page is None:
            return False

        step_started_at = _time.perf_counter()
        self.ensure_page_in_stacked_widget(page)
        self._log_step_timing(page_name, "show.stack", step_started_at)
        use_nav_route = self.has_nav_item(page_name)
        step_started_at = _time.perf_counter()
        switched = self.set_stacked_widget_current_page(page, animate=False)
        self._log_step_timing(page_name, "show.switch", step_started_at)
        if not switched:
            return False

        step_started_at = _time.perf_counter()
        try:
            route_key = get_page_route_key(page_name)
            if route_key and use_nav_route:
                self._window.navigationInterface.setCurrentItem(route_key)
        except Exception:
            pass
        self._log_step_timing(page_name, "show.navigation", step_started_at)
        self._shown_pages.add(page_name)
        log_page_metric(
            page_name,
            "show.first" if first_show else "show.repeat",
            (_time.perf_counter() - started_at) * 1000,
            budget_ms=(
                get_page_performance_profile(page_name).first_show_budget_ms
                if first_show
                else get_page_performance_profile(page_name).repeat_show_budget_ms
            ),
        )
        return True


__all__ = ["WindowPageHost"]
