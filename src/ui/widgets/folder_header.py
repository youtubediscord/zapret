from __future__ import annotations

from PyQt6.QtCore import QEvent, QRect, Qt, pyqtSignal
from PyQt6.QtGui import QCursor, QFontMetrics, QPainter
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QStyle, QStyleOptionViewItem, QVBoxLayout, QWidget
from qfluentwidgets import HorizontalSeparator, StrongBodyLabel

from ui.presets_menu.common import cached_icon, to_qcolor
from ui.theme import get_cached_qta_pixmap, get_theme_tokens
from ui.theme_refresh import ThemeRefreshBinding


FOLDER_HEADER_HEIGHT = 28


def folder_header_icon_name(expanded: bool) -> str:
    return "fa5s.chevron-down" if bool(expanded) else "fa5s.chevron-right"


def folder_header_title(title: object, count: int = 0) -> str:
    text = str(title or "").strip()
    try:
        normalized_count = int(count or 0)
    except Exception:
        normalized_count = 0
    if normalized_count > 0:
        return f"{text}  {normalized_count}"
    return text


def folder_header_icon_color() -> str:
    try:
        tokens = get_theme_tokens()
        return "#666666" if tokens.is_light else "#808080"
    except Exception:
        return "#808080"


def is_folder_toggle_click(event) -> bool:
    try:
        return (
            event.type() == QEvent.Type.MouseButtonRelease
            and event.button() == Qt.MouseButton.LeftButton
        )
    except Exception:
        return False


class FolderGroupHeader(QFrame):
    toggled = pyqtSignal(str, bool)

    def __init__(self, group_key: str, title: str, parent=None):
        super().__init__(parent)
        self._group_key = str(group_key or "")
        self._title = str(title or "")
        self._expanded = True
        self._pressed = False
        self._build_ui()

    @property
    def group_key(self) -> str:
        return self._group_key

    @property
    def is_expanded(self) -> bool:
        return self._expanded

    def _build_ui(self) -> None:
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setFixedHeight(FOLDER_HEADER_HEIGHT)
        self.setProperty("clickable", True)
        self.setProperty("noDrag", True)
        self.setProperty("folderHeader", True)
        self.setStyleSheet("""
            QFrame[folderHeader="true"] {
                background: transparent;
                border: none;
                border-radius: 4px;
            }
            QFrame[folderHeader="true"]:hover {
                background: rgba(128, 128, 128, 0.08);
            }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 8, 0)
        layout.setSpacing(4)

        self._chevron = QLabel()
        self._chevron.setFixedSize(16, 16)
        self._update_chevron()
        layout.addWidget(self._chevron)

        self._title_label = StrongBodyLabel(self._title)
        layout.addWidget(self._title_label)

        self._line = HorizontalSeparator()
        layout.addWidget(self._line, 1)
        self._theme_refresh = ThemeRefreshBinding(self, self._update_chevron)

    def _update_chevron(self) -> None:
        self._chevron.setPixmap(
            get_cached_qta_pixmap(
                folder_header_icon_name(self._expanded),
                color=folder_header_icon_color(),
                size=12,
            )
        )

    def mousePressEvent(self, event):  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._pressed = True
            event.accept()
        return super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):  # noqa: N802
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

    def toggle(self) -> None:
        self._expanded = not self._expanded
        self._update_chevron()
        self.toggled.emit(self._group_key, self._expanded)

    def set_expanded(self, expanded: bool) -> None:
        if self._expanded != bool(expanded):
            self._expanded = bool(expanded)
            self._update_chevron()


class FolderGroup(QWidget):
    toggled = pyqtSignal(str, bool)

    def __init__(self, group_key: str, title: str, parent=None):
        super().__init__(parent)
        self._group_key = str(group_key or "")
        self._content_widget = None
        self._build_ui(str(title or ""))

    @property
    def group_key(self) -> str:
        return self._group_key

    @property
    def is_expanded(self) -> bool:
        return self._header.is_expanded

    @property
    def content_widget(self) -> QWidget:
        return self._content_widget

    def _build_ui(self, title: str) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self._header = FolderGroupHeader(self._group_key, title, self)
        self._header.toggled.connect(self._on_header_toggled)
        layout.addWidget(self._header)

        self._content_container = QWidget()
        self._content_layout = QVBoxLayout(self._content_container)
        self._content_layout.setContentsMargins(20, 0, 0, 8)
        self._content_layout.setSpacing(4)
        layout.addWidget(self._content_container)

    def _on_header_toggled(self, group_key: str, is_expanded: bool) -> None:
        self._content_container.setVisible(is_expanded)
        self.toggled.emit(group_key, is_expanded)

    def set_content(self, widget: QWidget) -> None:
        if self._content_widget:
            self._content_layout.removeWidget(self._content_widget)
            self._content_widget.deleteLater()
        self._content_widget = widget
        self._content_layout.addWidget(widget)

    def add_widget(self, widget: QWidget) -> None:
        self._content_layout.addWidget(widget)

    def set_expanded(self, expanded: bool) -> None:
        self._header.set_expanded(expanded)
        self._content_container.setVisible(expanded)

    def clear_content(self) -> None:
        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._content_widget = None


def paint_folder_header_row(
    painter: QPainter,
    option: QStyleOptionViewItem,
    *,
    title: str,
    expanded: bool,
    count: int = 0,
) -> None:
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    tokens = get_theme_tokens()

    row_rect = option.rect.adjusted(4, 1, -4, -1)
    if bool(option.state & QStyle.StateFlag.State_MouseOver):
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(to_qcolor(tokens.surface_bg_hover, "rgba(128,128,128,0.08)"))
        painter.drawRoundedRect(row_rect, 4, 4)

    rect = option.rect.adjusted(12, 0, -12, 0)
    icon_rect = QRect(rect.left(), rect.center().y() - 6, 12, 12)
    cached_icon(folder_header_icon_name(expanded), folder_header_icon_color()).paint(painter, icon_rect)

    text = folder_header_title(title, count)
    text_rect = QRect(icon_rect.right() + 8, rect.top(), max(0, rect.width() - 20), rect.height())
    painter.setPen(to_qcolor(tokens.fg, "#f5f5f5"))
    painter.drawText(text_rect, int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter), text)

    line_y = rect.center().y()
    metrics = QFontMetrics(painter.font())
    left_end = text_rect.left() + metrics.horizontalAdvance(text) + 12
    if left_end < rect.right():
        painter.setPen(to_qcolor(tokens.divider, "#5f6368"))
        painter.drawLine(left_end, line_y, rect.right(), line_y)

    painter.restore()


__all__ = [
    "FOLDER_HEADER_HEIGHT",
    "FolderGroup",
    "FolderGroupHeader",
    "folder_header_icon_color",
    "folder_header_icon_name",
    "folder_header_title",
    "is_folder_toggle_click",
    "paint_folder_header_row",
]
