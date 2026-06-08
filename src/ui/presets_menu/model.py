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
    FolderKeyRole = Qt.ItemDataRole.UserRole + 13
    CollapsedRole = Qt.ItemDataRole.UserRole + 14
    CountRole = Qt.ItemDataRole.UserRole + 15
    SystemRole = Qt.ItemDataRole.UserRole + 16
    ServiceRole = Qt.ItemDataRole.UserRole + 17

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rows: list[dict[str, object]] = []
        self._preset_row_by_file_name: dict[str, int] = {}
        self._preset_name_by_file_name: dict[str, str] = {}
        self._preset_builtin_by_file_name: dict[str, bool] = {}
        self._preset_rating_by_file_name: dict[str, int] = {}
        self._active_preset_file_names: set[str] = set()
        self._first_preset_row = -1

    def set_rows(self, rows: list[dict[str, object]]) -> bool:
        next_rows = list(rows)
        if self._rows == next_rows:
            return False

        if _same_stable_rows(self._rows, next_rows):
            changed_rows = [
                row_index
                for row_index, (current_row, next_row) in enumerate(zip(self._rows, next_rows, strict=True))
                if current_row != next_row
            ]
            self._rows = next_rows
            self._rebuild_row_index()
            roles = _all_data_roles()
            for row_index in changed_rows:
                model_index = self.index(row_index, 0)
                self.dataChanged.emit(model_index, model_index, roles)
            return True

        single_move = _single_row_move(self._rows, next_rows)
        if single_move is not None:
            source_index, insert_index = single_move
            destination_child = _move_destination_child(source_index, insert_index)
            if destination_child not in {source_index, source_index + 1}:
                previous_rows_by_identity = {
                    _stable_row_identity(row): row
                    for row in self._rows
                }
                self.beginMoveRows(QModelIndex(), source_index, source_index, QModelIndex(), destination_child)
                self._rows = next_rows
                self._rebuild_row_index()
                self.endMoveRows()
                roles = _all_data_roles()
                for row_index, row in enumerate(self._rows):
                    previous_row = previous_rows_by_identity.get(_stable_row_identity(row))
                    if previous_row is None or previous_row == row:
                        continue
                    model_index = self.index(row_index, 0)
                    self.dataChanged.emit(model_index, model_index, roles)
                return True

        self.beginResetModel()
        self._rows = next_rows
        self._rebuild_row_index()
        self.endResetModel()
        return True

    def _rebuild_row_index(self) -> None:
        self._preset_row_by_file_name = {}
        self._preset_name_by_file_name = {}
        self._preset_builtin_by_file_name = {}
        self._preset_rating_by_file_name = {}
        self._active_preset_file_names = set()
        self._first_preset_row = -1
        for row_index, row in enumerate(self._rows):
            if str(row.get("kind") or "") != "preset":
                continue
            if self._first_preset_row < 0:
                self._first_preset_row = row_index
            file_name = str(row.get("file_name") or "").strip()
            if not file_name:
                continue
            self._preset_row_by_file_name[file_name] = row_index
            display_name = str(row.get("name") or "").strip()
            if display_name:
                self._preset_name_by_file_name[file_name] = display_name
            self._preset_builtin_by_file_name[file_name] = bool(row.get("is_builtin", False))
            self._preset_rating_by_file_name[file_name] = _safe_int(row.get("rating"))
            if bool(row.get("is_active", False)):
                self._active_preset_file_names.add(file_name)

    def find_preset_row(self, file_name: str) -> int:
        candidate = str(file_name or "").strip()
        if not candidate:
            return -1
        return int(self._preset_row_by_file_name.get(candidate, -1))

    def preset_display_name(self, file_name: str) -> str:
        candidate = str(file_name or "").strip()
        if not candidate:
            return ""
        return str(self._preset_name_by_file_name.get(candidate, "") or "").strip()

    def preset_is_builtin(self, file_name: str) -> bool | None:
        candidate = str(file_name or "").strip()
        if not candidate:
            return None
        return self._preset_builtin_by_file_name.get(candidate)

    def preset_rating(self, file_name: str) -> int | None:
        candidate = str(file_name or "").strip()
        if not candidate:
            return None
        return self._preset_rating_by_file_name.get(candidate)

    def active_preset_file_name(self) -> str:
        for file_name in self._active_preset_file_names:
            return str(file_name or "").strip()
        return ""

    def first_preset_row(self) -> int:
        return int(self._first_preset_row)

    def move_preset(
        self,
        file_name: str,
        destination_kind: str,
        destination_id: str = "",
        destination_folder_key: str = "",
    ) -> bool:
        source_name = str(file_name or "").strip()
        kind = str(destination_kind or "").strip()
        source_index = self.find_preset_row(source_name)
        if source_index < 0:
            return False

        destination_index = self.find_preset_row(destination_id) if destination_id else -1
        if kind in {"preset", "preset_after"} and destination_index < 0:
            return False
        if kind in {"preset", "preset_after"} and source_index == destination_index:
            return False

        rows = [dict(row) for row in self._rows]
        source_row = rows.pop(source_index)
        if destination_index > source_index:
            destination_index -= 1

        if kind in {"preset", "preset_after"}:
            target_folder = str(destination_folder_key or rows[destination_index].get("folder_key") or "").strip()
            insert_index = destination_index + (1 if kind == "preset_after" else 0)
        elif kind == "folder":
            target_folder = str(destination_folder_key or destination_id or "").strip()
            insert_index = _folder_insert_index(rows, target_folder)
        elif kind == "end":
            target_folder = str(destination_folder_key or source_row.get("folder_key") or "").strip()
            insert_index = _folder_insert_index(rows, target_folder)
        else:
            return False
        if not target_folder:
            return False

        source_folder = str(source_row.get("folder_key") or "").strip()
        source_row["folder_key"] = target_folder
        if _folder_is_expanded(rows, target_folder):
            rows.insert(insert_index, source_row)

        visible_after_move = _folder_is_expanded(rows, target_folder)
        if source_folder != target_folder:
            _shift_folder_count(rows, source_folder, -1)
            _shift_folder_count(rows, target_folder, 1)

        if visible_after_move:
            destination_child = _move_destination_child(source_index, insert_index)
            if destination_child in {source_index, source_index + 1}:
                return False
            self.beginMoveRows(QModelIndex(), source_index, source_index, QModelIndex(), destination_child)
        else:
            self.beginRemoveRows(QModelIndex(), source_index, source_index)
        self._rows = rows
        self._rebuild_row_index()
        if visible_after_move:
            self.endMoveRows()
        else:
            self.endRemoveRows()
        if source_folder != target_folder:
            self._emit_folder_count_changed(source_folder)
            self._emit_folder_count_changed(target_folder)
        return True

    def _emit_folder_count_changed(self, folder_key: str) -> None:
        folder_index = _row_index_for_folder(self._rows, folder_key)
        if folder_index < 0:
            return
        model_index = self.index(folder_index, 0)
        self.dataChanged.emit(model_index, model_index, [self.CountRole])

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
            if key == "name":
                file_name = str(row.get("file_name") or "").strip()
                if file_name:
                    display_name = str(value or "").strip()
                    if display_name:
                        self._preset_name_by_file_name[file_name] = display_name
                    else:
                        self._preset_name_by_file_name.pop(file_name, None)
            if key == "is_active":
                file_name = str(row.get("file_name") or "").strip()
                if file_name:
                    if bool(value):
                        self._active_preset_file_names.add(file_name)
                    else:
                        self._active_preset_file_names.discard(file_name)
            if key == "is_builtin":
                file_name = str(row.get("file_name") or "").strip()
                if file_name:
                    self._preset_builtin_by_file_name[file_name] = bool(value)
            if key == "rating":
                file_name = str(row.get("file_name") or "").strip()
                if file_name:
                    self._preset_rating_by_file_name[file_name] = _safe_int(value)
            changed_roles.update(role_map[key])

        if not changed_roles:
            return False

        model_index = self.index(row_index, 0)
        self.dataChanged.emit(model_index, model_index, sorted(changed_roles))
        return True

    def set_folder_collapsed(self, folder_key: str, collapsed: bool) -> bool:
        key = str(folder_key or "").strip()
        folder_index = _row_index_for_folder(self._rows, key)
        if folder_index < 0:
            return False

        next_collapsed = bool(collapsed)
        folder_row = self._rows[folder_index]
        if bool(folder_row.get("is_collapsed", False)) == next_collapsed:
            return False
        if not next_collapsed:
            return False

        remove_start = folder_index + 1
        remove_end = remove_start
        while remove_end < len(self._rows):
            row = self._rows[remove_end]
            if str(row.get("kind") or "") == "folder":
                break
            remove_end += 1

        folder_row["is_collapsed"] = True
        if remove_end > remove_start:
            self.beginRemoveRows(QModelIndex(), remove_start, remove_end - 1)
            del self._rows[remove_start:remove_end]
            self._rebuild_row_index()
            self.endRemoveRows()

        model_index = self.index(folder_index, 0)
        self.dataChanged.emit(model_index, model_index, [self.CollapsedRole])
        return True

    def remove_preset(self, file_name: str) -> bool:
        preset_file_name = str(file_name or "").strip()
        row_index = self.find_preset_row(preset_file_name)
        if row_index < 0:
            return False

        row = self._rows[row_index]
        folder_key = str(row.get("folder_key") or "").strip()
        rows = [dict(entry) for entry in self._rows]
        if _folder_count(rows, folder_key) <= 1:
            return False

        rows.pop(row_index)
        _shift_folder_count(rows, folder_key, -1)
        self.beginRemoveRows(QModelIndex(), row_index, row_index)
        self._rows = rows
        self._rebuild_row_index()
        self.endRemoveRows()
        folder_index = _row_index_for_folder(self._rows, folder_key)
        if folder_index >= 0:
            model_index = self.index(folder_index, 0)
            self.dataChanged.emit(model_index, model_index, [self.CountRole])
        return True

    def insert_preset(self, row: dict[str, object]) -> bool:
        preset_file_name = str(row.get("file_name") or "").strip()
        if not preset_file_name or preset_file_name in self._preset_row_by_file_name:
            return False

        next_row = dict(row)
        next_row["kind"] = "preset"
        next_row["file_name"] = preset_file_name
        folder_key = str(next_row.get("folder_key") or "common").strip() or "common"
        next_row["folder_key"] = folder_key
        next_row.setdefault("depth", 1)
        next_row.setdefault("is_active", False)
        next_row.setdefault("is_builtin", False)
        next_row.setdefault("description", "")
        next_row.setdefault("date", "")
        next_row.setdefault("icon_color", "")
        next_row.setdefault("is_pinned", False)
        next_row.setdefault("rating", 0)

        folder_index = _row_index_for_folder(self._rows, folder_key)
        if folder_index >= 0 and bool(self._rows[folder_index].get("is_collapsed", False)):
            _shift_folder_count(self._rows, folder_key, 1)
            model_index = self.index(folder_index, 0)
            self.dataChanged.emit(model_index, model_index, [self.CountRole])
            return True

        insert_index = _folder_insert_index(self._rows, folder_key) if folder_index >= 0 else len(self._rows)
        _shift_folder_count(self._rows, folder_key, 1)
        self.beginInsertRows(QModelIndex(), insert_index, insert_index)
        self._rows.insert(insert_index, next_row)
        self._rebuild_row_index()
        self.endInsertRows()
        if folder_index >= 0:
            model_index = self.index(folder_index, 0)
            self.dataChanged.emit(model_index, model_index, [self.CountRole])
        return True

    def rename_preset(self, current_file_name: str, next_file_name: str, *, name: str = "") -> bool:
        current_name = str(current_file_name or "").strip()
        next_name = str(next_file_name or "").strip()
        if not current_name or not next_name:
            return False
        row_index = self.find_preset_row(current_name)
        if row_index < 0:
            return False

        row = self._rows[row_index]
        next_display_name = str(name or "").strip()
        current_display_name = str(row.get("name") or "").strip()
        if current_name == next_name and (not next_display_name or next_display_name == current_display_name):
            return False
        row["file_name"] = next_name
        if next_display_name:
            row["name"] = next_display_name
        if current_name in self._active_preset_file_names:
            self._active_preset_file_names.discard(current_name)
            self._active_preset_file_names.add(next_name)
            row["is_active"] = True
        self._rebuild_row_index()
        model_index = self.index(row_index, 0)
        self.dataChanged.emit(
            model_index,
            model_index,
            [int(Qt.ItemDataRole.DisplayRole), self.FileNameRole, self.NameRole, self.ActiveRole],
        )
        return True

    def set_active_preset(
        self,
        file_name: str,
    ) -> bool:
        preset_file_name = str(file_name or "").strip()
        next_active_files = {preset_file_name} if preset_file_name in self._preset_row_by_file_name else set()
        candidate_files = set(self._active_preset_file_names)
        candidate_files.update(next_active_files)
        changed_rows: list[int] = []

        for row_file_name in candidate_files:
            row_index = self._preset_row_by_file_name.get(row_file_name, -1)
            if row_index < 0 or row_index >= len(self._rows):
                continue
            row = self._rows[row_index]
            next_active = row_file_name in next_active_files
            if bool(row.get("is_active", False)) == bool(next_active):
                continue
            row["is_active"] = next_active
            changed_rows.append(row_index)

        self._active_preset_file_names = set(next_active_files)
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
        if role == int(Qt.ItemDataRole.AccessibleTextRole):
            return _preset_accessible_text(row)

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
        if role == self.FolderKeyRole:
            return row.get("folder_key", "")
        if role == self.CollapsedRole:
            return bool(row.get("is_collapsed", False))
        if role == self.CountRole:
            return int(row.get("count", 0) or 0)
        if role == self.SystemRole:
            return bool(row.get("is_system", False))
        if role == self.ServiceRole:
            return bool(row.get("is_service", False))

        return None


