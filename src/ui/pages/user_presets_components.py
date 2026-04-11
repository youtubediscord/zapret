from __future__ import annotations

import json
import re
from typing import Optional

from PyQt6.QtCore import (
    Qt,
    pyqtSignal,
    QSize,
    QTimer,
    QAbstractListModel,
    QModelIndex,
    QRect,
    QEvent,
    QPoint,
    QMimeData,
)
from PyQt6.QtGui import QAction, QColor, QPainter, QFontMetrics, QMouseEvent, QHelpEvent, QTransform, QDrag
from PyQt6.QtWidgets import (
    QLabel,
    QListView,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QStyle,
    QToolTip,
    QApplication,
    QHBoxLayout,
    QSizePolicy,
    QWidget,
    QVBoxLayout,
)
import qtawesome as qta

from ui.text_catalog import tr as tr_catalog
from ui.theme import get_theme_tokens
from ui.theme_semantic import get_semantic_palette

try:
    from qfluentwidgets import Action, FluentIcon, ListView
except ImportError:
    Action = None
    FluentIcon = None
    ListView = QListView


_icon_cache: dict[str, object] = {}
_DEFAULT_PRESET_ICON_COLOR = "#5caee8"
_HEX_COLOR_RGB_RE = re.compile(r"^#(?:[0-9a-fA-F]{6})$")
_HEX_COLOR_RGBA_RE = re.compile(r"^#(?:[0-9a-fA-F]{8})$")
_CSS_RGBA_COLOR_RE = re.compile(
    r"^\s*rgba?\(\s*([0-9]{1,3})\s*,\s*([0-9]{1,3})\s*,\s*([0-9]{1,3})\s*(?:,\s*([0-9]*\.?[0-9]+)\s*)?\)\s*$",
    re.IGNORECASE,
)


class UserPresetsToolbarLayout:
    """Shared wrapping toolbar for user-presets pages."""

    def __init__(
        self,
        parent: QWidget,
        *,
        row_count: int = 4,
        row_spacing: int = 8,
        button_spacing: int = 12,
    ) -> None:
        self.container = QWidget(parent)
        self.container.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

        self._row_spacing = max(0, int(row_spacing))
        self._button_spacing = max(0, int(button_spacing))
        self._buttons: list[QWidget] = []
        self._rows: list[tuple[QWidget, QHBoxLayout]] = []

        self._layout = QVBoxLayout(self.container)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(self._row_spacing)

        for _ in range(max(1, int(row_count))):
            row_widget = QWidget(self.container)
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(self._button_spacing)
            row_widget.setVisible(False)
            self._layout.addWidget(row_widget)
            self._rows.append((row_widget, row_layout))

    def create_action_button(
        self,
        text: str,
        icon_name: str | None,
        *,
        accent: bool = False,
        fixed_height: int = 32,
    ) -> QWidget:
        from ui.compat_widgets import ActionButton, PrimaryActionButton

        button_cls = PrimaryActionButton if accent else ActionButton
        button = button_cls(text, icon_name, parent=self.container)
        button.setFixedHeight(int(fixed_height))
        return button

    def create_primary_tool_button(self, button_cls, icon_arg, *, size: int = 36):
        button = button_cls(icon_arg)
        button.setParent(self.container)
        button.setFixedSize(int(size), int(size))
        return button

    def set_buttons(self, buttons) -> None:
        self._buttons = [button for button in buttons if button is not None]

    def refresh_for_viewport(self, viewport_width: int, margins) -> None:
        available_width = max(
            0,
            int(viewport_width) - int(margins.left()) - int(margins.right()),
        )
        self.refresh_layout(available_width)

    def refresh_layout(self, available_width: int) -> None:
        assigned_rows = self._compute_rows(int(available_width))

        for index, (row_widget, row_layout) in enumerate(self._rows):
            self._clear_row(row_layout)
            row_buttons = assigned_rows[index] if index < len(assigned_rows) else []

            if row_buttons:
                for button in row_buttons:
                    row_layout.addWidget(button)
                row_layout.addStretch(1)
                row_widget.setVisible(True)
            else:
                row_widget.setVisible(False)

    def _visible_buttons(self) -> list[QWidget]:
        return [button for button in self._buttons if not button.isHidden()]

    def _compute_rows(self, available_width: int) -> list[list[QWidget]]:
        buttons = self._visible_buttons()
        if not buttons:
            return []

        if available_width <= 0:
            return [buttons]

        rows: list[list[QWidget]] = []
        current_row: list[QWidget] = []
        current_width = 0

        for button in buttons:
            button_width = button.sizeHint().width()
            if not current_row:
                current_row = [button]
                current_width = button_width
                continue

            next_width = current_width + self._button_spacing + button_width
            if next_width <= available_width:
                current_row.append(button)
                current_width = next_width
                continue

            rows.append(current_row)
            current_row = [button]
            current_width = button_width

        if current_row:
            rows.append(current_row)

        return rows

    @staticmethod
    def _clear_row(row_layout: QHBoxLayout) -> None:
        while row_layout.count():
            row_layout.takeAt(0)


