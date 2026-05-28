from __future__ import annotations

import json
from typing import Any

from PyQt6.QtCore import QAbstractListModel, QMimeData, QModelIndex, QPoint, Qt, pyqtSignal
from PyQt6.QtWidgets import QListView, QVBoxLayout, QWidget

from profile.icons import resolve_profile_icon
from profile.match_filters import ports_label_from_match_lines, protocol_label_from_match_lines
from profile.ui.profile_list_delegate import ProfileListDelegate
from profile.ui.profile_list_model import ProfileListModel
from profile.ui.profile_list_view import ProfileListView
from ui.smooth_scroll import apply_page_smooth_scroll_preference
from ui.widgets.fluent_scrollbar import install_fluent_scrollbars


class ProfileOrderListModel(QAbstractListModel):
    MIME_TYPE = ProfileListModel.MIME_TYPE

    def __init__(self, parent=None):
        super().__init__(parent)
        self._items: tuple[Any, ...] = ()

    def set_profiles(self, items: tuple[Any, ...]) -> None:
        rows = [item for item in tuple(items or ()) if bool(getattr(item, "in_preset", False))]
        rows.sort(key=lambda item: int(getattr(item, "profile_index", 0) or 0))
        self.beginResetModel()
        self._items = tuple(rows)
        self.endResetModel()

    def move_profile(self, source_profile_key: str, action: str, destination_profile_key: str = "") -> bool:
        source_key = str(source_profile_key or "").strip()
        move_action = str(action or "").strip()
        destination_key = str(destination_profile_key or "").strip()
        if not source_key:
            return False

        rows = list(self._items)
        source_index = next((index for index, item in enumerate(rows) if str(getattr(item, "key", "") or "") == source_key), -1)
        if source_index < 0:
            return False
        source = rows.pop(source_index)

        if move_action == "end":
            insert_index = len(rows)
        else:
            destination_index = next((index for index, item in enumerate(rows) if str(getattr(item, "key", "") or "") == destination_key), -1)
            if destination_index < 0:
                return False
            insert_index = destination_index + (1 if move_action == "after" else 0)
        rows.insert(insert_index, source)

        if insert_index in {source_index, source_index + 1}:
            return True
        destination_child = insert_index + 1 if insert_index > source_index else insert_index
        self.beginMoveRows(QModelIndex(), source_index, source_index, QModelIndex(), destination_child)
        self._items = tuple(rows)
        self.endMoveRows()
        return True

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self._items)

    def flags(self, index: QModelIndex):
        if not index.isValid():
            return Qt.ItemFlag.ItemIsEnabled
        return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsDragEnabled

    def supportedDragActions(self):
        return Qt.DropAction.MoveAction

    def supportedDropActions(self):
        return Qt.DropAction.MoveAction

    def mimeTypes(self):
        return [self.MIME_TYPE]

    def mimeData(self, indexes):
        mime = QMimeData()
        if not indexes:
            return mime
        index = indexes[0]
        key = str(index.data(ProfileListModel.ProfileKeyRole) or "")
        if key:
            mime.setData(self.MIME_TYPE, json.dumps({"profile_key": key}).encode("utf-8"))
        return mime

    def data(self, index: QModelIndex, role: int = int(Qt.ItemDataRole.DisplayRole)):
        if not index.isValid() or index.row() < 0 or index.row() >= len(self._items):
            return None
        item = self._items[index.row()]
        match_lines = tuple(getattr(item, "match_lines", ()) or ())
        display_name = str(getattr(item, "display_name", "") or "Profile")
        description = " | ".join(part for part in (protocol_label_from_match_lines(match_lines), ports_label_from_match_lines(match_lines)) if part)

        if role == int(Qt.ItemDataRole.DisplayRole):
            return display_name
        if role == ProfileListModel.KindRole:
            return "profile"
        if role == ProfileListModel.ProfileKeyRole:
            return str(getattr(item, "key", "") or "")
        if role == ProfileListModel.PersistentKeyRole:
            return str(getattr(item, "persistent_key", "") or "")
        if role == ProfileListModel.DisplayNameRole:
            return display_name
        if role == ProfileListModel.DescriptionRole:
            return description
        if role == ProfileListModel.StrategyIdRole:
            return str(getattr(item, "strategy_id", "") or "")
        if role == ProfileListModel.StrategyNameRole:
            return str(getattr(item, "strategy_name", "") or "")
        if role == ProfileListModel.MatchLinesRole:
            return match_lines
        if role == ProfileListModel.ListTypeRole:
            return str(getattr(item, "list_type", "") or "")
        if role == ProfileListModel.RatingRole:
            return ""
        if role == ProfileListModel.FavoriteRole:
            return False
        if role == ProfileListModel.InPresetRole:
            return True
        if role == ProfileListModel.EnabledRole:
            return bool(getattr(item, "enabled", False))
        if role == ProfileListModel.GroupRole:
            return ""
        if role == ProfileListModel.GroupNameRole:
            return ""
        if role == ProfileListModel.CollapsedRole:
            return False
        if role == ProfileListModel.CountRole:
            return 0
        if role == ProfileListModel.IconNameRole:
            icon = resolve_profile_icon(display_name, match_lines)
            return icon.icon_name
        if role == ProfileListModel.IconColorRole:
            icon = resolve_profile_icon(display_name, match_lines)
            return icon.color
        if role == ProfileListModel.TooltipRole:
            return "\n".join((display_name, description)).strip()
        return None


class ProfileOrderList(QWidget):
    profile_move_requested = pyqtSignal(str, str)
    profile_move_after_requested = pyqtSignal(str, str)
    profile_move_to_end_requested = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self._model = ProfileOrderListModel(self)
        self._view = ProfileListView(self)
        self._view.setModel(self._model)
        self._view.setSelectionMode(QListView.SelectionMode.SingleSelection)
        self._view.setEditTriggers(QListView.EditTrigger.NoEditTriggers)
        self._view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._view.setVerticalScrollMode(QListView.ScrollMode.ScrollPerPixel)
        self._view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._view.setDragDropMode(QListView.DragDropMode.DragDrop)
        self._view.setDefaultDropAction(Qt.DropAction.MoveAction)
        self._view.setUniformItemSizes(False)
        self._view.setMouseTracking(True)
        self._view.setStyleSheet(
            "QListView { background: transparent; border: none; outline: none; }"
            "QListView::item { background: transparent; border: none; }"
        )
        self._delegate = ProfileListDelegate(self._view)
        self._view.setItemDelegate(self._delegate)
        self._view.profile_move_requested.connect(lambda source, destination, _group: self.profile_move_requested.emit(source, destination))
        self._view.profile_move_after_requested.connect(lambda source, destination, _group: self.profile_move_after_requested.emit(source, destination))
        self._view.profile_move_to_end_requested.connect(self.profile_move_to_end_requested)
        install_fluent_scrollbars(self._view, vertical=True, horizontal=False, reserve_vertical_space=True)
        apply_page_smooth_scroll_preference(self._view)
        layout.addWidget(self._view, 1)

    def set_profiles(self, items: tuple[Any, ...]) -> None:
        self._model.set_profiles(tuple(items or ()))

    def move_profile_item(self, source_profile_key: str, action: str, destination_profile_key: str = "") -> bool:
        return self._model.move_profile(source_profile_key, action, destination_profile_key)


__all__ = ["ProfileOrderList", "ProfileOrderListModel"]
