from __future__ import annotations

from PyQt6.QtCore import QEvent, QPoint, QRect, Qt, pyqtSignal
from PyQt6.QtGui import QCursor, QFont, QFontMetrics, QPainter
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QStyle, QStyleOptionViewItem, QVBoxLayout, QWidget
from qfluentwidgets import HorizontalSeparator, StrongBodyLabel

from ui.accessibility import set_control_accessibility, set_state_text
from ui.presets_menu.common import cached_icon, to_qcolor
from ui.theme import get_cached_qta_pixmap, get_theme_tokens
from ui.theme_refresh import ThemeRefreshBinding


FOLDER_HEADER_HEIGHT = 28
FOLDER_HEADER_RADIUS = 4
FOLDER_HEADER_ICON_BOX = 16
FOLDER_HEADER_ICON_SIZE = 12
FOLDER_HEADER_LEFT_MARGIN = 0
FOLDER_HEADER_RIGHT_MARGIN = 8
FOLDER_HEADER_GAP = 4
FOLDER_HEADER_LINE_GAP = 12
FOLDER_HEADER_HOVER_BG = "rgba(128, 128, 128, 0.08)"
FOLDER_HEADER_STYLE_SHEET = f"""
    QFrame[folderHeader="true"] {{
        background: transparent;
        border: none;
        border-radius: {FOLDER_HEADER_RADIUS}px;
    }}
    QFrame[folderHeader="true"]:hover {{
        background: {FOLDER_HEADER_HOVER_BG};
    }}
"""


def folder_header_icon_name(expanded: bool) -> str:
    return "fa5s.chevron-down" if bool(expanded) else "fa5s.chevron-right"


def folder_header_title(title: object, count: int = 0) -> str:
    text = str(title or "").strip()
    normalized_count = _safe_count(count)
    if normalized_count > 0:
        return f"{text}  {normalized_count}"
    return text


def folder_header_font(base_font: QFont) -> QFont:
    font = QFont(base_font)
    font.setWeight(QFont.Weight.DemiBold)
    return font


