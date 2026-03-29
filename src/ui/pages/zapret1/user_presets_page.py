# ui/pages/zapret2/user_presets_page.py
"""Zapret 2 Direct: user presets management."""

from __future__ import annotations

from datetime import datetime
import json
import time
import re
import webbrowser
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import (
    Qt,
    pyqtSignal,
    QSize,
    QTimer,
    QFileSystemWatcher,
    QAbstractListModel,
    QModelIndex,
    QRect,
    QEvent,
    QPoint,
    QMimeData,
)
from PyQt6.QtGui import QAction, QColor, QPainter, QFontMetrics, QMouseEvent, QHelpEvent, QTransform, QDrag
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QLineEdit,
    QFileDialog,
    QListView,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QStyle,
    QToolTip,
    QSizePolicy,
    QApplication,
    QFrame,
    QComboBox,
)
from PyQt6.QtGui import QCursor
import qtawesome as qta

from ui.pages.base_page import BasePage
from ui.compat_widgets import ActionButton, SettingsCard, LineEdit, set_tooltip
from ui.text_catalog import tr as tr_catalog

try:
    from qfluentwidgets import (
        BodyLabel, CaptionLabel, StrongBodyLabel, SubtitleLabel,
        PushButton as FluentPushButton, PrimaryPushButton, ToolButton, PrimaryToolButton,
        MessageBox, InfoBar, MessageBoxBase, TransparentToolButton, TransparentPushButton, FluentIcon,
        RoundMenu, Action,
    )
    _HAS_FLUENT_LABELS = True
except ImportError:
    BodyLabel = QLabel
    CaptionLabel = QLabel
    StrongBodyLabel = QLabel
    SubtitleLabel = QLabel
    FluentPushButton = QPushButton
    PrimaryPushButton = QPushButton
    ToolButton = QPushButton
    PrimaryToolButton = QPushButton
    TransparentPushButton = QPushButton
    MessageBox = None
    InfoBar = None
    MessageBoxBase = object
    TransparentToolButton = None
    FluentIcon = None
    RoundMenu = None
    Action = None
    _HAS_FLUENT_LABELS = False


from ui.theme import get_theme_tokens
from ui.theme_semantic import get_semantic_palette
from log import log
from core.presets.library_hierarchy import (
    ROOT_FOLDER_ID,
    PresetHierarchyStore,
)


_icon_cache: dict[str, object] = {}
_DEFAULT_PRESET_ICON_COLOR = "#5caee8"
_HEX_COLOR_RGB_RE = re.compile(r"^#(?:[0-9a-fA-F]{6})$")
_HEX_COLOR_RGBA_RE = re.compile(r"^#(?:[0-9a-fA-F]{8})$")
_CSS_RGBA_COLOR_RE = re.compile(
    r"^\s*rgba?\(\s*([0-9]{1,3})\s*,\s*([0-9]{1,3})\s*,\s*([0-9]{1,3})\s*(?:,\s*([0-9]*\.?[0-9]+)\s*)?\)\s*$",
    re.IGNORECASE,
)
_PRESET_LIST_METADATA_CACHE: dict[tuple[str, int, int], dict[str, str]] = {}


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
    """Chooses readable foreground for the current accent color."""
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


def _read_preset_list_metadata(path: Path) -> dict[str, str]:
    result = {
        "description": "",
        "modified": "",
        "icon_color": "",
    }

    try:
        stat = path.stat()
        cache_key = (str(path), int(getattr(stat, "st_mtime_ns", int(stat.st_mtime * 1_000_000_000))), int(stat.st_size))
        cached = _PRESET_LIST_METADATA_CACHE.get(cache_key)
        if cached is not None:
            return dict(cached)

        with path.open("r", encoding="utf-8", errors="replace") as handle:
            for raw in handle:
                stripped = raw.strip()
                if not stripped:
                    continue
                if not stripped.startswith("#"):
                    break

                modified_match = re.match(r"#\s*Modified:\s*(.+)", stripped, re.IGNORECASE)
                if modified_match:
                    result["modified"] = modified_match.group(1).strip()
                    continue

                desc_match = re.match(r"#\s*Description:\s*(.*)", stripped, re.IGNORECASE)
                if desc_match:
                    result["description"] = desc_match.group(1).strip()
                    continue

                icon_color_match = re.match(r"#\s*IconColor:\s*(.+)", stripped, re.IGNORECASE)
                if icon_color_match:
                    result["icon_color"] = icon_color_match.group(1).strip()
                    continue
    except Exception:
        pass

    try:
        _PRESET_LIST_METADATA_CACHE[cache_key] = dict(result)
    except Exception:
        pass

    return result


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
    FolderIdRole = Qt.ItemDataRole.UserRole + 11
    PinnedRole = Qt.ItemDataRole.UserRole + 12
    RatingRole = Qt.ItemDataRole.UserRole + 13
    BuiltinFolderRole = Qt.ItemDataRole.UserRole + 14
    FolderCollapsedRole = Qt.ItemDataRole.UserRole + 15

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rows: list[dict[str, object]] = []

    def set_rows(self, rows: list[dict[str, object]]) -> None:
        self.beginResetModel()
        self._rows = rows
        self.endResetModel()

    def set_active_preset(self, file_name: str) -> bool:
        target_file_name = str(file_name or "").strip()
        changed_rows: list[int] = []
        for row_index, row in enumerate(self._rows):
            if str(row.get("kind") or "") != "preset":
                continue
            next_active = bool(target_file_name and str(row.get("file_name") or "") == target_file_name)
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
        if kind in {"preset", "folder"}:
            flags |= Qt.ItemFlag.ItemIsDragEnabled
        if kind == "folder":
            flags |= Qt.ItemFlag.ItemIsDropEnabled
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
        payload = {"kind": kind}
        if kind == "preset":
            payload["file_name"] = str(index.data(self.FileNameRole) or "")
        elif kind == "folder":
            payload["folder_id"] = str(index.data(self.FolderIdRole) or "")
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
        if role == self.FolderIdRole:
            return row.get("folder_id", "")
        if role == self.PinnedRole:
            return bool(row.get("is_pinned", False))
        if role == self.RatingRole:
            return int(row.get("rating", 0) or 0)
        if role == self.BuiltinFolderRole:
            return bool(row.get("is_builtin_folder", False))
        if role == self.FolderCollapsedRole:
            return bool(row.get("is_collapsed", False))

        return None


class _LinkedWheelListView(QListView):
    preset_activated = pyqtSignal(str)
    preset_move_requested = pyqtSignal(str, int)
    item_dropped = pyqtSignal(str, str, str, str)
    preset_context_requested = pyqtSignal(str, QPoint)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._drag_start_pos: QPoint | None = None

    def wheelEvent(self, e):
        scrollbar = self.verticalScrollBar()
        if scrollbar is None:
            super().wheelEvent(e)
            return

        delta = e.angleDelta().y()
        at_top = scrollbar.value() <= scrollbar.minimum()
        at_bottom = scrollbar.value() >= scrollbar.maximum()

        if (delta > 0 and at_top) or (delta < 0 and at_bottom):
            # Let parent scroll area handle wheel at boundaries.
            e.ignore()
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
        if kind not in {"preset", "folder"}:
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
        source_id = str(payload.get("file_name") or payload.get("name") or payload.get("folder_id") or "").strip()
        if source_kind not in {"preset", "folder"} or not source_id:
            event.ignore()
            return

        target_index = self.indexAt(event.position().toPoint())
        target_kind = "folder"
        target_id = ROOT_FOLDER_ID
        if target_index.isValid():
            target_kind = str(target_index.data(_PresetListModel.KindRole) or "")
            if target_kind == "folder":
                target_id = str(target_index.data(_PresetListModel.FolderIdRole) or ROOT_FOLDER_ID)
            elif target_kind == "preset":
                target_id = str(target_index.data(_PresetListModel.FileNameRole) or "")

        self.item_dropped.emit(source_kind, source_id, target_kind, target_id)
        event.acceptProposedAction()