def _tr_text(key: str, language: str, default: str, **kwargs) -> str:
    text = tr_catalog(key, language=language, default=default)
    if kwargs:
        try:
            return text.format(**kwargs)
        except Exception:
            return text
    return text


def _fluent_icon(name: str):
    if FluentIcon is None:
        return None
    return getattr(FluentIcon, name, None)


def _make_menu_action(text: str, *, icon=None, parent=None):
    if Action is not None:
        if icon is not None:
            try:
                return Action(icon, text, parent)
            except TypeError:
                pass
        try:
            action = Action(text, parent)
        except TypeError:
            try:
                action = Action(text)
            except TypeError:
                action = None
        if action is not None:
            try:
                if icon is not None and hasattr(action, "setIcon"):
                    action.setIcon(icon)
            except Exception:
                pass
            return action

    action = QAction(text, parent)
    try:
        if icon is not None:
            action.setIcon(icon)
    except Exception:
        pass
    return action


def _accent_fg_for_tokens(tokens) -> str:
    try:
        return str(tokens.accent_fg)
    except Exception:
        return "rgba(18, 18, 18, 0.90)"


def _normalize_preset_icon_color(value: Optional[str]) -> str:
    raw = str(value or "").strip()
    if _HEX_COLOR_RGB_RE.fullmatch(raw):
        return raw.lower()
    if _HEX_COLOR_RGBA_RE.fullmatch(raw):
        lowered = raw.lower()
        return f"#{lowered[1:7]}"
    try:
        return get_theme_tokens().accent_hex
    except Exception:
        return _DEFAULT_PRESET_ICON_COLOR


def _cached_icon(name: str, color: str):
    key = f"{name}|{color}"
    icon = _icon_cache.get(key)
    if icon is None:
        icon = qta.icon(name, color=color)
        _icon_cache[key] = icon
    return icon


def _relative_luminance(color: QColor) -> float:
    def _channel_luma(channel: int) -> float:
        value = max(0.0, min(1.0, float(channel) / 255.0))
        if value <= 0.03928:
            return value / 12.92
        return ((value + 0.055) / 1.055) ** 2.4

    return (
        0.2126 * _channel_luma(color.red())
        + 0.7152 * _channel_luma(color.green())
        + 0.0722 * _channel_luma(color.blue())
    )


def _contrast_ratio(foreground: QColor, background: QColor) -> float:
    fg = QColor(foreground)
    bg = QColor(background)
    fg.setAlpha(255)
    bg.setAlpha(255)
    l1 = _relative_luminance(fg)
    l2 = _relative_luminance(bg)
    lighter = max(l1, l2)
    darker = min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


def _pick_contrast_color(
    preferred_color: str,
    background_color: QColor,
    fallback_colors: list[str],
    *,
    minimum_ratio: float = 2.4,
) -> str:
    bg = QColor(background_color)
    if not bg.isValid():
        bg = QColor("#000000")
    bg.setAlpha(255)

    candidates: list[str] = []
    for raw in [preferred_color, *fallback_colors]:
        value = str(raw or "").strip()
        if value and value not in candidates:
            candidates.append(value)

    best_color = None
    best_ratio = -1.0
    for candidate in candidates:
        color = QColor(candidate)
        if not color.isValid():
            continue
        color.setAlpha(255)
        ratio = _contrast_ratio(color, bg)
        if ratio >= minimum_ratio:
            return color.name(QColor.NameFormat.HexRgb)
        if ratio > best_ratio:
            best_ratio = ratio
            best_color = color

    if best_color is not None:
        return best_color.name(QColor.NameFormat.HexRgb)
    return "#f5f5f5" if _relative_luminance(bg) < 0.45 else "#111111"


def _color_with_alpha(color_value: str, alpha: int, fallback_hex: str) -> str:
    color = QColor(color_value)
    if not color.isValid():
        color = QColor(fallback_hex)
    color.setAlpha(max(0, min(255, int(alpha))))
    return f"rgba({color.red()}, {color.green()}, {color.blue()}, {color.alpha()})"