def _folder_is_expanded(rows: list[dict[str, object]], folder_key: str) -> bool:
    for row in rows:
        if str(row.get("kind") or "") != "folder":
            continue
        if str(row.get("folder_key") or "") == folder_key:
            return not bool(row.get("is_collapsed", False))
    return True


def _folder_insert_index(rows: list[dict[str, object]], folder_key: str) -> int:
    folder_index = -1
    for index, row in enumerate(rows):
        if str(row.get("kind") or "") == "folder" and str(row.get("folder_key") or "") == folder_key:
            folder_index = index
            break
    if folder_index < 0:
        return len(rows)
    insert_index = folder_index + 1
    while insert_index < len(rows):
        row = rows[insert_index]
        if str(row.get("kind") or "") == "folder":
            break
        if str(row.get("folder_key") or "") == folder_key:
            insert_index += 1
            continue
        break
    return insert_index


def _move_destination_child(source_index: int, insert_index_after_removal: int) -> int:
    if insert_index_after_removal > source_index:
        return insert_index_after_removal + 1
    return insert_index_after_removal


def _folder_count(rows: list[dict[str, object]], folder_key: str) -> int:
    index = _row_index_for_folder(rows, folder_key)
    if index < 0:
        return 2
    try:
        return int(rows[index].get("count", 0) or 0)
    except Exception:
        return 0


