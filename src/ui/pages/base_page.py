# ui/pages/base_page.py
"""Базовый класс для страниц — использует qfluentwidgets ScrollArea."""

import sys
from PyQt6.QtCore import Qt, QEvent, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QScrollArea, QFrame,
    QSizePolicy, QPlainTextEdit, QTextEdit,
)
from PyQt6.QtGui import QFont

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
from ui.theme_refresh import ThemeRefreshController


def _apply_widget_smooth_mode(widget, enabled: bool) -> None:
    try:
        from PyQt6.QtCore import Qt
        from qfluentwidgets.common.smooth_scroll import SmoothMode

        mode = SmoothMode.COSINE if enabled else SmoothMode.NO_SMOOTH

        def _apply_delegate_mode(delegate) -> None:
            if delegate is None:
                return
            try:
                if hasattr(delegate, "useAni"):
                    if not hasattr(delegate, "_zapret_base_use_ani"):
                        delegate._zapret_base_use_ani = bool(delegate.useAni)
                    delegate.useAni = bool(delegate._zapret_base_use_ani) if enabled else False
            except Exception:
                pass

            for smooth_attr in ("verticalSmoothScroll", "horizonSmoothScroll"):
                smooth = getattr(delegate, smooth_attr, None)
                setter = getattr(smooth, "setSmoothMode", None)
                if callable(setter):
                    try:
                        setter(mode)
                    except Exception:
                        pass

            setter = getattr(delegate, "setSmoothMode", None)
            if callable(setter):
                try:
                    setter(mode)
                except TypeError:
                    try:
                        setter(mode, Qt.Orientation.Vertical)
                    except Exception:
                        pass
                except Exception:
                    pass

        setter = getattr(widget, "setSmoothMode", None)
        if not callable(setter):
            _apply_delegate_mode(getattr(widget, "scrollDelegate", None))
            _apply_delegate_mode(getattr(widget, "scrollDelagate", None))
            _apply_delegate_mode(getattr(widget, "delegate", None))
            return

        try:
            setter(mode, Qt.Orientation.Vertical)
        except TypeError:
            setter(mode)

        _apply_delegate_mode(getattr(widget, "scrollDelegate", None))
        _apply_delegate_mode(getattr(widget, "scrollDelagate", None))
        _apply_delegate_mode(getattr(widget, "delegate", None))
    except Exception:
        pass


class ScrollBlockingPlainTextEdit(_FluentPlainTextEdit):
    """PlainTextEdit с fluent-скроллбарами, не пропускающий прокрутку к родителю.

    SmoothScrollDelegate (из qfluentwidgets) намеренно пропускает wheel-событие
    к родителю когда достигнута граница скролла (return False в eventFilter).
    Переопределяем wheelEvent чтобы принять событие и не дать BasePage прокрутиться.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setProperty("noDrag", True)
        try:
            from config.reg import get_smooth_scroll_enabled
            self.set_smooth_scroll_enabled(get_smooth_scroll_enabled())
        except Exception:
            pass

    def set_smooth_scroll_enabled(self, enabled: bool) -> None:
        _apply_widget_smooth_mode(self, enabled)

    def wheelEvent(self, event):
        # SmoothScrollDelegate поглощает событие когда НЕ у границы (возвращает True),
        # поэтому этот метод вызывается ТОЛЬКО у границы скролла.
        event.accept()


class ScrollBlockingTextEdit(_FluentTextEdit):
    """TextEdit с fluent-скроллбарами, не пропускающий прокрутку к родителю."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setProperty("noDrag", True)
        try:
            from config.reg import get_smooth_scroll_enabled
            self.set_smooth_scroll_enabled(get_smooth_scroll_enabled())
        except Exception:
            pass

    def set_smooth_scroll_enabled(self, enabled: bool) -> None:
        _apply_widget_smooth_mode(self, enabled)

    def wheelEvent(self, event):
        event.accept()