class _PresetListDelegate(QStyledItemDelegate):
    action_triggered = pyqtSignal(str, str)

    _ROW_HEIGHT = 44
    _FOLDER_HEIGHT = 28
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

    def __init__(self, view: QListView):
        super().__init__(view)
        self._view = view
        self._ui_language = "ru"
        self._action_tooltips: dict[str, str] = {}
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
        self._action_tooltips = {
            "folder": self._tr("page.z1_user_presets.delegate.tooltip.folder", "Переместить в папку"),
            "rating": self._tr("page.z1_user_presets.delegate.tooltip.rating", "Поставить рейтинг"),
            "edit": self._tr("page.z1_user_presets.delegate.tooltip.edit", "Меню пресета"),
            "pin": self._tr("page.z1_user_presets.delegate.tooltip.pin", "Закрепить сверху"),
        }

    def reset_interaction_state(self):
        self._clear_pending_destructive(update=False)

    def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex) -> QSize:
        kind = index.data(_PresetListModel.KindRole)
        if kind == "folder":
            return QSize(0, self._FOLDER_HEIGHT)
        if kind == "section":
            return QSize(0, self._SECTION_HEIGHT)
        if kind == "empty":
            return QSize(0, self._EMPTY_HEIGHT)
        return QSize(0, self._ROW_HEIGHT)

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex):
        kind = index.data(_PresetListModel.KindRole)

        if kind == "folder":
            self._paint_folder_row(painter, option, index)
            return

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
        if kind not in {"preset", "folder"}:
            return False
        if event.type() != QEvent.Type.MouseButtonRelease:
            return False
        if not isinstance(event, QMouseEvent):
            return False
        if event.button() != Qt.MouseButton.LeftButton:
            return False

        item_id = str(index.data(_PresetListModel.FileNameRole) or "")
        if kind == "folder":
            item_id = str(index.data(_PresetListModel.FolderIdRole) or "")
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
        if kind == "preset":
            self.action_triggered.emit("activate", item_id)
        elif kind == "folder":
            self.action_triggered.emit("toggle_folder", item_id)
        return True

    def helpEvent(self, event: QHelpEvent, view, option: QStyleOptionViewItem, index: QModelIndex) -> bool:
        kind = str(index.data(_PresetListModel.KindRole) or "")
        if kind not in {"preset", "folder"}:
            return super().helpEvent(event, view, option, index)

        name = str(index.data(_PresetListModel.FileNameRole) or "")
        if kind == "folder":
            name = str(index.data(_PresetListModel.FolderIdRole) or "")
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
        _ = is_active
        if kind == "folder":
            return []
        if is_builtin:
            return ["rating", "edit"]
        return ["folder", "rating", "edit"]

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

    def _pin_rect(self, row_rect: QRect, kind: str, depth: int = 0) -> Optional[QRect]:
        if kind != "preset":
            return None
        left = row_rect.left() + 12 + depth * 18
        top = row_rect.center().y() - (self._PIN_SIZE // 2)
        return QRect(left, top, self._PIN_SIZE, self._PIN_SIZE)

    def _paint_action_icon(self, painter: QPainter, icon_name: str, icon_color: str, icon_rect: QRect, rotation: int = 0):
        icon = _cached_icon(icon_name, icon_color)
        pixmap = icon.pixmap(icon_rect.size())
        if pixmap.isNull():
            return

        if rotation:
            rotated = pixmap.transformed(QTransform().rotate(rotation), Qt.TransformationMode.SmoothTransformation)
            center = icon_rect.center()
            draw_x = center.x() - (rotated.width() // 2)
            draw_y = center.y() - (rotated.height() // 2)
            painter.drawPixmap(draw_x, draw_y, rotated)
            return

        painter.drawPixmap(icon_rect.topLeft(), pixmap)

    def _paint_section_row(self, painter: QPainter, option: QStyleOptionViewItem, text: str):
        painter.save()
        tokens = get_theme_tokens()
        rect = option.rect

        text_rect = rect.adjusted(12, 0, -12, 0)
        font = painter.font()
        font.setPointSize(9)
        font.setBold(True)
        painter.setFont(font)

        metrics = QFontMetrics(font)
        text_width = metrics.horizontalAdvance(text)

        painter.setPen(_to_qcolor(tokens.fg_muted, "#9aa2af"))
        painter.drawText(text_rect, int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter), text)

        # Draw a subtle separator line to the right of the label.
        line_x1 = text_rect.left() + text_width + 10
        line_x2 = rect.right() - 12
        if line_x2 > line_x1:
            painter.setPen(_to_qcolor(tokens.divider, "#5f6368"))
            y = rect.center().y()
            painter.drawLine(line_x1, y, line_x2, y)
        painter.restore()

    def _paint_folder_row(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex):
        painter.save()
        tokens = get_theme_tokens()
        rect = option.rect
        depth = int(index.data(_PresetListModel.DepthRole) or 0)
        text = str(index.data(_PresetListModel.TextRole) or "")
        is_builtin_folder = bool(index.data(_PresetListModel.BuiltinFolderRole))
        is_collapsed = bool(index.data(_PresetListModel.FolderCollapsedRole))

        left = rect.left() + 12 + depth * 18
        arrow_rect = QRect(left, rect.center().y() - 6, 12, 12)
        arrow_icon = "fa5s.chevron-right" if is_collapsed else "fa5s.chevron-down"
        _cached_icon(arrow_icon, tokens.fg_faint).paint(painter, arrow_rect)
        left += 14
        icon_rect = QRect(left, rect.center().y() - 8, 16, 16)
        icon_name = "fa5s.lock" if is_builtin_folder else "fa5s.folder"
        icon_color = tokens.fg_muted if is_builtin_folder else tokens.accent_hex
        _cached_icon(icon_name, icon_color).paint(painter, icon_rect)

        text_rect = rect.adjusted(left + 24, 0, -12, 0)
        font = painter.font()
        font.setPointSize(9)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(_to_qcolor(tokens.fg_muted, "#9aa2af"))
        painter.drawText(text_rect, int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter), text)

        line_x1 = text_rect.left() + QFontMetrics(font).horizontalAdvance(text) + 10
        line_x2 = rect.right() - 12
        if line_x2 > line_x1:
            painter.setPen(_to_qcolor(tokens.divider, "#5f6368"))
            painter.drawLine(line_x1, rect.center().y(), line_x2, rect.center().y())
        painter.restore()

    def _paint_empty_row(self, painter: QPainter, option: QStyleOptionViewItem, text: str):
        painter.save()
        tokens = get_theme_tokens()
        painter.setPen(_to_qcolor(tokens.fg_muted, "#9aa2af"))
        font = painter.font()
        font.setPointSize(10)
        painter.setFont(font)
        painter.drawText(option.rect.adjusted(8, 0, -8, 0), int(Qt.AlignmentFlag.AlignCenter), text)
        painter.restore()

    def _paint_preset_row(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex):
        tokens = get_theme_tokens()
        name = str(index.data(_PresetListModel.NameRole) or "")
        date_text = str(index.data(_PresetListModel.DateRole) or "")
        is_active = bool(index.data(_PresetListModel.ActiveRole))
        is_builtin = bool(index.data(_PresetListModel.BuiltinRole))
        depth = int(index.data(_PresetListModel.DepthRole) or 0)
        is_pinned = bool(index.data(_PresetListModel.PinnedRole))
        rating = int(index.data(_PresetListModel.RatingRole) or 0)

        row_rect = option.rect
        hovered = bool(option.state & QStyle.StateFlag.State_MouseOver)

        if is_active:
            bg = _to_qcolor(tokens.accent_soft_bg, tokens.accent_hex)
        elif hovered:
            bg = _to_qcolor(tokens.surface_bg_hover, tokens.surface_bg)
        else:
            bg = QColor(Qt.GlobalColor.transparent)

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        if bg.alpha() > 0:
            painter.fillRect(row_rect, bg)

        pin_rect = self._pin_rect(row_rect, "preset", depth)
        if pin_rect is not None:
            icon_left = pin_rect.left() + self._PIN_COLUMN_WIDTH + self._PIN_TO_ICON_SPACING
        else:
            icon_left = row_rect.left() + 12 + depth * 18
        icon_rect = QRect(icon_left, row_rect.center().y() - 10, 20, 20)
        icon_name = "fa5s.star" if is_active else "fa5s.file-alt"
        icon_color = _pick_contrast_color(
            _normalize_preset_icon_color(str(index.data(_PresetListModel.IconColorRole) or "")),
            bg,
            [tokens.accent_hex, tokens.fg],
            minimum_ratio=2.6,
        )
        _cached_icon(icon_name, icon_color).paint(painter, icon_rect)

        action_rects = self._action_rects(row_rect, "preset", is_active, is_builtin)
        right_cursor = action_rects[0][1].left() - 10 if action_rects else row_rect.right() - 12

        if is_active:
            badge_text = self._tr("page.z1_user_presets.delegate.badge.active", "Активен")
            badge_font = painter.font()
            badge_font.setPointSize(8)
            badge_font.setBold(True)
            badge_metrics = QFontMetrics(badge_font)
            badge_width = badge_metrics.horizontalAdvance(badge_text) + 14
            badge_rect = QRect(right_cursor - badge_width, row_rect.center().y() - 9, badge_width, 18)

            painter.setBrush(QColor(tokens.accent_hex))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(badge_rect, 4, 4)

            painter.setFont(badge_font)
            painter.setPen(_to_qcolor(_accent_fg_for_tokens(tokens), "#f5f5f5"))
            painter.drawText(badge_rect, int(Qt.AlignmentFlag.AlignCenter), badge_text)
            right_cursor = badge_rect.left() - 10

        if date_text:
            date_font = painter.font()
            date_font.setPointSize(9)
            date_font.setBold(False)
            painter.setFont(date_font)
            date_metrics = QFontMetrics(date_font)
            date_width = date_metrics.horizontalAdvance(date_text)
            date_rect = QRect(max(row_rect.left() + 80, right_cursor - date_width), row_rect.top(), date_width, row_rect.height())
            painter.setPen(_to_qcolor(tokens.fg_faint, "#aeb5c1"))
            painter.drawText(date_rect, int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter), date_text)
            right_cursor = date_rect.left() - 10

        if rating > 0:
            rating_text = f"{rating}/10"
            rating_font = painter.font()
            rating_font.setPointSize(8)
            rating_font.setBold(True)
            painter.setFont(rating_font)
            rating_metrics = QFontMetrics(rating_font)
            rating_width = rating_metrics.horizontalAdvance(rating_text) + 14
            rating_rect = QRect(max(row_rect.left() + 80, right_cursor - rating_width), row_rect.center().y() - 9, rating_width, 18)
            painter.setBrush(_to_qcolor(tokens.surface_bg_hover, tokens.surface_bg))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(rating_rect, 4, 4)
            painter.setPen(_to_qcolor(tokens.fg_muted, "#c3cad5"))
            painter.drawText(rating_rect, int(Qt.AlignmentFlag.AlignCenter), rating_text)
            right_cursor = rating_rect.left() - 10

        name_left = icon_rect.right() + 10
        name_rect = QRect(name_left, row_rect.top(), max(40, right_cursor - name_left), row_rect.height())
        name_font = painter.font()
        name_font.setPointSize(10)
        name_font.setBold(True)
        painter.setFont(name_font)
        painter.setPen(_to_qcolor(tokens.fg, "#f5f5f5"))
        name_metrics = QFontMetrics(name_font)
        elided_name = name_metrics.elidedText(name, Qt.TextElideMode.ElideRight, name_rect.width())
        painter.drawText(name_rect, int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter), elided_name)

        if pin_rect is not None:
            pin_color = tokens.accent_hex if is_pinned else tokens.fg_faint
            self._paint_action_icon(
                painter,
                "fa5s.thumbtack",
                pin_color,
                pin_rect.adjusted(2, 2, -2, -2),
            )

        for action, action_rect in action_rects:
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
            self._paint_action_icon(
                painter,
                icon_name,
                icon_col,
                action_rect.adjusted(7, 7, -7, -7),
            )

        painter.restore()


class _CreatePresetDialog(MessageBoxBase):
    """Диалог создания нового пресета."""

    def __init__(self, existing_names: list, parent=None, language: str = "ru"):
        if parent and not parent.isWindow():
            parent = parent.window()
        super().__init__(parent)
        self._ui_language = language

        def _tr(key: str, default: str, **kwargs) -> str:
            return _tr_text(key, self._ui_language, default, **kwargs)

        self._tr = _tr
        self._existing_names = list(existing_names)
        self._source = "current"

        self.titleLabel = SubtitleLabel(
            self._tr("page.z1_user_presets.dialog.create.title", "Новый пресет"),
            self.widget,
        )
        self.subtitleLabel = BodyLabel(
            self._tr(
                "page.z1_user_presets.dialog.create.subtitle",
                "Сохраните текущие настройки как отдельный пресет, чтобы быстро переключаться между конфигурациями.",
            ),
            self.widget,
        )
        self.subtitleLabel.setWordWrap(True)

        name_label = BodyLabel(
            self._tr("page.z1_user_presets.dialog.create.name", "Название"),
            self.widget,
        )
        self.nameEdit = LineEdit(self.widget)
        self.nameEdit.setPlaceholderText(
            self._tr(
                "page.z1_user_presets.dialog.create.placeholder",
                "Например: Игры / YouTube / Дом",
            )
        )
        self.nameEdit.setClearButtonEnabled(True)

        source_row = QHBoxLayout()
        source_label = BodyLabel(
            self._tr("page.z1_user_presets.dialog.create.source", "Создать на основе"),
            self.widget,
        )
        source_row.addWidget(source_label)
        source_row.addStretch()
        try:
            from qfluentwidgets import SegmentedWidget
            self._source_seg = SegmentedWidget(self.widget)
            self._source_seg.addItem(
                "current",
                self._tr("page.z1_user_presets.dialog.create.source.current", "Текущего активного"),
            )
            self._source_seg.addItem(
                "empty",
                self._tr("page.z1_user_presets.dialog.create.source.empty", "Пустого"),
            )
            self._source_seg.setCurrentItem("current")
            self._source_seg.currentItemChanged.connect(lambda k: setattr(self, "_source", k))
            source_row.addWidget(self._source_seg)
        except Exception:
            pass

        self.warningLabel = CaptionLabel("", self.widget)
        try:
            from PyQt6.QtGui import QColor
            self.warningLabel.setTextColor("#cf1010", QColor(255, 28, 32))
        except Exception:
            self.warningLabel.setStyleSheet("color: #cf1010;")
        self.warningLabel.hide()

        self.viewLayout.addWidget(self.titleLabel)
        self.viewLayout.addWidget(self.subtitleLabel)
        self.viewLayout.addWidget(name_label)
        self.viewLayout.addWidget(self.nameEdit)
        self.viewLayout.addLayout(source_row)
        self.viewLayout.addWidget(self.warningLabel)

        self.yesButton.setText(self._tr("page.z1_user_presets.dialog.create.button.create", "Создать"))
        self.cancelButton.setText(self._tr("page.z1_user_presets.dialog.button.cancel", "Отмена"))
        self.widget.setMinimumWidth(420)

    def validate(self) -> bool:
        name = self.nameEdit.text().strip()
        if not name:
            self.warningLabel.setText(
                self._tr("page.z1_user_presets.dialog.validation.enter_name", "Введите название.")
            )
            self.warningLabel.show()
            return False
        self.warningLabel.hide()
        return True