def _row_index_for_folder(rows: list[dict[str, object]], folder_key: str) -> int:
    key = str(folder_key or "").strip()
    if not key:
        return -1
    for index, row in enumerate(rows):
        if str(row.get("kind") or "") != "folder":
            continue
        if str(row.get("folder_key") or "") == key:
            return index
    return -1


def _shift_folder_count(rows: list[dict[str, object]], folder_key: str, delta: int) -> None:
    key = str(folder_key or "").strip()
    if not key or not delta:
        return
    for row in rows:
        if str(row.get("kind") or "") != "folder":
            continue
        if str(row.get("folder_key") or "") != key:
            continue
        try:
            row["count"] = max(0, int(row.get("count", 0) or 0) + int(delta))
        except Exception:
            row["count"] = max(0, int(delta))
        return


def _same_stable_rows(current_rows: list[dict[str, object]], next_rows: list[dict[str, object]]) -> bool:
    if len(current_rows) != len(next_rows):
        return False
    return all(
        _stable_row_identity(current_row) == _stable_row_identity(next_row)
        for current_row, next_row in zip(current_rows, next_rows, strict=True)
    )


def _single_row_move(
    current_rows: list[dict[str, object]],
    next_rows: list[dict[str, object]],
) -> tuple[int, int] | None:
    if len(current_rows) != len(next_rows):
        return None
    current_identities = [_stable_row_identity(row) for row in current_rows]
    next_identities = [_stable_row_identity(row) for row in next_rows]
    if current_identities == next_identities:
        return None
    if len(set(current_identities)) != len(current_identities):
        return None
    if set(current_identities) != set(next_identities):
        return None

    current_positions = {identity: index for index, identity in enumerate(current_identities)}
    first_changed = next(
        (
            index
            for index, identity in enumerate(next_identities)
            if current_positions.get(identity) != index
        ),
        -1,
    )
    if first_changed < 0:
        return None

    last_changed = len(next_identities) - 1
    while last_changed > first_changed and current_identities[last_changed] == next_identities[last_changed]:
        last_changed -= 1

    if current_identities[first_changed] == next_identities[last_changed]:
        return first_changed, last_changed
    if current_identities[last_changed] == next_identities[first_changed]:
        return last_changed, first_changed
    return None