def _to_qcolor(value, fallback_hex: str = "#000000") -> QColor:
    if isinstance(value, QColor):
        color = QColor(value)
        if color.isValid():
            return color

    text = str(value or "").strip()
    if text:
        match = _CSS_RGBA_COLOR_RE.fullmatch(text)
        if match:
            try:
                r = max(0, min(255, int(match.group(1))))
                g = max(0, min(255, int(match.group(2))))
                b = max(0, min(255, int(match.group(3))))
                alpha_raw = match.group(4)

                if alpha_raw is None:
                    a = 255
                else:
                    a_float = float(alpha_raw)
                    if a_float <= 1.0:
                        a = int(round(max(0.0, min(1.0, a_float)) * 255.0))
                    else:
                        a = int(round(max(0.0, min(255.0, a_float))))

                return QColor(r, g, b, a)
            except Exception:
                pass

        color = QColor(text)
        if color.isValid():
            return color

    fallback = QColor(fallback_hex)
    if fallback.isValid():
        return fallback
    return QColor(0, 0, 0)


class _PresetListModel(QAbstractListModel):
    KindRole = Qt.ItemDataRole.UserRole + 1
    NameRole = Qt.ItemDataRole.UserRole + 2
    FileNameRole = Qt.ItemDataRole.UserRole + 3
    DescriptionRole = Qt.ItemDataRole.UserRole + 4
    DateRole = Qt.ItemDataRole.UserRole + 5
    ActiveRole = Qt.ItemDataRole.UserRole + 6
    TextRole = Qt.ItemDataRole.UserRole + 7
    IconColorRole = Qt.ItemDataRole.UserRole + 8
    BuiltinRole = Qt.ItemDataRole.UserRole + 9
    DepthRole = Qt.ItemDataRole.UserRole + 10
    PinnedRole = Qt.ItemDataRole.UserRole + 11
    RatingRole = Qt.ItemDataRole.UserRole + 12

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rows: list[dict[str, object]] = []

    def set_rows(self, rows: list[dict[str, object]]) -> None:
        self.beginResetModel()
        self._rows = rows
        self.endResetModel()

    def find_preset_row(self, file_name: str) -> int:
        target = str(file_name or "").strip()
        if not target:
            return -1
        for row_index, row in enumerate(self._rows):
            if str(row.get("kind") or "") != "preset":
                continue
            if str(row.get("file_name") or "") == target:
                return row_index
        return -1

    def update_preset_row(self, file_name: str, **changes) -> bool:
        row_index = self.find_preset_row(file_name)
        if row_index < 0:
            return False

        row = self._rows[row_index]
        role_map = {
            "name": [int(Qt.ItemDataRole.DisplayRole), self.NameRole],
            "description": [self.DescriptionRole],
            "date": [self.DateRole],
            "is_active": [self.ActiveRole],
            "icon_color": [self.IconColorRole],
            "is_builtin": [self.BuiltinRole],
            "is_pinned": [self.PinnedRole],
            "rating": [self.RatingRole],
        }

        changed_roles: set[int] = set()
        for key, value in changes.items():
            if key not in role_map:
                continue
            if row.get(key) == value:
                continue
            row[key] = value
            changed_roles.update(role_map[key])

        if not changed_roles:
            return False

        model_index = self.index(row_index, 0)
        self.dataChanged.emit(model_index, model_index, sorted(changed_roles))
        return True

    def set_active_preset(
        self,
        file_name: str,
        *,
        display_name: str = "",
        use_display_name_fallback: bool = False,
    ) -> bool:
        target_file_name = str(file_name or "").strip()
        target_display_name = str(display_name or "").strip()
        changed_rows: list[int] = []
        for row_index, row in enumerate(self._rows):
            if str(row.get("kind") or "") != "preset":
                continue
            row_file_name = str(row.get("file_name") or "")
            row_display_name = str(row.get("name") or "")
            next_active = bool(target_file_name and row_file_name == target_file_name)
            if not next_active and use_display_name_fallback:
                next_active = bool(target_display_name and row_display_name == target_display_name)
            if bool(row.get("is_active", False)) == next_active:
                continue
            row["is_active"] = next_active
            changed_rows.append(row_index)

        for row_index in changed_rows:
            model_index = self.index(row_index, 0)
            self.dataChanged.emit(model_index, model_index, [self.ActiveRole])

        return bool(changed_rows)

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self._rows)

    def flags(self, index: QModelIndex):
        if not index.isValid():
            return Qt.ItemFlag.ItemIsEnabled

        kind = str(index.data(self.KindRole) or "")
        flags = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        if kind == "preset":
            flags |= Qt.ItemFlag.ItemIsDragEnabled
        return flags

    def supportedDragActions(self):
        return Qt.DropAction.MoveAction

    def supportedDropActions(self):
        return Qt.DropAction.MoveAction

    def mimeTypes(self):
        return ["application/x-zapret-preset-item"]

    def mimeData(self, indexes):
        mime = QMimeData()
        if not indexes:
            return mime

        index = indexes[0]
        kind = str(index.data(self.KindRole) or "")
        if kind != "preset":
            return mime
        payload = {"kind": kind, "file_name": str(index.data(self.FileNameRole) or "")}
        mime.setData("application/x-zapret-preset-item", json.dumps(payload).encode("utf-8"))
        return mime

    def data(self, index: QModelIndex, role: int = int(Qt.ItemDataRole.DisplayRole)):
        if not index.isValid() or index.row() < 0 or index.row() >= len(self._rows):
            return None

        row = self._rows[index.row()]
        kind = row.get("kind", "preset")

        if role == int(Qt.ItemDataRole.DisplayRole):
            if kind == "preset":
                return row.get("name", "")
            return row.get("text", "")

        if role == self.KindRole:
            return kind
        if role == self.NameRole:
            return row.get("name", "")
        if role == self.FileNameRole:
            return row.get("file_name", "")
        if role == self.DescriptionRole:
            return row.get("description", "")
        if role == self.DateRole:
            return row.get("date", "")
        if role == self.ActiveRole:
            return bool(row.get("is_active", False))
        if role == self.TextRole:
            return row.get("text", "")
        if role == self.IconColorRole:
            return row.get("icon_color", _DEFAULT_PRESET_ICON_COLOR)
        if role == self.BuiltinRole:
            return bool(row.get("is_builtin", False))
        if role == self.DepthRole:
            return int(row.get("depth", 0) or 0)
        if role == self.PinnedRole:
            return bool(row.get("is_pinned", False))
        if role == self.RatingRole:
            return int(row.get("rating", 0) or 0)

        return None


