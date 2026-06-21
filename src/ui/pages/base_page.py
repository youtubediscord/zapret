# ui/pages/base_page.py
"""Базовый класс для страниц — использует qfluentwidgets ScrollArea."""

import time as _time
from PyQt6.QtCore import Qt, QEvent, QTimer
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QFrame, QSizePolicy,
)
from qfluentwidgets import (
    BodyLabel,
    PlainTextEdit as _FluentPlainTextEdit,
    ScrollArea as _FluentScrollArea,
    StrongBodyLabel,
    TextEdit as _FluentTextEdit,
    TitleLabel,
)

from app.ui_texts import tr as tr_catalog, normalize_language
from ui.accessibility import remove_scrollbar_arrow_buttons_from_tab_order, set_state_text
from ui.performance_metrics import log_page_timing
from ui.smooth_scroll import (
    apply_editor_smooth_scroll_preference,
    apply_page_smooth_scroll_preference,
    apply_smooth_scroll_mode,
)


class ScrollBlockingPlainTextEdit(_FluentPlainTextEdit):
    """PlainTextEdit с fluent-скроллбарами, не пропускающий прокрутку к родителю.

    SmoothScrollDelegate (из qfluentwidgets) намеренно пропускает wheel-событие
    к родителю когда достигнута граница скролла (return False в eventFilter).
    Переопределяем wheelEvent чтобы принять событие и не дать BasePage прокрутиться.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setProperty("noDrag", True)
        apply_editor_smooth_scroll_preference(self)

    def set_smooth_scroll_enabled(self, enabled: bool) -> None:
        apply_smooth_scroll_mode(self, enabled)

    def wheelEvent(self, event):
        # SmoothScrollDelegate поглощает событие когда НЕ у границы (возвращает True),
        # поэтому этот метод вызывается ТОЛЬКО у границы скролла.
        event.accept()


class ScrollBlockingTextEdit(_FluentTextEdit):
    """TextEdit с fluent-скроллбарами, не пропускающий прокрутку к родителю."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setProperty("noDrag", True)
        apply_editor_smooth_scroll_preference(self)

    def set_smooth_scroll_enabled(self, enabled: bool) -> None:
        apply_smooth_scroll_mode(self, enabled)

    def wheelEvent(self, event):
        event.accept()