class _RenamePresetDialog(MessageBoxBase):
    """Диалог переименования пресета."""

    def __init__(self, current_name: str, existing_names: list, parent=None, language: str = "ru"):
        if parent and not parent.isWindow():
            parent = parent.window()
        super().__init__(parent)
        self._ui_language = language

        def _tr(key: str, default: str, **kwargs) -> str:
            return _tr_text(key, self._ui_language, default, **kwargs)

        self._tr = _tr
        self._current_name = str(current_name or "")
        self._existing_names = [n for n in existing_names if n != self._current_name]

        self.titleLabel = SubtitleLabel(
            self._tr("page.z1_user_presets.dialog.rename.title", "Переименовать"),
            self.widget,
        )
        self.subtitleLabel = BodyLabel(
            self._tr(
                "page.z1_user_presets.dialog.rename.subtitle",
                "Имя пресета отображается в списке и используется для переключения.",
            ),
            self.widget,
        )
        self.subtitleLabel.setWordWrap(True)

        from_label = CaptionLabel(
            self._tr(
                "page.z1_user_presets.dialog.rename.current_name",
                "Текущее имя: {name}",
                name=self._current_name,
            ),
            self.widget,
        )
        name_label = BodyLabel(
            self._tr("page.z1_user_presets.dialog.rename.new_name", "Новое имя"),
            self.widget,
        )
        self.nameEdit = LineEdit(self.widget)
        self.nameEdit.setText(self._current_name)
        self.nameEdit.setPlaceholderText(
            self._tr("page.z1_user_presets.dialog.rename.placeholder", "Новое имя...")
        )
        self.nameEdit.selectAll()
        self.nameEdit.setClearButtonEnabled(True)

        self.warningLabel = CaptionLabel("", self.widget)
        try:
            from PyQt6.QtGui import QColor
            self.warningLabel.setTextColor("#cf1010", QColor(255, 28, 32))
        except Exception:
            self.warningLabel.setStyleSheet("color: #cf1010;")
        self.warningLabel.hide()

        self.viewLayout.addWidget(self.titleLabel)
        self.viewLayout.addWidget(self.subtitleLabel)
        self.viewLayout.addWidget(from_label)
        self.viewLayout.addWidget(name_label)
        self.viewLayout.addWidget(self.nameEdit)
        self.viewLayout.addWidget(self.warningLabel)

        self.yesButton.setText(self._tr("page.z1_user_presets.dialog.rename.button", "Переименовать"))
        self.cancelButton.setText(self._tr("page.z1_user_presets.dialog.button.cancel", "Отмена"))
        self.widget.setMinimumWidth(420)

    def validate(self) -> bool:
        name = self.nameEdit.text().strip()
        if not name:
            self.warningLabel.setText(
                self._tr("page.z1_user_presets.dialog.validation.enter_name", "Введите название.")
            )
            self.warningLabel.show()
            return False
        if name == self._current_name:
            self.warningLabel.hide()
            return True
        self.warningLabel.hide()
        return True


class _PresetFolderDialog(MessageBoxBase):
    def __init__(
        self,
        *,
        preset_name: str,
        folder_choices: list[dict],
        current_folder_id: str,
        parent=None,
        language: str = "ru",
    ):
        if parent and not parent.isWindow():
            parent = parent.window()
        super().__init__(parent)
        self._ui_language = language

        self.titleLabel = SubtitleLabel("Куда переместить пресет", self.widget)
        self.subtitleLabel = BodyLabel(
            f"Выберите папку для пресета «{preset_name}».",
            self.widget,
        )
        self.subtitleLabel.setWordWrap(True)

        self.folderCombo = QComboBox(self.widget)
        for item in folder_choices:
            indent = "    " * int(item.get("depth", 0) or 0)
            self.folderCombo.addItem(f"{indent}{item.get('name', '')}", item.get("id", ROOT_FOLDER_ID))

        selected_index = 0
        for index in range(self.folderCombo.count()):
            if str(self.folderCombo.itemData(index) or "") == str(current_folder_id or ROOT_FOLDER_ID):
                selected_index = index
                break
        self.folderCombo.setCurrentIndex(selected_index)

        self.viewLayout.addWidget(self.titleLabel)
        self.viewLayout.addWidget(self.subtitleLabel)
        self.viewLayout.addWidget(self.folderCombo)

        self.yesButton.setText("Переместить")
        self.cancelButton.setText("Отмена")
        self.widget.setMinimumWidth(420)

    def selected_folder_id(self) -> str:
        return str(self.folderCombo.currentData() or ROOT_FOLDER_ID)


class _ResetAllPresetsDialog(MessageBoxBase):
    """Диалог подтверждения перезаписи пресетов из шаблонов."""

    def __init__(self, parent=None, language: str = "ru"):
        if parent and not parent.isWindow():
            parent = parent.window()
        super().__init__(parent)
        self._ui_language = language
        self.titleLabel = SubtitleLabel(
            _tr_text(
                "page.z1_user_presets.dialog.reset_all.title",
                self._ui_language,
                "Вернуть заводские пресеты",
            ),
            self.widget,
        )
        self.bodyLabel = BodyLabel(
            _tr_text(
                "page.z1_user_presets.dialog.reset_all.body",
                self._ui_language,
                "Стандартные пресеты будут восстановлены как после установки.\n"
                "Ваши изменения в стандартных пресетах будут потеряны.\n"
                "Пользовательские пресеты с другими именами останутся.\n"
                "Текущий активный пресет будет применен заново автоматически.",
            ),
            self.widget,
        )
        self.bodyLabel.setWordWrap(True)
        self.viewLayout.addWidget(self.titleLabel)
        self.viewLayout.addWidget(self.bodyLabel)
        self.yesButton.setText(
            _tr_text(
                "page.z1_user_presets.dialog.reset_all.button",
                self._ui_language,
                "Вернуть заводские",
            )
        )
        self.cancelButton.setText(
            _tr_text("page.z1_user_presets.dialog.button.cancel", self._ui_language, "Отмена")
        )
        self.widget.setMinimumWidth(380)


