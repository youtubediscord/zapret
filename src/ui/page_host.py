from __future__ import annotations

import os
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
from ui.performance_metrics import log_page_timing
from ui.page_registry import get_page_performance_profile
from ui.startup_ui_metrics import (
    record_startup_page_init_metric,
)
from ui.window_ui_session import get_window_ui_session


ANIMATED_NAV_REPEAT_SHOW_BUDGET_MS = 120


SWITCH_PROFILE_AUTO_SAMPLES = 8
SWITCH_PROFILE_MIN_LOG_MS = 40

_switch_profile_samples_left = SWITCH_PROFILE_AUTO_SAMPLES


def _switch_profile_forced() -> bool:
    return str(os.environ.get("ZAPRET_SWITCH_PROFILE") or "").strip().lower() in {"1", "true", "yes", "on"}


def _should_profile_switch() -> bool:
    """Автосэмплинг: первые N переключений сессии профилируются без флагов."""
    global _switch_profile_samples_left
    if _switch_profile_forced():
        return True
    if _switch_profile_samples_left <= 0:
        return False
    _switch_profile_samples_left -= 1
    return True


class _SwitchTracer:
    """Минимальный профайлер на sys.setprofile.

    stdlib cProfile в этом приложении не работает: он делает `import profile`
    и получает наш пакет src/profile вместо стандартного модуля
    (AttributeError на profile.run). Поэтому считаем cumtime сами.
    """

    __slots__ = ("stats", "_stack")

    def __init__(self) -> None:
        self.stats: dict[str, list[float]] = {}
        self._stack: list[tuple[str, float]] = []

    @staticmethod
    def _python_key(frame) -> str:
        code = frame.f_code
        file_name = code.co_filename.replace("\\", "/").rsplit("/", 1)[-1]
        return f"{file_name}:{code.co_firstlineno}({code.co_qualname})"

    @staticmethod
    def _c_key(arg) -> str:
        module = getattr(arg, "__module__", "") or "builtins"
        return f"<C> {module}.{getattr(arg, '__qualname__', repr(arg))}"

    def __call__(self, frame, event, arg):
        now = time.perf_counter()
        if event == "call":
            self._stack.append((self._python_key(frame), now))
        elif event == "c_call":
            self._stack.append((self._c_key(arg), now))
        elif event in ("return", "c_return", "c_exception"):
            if not self._stack:
                return
            key, started_at = self._stack.pop()
            entry = self.stats.get(key)
            if entry is None:
                self.stats[key] = [1, now - started_at]
            else:
                entry[0] += 1
                entry[1] += now - started_at

    def report(self, top_n: int = 12) -> str:
        rows = sorted(self.stats.items(), key=lambda item: item[1][1], reverse=True)[:top_n]
        return "\n".join(
            f"  {cum * 1000:8.1f}ms  {int(calls):6d} calls  {key}"
            for key, (calls, cum) in rows
        )