class _LinkedWheelListView(ListView):
    preset_activated = pyqtSignal(str)
    preset_move_requested = pyqtSignal(str, int)
    item_dropped = pyqtSignal(str, str, str, str)
    preset_context_requested = pyqtSignal(str, QPoint)

    def __init__(self, parent=None, *, draggable_kinds: set[str] | None = None):
        super().__init__(parent)
        self._drag_start_pos: QPoint | None = None
        self._draggable_kinds = {str(kind) for kind in (draggable_kinds or {"preset"})}

    def wheelEvent(self, e):
        scrollbar = self.verticalScrollBar()
        if scrollbar is None:
            super().wheelEvent(e)
            return

        delta = e.angleDelta().y()
        at_top = scrollbar.value() <= scrollbar.minimum()
        at_bottom = scrollbar.value() >= scrollbar.maximum()

        if (delta > 0 and at_top) or (delta < 0 and at_bottom):
            e.accept()
            return

        super().wheelEvent(e)
        e.accept()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start_pos = event.position().toPoint()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if not (event.buttons() & Qt.MouseButton.LeftButton):
            super().mouseMoveEvent(event)
            return

        if self._drag_start_pos is None:
            super().mouseMoveEvent(event)
            return

        if (event.position().toPoint() - self._drag_start_pos).manhattanLength() < QApplication.startDragDistance():
            super().mouseMoveEvent(event)
            return

        index = self.indexAt(self._drag_start_pos)
        if not index.isValid():
            super().mouseMoveEvent(event)
            return

        kind = str(index.data(_PresetListModel.KindRole) or "")
        if kind not in self._draggable_kinds:
            super().mouseMoveEvent(event)
            return

        model = self.model()
        if model is None:
            super().mouseMoveEvent(event)
            return

        mime = model.mimeData([index])
        if mime is None:
            super().mouseMoveEvent(event)
            return

        drag = QDrag(self)
        drag.setMimeData(mime)
        self._drag_start_pos = None
        drag.exec(Qt.DropAction.MoveAction)
        event.accept()
        return

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton:
            index = self.indexAt(event.position().toPoint())
            if index.isValid() and str(index.data(_PresetListModel.KindRole) or "") == "preset":
                name = str(index.data(_PresetListModel.FileNameRole) or "")
                if name:
                    self.setCurrentIndex(index)
                    self.preset_context_requested.emit(name, self.viewport().mapToGlobal(event.position().toPoint()))
                    event.accept()
                    return
        super().mouseReleaseEvent(event)

    def focusInEvent(self, event):
        super().focusInEvent(event)
        if not self.currentIndex().isValid() and self.model() is not None:
            for row in range(self.model().rowCount()):
                index = self.model().index(row, 0)
                if str(index.data(_PresetListModel.KindRole) or "") == "preset":
                    self.setCurrentIndex(index)
                    break

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_PageUp, Qt.Key.Key_PageDown):
            index = self.currentIndex()
            if index.isValid() and str(index.data(_PresetListModel.KindRole) or "") == "preset":
                name = str(index.data(_PresetListModel.FileNameRole) or "")
                if name:
                    direction = -1 if event.key() == Qt.Key.Key_PageUp else 1
                    self.preset_move_requested.emit(name, direction)
                    event.accept()
                    return
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            index = self.currentIndex()
            if index.isValid() and str(index.data(_PresetListModel.KindRole) or "") == "preset":
                name = str(index.data(_PresetListModel.FileNameRole) or "")
                if name:
                    self.preset_activated.emit(name)
                    event.accept()
                    return
        super().keyPressEvent(event)

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat("application/x-zapret-preset-item"):
            event.acceptProposedAction()
            return
        super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if event.mimeData().hasFormat("application/x-zapret-preset-item"):
            event.acceptProposedAction()
            return
        super().dragMoveEvent(event)

    def dropEvent(self, event):
        if not event.mimeData().hasFormat("application/x-zapret-preset-item"):
            super().dropEvent(event)
            return

        try:
            payload = json.loads(bytes(event.mimeData().data("application/x-zapret-preset-item")).decode("utf-8"))
        except Exception:
            event.ignore()
            return

        source_kind = str(payload.get("kind") or "")
        source_id = str(payload.get("file_name") or payload.get("name") or "").strip()
        if source_kind != "preset" or not source_id:
            event.ignore()
            return

        target_index = self.indexAt(event.position().toPoint())
        target_kind = "end"
        target_id = ""
        if target_index.isValid():
            target_kind = str(target_index.data(_PresetListModel.KindRole) or "")
            if target_kind == "preset":
                target_id = str(target_index.data(_PresetListModel.FileNameRole) or "")
            else:
                target_kind = "end"
                target_id = ""

        self.item_dropped.emit(source_kind, source_id, target_kind, target_id)
        event.acceptProposedAction()