def _stable_row_identity(row: dict[str, object]) -> tuple[str, str]:
    kind = str(row.get("kind") or "preset")
    if kind == "preset":
        return kind, str(row.get("file_name") or "").strip()
    if kind == "folder":
        return kind, str(row.get("folder_key") or "").strip()
    if kind == "empty":
        return kind, str(row.get("text") or "")
    return kind, str(row.get("file_name") or row.get("folder_key") or row.get("text") or row.get("name") or "")


def _all_data_roles() -> list[int]:
    return [
        int(Qt.ItemDataRole.DisplayRole),
        PresetListModel.KindRole,
        PresetListModel.NameRole,
        PresetListModel.FileNameRole,
        PresetListModel.DescriptionRole,
        PresetListModel.DateRole,
        PresetListModel.ActiveRole,
        PresetListModel.TextRole,
        PresetListModel.IconColorRole,
        PresetListModel.BuiltinRole,
        PresetListModel.DepthRole,
        PresetListModel.PinnedRole,
        PresetListModel.RatingRole,
        PresetListModel.FolderKeyRole,
        PresetListModel.CollapsedRole,
        PresetListModel.CountRole,
        PresetListModel.SystemRole,
        PresetListModel.ServiceRole,
        int(Qt.ItemDataRole.AccessibleTextRole),
    ]