class BasePage(_FluentScrollArea):
    """Базовый класс для страниц контента.

    Uses qfluentwidgets ScrollArea for smooth Fluent-style scrolling.
    The public API (self.layout, add_widget, add_spacing, add_section_title,
    self.parent_app, self.title_label, self.subtitle_label) is kept
    backward-compatible so all 40+ pages work without changes.
    """

    ui_built = pyqtSignal()

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
        self._deferred_ui_build_enabled = False
        self._deferred_ui_build_done = True
        self._deferred_ui_build_callable = None
        self._deferred_ui_after_build = None
        self._page_theme_refresh = ThemeRefreshController(
            self,
            self._apply_page_theme,
            is_build_pending=self.is_deferred_ui_build_pending,
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

        # Apply smooth scroll preference from registry
        try:
            from config.reg import get_smooth_scroll_enabled
            from qfluentwidgets.common.smooth_scroll import SmoothMode
            if not get_smooth_scroll_enabled():
                self.setSmoothMode(SmoothMode.NO_SMOOTH, Qt.Orientation.Vertical)
        except Exception:
            pass

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

    def enable_deferred_ui_build(self, *, build=None, after_build=None) -> None:
        """Переводит страницу на канонический deferred-build путь.

        После этого основной UI страницы должен собираться не в `__init__`,
        а при первом реальном показе страницы. Это уменьшает стоимость
        lazy-инициализации страницы в момент первого клика по навигации.
        """
        self._deferred_ui_build_enabled = True
        self._deferred_ui_build_done = False
        self._deferred_ui_build_callable = build
        self._deferred_ui_after_build = after_build

    def is_deferred_ui_build_pending(self) -> bool:
        return bool(self._deferred_ui_build_enabled) and not bool(self._deferred_ui_build_done)

    def ensure_deferred_ui_built(self) -> bool:
        if not self.is_deferred_ui_build_pending():
            return False

        builder = getattr(self, "_deferred_ui_build_callable", None)
        if not callable(builder):
            builder = getattr(self, "_build_ui", None)
        after_build = getattr(self, "_deferred_ui_after_build", None)

        if not callable(builder):
            self._deferred_ui_build_done = True
            return False

        builder()
        self._deferred_ui_build_done = True

        if callable(after_build):
            after_build()

        self._postprocess_deferred_ui_build()

        self.ui_built.emit()
        return True

    def _postprocess_deferred_ui_build(self) -> None:
        """Доводит тему/шрифты/локализацию после поздней сборки UI.

        При deferred-build часть страниц создаёт виджеты уже после того, как
        приложение успело применить тему, шрифты и язык интерфейса. Без явной
        дополировки некоторые страницы могут остаться с сырыми стилями или
        недообновлёнными подписями.
        """
        try:
            self.ensurePolished()
        except Exception:
            pass

        try:
            content = getattr(self, "content", None)
            if content is not None:
                content.ensurePolished()
        except Exception:
            pass

        try:
            self._retranslate_base_texts()
        except Exception:
            pass

        set_ui_language = getattr(self, "set_ui_language", None)
        if callable(set_ui_language):
            try:
                set_ui_language(self._ui_language)
            except Exception:
                pass

        try:
            self._page_theme_refresh.invalidate()
            self._page_theme_refresh.request_refresh(force=True)
        except Exception:
            pass

        try:
            style = self.style()
            if style is not None:
                style.unpolish(self)
                style.polish(self)
        except Exception:
            pass

        try:
            content = getattr(self, "content", None)
            if content is not None:
                style = content.style()
                if style is not None:
                    style.unpolish(content)
                    style.polish(content)
        except Exception:
            pass

        try:
            self.updateGeometry()
            self.update()
            content = getattr(self, "content", None)
            if content is not None:
                content.updateGeometry()
                content.update()
        except Exception:
            pass

    def _resolve_ui_language(self) -> str:
        try:
            from config.reg import get_ui_language

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

    def showEvent(self, event):  # noqa: N802 (Qt override)
        super().showEvent(event)
        if not bool(getattr(self, "_deferred_ui_build_enabled", False)):
            try:
                self._page_theme_refresh.flush_pending()
            except Exception:
                pass
            return
        if event is not None and event.spontaneous():
            try:
                self._page_theme_refresh.flush_pending()
            except Exception:
                pass
            return
        self.ensure_deferred_ui_built()
        try:
            self._page_theme_refresh.flush_pending()
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
