# ui/pages/base_page.py
"""Базовый класс для страниц — использует qfluentwidgets ScrollArea."""

import time as _time
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QScrollArea, QFrame,
    QSizePolicy, QPlainTextEdit, QTextEdit,
)

try:
    from qfluentwidgets import (ScrollArea as _FluentScrollArea, TitleLabel, BodyLabel, StrongBodyLabel,
                                PlainTextEdit as _FluentPlainTextEdit, TextEdit as _FluentTextEdit)
    _USE_FLUENT = True
except ImportError:
    _FluentScrollArea = QScrollArea
    _FluentPlainTextEdit = QPlainTextEdit
    _FluentTextEdit = QTextEdit
    _USE_FLUENT = False

from ui.text_catalog import tr as tr_catalog, normalize_language
from ui.page_performance import log_page_metric
from ui.theme_refresh import ThemeRefreshController
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
    self.parent_app, self.title_label, self.subtitle_label) is kept
    backward-compatible so all 40+ pages work without changes.
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
        self.parent_app = parent
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
        self._ready_callbacks: list[object] = []
        self._cleanup_in_progress = False
        self._page_theme_refresh = ThemeRefreshController(
            self,
            self._apply_page_theme,
            is_build_pending=lambda: False,
        )

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

        # --- Content container ---
        self.content = QWidget(self)
        self.content.setStyleSheet("background-color: transparent;")
        # Expanding horizontally so the content fills the viewport width and
        # word-wrapped labels can actually wrap instead of overflowing.
        self.content.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.setWidget(self.content)

        # --- Main layout (backward-compat: self.layout) ---
        self.vBoxLayout = QVBoxLayout(self.content)
        self.vBoxLayout.setContentsMargins(36, 28, 36, 28)
        self.vBoxLayout.setSpacing(16)
        self.vBoxLayout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Backward compatibility: old pages use self.layout.addWidget(...)
        self.layout = self.vBoxLayout

        # --- Title ---
        if _USE_FLUENT:
            self.title_label = TitleLabel(self.content)
            self.title_label.setText(title)
        else:
            self.title_label = QLabel(title)
            self.title_label.setStyleSheet(
                "font-size: 28px; font-weight: 600; "
                "font-family: 'Segoe UI Variable Display', 'Segoe UI', sans-serif; "
                "padding-bottom: 4px;"
            )
        self.vBoxLayout.addWidget(self.title_label)

        # --- Subtitle ---
        if subtitle:
            if _USE_FLUENT:
                self.subtitle_label = BodyLabel(self.content)
                self.subtitle_label.setText(subtitle)
            else:
                self.subtitle_label = QLabel(subtitle)
                self.subtitle_label.setStyleSheet("font-size: 12px; padding-bottom: 16px;")
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
            from settings.store import get_ui_language

            return normalize_language(get_ui_language())
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

        if _USE_FLUENT:
            label = StrongBodyLabel(self.content)
            label.setText(text)
        else:
            label = QLabel(text)
            label.setStyleSheet("font-size: 13px; font-weight: 600; padding-top: 8px; padding-bottom: 4px;")
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

    def _flush_page_theme_refresh(self) -> None:
        try:
            self._page_theme_refresh.flush_pending()
        except Exception:
            pass

    def showEvent(self, event):  # noqa: N802 (Qt override)
        super().showEvent(event)
        is_spontaneous = bool(event is not None and event.spontaneous())
        if is_spontaneous:
            self._flush_page_theme_refresh()
            return
        self._flush_ready_callbacks()
        self._schedule_activation()
        self._flush_page_theme_refresh()

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
            log_page_metric(
                self._page_label(),
                "activation.first" if first_show else "activation.repeat",
                (_time.perf_counter() - started_at) * 1000,
                budget_ms=(
                    self._resolve_page_budget("first_show_budget_ms")
                    if first_show
                    else self._resolve_page_budget("repeat_show_budget_ms")
                ),
            )

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
                self.title_label.setText(
                    tr_catalog(
                        self._title_key,
                        language=self._ui_language,
                        default=self._title_fallback,
                    )
                )
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
            except Exception:
                pass

        for label, text_key, fallback_text in list(self._section_title_bindings):
            if label is None:
                continue
            try:
                text_setter = getattr(label, "setText", None)
                if callable(text_setter):
                    text_setter(
                        tr_catalog(
                            text_key,
                            language=self._ui_language,
                            default=fallback_text,
                        )
                    )
            except Exception:
                pass
