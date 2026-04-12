# filters/ui/collapsible_group.py
"""
Сворачиваемые группы для группировки стратегий по сервисам.
Использует встроенные виджеты qfluentwidgets: StrongBodyLabel, HorizontalSeparator.
"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QCursor

from ui.theme import get_cached_qta_pixmap, get_theme_tokens
from ui.theme_refresh import ThemeRefreshController

try:
    from qfluentwidgets import StrongBodyLabel, HorizontalSeparator
    _HAS_FLUENT = True
except ImportError:
    StrongBodyLabel = None   # type: ignore[assignment,misc]
    HorizontalSeparator = None  # type: ignore[assignment,misc]
    _HAS_FLUENT = False


class CollapsibleServiceHeader(QFrame):
    """
    Заголовок сворачиваемой группы сервиса.

    Содержит:
    - Chevron иконку (вправо/вниз)
    - Название группы (StrongBodyLabel)
    - Линию-разделитель (HorizontalSeparator)

    Signals:
        toggled(str, bool): (group_key, is_expanded)
    """

    toggled = pyqtSignal(str, bool)

    def __init__(self, group_key: str, title: str, parent=None):
        super().__init__(parent)
        self._group_key = group_key
        self._title = title
        self._expanded = True
        self._pressed = False
        self._build_ui()

    @property
    def group_key(self) -> str:
        return self._group_key

    @property
    def is_expanded(self) -> bool:
        return self._expanded

    def _build_ui(self):
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setFixedHeight(28)
        self.setProperty("clickable", True)
        self.setProperty("noDrag", True)

        # Static hover — semi-transparent neutral, works in both light and dark
        self.setStyleSheet("""
            CollapsibleServiceHeader {
                background: transparent;
                border: none;
                border-radius: 4px;
            }
            CollapsibleServiceHeader:hover {
                background: rgba(128, 128, 128, 0.08);
            }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 0, 8, 0)
        layout.setSpacing(6)

        # Chevron
        self._chevron = QLabel()
        self._chevron.setFixedSize(16, 16)
        self._update_chevron()
        layout.addWidget(self._chevron)

        # Название группы
        if _HAS_FLUENT and StrongBodyLabel is not None:
            self._title_label = StrongBodyLabel(self._title)
        else:
            from PyQt6.QtGui import QFont
            self._title_label = QLabel(self._title)
            self._title_label.setFont(QFont("Segoe UI Semibold", 10))
        layout.addWidget(self._title_label)

        # Линия-разделитель (растягивается)
        if _HAS_FLUENT and HorizontalSeparator is not None:
            self._line = HorizontalSeparator()
        else:
            self._line = QFrame()
            self._line.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(self._line, 1)
        self._theme_refresh = ThemeRefreshController(self, self._update_chevron)

    def _update_chevron(self):
        icon_name = "fa5s.chevron-down" if self._expanded else "fa5s.chevron-right"
        try:
            tokens = get_theme_tokens()
            color = "#666666" if tokens.is_light else "#808080"
        except Exception:
            color = "#808080"
        self._chevron.setPixmap(get_cached_qta_pixmap(icon_name, color=color, size=12))

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._pressed = True
            event.accept()
        return super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            was_pressed = bool(self._pressed)
            self._pressed = False
            if was_pressed and self.rect().contains(event.position().toPoint()):
                self.toggle()
                event.accept()
        return super().mouseReleaseEvent(event)

    def leaveEvent(self, event):  # noqa: N802
        self._pressed = False
        return super().leaveEvent(event)

    def toggle(self):
        self._expanded = not self._expanded
        self._update_chevron()
        self.toggled.emit(self._group_key, self._expanded)

    def set_expanded(self, expanded: bool):
        if self._expanded != expanded:
            self._expanded = expanded
            self._update_chevron()


class CollapsibleGroup(QWidget):
    """
    Сворачиваемая группа с заголовком и контентом.

    Signals:
        toggled(str, bool): (group_key, is_expanded)
    """

    toggled = pyqtSignal(str, bool)

    def __init__(self, group_key: str, title: str, parent=None):
        super().__init__(parent)
        self._group_key = group_key
        self._content_widget = None
        self._build_ui(title)

    @property
    def group_key(self) -> str:
        return self._group_key

    @property
    def is_expanded(self) -> bool:
        return self._header.is_expanded

    @property
    def content_widget(self) -> QWidget:
        return self._content_widget

    def _build_ui(self, title: str):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self._header = CollapsibleServiceHeader(self._group_key, title, self)
        self._header.toggled.connect(self._on_header_toggled)
        layout.addWidget(self._header)

        self._content_container = QWidget()
        self._content_layout = QVBoxLayout(self._content_container)
        self._content_layout.setContentsMargins(20, 0, 0, 8)
        self._content_layout.setSpacing(4)
        layout.addWidget(self._content_container)

    def _on_header_toggled(self, group_key: str, is_expanded: bool):
        self._content_container.setVisible(is_expanded)
        self.toggled.emit(group_key, is_expanded)

    def set_content(self, widget: QWidget):
        if self._content_widget:
            self._content_layout.removeWidget(self._content_widget)
            self._content_widget.deleteLater()
        self._content_widget = widget
        self._content_layout.addWidget(widget)

    def add_widget(self, widget: QWidget):
        self._content_layout.addWidget(widget)

    def set_expanded(self, expanded: bool):
        self._header.set_expanded(expanded)
        self._content_container.setVisible(expanded)

    def clear_content(self):
        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._content_widget = None