class Zapret1UserPresetsPage(BasePage):
    preset_open_requested = pyqtSignal(str)  # file_name
    folders_open_requested = pyqtSignal()
    back_clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(
            "Мои пресеты",
            "",
            parent,
            title_key="page.z1_user_presets.title",
        )

        self._back_btn = None
        self._configs_title_label = None
        self._get_configs_btn = None

        # Back navigation (breadcrumb — to Zapret1DirectControlPage)
        try:
            tokens = get_theme_tokens()
            _back_btn = TransparentPushButton()
            _back_btn.setText(self._tr("page.z1_user_presets.back.control", "Управление"))
            _back_btn.setIcon(qta.icon("fa5s.chevron-left", color=tokens.fg_muted))
            _back_btn.setIconSize(QSize(12, 12))
            _back_btn.clicked.connect(self.back_clicked.emit)
            self._back_btn = _back_btn
            _back_row_layout = QHBoxLayout()
            _back_row_layout.setContentsMargins(0, 0, 0, 0)
            _back_row_layout.setSpacing(0)
            _back_row_layout.addWidget(_back_btn)
            _back_row_layout.addStretch()
            _back_row_widget = QWidget()
            _back_row_widget.setLayout(_back_row_layout)
            self.layout.insertWidget(0, _back_row_widget)
        except Exception:
            pass

        self._presets_model: Optional[_PresetListModel] = None
        self._presets_delegate: Optional[_PresetListDelegate] = None
        self._ui_dirty = True  # needs rebuild on next show
        self._cached_presets_metadata: dict[str, dict[str, object]] = {}
        self._page_theme_refresh_scheduled = False
        self._last_page_theme_key: tuple[str, str, str] | None = None

        self._file_watcher: Optional[QFileSystemWatcher] = None
        self._watcher_active = False
        self._watcher_reload_timer = QTimer(self)
        self._watcher_reload_timer.setSingleShot(True)
        self._watcher_reload_timer.timeout.connect(self._reload_presets_from_watcher)

        self._bulk_reset_running = False
        self._layout_resync_timer = QTimer(self)
        self._layout_resync_timer.setSingleShot(True)
        self._layout_resync_timer.timeout.connect(self._resync_layout_metrics)
        self._layout_resync_delayed_timer = QTimer(self)
        self._layout_resync_delayed_timer.setSingleShot(True)
        self._layout_resync_delayed_timer.timeout.connect(self._resync_layout_metrics)

        self._preset_search_timer = QTimer(self)
        self._preset_search_timer.setSingleShot(True)
        self._preset_search_timer.timeout.connect(self._apply_preset_search)
        self._preset_search_input: Optional[QLineEdit] = None

        self._ui_initialized = False
        self._lazy_show_scheduled = False

    def _tr(self, key: str, default: str, **kwargs) -> str:
        return _tr_text(key, self._ui_language, default, **kwargs)

    def _on_store_changed(self):
        """Central store says the preset list changed."""
        self._ui_dirty = True
        if self._bulk_reset_running:
            return
        if self.isVisible():
            self._load_presets()

    def _on_store_switched(self, _name: str):
        """Central store says the selected source preset switched."""
        if self._bulk_reset_running:
            return
        marker_changed = self._apply_active_preset_marker()
        if self.isVisible() and marker_changed:
            return
        if not self._ui_dirty and marker_changed:
            return
        self._ui_dirty = True
        if self.isVisible():
            self._load_presets()

    def _apply_active_preset_marker(self) -> bool:
        if self._presets_model is None:
            return False
        active_file_name = self._get_selected_source_preset_file_name_light()
        changed = self._presets_model.set_active_preset(active_file_name)
        if changed and hasattr(self, "presets_list"):
            self.presets_list.viewport().update()
        return changed

    def _list_preset_entries_light(self) -> list[dict[str, object]]:
        try:
            facade = self._get_direct_facade()
            return [
                {
                    "file_name": item.file_name,
                    "display_name": item.name,
                    "kind": item.kind,
                    "is_builtin": str(item.kind or "").strip().lower() == "builtin",
                }
                for item in facade.list_manifests()
            ]
        except Exception:
            pass

        return []

    def _get_selected_source_preset_file_name_light(self) -> str:
        try:
            from core.services import get_selection_service

            return str(get_selection_service().get_selected_file_name("winws1") or "").strip()
        except Exception:
            return ""

    def _load_preset_list_metadata_light(self) -> dict[str, dict[str, object]]:
        metadata: dict[str, dict[str, object]] = {}
        from core.services import get_app_paths

        presets_dir = get_app_paths().engine_paths("winws1").ensure_directories().presets_dir
        for entry in self._list_preset_entries_light():
            file_name = str(entry.get("file_name") or "").strip()
            display_name = str(entry.get("display_name") or file_name).strip()
            kind = str(entry.get("kind") or "").strip() or "user"
            is_builtin = bool(entry.get("is_builtin", False))
            if not file_name:
                continue
            try:
                path = presets_dir / file_name
                metadata[file_name] = {
                    **_read_preset_list_metadata(path),
                    "display_name": display_name,
                    "kind": kind,
                    "is_builtin": is_builtin,
                }
            except Exception:
                metadata[file_name] = {
                    "description": "",
                    "modified": "",
                    "icon_color": "",
                    "display_name": display_name,
                    "kind": kind,
                    "is_builtin": is_builtin,
                }
        return metadata

    def _resolve_display_name(self, reference: str) -> str:
        candidate = str(reference or "").strip()
        if not candidate:
            return ""
        if candidate.lower().endswith(".txt"):
            try:
                manifest = self._get_direct_facade().get_manifest_by_file_name(candidate)
                if manifest is not None:
                    return manifest.name
            except Exception:
                pass
        return candidate

    def _get_direct_facade(self):
        from core.presets.direct_facade import DirectPresetFacade

        return DirectPresetFacade.from_launch_method("direct_zapret1")

    def _get_preset_store(self):
        from core.services import get_preset_store_v1

        return get_preset_store_v1()

    def _is_builtin_preset_file(self, name: str) -> bool:
        candidate = str(name or "").strip()
        if not candidate or not candidate.lower().endswith(".txt"):
            return False
        try:
            manifest = self._get_direct_facade().get_manifest_by_file_name(candidate)
            return bool(manifest is not None and str(manifest.kind or "").strip().lower() == "builtin")
        except Exception:
            return False

    def _hierarchy_scope_key(self) -> str:
        return "preset_zapret1"

    def _get_hierarchy_store(self) -> PresetHierarchyStore:
        return PresetHierarchyStore(self._hierarchy_scope_key())

    def showEvent(self, event):
        super().showEvent(event)
        if not self._ui_initialized:
            if not self._lazy_show_scheduled:
                self._lazy_show_scheduled = True
                QTimer.singleShot(0, self._finish_lazy_show)
            return
        self._start_watching_presets()
        self._resync_layout_metrics()
        if self._ui_dirty:
            self._load_presets()
        else:
            self._update_presets_view_height()
        self._schedule_layout_resync(include_delayed=True)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._resync_layout_metrics()
        self._schedule_layout_resync()

    def changeEvent(self, event):  # noqa: N802 (Qt override)
        try:
            if event.type() in (QEvent.Type.StyleChange, QEvent.Type.PaletteChange):
                try:
                    tokens = get_theme_tokens()
                    theme_key = (str(tokens.theme_name), str(tokens.accent_hex), str(tokens.surface_bg))
                    if theme_key == self._last_page_theme_key:
                        return super().changeEvent(event)
                except Exception:
                    pass
                if not self._page_theme_refresh_scheduled:
                    self._page_theme_refresh_scheduled = True
                    QTimer.singleShot(0, self._on_debounced_page_theme_change)
        except Exception:
            pass
        return super().changeEvent(event)

    def _on_debounced_page_theme_change(self) -> None:
        self._page_theme_refresh_scheduled = False
        self._apply_page_theme()
        self._schedule_layout_resync()

    def hideEvent(self, event):
        self._layout_resync_timer.stop()
        self._layout_resync_delayed_timer.stop()
        self._stop_watching_presets()
        super().hideEvent(event)

    def _ensure_ui_initialized(self) -> None:
        if self._ui_initialized:
            return

        started_at = time.perf_counter()
        self._build_ui()
        self._apply_page_theme()

        try:
            store = self._get_preset_store()
            store.presets_changed.connect(self._on_store_changed)
            store.preset_switched.connect(self._on_store_switched)
            store.preset_updated.connect(lambda _name: self._on_store_changed())
        except Exception:
            pass

        self._ui_initialized = True
        elapsed_ms = int((time.perf_counter() - started_at) * 1000)
        log(f"Z1UserPresetsPage: lazy ui init {elapsed_ms}ms", "DEBUG")

    def _finish_lazy_show(self) -> None:
        self._lazy_show_scheduled = False
        if not self.isVisible():
            return

        self._ensure_ui_initialized()
        self._start_watching_presets()
        self._resync_layout_metrics()
        if self._ui_dirty:
            self._load_presets()
        else:
            self._update_presets_view_height()
        self._schedule_layout_resync(include_delayed=True)

    def _schedule_layout_resync(self, include_delayed: bool = False):
        self._layout_resync_timer.start(0)
        if include_delayed:
            self._layout_resync_delayed_timer.start(220)

    def _resync_layout_metrics(self):
        self._update_toolbar_buttons_layout()
        self._update_presets_view_height()

    def set_smooth_scroll_enabled(self, enabled: bool) -> None:
        delegate = getattr(self, "_presets_scroll_delegate", None)
        if delegate is None:
            return
        try:
            from qfluentwidgets.common.smooth_scroll import SmoothMode
            mode = SmoothMode.COSINE if enabled else SmoothMode.NO_SMOOTH

            if hasattr(delegate, "useAni"):
                if not hasattr(delegate, "_zapret_base_use_ani"):
                    delegate._zapret_base_use_ani = bool(delegate.useAni)
                delegate.useAni = bool(delegate._zapret_base_use_ani) if enabled else False

            for smooth_attr in ("verticalSmoothScroll", "horizonSmoothScroll"):
                smooth = getattr(delegate, smooth_attr, None)
                smooth_setter = getattr(smooth, "setSmoothMode", None)
                if callable(smooth_setter):
                    smooth_setter(mode)

            setter = getattr(delegate, "setSmoothMode", None)
            if callable(setter):
                try:
                    setter(mode)
                except TypeError:
                    setter(mode, Qt.Orientation.Vertical)
            elif hasattr(delegate, "smoothMode"):
                delegate.smoothMode = mode
        except Exception:
            pass

    def _start_watching_presets(self):
        try:
            if self._watcher_active:
                return

            from core.services import get_app_paths

            presets_dir = get_app_paths().engine_paths("winws1").ensure_directories().presets_dir
            presets_dir.mkdir(parents=True, exist_ok=True)

            if not self._file_watcher:
                self._file_watcher = QFileSystemWatcher(self)
                self._file_watcher.directoryChanged.connect(self._on_presets_dir_changed)

            dir_path = str(presets_dir)
            if dir_path not in self._file_watcher.directories():
                self._file_watcher.addPath(dir_path)

            self._watcher_active = True

        except Exception as e:
            log(f"Ошибка запуска мониторинга пресетов: {e}", "DEBUG")

    def _stop_watching_presets(self):
        try:
            if not self._watcher_active:
                return
            if self._file_watcher:
                directories = self._file_watcher.directories()
                files = self._file_watcher.files()
                if directories:
                    self._file_watcher.removePaths(directories)
                if files:
                    self._file_watcher.removePaths(files)
            self._watcher_active = False
        except Exception as e:
            log(f"Ошибка остановки мониторинга пресетов: {e}", "DEBUG")

    def _on_presets_dir_changed(self, path: str):
        try:
            log(f"Обнаружены изменения в папке пресетов: {path}", "DEBUG")
            self._schedule_presets_reload()
        except Exception as e:
            log(f"Ошибка обработки изменений папки пресетов: {e}", "DEBUG")

    def _schedule_presets_reload(self, delay_ms: int = 500):
        try:
            self._watcher_reload_timer.stop()
            self._watcher_reload_timer.start(delay_ms)
        except Exception as e:
            log(f"Ошибка планирования обновления пресетов: {e}", "DEBUG")

    def _reload_presets_from_watcher(self):
        if not self.isVisible():
            return
        self._load_presets()

    def _build_ui(self):
        tokens = get_theme_tokens()
        semantic = get_semantic_palette(tokens.theme_name)

        # Telegram configs link
        configs_card = SettingsCard()
        configs_card.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        configs_layout = QHBoxLayout()
        configs_layout.setSpacing(12)
        self._configs_icon = QLabel()
        self._configs_icon.setPixmap(qta.icon("fa5b.telegram", color=tokens.accent_hex).pixmap(18, 18))
        configs_layout.addWidget(self._configs_icon)
        configs_title = StrongBodyLabel(
            self._tr(
                "page.z1_user_presets.configs.title",
                "Обменивайтесь категориями на нашем форуме-сайте через Telegram-бота: безопасно и анонимно",
            )
        )
        self._configs_title_label = configs_title
        configs_title.setWordWrap(True)
        configs_title.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        configs_title.setMinimumWidth(0)
        configs_layout.addWidget(configs_title, 1)
        get_configs_btn = ActionButton(
            self._tr("page.z1_user_presets.configs.button", "Получить конфиги"),
            "fa5s.external-link-alt",
            accent=True,
        )
        self._get_configs_btn = get_configs_btn
        get_configs_btn.setFixedHeight(36)
        get_configs_btn.clicked.connect(self._open_new_configs_post)
        configs_layout.addWidget(get_configs_btn)
        configs_card.add_layout(configs_layout)
        self.add_widget(configs_card)

        # "Restore deleted presets" button
        self._restore_deleted_btn = ActionButton(
            self._tr("page.z1_user_presets.button.restore_deleted", "Восстановить удалённые пресеты"),
            "fa5s.undo",
        )
        self._restore_deleted_btn.setFixedHeight(32)
        self._restore_deleted_btn.clicked.connect(self._on_restore_deleted)
        self._restore_deleted_btn.setVisible(False)

        self.add_spacing(12)

        # Buttons: create + import (above the preset list)
        self._buttons_container = QWidget()
        self._buttons_container.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self._buttons_container_layout = QVBoxLayout(self._buttons_container)
        self._buttons_container_layout.setContentsMargins(0, 0, 0, 0)
        self._buttons_container_layout.setSpacing(8)

        self._buttons_rows: list[tuple[QWidget, QHBoxLayout]] = []
        for _ in range(4):
            row_widget = QWidget()
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(12)
            row_widget.setVisible(False)
            self._buttons_container_layout.addWidget(row_widget)
            self._buttons_rows.append((row_widget, row_layout))

        self.create_btn = PrimaryToolButton(FluentIcon.ADD if FluentIcon else None)
        self.create_btn.setFixedSize(36, 36)
        set_tooltip(
            self.create_btn,
            self._tr("page.z1_user_presets.tooltip.create", "Создать новый пресет"),
        )
        self.create_btn.clicked.connect(self._on_create_clicked)

        self.import_btn = self._create_secondary_row_button(
            self._tr("page.z1_user_presets.button.import", "Импорт"),
            "fa5s.file-import",
        )
        set_tooltip(
            self.import_btn,
            self._tr("page.z1_user_presets.tooltip.import", "Импорт пресета из файла"),
        )
        self.import_btn.clicked.connect(self._on_import_clicked)

        self.folders_btn = self._create_secondary_row_button(
            self._tr("page.z1_user_presets.button.folders", "Папки"),
            "fa5s.sitemap",
        )
        set_tooltip(
            self.folders_btn,
            self._tr("page.z1_user_presets.tooltip.folders", "Создать папки и изменить их порядок"),
        )
        self.folders_btn.clicked.connect(self._on_manage_folders_clicked)

        self.reset_all_btn = self._create_secondary_row_button(
            self._tr("page.z1_user_presets.button.reset_all", "Вернуть заводские"),
            "fa5s.undo",
        )
        set_tooltip(
            self.reset_all_btn,
            self._tr(
                "page.z1_user_presets.tooltip.reset_all",
                "Восстанавливает стандартные пресеты. Ваши изменения в стандартных пресетах будут потеряны.",
            ),
        )
        self.reset_all_btn.clicked.connect(self._on_reset_all_presets_clicked)

        self.presets_info_btn = self._create_secondary_row_button(
            self._tr("page.z1_user_presets.button.wiki", "Вики по пресетам"),
            "fa5s.info-circle",
        )
        self.presets_info_btn.clicked.connect(self._open_presets_info)

        self.info_btn = self._create_secondary_row_button(
            self._tr("page.z1_user_presets.button.what_is_this", "Что это такое?"),
            "fa5s.question-circle",
        )
        self.info_btn.clicked.connect(self._on_info_clicked)

        self._toolbar_buttons = [
            self.create_btn,
            self.import_btn,
            self.folders_btn,
            self._restore_deleted_btn,
            self.reset_all_btn,
            self.presets_info_btn,
            self.info_btn,
        ]
        self._update_toolbar_buttons_layout()
        self.add_widget(self._buttons_container)

        self.add_spacing(4)

        # Search presets by name (filters the list).
        self._preset_search_input = LineEdit()
        self._preset_search_input.setPlaceholderText(
            self._tr("page.z1_user_presets.search.placeholder", "Поиск пресетов по имени...")
        )
        self._preset_search_input.setClearButtonEnabled(True)
        self._preset_search_input.setFixedHeight(34)
        self._preset_search_input.setProperty("noDrag", True)
        self._preset_search_input.textChanged.connect(self._on_preset_search_text_changed)
        self.add_widget(self._preset_search_input)

        self.presets_list = _LinkedWheelListView(self)
        self.presets_list.setObjectName("userPresetsList")
        self.presets_list.setMouseTracking(True)
        self.presets_list.setSelectionMode(QListView.SelectionMode.SingleSelection)
        self.presets_list.setEditTriggers(QListView.EditTrigger.NoEditTriggers)
        self.presets_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.presets_list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.presets_list.setVerticalScrollMode(QListView.ScrollMode.ScrollPerPixel)
        self.presets_list.setUniformItemSizes(False)
        self.presets_list.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.presets_list.setProperty("uiList", True)
        self.presets_list.setProperty("noDrag", True)
        self.presets_list.viewport().setProperty("noDrag", True)
        self.presets_list.preset_activated.connect(self._on_activate_preset)
        self.presets_list.preset_move_requested.connect(self._move_preset_by_step)
        self.presets_list.item_dropped.connect(self._on_item_dropped)
        self.presets_list.preset_context_requested.connect(self._on_preset_context_requested)
        self.presets_list.setDragEnabled(True)
        self.presets_list.setAcceptDrops(True)
        self.presets_list.setDropIndicatorShown(True)
        self.presets_list.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.presets_list.setDragDropMode(QListView.DragDropMode.DragDrop)

        self._presets_model = _PresetListModel(self.presets_list)
        self._presets_delegate = _PresetListDelegate(self.presets_list)
        self._presets_delegate.set_ui_language(self._ui_language)
        self._presets_delegate.action_triggered.connect(self._on_preset_list_action)
        self.presets_list.setModel(self._presets_model)
        self.presets_list.setItemDelegate(self._presets_delegate)
        self.presets_list.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.presets_list.setFrameShape(QFrame.Shape.NoFrame)
        self.presets_list.verticalScrollBar().setSingleStep(28)
        try:
            from qfluentwidgets import SmoothScrollDelegate
            from config.reg import get_smooth_scroll_enabled
            smooth_enabled = get_smooth_scroll_enabled()
            self._presets_scroll_delegate = SmoothScrollDelegate(
                self.presets_list,
                useAni=smooth_enabled,
            )
            self.set_smooth_scroll_enabled(smooth_enabled)
        except Exception:
            self._presets_scroll_delegate = None
        self.add_widget(self.presets_list)

        # Make outer page scrolling feel less sluggish on long lists.
        self.verticalScrollBar().setSingleStep(48)

    def _on_info_clicked(self) -> None:
        if MessageBox:
            box = MessageBox(
                self._tr("page.z1_user_presets.info.title", "Что это такое?"),
                self._tr(
                    "page.z1_user_presets.info.body",
                    'Здесь кнопка для нубов — "хочу чтобы нажал и всё работало". '
                    "Выбираете любой пресет — тыкаете — перезагружаете вкладку и смотрите, "
                    "что ресурс открывается (или не открывается). Если не открывается — тыкаете на следующий пресет. "
                    "Также здесь можно создавать, импортировать, экспортировать и переключать пользовательские пресеты.",
                ),
                self.window(),
            )
            box.cancelButton.hide()
            box.exec()

    def _create_secondary_row_button(self, text: str, icon_name: str) -> ActionButton:
        btn = ActionButton(text, icon_name)
        btn.setFixedHeight(32)
        return btn

    def _apply_page_theme(self) -> None:
        try:
            tokens = get_theme_tokens()
            theme_key = (str(tokens.theme_name), str(tokens.accent_hex), str(tokens.surface_bg))
            if theme_key == self._last_page_theme_key:
                return

            semantic = get_semantic_palette(tokens.theme_name)

            if getattr(self, "_configs_icon", None) is not None:
                self._configs_icon.setPixmap(qta.icon("fa5b.telegram", color=tokens.accent_hex).pixmap(18, 18))

            # _restore_deleted_btn is ActionButton — self-styling, skip explicit update

            # create_btn is PrimaryToolButton — self-styling, skip explicit update
            # import_btn / presets_info_btn are ActionButton — self-styling, skip explicit update

            if getattr(self, "reset_all_btn", None) is not None:
                try:
                    self.reset_all_btn.setIcon(qta.icon("fa5s.undo", color=tokens.fg))
                except Exception:
                    pass

            if getattr(self, "presets_list", None) is not None:
                self.presets_list.viewport().update()

            self._last_page_theme_key = theme_key

        except Exception as e:
            log(f"Ошибка применения темы на странице пресетов: {e}", "DEBUG")

    def _content_inner_width(self) -> int:
        margins = self.layout.contentsMargins()
        return max(0, self.viewport().width() - margins.left() - margins.right())

    def _visible_toolbar_buttons(self) -> list[QPushButton]:
        buttons: list[QPushButton] = []
        restore_deleted_btn = getattr(self, "_restore_deleted_btn", None)
        for button in getattr(self, "_toolbar_buttons", []):
            if button is None:
                continue
            # Most toolbar buttons are always available. Filtering via isHidden()
            # is unreliable here because unparented Qt widgets report as hidden
            # before the first layout pass, which made the whole toolbar collapse.
            if button is restore_deleted_btn and restore_deleted_btn is not None and not restore_deleted_btn.isVisible():
                continue
            buttons.append(button)
        return buttons

    def _compute_toolbar_rows(self, available_width: int) -> list[list[QPushButton]]:
        buttons = self._visible_toolbar_buttons()
        if not buttons:
            return []

        if available_width <= 0:
            return [buttons]

        spacing = 12
        rows: list[list[QPushButton]] = []
        current_row: list[QPushButton] = []
        current_width = 0

        for button in buttons:
            button_width = button.sizeHint().width()
            if not current_row:
                current_row = [button]
                current_width = button_width
                continue

            next_width = current_width + spacing + button_width
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

    def _clear_toolbar_row(self, row_layout: QHBoxLayout):
        while row_layout.count():
            row_layout.takeAt(0)

    def _update_toolbar_buttons_layout(self):
        rows = getattr(self, "_buttons_rows", None)
        if not rows:
            return

        assigned_rows = self._compute_toolbar_rows(self._content_inner_width())

        for index, (row_widget, row_layout) in enumerate(rows):
            self._clear_toolbar_row(row_layout)
            row_buttons = assigned_rows[index] if index < len(assigned_rows) else []

            if row_buttons:
                for button in row_buttons:
                    row_layout.addWidget(button)
                row_layout.addStretch(1)
                row_widget.setVisible(True)
            else:
                row_widget.setVisible(False)

    def _is_game_filter_preset_name(self, name: str) -> bool:
        return "game filter" in name.lower()

    def _is_all_tcp_udp_preset_name(self, name: str) -> bool:
        return "all tcp" in name.lower()

    def _format_modified_timestamp(self, modified: str) -> str:
        if not modified:
            return ""
        try:
            dt = datetime.fromisoformat(modified.replace("Z", "+00:00"))
            return dt.strftime("%d.%m.%Y %H:%M")
        except Exception:
            return modified

    def _on_preset_search_text_changed(self, _text: str) -> None:
        # Debounce to avoid reloading on every keystroke.
        try:
            self._preset_search_timer.start(180)
        except Exception:
            self._load_presets()

    def _apply_preset_search(self) -> None:
        if not self.isVisible():
            self._ui_dirty = True
            return
        self._load_presets()

    def _update_presets_view_height(self):
        if not self._presets_model or not hasattr(self, "presets_list"):
            return

        viewport_height = self.viewport().height()
        if viewport_height <= 0:
            return

        top = max(0, self.presets_list.geometry().top())
        bottom_margin = self.layout.contentsMargins().bottom()
        target_height = max(220, viewport_height - top - bottom_margin)

        if self.presets_list.minimumHeight() != target_height:
            self.presets_list.setMinimumHeight(target_height)
        if self.presets_list.maximumHeight() != target_height:
            self.presets_list.setMaximumHeight(target_height)

    def _show_inline_action_create(self):
        dlg = _CreatePresetDialog([], self.window(), language=self._ui_language)
        if not dlg.exec():
            return

        name = dlg.nameEdit.text().strip()
        from_current = getattr(dlg, "_source", "current") == "current"

        try:
            self._get_direct_facade().create(name, from_current=from_current)
            self._get_preset_store().notify_presets_changed()
            log(f"Создан пресет '{name}'", "INFO")
        except Exception as e:
            log(f"Ошибка создания пресета: {e}", "ERROR")
            InfoBar.error(
                title=self._tr("common.error.title", "Ошибка"),
                content=self._tr("page.z1_user_presets.error.generic", "Ошибка: {error}", error=e),
                parent=self.window(),
            )

    def _show_inline_action_rename(self, current_name: str):
        display_name = self._resolve_display_name(current_name)
        if self._is_builtin_preset_file(current_name):
            InfoBar.warning(
                title=self._tr("common.error.title", "Ошибка"),
                content="Встроенный пресет нельзя переименовать. Можно создать копию и работать уже с ней.",
                parent=self.window(),
            )
            return
        dlg = _RenamePresetDialog(display_name, [], self.window(), language=self._ui_language)
        if not dlg.exec():
            return

        new_name = dlg.nameEdit.text().strip()
        if not new_name or new_name == display_name:
            return

        try:
            facade = self._get_direct_facade()
            updated = facade.rename_by_file_name(current_name, new_name)
            self._get_preset_store().notify_presets_changed()
            if facade.is_selected_file_name(updated.file_name):
                self._get_preset_store().notify_preset_switched(updated.file_name)
            log(f"Пресет '{display_name}' переименован в '{new_name}'", "INFO")
        except Exception as e:
            log(f"Ошибка переименования пресета: {e}", "ERROR")
            InfoBar.error(
                title=self._tr("common.error.title", "Ошибка"),
                content=self._tr("page.z1_user_presets.error.generic", "Ошибка: {error}", error=e),
                parent=self.window(),
            )

    def _on_create_clicked(self):
        self._show_inline_action_create()

    def _show_import_result_infobar(self, requested_name: str, actual_display_name: str, actual_file_name: str) -> None:
        requested = str(requested_name or "").strip()
        expected_file_name = f"{requested}.txt" if requested else ""
        file_name_changed = bool(
            actual_file_name and expected_file_name and actual_file_name.casefold() != expected_file_name.casefold()
        )
        content = (
            "Пресет импортирован.\n"
            f"Отображаемое имя: {actual_display_name}\n"
            f"Имя файла: {actual_file_name}"
        )
        if file_name_changed:
            InfoBar.warning(
                title="Импортирован с новым именем файла",
                content=content,
                parent=self.window(),
            )
            return
        InfoBar.success(
            title="Пресет импортирован",
            content=content,
            parent=self.window(),
        )

    def _on_import_clicked(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            self._tr("page.z1_user_presets.file_dialog.import_title", "Импортировать пресет"),
            "",
            "Preset files (*.txt);;All files (*.*)",
        )

        if not file_path:
            return

        try:
            name = Path(file_path).stem
            facade = self._get_direct_facade()

            imported = facade.import_from_file(Path(file_path), name)
            self._get_preset_store().notify_presets_changed()
            log(f"Импортирован пресет '{imported.name}'", "INFO")
            self._show_import_result_infobar(name, imported.name, imported.file_name)

        except Exception as e:
            log(f"Ошибка импорта пресета: {e}", "ERROR")
            InfoBar.error(
                title=self._tr("common.error.title", "Ошибка"),
                content=self._tr("page.z1_user_presets.error.import_exception", "Ошибка импорта: {error}", error=e),
                parent=self.window(),
            )

    def _on_reset_all_presets_clicked(self):
        dlg = _ResetAllPresetsDialog(self.window(), language=self._ui_language)
        if not dlg.exec():
            return

        self._bulk_reset_running = True
        try:
            facade = self._get_direct_facade()
            success_count, total, failed = facade.reset_all_to_templates()
            self._get_preset_store().notify_presets_changed()
            selected_file_name = facade.get_selected_file_name()
            if selected_file_name:
                self._get_preset_store().notify_preset_switched(selected_file_name)

            if failed:
                log(
                    f"Восстановление заводских пресетов завершено частично: "
                    f"успешно={success_count}/{total}, ошибки={len(failed)}",
                    "WARNING",
                )
            else:
                log(f"Восстановлены заводские пресеты: {success_count}/{total}", "INFO")

            self._show_reset_all_result(success_count, total)

        except Exception as e:
            log(f"Ошибка массового восстановления пресетов: {e}", "ERROR")
            InfoBar.error(
                title=self._tr("common.error.title", "Ошибка"),
                content=self._tr(
                    "page.z1_user_presets.error.reset_all_exception",
                    "Ошибка восстановления пресетов: {error}",
                    error=e,
                ),
                parent=self.window(),
            )
        finally:
            self._bulk_reset_running = False

    def _show_reset_all_result(self, success_count: int, total_count: int) -> None:
        total = int(total_count or 0)
        ok = int(success_count or 0)
        try:
            self.reset_all_btn.setText(f"{ok}/{total}")
            icon_name = "fa5s.check" if total > 0 and ok >= total else "fa5s.exclamation-triangle"
            self.reset_all_btn.setIcon(qta.icon(icon_name, color=get_theme_tokens().fg))
        except Exception:
            pass
        QTimer.singleShot(3000, self._restore_reset_all_button_label)

    def _restore_reset_all_button_label(self) -> None:
        try:
            self.reset_all_btn.setText(
                self._tr("page.z1_user_presets.button.reset_all", "Вернуть заводские")
            )
            self.reset_all_btn.setIcon(qta.icon("fa5s.undo", color=get_theme_tokens().fg))
        except Exception:
            pass

    def _load_presets(self):
        self._ui_dirty = False
        try:
            started_at = time.perf_counter()
            all_presets = self._load_preset_list_metadata_light()
            self._cached_presets_metadata = dict(all_presets)
            self._rebuild_presets_rows(all_presets, started_at=started_at)
        except Exception as e:
            log(f"Ошибка загрузки пресетов: {e}", "ERROR")

    def _refresh_presets_view_from_cache(self) -> None:
        if not self._cached_presets_metadata:
            self._load_presets()
            return
        self._rebuild_presets_rows(self._cached_presets_metadata)

    def _rebuild_presets_rows(self, all_presets: dict[str, dict[str, object]], *, started_at: float | None = None) -> None:
        try:
            active_file_name = self._get_selected_source_preset_file_name_light()
            hierarchy = self._get_hierarchy_store()
            builtin_by_file = {
                file_name: bool(meta.get("is_builtin", False))
                for file_name, meta in all_presets.items()
            }

            query = ""
            try:
                if self._preset_search_input is not None:
                    query = (self._preset_search_input.text() or "").strip().lower()
            except Exception:
                query = ""

            rows: list[dict[str, object]] = []
            layout_rows = hierarchy.build_rows(
                [
                    {
                        "file_name": file_name,
                        "display_name": str(meta.get("display_name") or file_name),
                        "is_builtin": builtin_by_file.get(file_name, False),
                    }
                    for file_name, meta in all_presets.items()
                ],
                query=query,
                is_builtin_resolver=lambda file_name: builtin_by_file.get(str(file_name or ""), False),
            )

            for item in layout_rows:
                kind = str(item.get("kind") or "")
                if kind == "folder":
                    rows.append(
                        {
                            "kind": "folder",
                            "folder_id": item.get("folder_id", ""),
                            "text": item.get("text", ""),
                            "depth": int(item.get("depth", 0) or 0),
                            "is_builtin_folder": bool(item.get("is_builtin_folder", False)),
                            "is_collapsed": bool(item.get("is_collapsed", False)),
                        }
                    )
                    continue

                if kind != "preset":
                    continue

                file_name = str(item.get("file_name") or item.get("name") or "")
                display_name = str(item.get("name") or file_name)
                preset = all_presets.get(file_name)
                if not preset:
                    continue
                is_builtin = builtin_by_file.get(file_name, False)

                effective_folder_id = hierarchy.get_effective_folder_id(
                    file_name,
                    is_builtin=is_builtin,
                    display_name=display_name,
                )
                rows.append(
                    {
                        "kind": "preset",
                        "name": display_name,
                        "file_name": file_name,
                        "description": str(preset.get("description") or ""),
                        "date": self._format_modified_timestamp(str(preset.get("modified") or "")),
                        "is_active": bool(file_name and file_name == active_file_name),
                        "is_builtin": is_builtin,
                        "icon_color": _normalize_preset_icon_color(str(preset.get("icon_color") or "")),
                        "depth": int(item.get("depth", 0) or 0),
                        "folder_id": effective_folder_id,
                        "is_pinned": bool(item.get("is_pinned", False)),
                        "rating": int(item.get("rating", 0) or 0),
                    }
                )

            if not rows:
                if query:
                    rows.append(
                        {
                            "kind": "empty",
                            "text": self._tr("page.z1_user_presets.empty.not_found", "Ничего не найдено."),
                        }
                    )
                else:
                    rows.append(
                        {
                            "kind": "empty",
                            "text": self._tr(
                                "page.z1_user_presets.empty.none",
                                "Нет пресетов. Создайте новый или импортируйте из файла.",
                            ),
                        }
                    )

            if self._presets_delegate:
                self._presets_delegate.reset_interaction_state()
            if self._presets_model:
                self._presets_model.set_rows(rows)
            self._ensure_preset_list_current_index()

            # Update restore-deleted button visibility
            try:
                from core.presets.template_support import get_deleted_template_names

                has_deleted = bool(get_deleted_template_names("direct_zapret1"))
                self._restore_deleted_btn.setVisible(has_deleted)
            except Exception:
                self._restore_deleted_btn.setVisible(False)

            self._update_presets_view_height()
            self._schedule_layout_resync()
            if started_at is not None:
                elapsed_ms = int((time.perf_counter() - started_at) * 1000)
                log(f"Z1UserPresetsPage: lightweight list reload {elapsed_ms}ms ({len(all_presets)} presets)", "DEBUG")

        except Exception as e:
            log(f"Ошибка загрузки пресетов: {e}", "ERROR")

    def _on_preset_list_action(self, action: str, name: str):
        handlers = {
            "activate": self._on_activate_preset,
            "open": self._open_preset_subpage,
            "toggle_folder": self._on_toggle_folder,
            "pin": self._on_toggle_pin_preset,
            "folder": self._on_assign_folder_preset,
            "rating": self._on_rate_preset,
            "edit": self._on_edit_preset,
            "rename": self._on_rename_preset,
            "duplicate": self._on_duplicate_preset,
            "reset": self._on_reset_preset,
            "delete": self._on_delete_preset,
            "export": self._on_export_preset,
        }
        handler = handlers.get(action)
        if handler:
            handler(name)

    def _open_preset_subpage(self, name: str):
        self.preset_open_requested.emit(name)

    def _on_preset_context_requested(self, name: str, global_pos: QPoint):
        self._on_edit_preset(name, global_pos=global_pos)

    def _on_toggle_folder(self, folder_id: str):
        try:
            self._get_hierarchy_store().toggle_folder_collapsed(folder_id)
            self._refresh_presets_view_from_cache()
        except Exception as e:
            log(f"Ошибка сворачивания папки: {e}", "ERROR")

    def _on_manage_folders_clicked(self):
        self.folders_open_requested.emit()

    def _on_toggle_pin_preset(self, name: str):
        try:
            display_name = self._resolve_display_name(name)
            pinned = self._get_hierarchy_store().toggle_preset_pin(name, display_name=display_name)
            log(f"Пресет '{display_name}' {'закреплён' if pinned else 'откреплён'}", "INFO")
            self._refresh_presets_view_from_cache()
        except Exception as e:
            log(f"Ошибка закрепления пресета: {e}", "ERROR")

    def _on_assign_folder_preset(self, name: str):
        try:
            display_name = self._resolve_display_name(name)
            if self._is_builtin_preset_file(name):
                InfoBar.warning(
                    title=self._tr("common.error.title", "Ошибка"),
                    content="Встроенные пресеты остаются в системных папках. Для них перенос в пользовательскую папку отключён.",
                    parent=self.window(),
                )
                return
            hierarchy = self._get_hierarchy_store()
            current_folder_id = hierarchy.get_effective_folder_id(name, is_builtin=False, display_name=display_name)
            choices = hierarchy.get_folder_choices(include_root=True)
            dlg = _PresetFolderDialog(
                preset_name=display_name,
                folder_choices=choices,
                current_folder_id=current_folder_id,
                parent=self.window(),
                language=self._ui_language,
            )
            if not dlg.exec():
                return
            target_folder_id = dlg.selected_folder_id()
            hierarchy.move_preset_to_folder_end(
                self._list_preset_entries_light(),
                name,
                target_folder_id,
                is_builtin_resolver=self._is_builtin_preset_file,
            )
            self._refresh_presets_view_from_cache()
        except Exception as e:
            log(f"Ошибка перемещения пресета в папку: {e}", "ERROR")

    def _on_rate_preset(self, name: str):
        self._show_rating_menu(name)

    def _move_preset_by_step(self, name: str, direction: int):
        try:
            hierarchy = self._get_hierarchy_store()

            moved = hierarchy.move_preset_by_step(
                self._list_preset_entries_light(),
                name,
                direction,
                is_builtin_resolver=self._is_builtin_preset_file,
            )
            if moved:
                self._refresh_presets_view_from_cache()
        except Exception as e:
            log(f"Ошибка перестановки пресета: {e}", "ERROR")

    def _on_item_dropped(self, source_kind: str, source_id: str, target_kind: str, target_id: str):
        try:
            hierarchy = self._get_hierarchy_store()
            all_names = self._list_preset_entries_light()

            if source_kind == "folder":
                moved = False
                if target_kind == "folder" and target_id:
                    moved = hierarchy.move_folder_before(source_id, target_id)
                if moved:
                    self._refresh_presets_view_from_cache()
                return

            if source_kind != "preset":
                return

            moved = False
            if target_kind == "preset" and target_id:
                moved = hierarchy.move_preset_before(
                    all_names,
                    source_id,
                    target_id,
                    is_builtin_resolver=self._is_builtin_preset_file,
                )
            else:
                moved = hierarchy.move_preset_to_folder_end(
                    all_names,
                    source_id,
                    target_id,
                    is_builtin_resolver=self._is_builtin_preset_file,
                )
            if moved:
                self._refresh_presets_view_from_cache()
        except Exception as e:
            log(f"Ошибка перетаскивания элемента: {e}", "ERROR")

    def _on_activate_preset(self, name: str):
        try:
            from core.services import get_direct_flow_coordinator
            get_direct_flow_coordinator().select_preset_file_name("direct_zapret1", name)
            self._get_preset_store().notify_preset_switched(name)
            display_name = self._resolve_display_name(name)
            log(f"Активирован пресет '{display_name}'", "INFO")
            self._apply_active_preset_marker()
        except Exception as e:
            log(f"Ошибка активации пресета: {e}", "ERROR")
            InfoBar.warning(
                title=self._tr("common.error.title", "Ошибка"),
                content=self._tr(
                    "page.z1_user_presets.error.activate_failed",
                    "Не удалось активировать пресет '{name}'",
                    name=name,
                ),
                parent=self.window(),
            )

    def _on_edit_preset(self, name: str, global_pos: QPoint | None = None):
        is_builtin = self._is_builtin_preset_file(name)
        if RoundMenu is not None and Action is not None:
            menu = RoundMenu(parent=self)
            open_action = _make_menu_action(
                self._tr("page.z1_user_presets.menu.open", "Открыть"),
                icon=_fluent_icon("VIEW"),
                parent=menu,
            )
            rating_action = _make_menu_action(
                self._tr("page.z1_user_presets.menu.rating", "Рейтинг"),
                icon=_fluent_icon("FAVORITE"),
                parent=menu,
            )
            duplicate_action = _make_menu_action(
                self._tr("page.z1_user_presets.menu.duplicate", "Дублировать"),
                icon=_fluent_icon("COPY"),
                parent=menu,
            )
            export_action = _make_menu_action(
                self._tr("page.z1_user_presets.menu.export", "Экспорт"),
                icon=_fluent_icon("SHARE"),
                parent=menu,
            )
            reset_action = _make_menu_action(
                self._tr("page.z1_user_presets.menu.reset", "Сбросить"),
                icon=_fluent_icon("SYNC"),
                parent=menu,
            )
            move_up_action = _make_menu_action(
                self._tr("page.z1_user_presets.menu.move_up", "Переместить выше"),
                icon=_fluent_icon("UP"),
                parent=menu,
            )
            move_down_action = _make_menu_action(
                self._tr("page.z1_user_presets.menu.move_down", "Переместить ниже"),
                icon=_fluent_icon("DOWN"),
                parent=menu,
            )

            open_action.triggered.connect(lambda: self._open_preset_subpage(name))
            rating_action.triggered.connect(lambda: self._show_rating_menu(name))
            move_up_action.triggered.connect(lambda: self._move_preset_by_step(name, -1))
            move_down_action.triggered.connect(lambda: self._move_preset_by_step(name, 1))
            duplicate_action.triggered.connect(lambda: self._on_duplicate_preset(name))
            export_action.triggered.connect(lambda: self._on_export_preset(name))
            reset_action.triggered.connect(lambda: self._on_reset_preset(name))

            menu.addAction(open_action)
            menu.addAction(rating_action)
            menu.addAction(move_up_action)
            menu.addAction(move_down_action)
            if not is_builtin:
                folder_action = _make_menu_action(
                    self._tr("page.z1_user_presets.menu.folder", "Переместить в папку"),
                    icon=_fluent_icon("FOLDER"),
                    parent=menu,
                )
                rename_action = _make_menu_action(
                    self._tr("page.z1_user_presets.menu.rename", "Переименовать"),
                    icon=_fluent_icon("RENAME"),
                    parent=menu,
                )
                delete_action = _make_menu_action(
                    self._tr("page.z1_user_presets.menu.delete", "Удалить"),
                    icon=_fluent_icon("DELETE"),
                    parent=menu,
                )
                folder_action.triggered.connect(lambda: self._on_assign_folder_preset(name))
                rename_action.triggered.connect(lambda: self._on_rename_preset(name))
                delete_action.triggered.connect(lambda: self._on_delete_preset(name))
                menu.addAction(folder_action)
                menu.addAction(rename_action)
            menu.addAction(duplicate_action)
            menu.addAction(export_action)
            menu.addAction(reset_action)
            if not is_builtin:
                menu.addAction(delete_action)
            menu.exec(global_pos or QCursor.pos())
            return

        from PyQt6.QtWidgets import QMenu

        menu = QMenu(self)
        open_action = menu.addAction(self._tr("page.z1_user_presets.menu.open", "Открыть"))
        rating_action = menu.addAction(self._tr("page.z1_user_presets.menu.rating", "Рейтинг"))
        move_up_action = menu.addAction(self._tr("page.z1_user_presets.menu.move_up", "Переместить выше"))
        move_down_action = menu.addAction(self._tr("page.z1_user_presets.menu.move_down", "Переместить ниже"))
        folder_action = None
        rename_action = None
        delete_action = None
        if not is_builtin:
            folder_action = menu.addAction(self._tr("page.z1_user_presets.menu.folder", "Переместить в папку"))
            rename_action = menu.addAction(self._tr("page.z1_user_presets.menu.rename", "Переименовать"))
        duplicate_action = menu.addAction(self._tr("page.z1_user_presets.menu.duplicate", "Дублировать"))
        export_action = menu.addAction(self._tr("page.z1_user_presets.menu.export", "Экспорт"))
        reset_action = menu.addAction(self._tr("page.z1_user_presets.menu.reset", "Сбросить"))
        if not is_builtin:
            delete_action = menu.addAction(self._tr("page.z1_user_presets.menu.delete", "Удалить"))
        chosen = menu.exec(global_pos or QCursor.pos())
        if chosen == open_action:
            self._open_preset_subpage(name)
        elif chosen == folder_action:
            self._on_assign_folder_preset(name)
        elif chosen == rating_action:
            self._show_rating_menu(name)
        elif chosen == move_up_action:
            self._move_preset_by_step(name, -1)
        elif chosen == move_down_action:
            self._move_preset_by_step(name, 1)
        elif chosen == rename_action:
            self._on_rename_preset(name)
        elif chosen == duplicate_action:
            self._on_duplicate_preset(name)
        elif chosen == export_action:
            self._on_export_preset(name)
        elif chosen == reset_action:
            self._on_reset_preset(name)
        elif chosen == delete_action:
            self._on_delete_preset(name)

    def _show_rating_menu(self, name: str):
        from PyQt6.QtWidgets import QMenu

        menu = QMenu(self)
        display_name = self._resolve_display_name(name)
        current_rating = int(self._get_hierarchy_store().get_preset_meta(name, display_name=display_name).get("rating", 0) or 0)
        clear_action = menu.addAction(self._tr("page.z1_user_presets.menu.rating_clear", "Сбросить рейтинг"))
        clear_action.setCheckable(True)
        clear_action.setChecked(current_rating == 0)
        menu.addSeparator()

        actions = {}
        for value in range(1, 11):
            action = menu.addAction(f"{value}/10")
            action.setCheckable(True)
            action.setChecked(current_rating == value)
            actions[action] = value

        chosen = menu.exec(QCursor.pos())
        if chosen == clear_action:
            self._get_hierarchy_store().set_preset_rating(name, 0, display_name=display_name)
            self._refresh_presets_view_from_cache()
            return
        if chosen in actions:
            self._get_hierarchy_store().set_preset_rating(name, actions[chosen], display_name=display_name)
            self._refresh_presets_view_from_cache()

    def _ensure_preset_list_current_index(self) -> None:
        if self._presets_model is None:
            return
        current = self.presets_list.currentIndex()
        if current.isValid() and str(current.data(_PresetListModel.KindRole) or "") == "preset":
            return
        for row in range(self._presets_model.rowCount()):
            index = self._presets_model.index(row, 0)
            if str(index.data(_PresetListModel.KindRole) or "") == "preset":
                self.presets_list.setCurrentIndex(index)
                break

    def _on_rename_preset(self, name: str):
        if self._is_builtin_preset_file(name):
            InfoBar.warning(
                title=self._tr("common.error.title", "Ошибка"),
                content="Встроенный пресет нельзя переименовать. Создайте копию, если нужен свой вариант.",
                parent=self.window(),
            )
            return
        self._show_inline_action_rename(name)

    def _on_duplicate_preset(self, name: str):
        try:
            display_name = self._resolve_display_name(name)
            new_name = f"{display_name} (копия)"
            facade = self._get_direct_facade()

            facade.duplicate_by_file_name(name, new_name)
            try:
                self._get_hierarchy_store().copy_preset_meta_to_new(name, new_name, source_display_name=display_name)
            except Exception:
                pass
            self._get_preset_store().notify_presets_changed()
            log(f"Пресет '{display_name}' дублирован как '{new_name}'", "INFO")

        except Exception as e:
            log(f"Ошибка дублирования пресета: {e}", "ERROR")
            InfoBar.error(
                title=self._tr("common.error.title", "Ошибка"),
                content=self._tr("page.z1_user_presets.error.generic", "Ошибка: {error}", error=e),
                parent=self.window(),
            )

    def _on_reset_preset(self, name: str):
        try:
            display_name = self._resolve_display_name(name)
            if MessageBox:
                box = MessageBox(
                    self._tr("page.z1_user_presets.dialog.reset_single.title", "Сбросить пресет?"),
                    self._tr(
                        "page.z1_user_presets.dialog.reset_single.body",
                        "Пресет '{name}' будет перезаписан данными из шаблона.\n"
                        "Все изменения в этом пресете будут потеряны.\n"
                        "Этот пресет станет активным и будет применен заново.",
                        name=display_name,
                    ),
                    self.window(),
                )
                box.yesButton.setText(
                    self._tr("page.z1_user_presets.dialog.reset_single.button", "Сбросить")
                )
                box.cancelButton.setText(
                    self._tr("page.z1_user_presets.dialog.button.cancel", "Отмена")
                )
                if not box.exec():
                    return

            facade = self._get_direct_facade()
            facade.reset_to_template_by_file_name(name)
            self._get_preset_store().notify_preset_saved(name)
            if facade.is_selected_file_name(name):
                self._get_preset_store().notify_preset_switched(name)

            log(f"Сброшен пресет '{display_name}' к шаблону", "INFO")

        except Exception as e:
            log(f"Ошибка сброса пресета: {e}", "ERROR")
            InfoBar.error(
                title=self._tr("common.error.title", "Ошибка"),
                content=self._tr("page.z1_user_presets.error.generic", "Ошибка: {error}", error=e),
                parent=self.window(),
            )

    def _on_delete_preset(self, name: str):
        try:
            display_name = self._resolve_display_name(name)
            if self._is_builtin_preset_file(name):
                InfoBar.warning(
                    title=self._tr("common.error.title", "Ошибка"),
                    content="Встроенные пресеты удалять нельзя. Можно удалить только пользовательские пресеты.",
                    parent=self.window(),
                )
                return
            if MessageBox:
                box = MessageBox(
                    self._tr("page.z1_user_presets.dialog.delete_single.title", "Удалить пресет?"),
                    self._tr(
                        "page.z1_user_presets.dialog.delete_single.body",
                        "Пресет '{name}' будет удален из списка пользовательских пресетов.\n"
                        "Изменения в этом пресете будут потеряны.\n"
                        "Вернуть его можно только через восстановление удаленных пресетов (если доступен шаблон).",
                        name=display_name,
                    ),
                    self.window(),
                )
                box.yesButton.setText(
                    self._tr("page.z1_user_presets.dialog.delete_single.button", "Удалить")
                )
                box.cancelButton.setText(
                    self._tr("page.z1_user_presets.dialog.button.cancel", "Отмена")
                )
                if not box.exec():
                    return

            facade = self._get_direct_facade()
            template_origin = ""
            try:
                manifest = facade.get_manifest_by_file_name(name)
                template_origin = str(getattr(manifest, "template_origin", "") or "").strip()
            except Exception:
                template_origin = ""
            facade.delete_by_file_name(name)
            self._get_preset_store().notify_presets_changed()
            log(f"Удалён пресет '{display_name}'", "INFO")
            # Mark as deleted so it can be restored later (if it has a matching template)
            try:
                from core.presets.template_support import mark_deleted_template

                if template_origin:
                    mark_deleted_template("direct_zapret1", template_origin)
            except Exception:
                pass

        except Exception as e:
            log(f"Ошибка удаления пресета: {e}", "ERROR")
            InfoBar.error(
                title=self._tr("common.error.title", "Ошибка"),
                content=self._tr("page.z1_user_presets.error.generic", "Ошибка: {error}", error=e),
                parent=self.window(),
            )

    def _on_export_preset(self, name: str):
        display_name = self._resolve_display_name(name)
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            self._tr("page.z1_user_presets.file_dialog.export_title", "Экспортировать пресет"),
            f"{display_name}.txt",
            "Preset files (*.txt);;All files (*.*)",
        )

        if not file_path:
            return

        try:
            self._get_direct_facade().export_plain_text_by_file_name(name, Path(file_path))
            log(f"Экспортирован пресет '{display_name}' в {file_path}", "INFO")
            InfoBar.success(
                title=self._tr("page.z1_user_presets.infobar.success", "Успех"),
                content=self._tr(
                    "page.z1_user_presets.info.exported",
                    "Пресет экспортирован: {path}",
                    path=file_path,
                ),
                parent=self.window(),
            )

        except Exception as e:
            log(f"Ошибка экспорта пресета: {e}", "ERROR")
            InfoBar.error(
                title=self._tr("common.error.title", "Ошибка"),
                content=self._tr("page.z1_user_presets.error.generic", "Ошибка: {error}", error=e),
                parent=self.window(),
            )

    def _on_restore_deleted(self):
        """Restore all previously deleted presets that have matching templates."""
        try:
            facade = self._get_direct_facade()
            facade.restore_deleted()
            self._get_preset_store().notify_presets_changed()
            selected_file_name = facade.get_selected_file_name()
            if selected_file_name:
                self._get_preset_store().notify_preset_switched(selected_file_name)
            log("Восстановлены удалённые пресеты", "INFO")
        except Exception as e:
            log(f"Ошибка восстановления удалённых пресетов: {e}", "ERROR")
            InfoBar.error(
                title=self._tr("common.error.title", "Ошибка"),
                content=self._tr(
                    "page.z1_user_presets.error.restore_deleted",
                    "Ошибка восстановления: {error}",
                    error=e,
                ),
                parent=self.window(),
            )

    def _on_dpi_reload_needed(self):
        try:
            widget = self
            while widget:
                if hasattr(widget, "dpi_controller"):
                    widget.dpi_controller.restart_dpi_async()
                    log("DPI перезапущен после смены пресета", "INFO")
                    return
                widget = widget.parent()

            from PyQt6.QtWidgets import QApplication
            for w in QApplication.topLevelWidgets():
                if hasattr(w, "dpi_controller"):
                    w.dpi_controller.restart_dpi_async()
                    log("DPI перезапущен после смены пресета", "INFO")
                    return

        except Exception as e:
            log(f"Ошибка перезапуска DPI: {e}", "ERROR")

    def _open_presets_info(self):
        """Открывает страницу с информацией о пресетах."""
        try:
            from config.urls import PRESET_INFO_URL

            webbrowser.open(PRESET_INFO_URL)
            log(f"Открыта страница о пресетах: {PRESET_INFO_URL}", "INFO")
        except Exception as e:
            log(f"Не удалось открыть страницу о пресетах: {e}", "ERROR")

    def _open_new_configs_post(self):
        try:
            from config.telegram_links import open_telegram_link

            open_telegram_link("bypassblock", post=1359)
        except Exception as e:
            log(f"Ошибка открытия Telegram: {e}", "ERROR")
            InfoBar.warning(
                title=self._tr("common.error.title", "Ошибка"),
                content=self._tr(
                    "page.z1_user_presets.error.open_telegram",
                    "Не удалось открыть Telegram: {error}",
                    error=e,
                ),
                parent=self.window(),
            )

    def set_ui_language(self, language: str) -> None:
        super().set_ui_language(language)

        if self._back_btn is not None:
            self._back_btn.setText(self._tr("page.z1_user_presets.back.control", "Управление"))

        if self._configs_title_label is not None:
            self._configs_title_label.setText(
                self._tr(
                    "page.z1_user_presets.configs.title",
                    "Обменивайтесь категориями на нашем форуме-сайте через Telegram-бота: безопасно и анонимно",
                )
            )
        if self._get_configs_btn is not None:
            self._get_configs_btn.setText(self._tr("page.z1_user_presets.configs.button", "Получить конфиги"))

        if self._restore_deleted_btn is not None:
            self._restore_deleted_btn.setText(
                self._tr("page.z1_user_presets.button.restore_deleted", "Восстановить удалённые пресеты")
            )

        if self.create_btn is not None:
            set_tooltip(self.create_btn, self._tr("page.z1_user_presets.tooltip.create", "Создать новый пресет"))

        if self.import_btn is not None:
            self.import_btn.setText(self._tr("page.z1_user_presets.button.import", "Импорт"))
            set_tooltip(self.import_btn, self._tr("page.z1_user_presets.tooltip.import", "Импорт пресета из файла"))
        if self.folders_btn is not None:
            self.folders_btn.setText(self._tr("page.z1_user_presets.button.folders", "Папки"))
            set_tooltip(
                self.folders_btn,
                self._tr("page.z1_user_presets.tooltip.folders", "Создать папки и изменить их порядок"),
            )

        if self.reset_all_btn is not None:
            current_text = self.reset_all_btn.text() or ""
            if "/" not in current_text:
                self.reset_all_btn.setText(self._tr("page.z1_user_presets.button.reset_all", "Вернуть заводские"))
            set_tooltip(
                self.reset_all_btn,
                self._tr(
                    "page.z1_user_presets.tooltip.reset_all",
                    "Восстанавливает стандартные пресеты. Ваши изменения в стандартных пресетах будут потеряны.",
                ),
            )

        if self.presets_info_btn is not None:
            self.presets_info_btn.setText(self._tr("page.z1_user_presets.button.wiki", "Вики по пресетам"))
        if self.info_btn is not None:
            self.info_btn.setText(self._tr("page.z1_user_presets.button.what_is_this", "Что это такое?"))

        if self._preset_search_input is not None:
            self._preset_search_input.setPlaceholderText(
                self._tr("page.z1_user_presets.search.placeholder", "Поиск пресетов по имени...")
            )

        if self._presets_delegate is not None:
            self._presets_delegate.set_ui_language(self._ui_language)

        self._update_toolbar_buttons_layout()
        self._load_presets()