def _profile_switch_call(page_name, callback) -> None:
    """Диагностика: раскладка Python-времени внутри setCurrentWidget.

    C-остаток поверх Python-времени — это нативный layout/polish Qt. В лог
    попадают только медленные переключения, чтобы не шуметь на быстрых.

    Любая поломка профилировщика не должна мешать самому переключению:
    callback выполняется ровно один раз при любом исходе диагностики.
    """
    import sys

    tracer = None
    try:
        tracer = _SwitchTracer()
        sys.setprofile(tracer)
    except Exception as exc:
        log(f"[SWITCH_PROFILE] диагностика недоступна: {exc}", "DEBUG")
        tracer = None

    started_at = time.perf_counter()
    try:
        callback()
    finally:
        if tracer is not None:
            try:
                sys.setprofile(None)
            except Exception:
                tracer = None

    if tracer is None:
        return
    elapsed_ms = (time.perf_counter() - started_at) * 1000
    if elapsed_ms < SWITCH_PROFILE_MIN_LOG_MS and not _switch_profile_forced():
        return
    try:
        log(f"[SWITCH_PROFILE] {page_name} ({elapsed_ms:.0f}ms):\n{tracer.report()}", "INFO")
    except Exception as exc:
        log(f"[SWITCH_PROFILE] не удалось сформировать отчёт: {exc}", "DEBUG")


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
    def _log_step_timing(
        page_name: PageName,
        stage: str,
        started_at: float,
        *,
        threshold_ms: int = 15,
        extra: str | None = None,
    ) -> None:
        elapsed_ms = (time.perf_counter() - started_at) * 1000
        if elapsed_ms < int(threshold_ms):
            return
        log_page_timing(page_name, stage, elapsed_ms, extra=extra)

    @staticmethod
    def _widget_debug_name(widget) -> str:
        if widget is None:
            return "none"
        try:
            object_name = str(widget.objectName() or "").strip()
            if object_name:
                return object_name
        except Exception:
            pass
        try:
            return type(widget).__name__
        except Exception:
            return "unknown"

    @staticmethod
    def _widget_tree_counts(widget) -> tuple[int, int]:
        if widget is None:
            return 0, 0
        try:
            children = list(widget.findChildren(QWidget))
        except Exception:
            return 0, 0
        visible = 0
        for child in children:
            try:
                if child.isVisible():
                    visible += 1
            except Exception:
                pass
        return len(children), visible

    @classmethod
    def _switch_detail_extra(cls, stack, target_page) -> str:
        try:
            current_page = stack.currentWidget()
        except Exception:
            current_page = None
        try:
            stack_count = int(stack.count())
        except Exception:
            stack_count = 0
        child_count, visible_count = cls._widget_tree_counts(target_page)
        return (
            f"from={cls._widget_debug_name(current_page)}, "
            f"to={cls._widget_debug_name(target_page)}, "
            f"children={child_count}, visible={visible_count}, stack={stack_count}"
        )

    @staticmethod
    def _show_budget_ms(page_name: PageName, *, first_show: bool, use_nav_route: bool) -> int:
        profile = get_page_performance_profile(page_name)
        if first_show:
            return profile.first_show_budget_ms
        if use_nav_route:
            return max(profile.repeat_show_budget_ms, ANIMATED_NAV_REPEAT_SHOW_BUDGET_MS)
        return profile.repeat_show_budget_ms

    def create_eager_pages(self, page_names: tuple[PageName, ...]) -> None:
        import time as _time

        started_at = _time.perf_counter()
        for page_name in page_names:
            self.ensure_page(page_name)

        log(
            f"⏱ Startup: _create_pages core {(_time.perf_counter() - started_at) * 1000:.0f}ms",
            "DEBUG",
        )

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

    def set_stacked_widget_current_page(
        self,
        page: QWidget | None,
        *,
        animate: bool = True,
        page_name: PageName | None = None,
    ) -> bool:
        stack = self._window.stackedWidget
        if page is None:
            return False

        if animate:
            try:
                self._window.switchTo(page)
                return True
            except Exception:
                pass

        # Не выключаем updates у всего stack: если очередь Qt занята событиями
        # runtime, отложенное включение оставляет окно визуально замороженным.
        # Запасной прямой переход лишь синхронно отключает анимацию qfluent.
        previous_animation_enabled = getattr(stack, "isAnimationEnabled", None)
        animation_flag_known = isinstance(previous_animation_enabled, bool)
        if animation_flag_known:
            step_started_at = time.perf_counter()
            try:
                stack.isAnimationEnabled = False
            except Exception:
                animation_flag_known = False
            self._log_optional_switch_step(page_name, "open.switch.disable_animation", step_started_at)

        try:
            step_started_at = time.perf_counter()
            switch_extra = self._switch_detail_extra(stack, page)

            def _set_current() -> None:
                try:
                    stack.setCurrentWidget(page, False)
                except TypeError:
                    stack.setCurrentWidget(page)

            if _should_profile_switch():
                _profile_switch_call(page_name, _set_current)
            else:
                _set_current()
            self._log_optional_switch_step(page_name, "open.switch.set_current", step_started_at, extra=switch_extra)
            return True
        except Exception:
            return False
        finally:
            if animation_flag_known:
                step_started_at = time.perf_counter()
                try:
                    stack.isAnimationEnabled = bool(previous_animation_enabled)
                except Exception:
                    pass
                self._log_optional_switch_step(page_name, "open.switch.restore_animation", step_started_at)

    def _log_optional_switch_step(
        self,
        page_name: PageName | None,
        stage: str,
        started_at: float,
        *,
        extra: str | None = None,
    ) -> None:
        if page_name is None:
            return
        self._log_step_timing(page_name, stage, started_at, extra=extra)

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
        log_page_timing(
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
        self._log_step_timing(page_name, "open.ensure_page", step_started_at)
        if page is None:
            return False
        self._begin_page_open_metric(page, page_name, started_at=started_at, first_show=first_show)

        step_started_at = _time.perf_counter()
        self.ensure_page_in_stacked_widget(page)
        self._log_step_timing(page_name, "open.stack", step_started_at)
        use_nav_route = self.has_nav_item(page_name)
        step_started_at = _time.perf_counter()
        if self.current_page() is page:
            switched = True
        else:
            switched = self.set_stacked_widget_current_page(
                page,
                animate=use_nav_route,
                page_name=page_name,
            )
        self._log_step_timing(page_name, "open.switch", step_started_at)
        if not switched:
            return False

        step_started_at = _time.perf_counter()
        try:
            route_key = get_page_route_key(page_name)
            if route_key and use_nav_route:
                self._window.navigationInterface.setCurrentItem(route_key)
        except Exception:
            pass
        self._log_step_timing(page_name, "open.navigation_sync", step_started_at)
        self._request_page_keyboard_focus(page)
        self._shown_pages.add(page_name)
        log_page_timing(
            page_name,
            "open.navigation.first" if first_show else "open.navigation.repeat",
            (_time.perf_counter() - started_at) * 1000,
            budget_ms=self._show_budget_ms(
                page_name,
                first_show=first_show,
                use_nav_route=use_nav_route,
            ),
            important=True,
            threshold_ms=0,
        )
        return True

    @staticmethod
    def _begin_page_open_metric(
        page: QWidget | None,
        page_name: PageName,
        *,
        started_at: float,
        first_show: bool,
    ) -> None:
        if page is None:
            return
        begin = getattr(page, "_begin_page_open_metric", None)
        if callable(begin):
            try:
                begin(page_name, started_at=started_at, first_show=first_show)
            except Exception:
                pass

    @staticmethod
    def _request_page_keyboard_focus(page: QWidget | None) -> None:
        if page is None:
            return
        request_focus = getattr(page, "request_keyboard_focus", None)
        if not callable(request_focus):
            return
        try:
            request_focus()
        except Exception:
            pass


__all__ = ["WindowPageHost"]