class _PresetListDelegate(QStyledItemDelegate):
    action_triggered = pyqtSignal(str, str)

    _ROW_HEIGHT = 44
    _SECTION_HEIGHT = 24
    _EMPTY_HEIGHT = 64
    _ACTION_SIZE = 28
    _ACTION_SPACING = 6
    _PIN_SIZE = 14
    _PIN_COLUMN_WIDTH = 18
    _PIN_TO_ICON_SPACING = 8

    _ACTION_ICONS = {
        "folder": "fa5s.folder-open",
        "rating": "fa5s.star-half-alt",
        "edit": "fa5s.ellipsis-v",
    }

    _PENDING_SHAKE_ROTATIONS = (0, -8, 8, -6, 6, -4, 4, -2, 0)
    _PENDING_SHAKE_INTERVAL_MS = 50

    def __init__(self, view: QListView, *, language_scope: str = "z2", help_name_role: str = "name"):
        super().__init__(view)
        self._view = view
        self._language_scope = str(language_scope or "z2")
        self._help_name_role = str(help_name_role or "name")
        self._ui_language = "ru"
        self._action_tooltips: dict[str, str] = {}
        self._hover_row = -1
        self._pressed_row = -1
        self._selected_rows: set[int] = set()
        self._pending_destructive: Optional[tuple[str, str]] = None
        self._pending_timer = QTimer(self)
        self._pending_timer.setSingleShot(True)
        self._pending_timer.timeout.connect(self._clear_pending_destructive)
        self._pending_shake_step = 0
        self._pending_shake_rotation = 0
        self._pending_shake_timer = QTimer(self)
        self._pending_shake_timer.timeout.connect(self._advance_pending_shake)
        self.set_ui_language("ru")

    def _tr(self, key: str, default: str, **kwargs) -> str:
        return _tr_text(key, self._ui_language, default, **kwargs)

    def set_ui_language(self, language: str) -> None:
        self._ui_language = language
        prefix = f"page.{self._language_scope}_user_presets.delegate.tooltip"
        self._action_tooltips = {
            "rating": self._tr(f"{prefix}.rating", "Поставить рейтинг"),
            "edit": self._tr(f"{prefix}.edit", "Меню пресета"),
            "pin": self._tr(f"{prefix}.pin", "Закрепить сверху"),
        }

    def reset_interaction_state(self):
        self._clear_pending_destructive(update=False)
        self.setHoverRow(-1)
        self.setPressedRow(-1)
        self.setSelectedRows([])

    def setHoverRow(self, row: int) -> None:
        self._hover_row = int(row)

    def setPressedRow(self, row: int) -> None:
        self._pressed_row = int(row)

    def setSelectedRows(self, indexes) -> None:
        rows: set[int] = set()
        try:
            for index in indexes or []:
                row = getattr(index, "row", None)
                row_value = row() if callable(row) else row
                if row_value is None:
                    continue
                rows.add(int(row_value))
        except Exception:
            rows = set()

        self._selected_rows = rows
        if self._pressed_row in self._selected_rows:
            self._pressed_row = -1

    def _icon_rect_for_row(self, row_rect: QRect, depth: int) -> QRect:
        pin_rect = self._pin_rect(row_rect, "preset", depth)
        if pin_rect is not None:
            icon_left = pin_rect.left() + self._PIN_COLUMN_WIDTH + self._PIN_TO_ICON_SPACING
        else:
            icon_left = row_rect.left() + 12 + depth * 18
        return QRect(icon_left, row_rect.center().y() - 10, 20, 20)

    def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex) -> QSize:
        kind = index.data(_PresetListModel.KindRole)
        if kind == "section":
            return QSize(0, self._SECTION_HEIGHT)
        if kind == "empty":
            return QSize(0, self._EMPTY_HEIGHT)
        return QSize(0, self._ROW_HEIGHT)

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex):
        kind = index.data(_PresetListModel.KindRole)

        if kind == "section":
            self._paint_section_row(painter, option, str(index.data(_PresetListModel.TextRole) or ""))
            return

        if kind == "empty":
            self._paint_empty_row(painter, option, str(index.data(_PresetListModel.TextRole) or ""))
            return

        self._paint_preset_row(painter, option, index)

    def editorEvent(self, event, model, option: QStyleOptionViewItem, index: QModelIndex):
        _ = model
        kind = str(index.data(_PresetListModel.KindRole) or "")
        if kind != "preset":
            return False
        if event.type() != QEvent.Type.MouseButtonRelease:
            return False
        if not isinstance(event, QMouseEvent):
            return False
        if event.button() != Qt.MouseButton.LeftButton:
            return False

        item_id = str(index.data(_PresetListModel.FileNameRole) or "")
        if not item_id:
            return False

        self._view.setCurrentIndex(index)
        is_active = bool(index.data(_PresetListModel.ActiveRole))
        is_builtin = bool(index.data(_PresetListModel.BuiltinRole))
        depth = int(index.data(_PresetListModel.DepthRole) or 0)
        action = self._action_at(option.rect, kind, is_active, is_builtin, depth, event.position().toPoint())

        if action:
            self._handle_action_click(item_id, action, event)
            return True

        self._clear_pending_destructive(update=False)
        self.action_triggered.emit("activate", item_id)
        return True

    def helpEvent(self, event: QHelpEvent, view, option: QStyleOptionViewItem, index: QModelIndex) -> bool:
        kind = str(index.data(_PresetListModel.KindRole) or "")
        if kind != "preset":
            return super().helpEvent(event, view, option, index)

        if self._help_name_role == "file_name":
            name = str(index.data(_PresetListModel.FileNameRole) or "")
        else:
            name = str(index.data(_PresetListModel.NameRole) or "")
        is_active = bool(index.data(_PresetListModel.ActiveRole))
        is_builtin = bool(index.data(_PresetListModel.BuiltinRole))
        depth = int(index.data(_PresetListModel.DepthRole) or 0)
        action = self._action_at(option.rect, kind, is_active, is_builtin, depth, event.pos())
        if not action:
            return super().helpEvent(event, view, option, index)

        tooltip = self._action_tooltips.get(action, "")
        if tooltip:
            QToolTip.showText(event.globalPos(), tooltip, view)
            return True
        return super().helpEvent(event, view, option, index)

    def _handle_action_click(self, name: str, action: str, _event: QMouseEvent):
        self._clear_pending_destructive(update=False)
        self.action_triggered.emit(action, name)
        self._view.viewport().update()

    def _pulse_destructive_action(self, name: str, action: str, delay_ms: int = 170) -> None:
        key = (name, action)
        if self._pending_destructive is not None:
            return

        self._pending_destructive = key
        self._start_pending_shake()
        self._pending_timer.start(max(800, int(delay_ms) + 200))
        self._view.viewport().update()

        def _emit_action() -> None:
            if self._pending_destructive != key:
                return
            self.action_triggered.emit(action, name)
            self._clear_pending_destructive(update=False)
            self._view.viewport().update()

        QTimer.singleShot(max(0, int(delay_ms)), _emit_action)

    def _clear_pending_destructive(self, update: bool = True):
        self._pending_timer.stop()
        self._pending_shake_timer.stop()
        self._pending_shake_step = 0
        self._pending_shake_rotation = 0
        if self._pending_destructive is None:
            return
        self._pending_destructive = None
        if update:
            self._view.viewport().update()

    def _start_pending_shake(self):
        self._pending_shake_timer.stop()
        self._pending_shake_step = 0
        self._pending_shake_rotation = int(self._PENDING_SHAKE_ROTATIONS[0])
        self._pending_shake_timer.start(self._PENDING_SHAKE_INTERVAL_MS)

    def _advance_pending_shake(self):
        self._pending_shake_step += 1
        if self._pending_shake_step >= len(self._PENDING_SHAKE_ROTATIONS):
            self._pending_shake_timer.stop()
            self._pending_shake_step = 0
            self._pending_shake_rotation = 0
            self._view.viewport().update()
            return

        self._pending_shake_rotation = int(self._PENDING_SHAKE_ROTATIONS[self._pending_shake_step])
        self._view.viewport().update()

    def _visible_actions(self, kind: str, is_active: bool, is_builtin: bool) -> list[str]:
        _ = (kind, is_active, is_builtin)
        return ["rating", "edit"]

    def _action_rects(self, row_rect: QRect, kind: str, is_active: bool, is_builtin: bool) -> list[tuple[str, QRect]]:
        actions = self._visible_actions(kind, is_active, is_builtin)
        if not actions:
            return []

        total_width = len(actions) * self._ACTION_SIZE + (len(actions) - 1) * self._ACTION_SPACING
        x = row_rect.right() - 12 - total_width + 1
        y = row_rect.center().y() - (self._ACTION_SIZE // 2)

        rects: list[tuple[str, QRect]] = []
        for action in actions:
            rects.append((action, QRect(x, y, self._ACTION_SIZE, self._ACTION_SIZE)))
            x += self._ACTION_SIZE + self._ACTION_SPACING
        return rects

    def _action_at(self, option_rect: QRect, kind: str, is_active: bool, is_builtin: bool, depth: int, pos) -> Optional[str]:
        pin_rect = self._pin_rect(option_rect, kind, depth)
        if pin_rect is not None and pin_rect.contains(pos):
            return "pin"

        for action, rect in self._action_rects(option_rect, kind, is_active, is_builtin):
            if rect.contains(pos):
                return action
        return None

    def _paint_action_icon(self, painter: QPainter, icon_name: str, icon_color: str, icon_rect: QRect, rotation: int = 0):
        icon = _cached_icon(icon_name, icon_color)
        if not rotation:
            icon.paint(painter, icon_rect)
            return

        painter.save()
        center = icon_rect.center()
        transform = QTransform()
        transform.translate(center.x(), center.y())
        transform.rotate(rotation)
        transform.translate(-center.x(), -center.y())
        painter.setTransform(transform, combine=True)
        icon.paint(painter, icon_rect)
        painter.restore()

    def _pin_rect(self, row_rect: QRect, kind: str, depth: int) -> QRect | None:
        if kind != "preset":
            return None
        x = row_rect.left() + 12 + depth * 18
        return QRect(x, row_rect.center().y() - (self._PIN_SIZE // 2), self._PIN_SIZE, self._PIN_SIZE)

    def _paint_section_row(self, painter: QPainter, option: QStyleOptionViewItem, text: str) -> None:
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = option.rect.adjusted(12, 0, -12, 0)
        tokens = get_theme_tokens()

        painter.setPen(_to_qcolor(tokens.fg_muted, "#9aa2af"))
        painter.drawText(rect, int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter), text)

        line_y = rect.center().y()
        text_width = painter.fontMetrics().horizontalAdvance(text)
        left_end = rect.left() + text_width + 12
        if left_end < rect.right():
            painter.setPen(_to_qcolor(tokens.divider, "#5f6368"))
            painter.drawLine(left_end, line_y, rect.right(), line_y)

        painter.restore()

    def _paint_empty_row(self, painter: QPainter, option: QStyleOptionViewItem, text: str) -> None:
        painter.save()
        tokens = get_theme_tokens()
        painter.setPen(_to_qcolor(tokens.fg_muted, "#9aa2af"))
        painter.drawText(option.rect, int(Qt.AlignmentFlag.AlignCenter), text)
        painter.restore()

    def _paint_preset_row(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex):
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        tokens = get_theme_tokens()
        palette = get_semantic_palette()
        rect = option.rect.adjusted(8, 2, -8, -2)

        name = str(index.data(_PresetListModel.NameRole) or "")
        date_text = str(index.data(_PresetListModel.DateRole) or "")
        is_active = bool(index.data(_PresetListModel.ActiveRole))
        is_builtin = bool(index.data(_PresetListModel.BuiltinRole))
        depth = int(index.data(_PresetListModel.DepthRole) or 0)
        is_pinned = bool(index.data(_PresetListModel.PinnedRole))
        rating = int(index.data(_PresetListModel.RatingRole) or 0)

        hovered = option.state & QStyle.StateFlag.State_MouseOver
        selected = option.state & QStyle.StateFlag.State_Selected
        pressed = self._pressed_row == index.row()

        if selected or is_active:
            bg = _to_qcolor(tokens.accent_soft_bg, tokens.accent_hex)
        elif hovered or pressed:
            bg = _to_qcolor(tokens.surface_bg_hover, tokens.surface_bg)
        else:
            bg = _to_qcolor(tokens.surface_bg, "#1f1f1f")

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(bg)
        painter.drawRoundedRect(rect, 10, 10)

        icon_rect = self._icon_rect_for_row(rect, depth)
        icon_name = "fa5s.file-alt"
        icon_color = _pick_contrast_color(
            _normalize_preset_icon_color(str(index.data(_PresetListModel.IconColorRole) or "")),
            bg,
            [tokens.accent_hex, tokens.fg],
            minimum_ratio=2.6,
        )
        _cached_icon(icon_name, icon_color).paint(painter, icon_rect)

        text_left = icon_rect.right() + 10
        actions = self._action_rects(rect, "preset", is_active, is_builtin)
        right_bound = rect.right() - 12
        if actions:
            right_bound = actions[0][1].left() - 10

        pin_rect = self._pin_rect(rect, "preset", depth)
        if pin_rect is not None and pin_rect.left() < icon_rect.left():
            text_left = icon_rect.right() + 10

        name_rect = QRect(text_left, rect.top() + 8, max(0, right_bound - text_left), 18)
        meta_rect = QRect(text_left, rect.bottom() - 22, max(0, right_bound - text_left), 16)

        name_font = painter.font()
        name_font.setBold(is_active)
        painter.setFont(name_font)
        painter.setPen(_to_qcolor(tokens.fg, "#f5f5f5"))
        name_metrics = QFontMetrics(name_font)
        elided_name = name_metrics.elidedText(name, Qt.TextElideMode.ElideRight, name_rect.width())
        painter.drawText(name_rect, int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter), elided_name)

        meta_font = painter.font()
        meta_font.setBold(False)
        painter.setFont(meta_font)
        meta_parts = []
        if is_builtin:
            meta_parts.append("Встроенный")
        if rating:
            meta_parts.append(f"Рейтинг: {rating}")
        if date_text:
            meta_parts.append(date_text)
        meta_text = " • ".join(meta_parts)
        if meta_text:
            painter.setPen(_to_qcolor(tokens.fg_faint, "#aeb5c1"))
            painter.drawText(meta_rect, int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter), meta_text)

        if pin_rect is not None:
            pin_color = tokens.accent_hex if is_pinned else tokens.fg_faint
            self._paint_action_icon(
                painter,
                "fa5s.thumbtack",
                pin_color,
                pin_rect.adjusted(2, 2, -2, -2),
            )

        for action, action_rect in actions:
            btn_bg = _to_qcolor(tokens.surface_bg_hover, tokens.surface_bg)
            icon_col = _pick_contrast_color(
                str(tokens.fg_muted),
                btn_bg,
                [tokens.fg],
                minimum_ratio=2.6,
            )

            painter.setBrush(btn_bg)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(action_rect, 6, 6)

            icon_name = self._ACTION_ICONS.get(action, "fa5s.circle")
            rotation = self._pending_shake_rotation if self._pending_destructive == (str(index.data(_PresetListModel.FileNameRole) or ""), action) else 0
            self._paint_action_icon(
                painter,
                icon_name,
                icon_col,
                action_rect.adjusted(7, 7, -7, -7),
                rotation=rotation,
            )

        painter.restore()