class BasePage(_FluentScrollArea):
    """Базовый класс для страниц контента.

    Uses qfluentwidgets ScrollArea for smooth Fluent-style scrolling.
    The public API (self.layout, add_widget, add_spacing, add_section_title,
    self.title_label, self.subtitle_label) is shared by all pages.
    """

    def __init__(
        self,
        title: str,
        subtitle: str = "",
        parent=None,
        *,
        title_key: str | None = None,
        subtitle_key: str | None = None,
    ):
        super().__init__(parent)
        self._ui_language = self._resolve_ui_language()
        self._title_key = title_key
        self._subtitle_key = subtitle_key
        self._title_fallback = title
        self._subtitle_fallback = subtitle
        self._section_title_bindings: list[tuple[object, str, str]] = []
        self._page_registry_name = None
        self._page_first_activation_done = False
        self._page_lifecycle_generation = 0
        self._page_load_generation = 0
        self._page_open_metric_started_at = 0.0
        self._page_open_metric_first_show = True
        self._content_paint_metric_targets: dict[int, dict[str, object]] = {}
        self._content_paint_metric_next_token = 0
        self._ready_callbacks: list[object] = []
        self._cleanup_in_progress = False
        self._page_theme_refresh = self._create_page_theme_refresh_if_needed()

        # Ensure objectName is set (required by FluentWindow.addSubInterface)
        if not self.objectName():
            self.setObjectName(self.__class__.__name__)

        if self._title_key:
            title = tr_catalog(self._title_key, language=self._ui_language, default=title)
        if self._subtitle_key:
            subtitle = tr_catalog(self._subtitle_key, language=self._ui_language, default=subtitle)

        # --- ScrollArea config ---
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setStyleSheet(
            "QScrollArea { background-color: transparent; border: none; }"
        )

        # Применяем обычную прокрутку для страниц и списков.
        apply_page_smooth_scroll_preference(self)
        remove_scrollbar_arrow_buttons_from_tab_order(self)

        # --- Content container ---
        self.content = QWidget(self)
        self.content.setStyleSheet("background-color: transparent;")
        # Expanding horizontally so the content fills the viewport width and
        # word-wrapped labels can actually wrap instead of overflowing.
        self.content.setMinimumWidth(0)
        self.content.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.setWidget(self.content)

        # --- Main layout ---
        self.vBoxLayout = QVBoxLayout(self.content)
        self.vBoxLayout.setContentsMargins(36, 28, 36, 28)
        self.vBoxLayout.setSpacing(16)
        self.vBoxLayout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Public layout alias used by page subclasses.
        self.layout = self.vBoxLayout

        # --- Title ---
        self.title_label = TitleLabel(self.content)
        self.title_label.setText(title)
        set_state_text(self.title_label, f"Заголовок страницы: {title}")
        self.vBoxLayout.addWidget(self.title_label)

        # --- Subtitle ---
        if subtitle:
            self.subtitle_label = BodyLabel(self.content)
            self.subtitle_label.setText(subtitle)
            set_state_text(self.subtitle_label, f"Описание страницы: {subtitle}")
            self.subtitle_label.setWordWrap(True)
            self.vBoxLayout.addWidget(self.subtitle_label)
        else:
            self.subtitle_label = None

    def _set_page_registry_name(self, page_name) -> None:
        self._page_registry_name = page_name

    def _page_label(self):
        return self._page_registry_name or self.__class__.__name__

    def _resolve_page_budget(self, budget_attr: str) -> int | None:
        page_name = getattr(self, "_page_registry_name", None)
        if page_name is None:
            return None
        try:
            from ui.page_registry import get_page_performance_profile

            return int(getattr(get_page_performance_profile(page_name), budget_attr))
        except Exception:
            return None

    def on_page_activated(self) -> None:
        pass

    def on_page_hidden(self) -> None:
        pass

    def invalidate_page_cache(self, reason: str) -> None:
        self.cancel_page_loads(reason=reason)

    def issue_page_load_token(self, *, reason: str = "") -> int:
        return self._issue_page_load_token(reason=reason)

    def is_page_load_token_current(self, token: int) -> bool:
        return self._is_page_load_token_current(token)

    def cancel_page_loads(self, *, reason: str = "") -> None:
        self._cancel_page_loads(reason=reason)

    def is_page_ready(self) -> bool:
        return bool(self.isVisible()) and not bool(getattr(self, "_cleanup_in_progress", False))

    def _begin_page_open_metric(self, page_name, *, started_at: float, first_show: bool) -> None:
        self._page_registry_name = page_name
        try:
            self._page_open_metric_started_at = float(started_at)
        except Exception:
            self._page_open_metric_started_at = _time.perf_counter()
        self._page_open_metric_first_show = bool(first_show)

    def _auto_mark_content_ready_after_activation(self) -> bool:
        return True

    def mark_content_ready(
        self,
        *,
        stage: str = "content.ready",
        extra: str = "",
        started_at: float | None = None,
    ) -> None:
        if started_at is None:
            started_at = float(self.__dict__.get("_page_open_metric_started_at", 0.0) or 0.0)
        if started_at <= 0:
            started_at = _time.perf_counter()
        elapsed_ms = (_time.perf_counter() - started_at) * 1000.0
        first_show = bool(self.__dict__.get("_page_open_metric_first_show", True))
        phase = "first" if first_show else "repeat"
        budget_attr = "first_show_budget_ms" if first_show else "repeat_show_budget_ms"
        log_page_timing(
            self._page_label(),
            f"{stage}.{phase}",
            elapsed_ms,
            budget_ms=self._resolve_page_budget(budget_attr),
            extra=extra,
            important=True,
            threshold_ms=0,
        )

    def mark_content_ready_after_next_paint(
        self,
        target,
        *,
        stage: str = "content.painted",
        extra: str = "",
        timeout_ms: int = 1_500,
    ) -> None:
        paint_target = self._resolve_content_paint_target(target)
        if paint_target is None:
            self.mark_content_ready(stage=stage, extra=f"{extra}; paint_target=missing" if extra else "paint_target=missing")
            return

        self._content_paint_metric_next_token = int(
            self.__dict__.get("_content_paint_metric_next_token", 0) or 0
        ) + 1
        token = self._content_paint_metric_next_token
        pending = self.__dict__.setdefault("_content_paint_metric_targets", {})
        pending[id(paint_target)] = {
            "target": paint_target,
            "token": token,
            "stage": str(stage or "content.painted"),
            "extra": str(extra or ""),
            "started_at": float(self.__dict__.get("_page_open_metric_started_at", 0.0) or 0.0),
        }

        try:
            paint_target.installEventFilter(self)
        except Exception:
            pending.pop(id(paint_target), None)
            self.mark_content_ready(stage=stage, extra=f"{extra}; paint_filter=failed" if extra else "paint_filter=failed")
            return
        try:
            paint_target.update()
        except Exception:
            pass

        def _timeout() -> None:
            self._finish_content_paint_metric(paint_target, token, timeout=True)

        try:
            QTimer.singleShot(max(1, int(timeout_ms)), _timeout)
        except Exception:
            pass

    @staticmethod
    def _resolve_content_paint_target(target):
        if target is None:
            return None
        inner_view = getattr(target, "_view", None)
        viewport = getattr(inner_view, "viewport", None)
        if callable(viewport):
            try:
                resolved = viewport()
                if resolved is not None:
                    return resolved
            except Exception:
                pass
        viewport = getattr(target, "viewport", None)
        if callable(viewport):
            try:
                resolved = viewport()
                if resolved is not None:
                    return resolved
            except Exception:
                pass
        return target

    def _finish_content_paint_metric(self, target, token: int, *, timeout: bool = False) -> None:
        pending = self.__dict__.get("_content_paint_metric_targets") or {}
        data = pending.get(id(target))
        if not data or int(data.get("token") or 0) != int(token):
            return
        pending.pop(id(target), None)
        try:
            target.removeEventFilter(self)
        except Exception:
            pass
        extra = str(data.get("extra") or "")
        if timeout:
            extra = f"{extra}; paint=timeout" if extra else "paint=timeout"
        self.mark_content_ready(
            stage=str(data.get("stage") or "content.painted"),
            extra=extra,
            started_at=float(data.get("started_at") or 0.0),
        )

    def eventFilter(self, watched, event):  # noqa: N802
        try:
            event_type = event.type()
        except Exception:
            event_type = None
        if event_type == QEvent.Type.Paint:
            pending = self.__dict__.get("_content_paint_metric_targets") or {}
            data = pending.get(id(watched))
            if data:
                self._finish_content_paint_metric(watched, int(data.get("token") or 0))
        try:
            return bool(super().eventFilter(watched, event))
        except Exception:
            return False

    def run_when_page_ready(self, callback) -> bool:
        if not callable(callback):
            return False
        if bool(getattr(self, "_cleanup_in_progress", False)):
            return False
        if self.is_page_ready():
            self._schedule_lifecycle_action(callback)
            return True
        self._ready_callbacks.append(callback)
        return False

    def _resolve_ui_language(self) -> str:
        try:
            from settings.appearance import peek_warmed_ui_language

            return normalize_language(peek_warmed_ui_language())
        except Exception:
            return normalize_language(None)

    # ------------------------------------------------------------------
    # Public helpers (backward-compat with all 40+ pages)
    # ------------------------------------------------------------------

    def add_widget(self, widget: QWidget, stretch: int = 0):
        """Добавляет виджет на страницу"""
        self.vBoxLayout.addWidget(widget, stretch)

    def add_spacing(self, height: int = 16):
        """Добавляет вертикальный отступ"""
        from PyQt6.QtWidgets import QSpacerItem
        spacer = QSpacerItem(0, height, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        self.vBoxLayout.addItem(spacer)

    def add_section_title(
        self,
        text: str = "",
        return_widget: bool = False,
        *,
        text_key: str | None = None,
    ):
        """Добавляет заголовок секции"""
        fallback_text = text
        if text_key:
            text = tr_catalog(text_key, language=self._ui_language, default=text or text_key)

        label = StrongBodyLabel(self.content)
        label.setText(text)
        set_state_text(label, f"Раздел страницы: {text}")
        label.setProperty("tone", "primary")
        if text_key:
            self._section_title_bindings.append((label, text_key, fallback_text or text_key))
        self.vBoxLayout.addWidget(label)
        if return_widget:
            return label

    def set_ui_language(self, language: str) -> None:
        self._ui_language = normalize_language(language)
        self._retranslate_base_texts()

    def _apply_page_theme(self, tokens=None, force: bool = False) -> None:
        _ = tokens
        _ = force

    def _create_page_theme_refresh_if_needed(self):
        if type(self)._apply_page_theme is BasePage._apply_page_theme:
            return None
        from ui.theme_refresh import ThemeRefreshBinding

        return ThemeRefreshBinding(
            self,
            self._apply_page_theme,
            is_build_pending=lambda: False,
        )

    def _flush_page_theme_refresh(self) -> None:
        started_at = _time.perf_counter()
        try:
            if self._page_theme_refresh is None:
                return
            self._page_theme_refresh.flush_pending()
        except Exception:
            pass
        finally:
            self._log_show_step_timing("qt_show.theme_flush", started_at)

    def _schedule_page_theme_refresh_flush(self) -> None:
        QTimer.singleShot(0, self._flush_page_theme_refresh)

    def _sync_content_width_to_viewport(self) -> None:
        """Не даёт странице становиться шире видимой области."""

        try:
            width = max(0, int(self.viewport().width()))
            if width > 0 and self.content.maximumWidth() != width:
                self.content.setMaximumWidth(width)
                self.content.updateGeometry()
        except Exception:
            pass

    def _log_show_step_timing(self, stage: str, started_at: float, *, threshold_ms: int = 15) -> None:
        elapsed_ms = (_time.perf_counter() - started_at) * 1000
        if elapsed_ms < int(threshold_ms):
            return
        log_page_timing(self._page_label(), stage, elapsed_ms)

    def showEvent(self, event):  # noqa: N802 (Qt override)
        super().showEvent(event)
        step_started_at = _time.perf_counter()
        self._sync_content_width_to_viewport()
        self._log_show_step_timing("qt_show.sync_width", step_started_at)
        step_started_at = _time.perf_counter()
        self._flush_ready_callbacks()
        self._log_show_step_timing("qt_show.ready_callbacks", step_started_at)
        step_started_at = _time.perf_counter()
        self._schedule_activation()
        self._log_show_step_timing("qt_show.schedule_activation", step_started_at)
        step_started_at = _time.perf_counter()
        self._schedule_page_theme_refresh_flush()
        self._log_show_step_timing("qt_show.schedule_theme_flush", step_started_at)
        self.request_keyboard_focus()

    def request_keyboard_focus(self) -> None:
        """Просит страницу поставить фокус на первый удобный для клавиатуры элемент."""

        self._schedule_first_keyboard_focus()

    def _schedule_first_keyboard_focus(self) -> None:
        QTimer.singleShot(0, self._focus_first_keyboard_control_if_needed)

    def _focus_first_keyboard_control_if_needed(self) -> None:
        """Ставит фокус на первый управляемый с клавиатуры элемент страницы."""

        if not self.isVisible():
            return
        if self._has_focus_inside_page():
            return
        target = self._first_keyboard_focus_control()
        if target is None:
            return
        try:
            target.setFocus(Qt.FocusReason.OtherFocusReason)
        except Exception:
            pass

    def _has_focus_inside_page(self) -> bool:
        focus_widget = QApplication.focusWidget()
        if focus_widget is None:
            return False
        if focus_widget is self or focus_widget is self.content:
            return True
        try:
            return bool(self.isAncestorOf(focus_widget))
        except Exception:
            return False

    def _first_keyboard_focus_control(self):
        for widget in self._iter_keyboard_focus_candidates():
            if self._is_keyboard_focus_control(widget):
                return widget
        return None

    def _iter_keyboard_focus_candidates(self):
        try:
            return tuple(self.content.findChildren(QWidget))
        except Exception:
            return ()

    @staticmethod
    def _is_keyboard_focus_control(widget) -> bool:
        try:
            if not widget.isEnabled() or not widget.isVisible():
                return False
        except Exception:
            return False
        try:
            object_name = str(widget.objectName() or "")
        except Exception:
            object_name = ""
        if object_name in {"lineEditButton"}:
            return False
        if type(widget).__name__ in {"ArrowButton", "Indicator"}:
            return False
        try:
            policy = widget.focusPolicy()
        except Exception:
            return False
        return policy in (
            Qt.FocusPolicy.TabFocus,
            Qt.FocusPolicy.StrongFocus,
            Qt.FocusPolicy.WheelFocus,
        )

    def resizeEvent(self, event):  # noqa: N802 (Qt override)
        super().resizeEvent(event)
        self._sync_content_width_to_viewport()

    def hideEvent(self, event):  # noqa: N802 (Qt override)
        self._cancel_page_lifecycle(reason="hidden")
        self.cancel_page_loads(reason="hidden")
        try:
            self.on_page_hidden()
        except Exception:
            pass
        super().hideEvent(event)

    def _run_page_activation(self, token: int) -> None:
        if not self._is_page_lifecycle_token_current(token):
            return
        if not self.isVisible():
            return

        first_show = not bool(self._page_first_activation_done)
        if first_show:
            self._page_first_activation_done = True

        started_at = _time.perf_counter()
        try:
            self.on_page_activated()
        except Exception:
            pass
        finally:
            log_page_timing(
                self._page_label(),
                "open.activation.first" if first_show else "open.activation.repeat",
                (_time.perf_counter() - started_at) * 1000,
                budget_ms=(
                    self._resolve_page_budget("first_show_budget_ms")
                    if first_show
                    else self._resolve_page_budget("repeat_show_budget_ms")
                ),
                important=True,
                threshold_ms=0,
            )
            if self._auto_mark_content_ready_after_activation():
                self.mark_content_ready()

    def _issue_page_lifecycle_token(self, *, reason: str = "") -> int:
        _ = reason
        self._page_lifecycle_generation += 1
        return self._page_lifecycle_generation

    def _schedule_activation(self) -> None:
        token = self._issue_page_lifecycle_token(reason="show:activate")
        self._schedule_lifecycle_action(lambda t=token: self._run_page_activation(t))

    def _cancel_page_lifecycle(self, *, reason: str = "") -> int:
        _ = reason
        self._page_lifecycle_generation += 1
        return self._page_lifecycle_generation

    def _is_page_lifecycle_token_current(self, token: int) -> bool:
        return int(token) == int(self._page_lifecycle_generation)

    def _issue_page_load_token(self, *, reason: str = "") -> int:
        _ = reason
        self._page_load_generation += 1
        return self._page_load_generation

    def _cancel_page_loads(self, *, reason: str = "") -> int:
        _ = reason
        self._page_load_generation += 1
        return self._page_load_generation

    def _is_page_load_token_current(self, token: int) -> bool:
        return int(token) == int(self._page_load_generation)

    @staticmethod
    def _schedule_lifecycle_action(callback) -> None:
        QTimer.singleShot(0, callback)

    def _flush_ready_callbacks(self) -> None:
        if not self.is_page_ready():
            return
        callbacks = list(self._ready_callbacks)
        self._ready_callbacks.clear()
        for callback in callbacks:
            if callable(callback):
                self._schedule_lifecycle_action(callback)

    def cleanup(self) -> None:
        self._cleanup_in_progress = True
        self._ready_callbacks.clear()
        self._cancel_page_lifecycle(reason="cleanup")
        self.cancel_page_loads(reason="cleanup")
        try:
            self._page_theme_refresh.cleanup()
        except Exception:
            pass

    def _retranslate_base_texts(self) -> None:
        if self._title_key and hasattr(self, "title_label") and self.title_label is not None:
            try:
                title_text = tr_catalog(
                    self._title_key,
                    language=self._ui_language,
                    default=self._title_fallback,
                )
                self.title_label.setText(title_text)
                set_state_text(self.title_label, f"Заголовок страницы: {title_text}")
            except Exception:
                pass

        subtitle_text = ""
        if self._subtitle_key:
            subtitle_text = tr_catalog(
                self._subtitle_key,
                language=self._ui_language,
                default=self._subtitle_fallback,
            )

        if hasattr(self, "subtitle_label") and self.subtitle_label is not None:
            try:
                if self._subtitle_key:
                    self.subtitle_label.setText(subtitle_text)
                self.subtitle_label.setVisible(bool(self.subtitle_label.text().strip()))
                if self.subtitle_label.text().strip():
                    set_state_text(self.subtitle_label, f"Описание страницы: {self.subtitle_label.text()}")
            except Exception:
                pass

        for label, text_key, fallback_text in list(self._section_title_bindings):
            if label is None:
                continue
            try:
                text_setter = getattr(label, "setText", None)
                if callable(text_setter):
                    section_text = tr_catalog(
                        text_key,
                        language=self._ui_language,
                        default=fallback_text,
                    )
                    text_setter(section_text)
                    set_state_text(label, f"Раздел страницы: {section_text}")
            except Exception:
                pass