def _preset_accessible_text(row: dict[str, object]) -> str:
    kind = str(row.get("kind") or "preset")
    if kind == "preset":
        name = str(row.get("name") or row.get("file_name") or "").strip()
        parts = [name]
        parts.append("активный preset" if bool(row.get("is_active", False)) else "не активный preset")
        parts.append("встроенный" if bool(row.get("is_builtin", False)) else "пользовательский")
        if bool(row.get("is_pinned", False)):
            parts.append("закреплённый")
        rating = _safe_int(row.get("rating"))
        if rating:
            parts.append(f"оценка {rating}")
        return ", ".join(part for part in parts if part)

    if kind == "folder":
        name = str(row.get("name") or row.get("text") or "").strip()
        count = _safe_int(row.get("count"))
        expanded_text = "свернута" if bool(row.get("is_collapsed", False)) else "развернута"
        return f"Папка {name}, {_preset_count_text(count)}, {expanded_text}"

    return str(row.get("text") or row.get("name") or "").strip()


def _preset_count_text(count: int) -> str:
    if count % 10 == 1 and count % 100 != 11:
        return f"{count} пресет"
    if count % 10 in {2, 3, 4} and count % 100 not in {12, 13, 14}:
        return f"{count} пресета"
    return f"{count} пресетов"


def _safe_int(value: object) -> int:
    try:
        return int(value or 0)
    except Exception:
        return 0


__all__ = ["PresetListModel"]