def _safe_count(count: object) -> int:
    try:
        return max(0, int(count or 0))
    except Exception:
        return 0


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
    context_requested = pyqtSignal(str, QPoint)

    def __init__(self, group_key: str, title: str, parent=None, *, count: int = 0):
        super().__init__(parent)
        self._group_key = str(group_key or "")
        self._title = str(title or "")
        self._count = _safe_count(count)
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
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setFixedHeight(FOLDER_HEADER_HEIGHT)
        self.setProperty("clickable", True)
        self.setProperty("noDrag", True)
        self.setProperty("folderHeader", True)
        self.setStyleSheet(FOLDER_HEADER_STYLE_SHEET)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(FOLDER_HEADER_LEFT_MARGIN, 0, FOLDER_HEADER_RIGHT_MARGIN, 0)
        layout.setSpacing(FOLDER_HEADER_GAP)

        self._chevron = QLabel()
        self._chevron.setFixedSize(FOLDER_HEADER_ICON_BOX, FOLDER_HEADER_ICON_BOX)
        self._update_chevron()
        layout.addWidget(self._chevron)

        self._title_label = StrongBodyLabel(folder_header_title(self._title, self._count))
        self._title_label.setFont(folder_header_font(self._title_label.font()))
        layout.addWidget(self._title_label)

        self._line = HorizontalSeparator()
        layout.addWidget(self._line, 1)
        self._theme_refresh = ThemeRefreshBinding(self, self._update_chevron)
        self._update_accessibility()

    def _update_chevron(self) -> None:
        self._chevron.setPixmap(
            get_cached_qta_pixmap(
                folder_header_icon_name(self._expanded),
                color=folder_header_icon_color(),
                size=FOLDER_HEADER_ICON_SIZE,
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

    def keyPressEvent(self, event):  # noqa: N802
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self.toggle()
            event.accept()
            return
        return super().keyPressEvent(event)

    def leaveEvent(self, event):  # noqa: N802
        self._pressed = False
        return super().leaveEvent(event)

    def contextMenuEvent(self, event):  # noqa: N802
        self.context_requested.emit(self._group_key, event.globalPos())
        event.accept()

    def toggle(self) -> None:
        self._expanded = not self._expanded
        self._update_chevron()
        self._update_accessibility()
        self.toggled.emit(self._group_key, self._expanded)

    def set_expanded(self, expanded: bool) -> None:
        if self._expanded != bool(expanded):
            self._expanded = bool(expanded)
            self._update_chevron()
            self._update_accessibility()

    def _update_accessibility(self) -> None:
        state = "развернута" if self._expanded else "свернута"
        count_text = f", элементов: {self._count}" if self._count > 0 else ""
        text = f"Папка {self._title}, {state}{count_text}"
        set_control_accessibility(
            self,
            name=text,
            description="Нажмите Enter или пробел, чтобы свернуть или развернуть папку.",
        )
        set_state_text(self, text)


class FolderGroup(QWidget):
    toggled = pyqtSignal(str, bool)
    context_requested = pyqtSignal(str, QPoint)

    def __init__(self, group_key: str, title: str, parent=None, *, count: int = 0):
        super().__init__(parent)
        self._group_key = str(group_key or "")
        self._content_widget = None
        self._build_ui(str(title or ""), count=_safe_count(count))

    @property
    def group_key(self) -> str:
        return self._group_key

    @property
    def is_expanded(self) -> bool:
        return self._header.is_expanded

    @property
    def content_widget(self) -> QWidget:
        return self._content_widget

    def _build_ui(self, title: str, *, count: int = 0) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self._header = FolderGroupHeader(self._group_key, title, self, count=count)
        self._header.toggled.connect(self._on_header_toggled)
        self._header.context_requested.connect(self.context_requested)
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

    row_rect = option.rect.adjusted(0, 0, 0, 0)
    if bool(option.state & QStyle.StateFlag.State_MouseOver):
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(to_qcolor(tokens.surface_bg_hover, FOLDER_HEADER_HOVER_BG))
        painter.drawRoundedRect(row_rect, FOLDER_HEADER_RADIUS, FOLDER_HEADER_RADIUS)

    rect = option.rect.adjusted(FOLDER_HEADER_LEFT_MARGIN, 0, -FOLDER_HEADER_RIGHT_MARGIN, 0)
    icon_box_rect = QRect(
        rect.left(),
        rect.center().y() - FOLDER_HEADER_ICON_BOX // 2,
        FOLDER_HEADER_ICON_BOX,
        FOLDER_HEADER_ICON_BOX,
    )
    icon_rect = QRect(
        icon_box_rect.center().x() - FOLDER_HEADER_ICON_SIZE // 2,
        icon_box_rect.center().y() - FOLDER_HEADER_ICON_SIZE // 2,
        FOLDER_HEADER_ICON_SIZE,
        FOLDER_HEADER_ICON_SIZE,
    )
    cached_icon(folder_header_icon_name(expanded), folder_header_icon_color()).paint(painter, icon_rect)

    text = folder_header_title(title, count)
    text_rect = QRect(
        icon_box_rect.right() + FOLDER_HEADER_GAP,
        rect.top(),
        max(0, rect.right() - icon_box_rect.right() - FOLDER_HEADER_GAP),
        rect.height(),
    )
    painter.setFont(folder_header_font(painter.font()))
    painter.setPen(to_qcolor(tokens.fg, "#f5f5f5"))
    painter.drawText(text_rect, int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter), text)

    line_y = rect.center().y()
    metrics = QFontMetrics(painter.font())
    left_end = text_rect.left() + metrics.horizontalAdvance(text) + FOLDER_HEADER_LINE_GAP
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
    "folder_header_font",
    "folder_header_title",
    "is_folder_toggle_click",
    "paint_folder_header_row",
]
