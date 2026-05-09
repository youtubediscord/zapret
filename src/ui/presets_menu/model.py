from __future__ import annotations

import json

from PyQt6.QtCore import QAbstractListModel, QMimeData, QModelIndex, Qt


class PresetListModel(QAbstractListModel):
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
        candidate = str(file_name or "").strip()
        if not candidate:
            return -1
        for row_index, row in enumerate(self._rows):
            if str(row.get("kind") or "") != "preset":
                continue
            if str(row.get("file_name") or "") == candidate:
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
        preset_file_name = str(file_name or "").strip()
        preset_display_name = str(display_name or "").strip()
        changed_rows: list[int] = []
        for row_index, row in enumerate(self._rows):
            if str(row.get("kind") or "") != "preset":
                continue
            row_file_name = str(row.get("file_name") or "")
            row_display_name = str(row.get("name") or "")
            next_active = bool(preset_file_name and row_file_name == preset_file_name)
            if not next_active and use_display_name_fallback:
                next_active = bool(preset_display_name and row_display_name == preset_display_name)
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
            return row.get("icon_color", "#5caee8")
        if role == self.BuiltinRole:
            return bool(row.get("is_builtin", False))
        if role == self.DepthRole:
            return int(row.get("depth", 0) or 0)
        if role == self.PinnedRole:
            return bool(row.get("is_pinned", False))
        if role == self.RatingRole:
            return int(row.get("rating", 0) or 0)

        return None


__all__ = ["PresetListModel"]
