from __future__ import annotations

import json
from dataclasses import replace
from typing import Any

from PyQt6.QtCore import QAbstractListModel, QMimeData, QModelIndex, Qt

from folders.defaults import build_default_profile_folders
from profile.icons import resolve_profile_icon
from profile.match_filters import is_voice_match, ports_label_from_match_lines, protocol_label_from_match_lines
from profile.ui.profile_display_items import ProfileDisplayItem, build_profile_display_items, profile_display_sort_key


class ProfileListModel(QAbstractListModel):
    KindRole = Qt.ItemDataRole.UserRole + 1
    ProfileKeyRole = Qt.ItemDataRole.UserRole + 2
    PersistentKeyRole = Qt.ItemDataRole.UserRole + 3
    DisplayNameRole = Qt.ItemDataRole.UserRole + 4
    DescriptionRole = Qt.ItemDataRole.UserRole + 5
    StrategyIdRole = Qt.ItemDataRole.UserRole + 6
    StrategyNameRole = Qt.ItemDataRole.UserRole + 7
    MatchLinesRole = Qt.ItemDataRole.UserRole + 8
    ListTypeRole = Qt.ItemDataRole.UserRole + 9
    RatingRole = Qt.ItemDataRole.UserRole + 10
    FavoriteRole = Qt.ItemDataRole.UserRole + 11
    InPresetRole = Qt.ItemDataRole.UserRole + 12
    EnabledRole = Qt.ItemDataRole.UserRole + 13
    GroupRole = Qt.ItemDataRole.UserRole + 14
    GroupNameRole = Qt.ItemDataRole.UserRole + 15
    CollapsedRole = Qt.ItemDataRole.UserRole + 16
    CountRole = Qt.ItemDataRole.UserRole + 17
    IconNameRole = Qt.ItemDataRole.UserRole + 18
    IconColorRole = Qt.ItemDataRole.UserRole + 19
    TooltipRole = Qt.ItemDataRole.UserRole + 20

    MIME_TYPE = "application/x-zapret-profile-key"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._all_items: tuple[ProfileDisplayItem, ...] = ()
        self._rows: list[dict[str, Any]] = []
        self._profile_items: dict[str, ProfileDisplayItem] = {}
        self._group_expanded: dict[str, bool] = {}
        self._active_profile_types: set[str] = {"all"}
        self._search_query = ""

    def set_profiles(
        self,
        items: tuple[Any, ...],
        *,
        active_profile_types: set[str] | None = None,
        search_query: str | None = None,
    ) -> None:
        display_items = build_profile_display_items(tuple(items or ()))
        active = _normalized_profile_types(
            self._active_profile_types if active_profile_types is None else active_profile_types
        )
        normalized_search = self._search_query if search_query is None else _normalized_search_query(search_query)
        self.beginResetModel()
        self._all_items = display_items
        self._profile_items = {item.key: item for item in display_items}
        self._group_expanded = _initial_group_expanded(display_items)
        self._active_profile_types = active
        self._search_query = normalized_search
        self._rows = self._build_rows()
        self.endResetModel()

    def update_profiles(
        self,
        items: tuple[Any, ...],
        *,
        active_profile_types: set[str] | None = None,
        search_query: str | None = None,
    ) -> bool:
        display_items = build_profile_display_items(tuple(items or ()))
        active = _normalized_profile_types(
            self._active_profile_types if active_profile_types is None else active_profile_types
        )
        normalized_search = self._search_query if search_query is None else _normalized_search_query(search_query)
        next_group_expanded = dict(self._group_expanded)
        for item in display_items:
            next_group_expanded.setdefault(str(item.group or "common"), True)
        next_rows = self._build_rows_from(display_items, next_group_expanded)
        next_profile_items = {item.key: item for item in display_items}

        filters_unchanged = self._active_profile_types == active and self._search_query == normalized_search
        can_keep_visible_rows = filters_unchanged and [_stable_row_identity(row) for row in self._rows] == [
            _stable_row_identity(row) for row in next_rows
        ]
        if can_keep_visible_rows:
            changed_rows = tuple(index for index, row in enumerate(next_rows) if self._rows[index] != row)
            self._all_items = display_items
            self._profile_items = next_profile_items
            self._group_expanded = next_group_expanded
            self._rows = next_rows
            self._emit_data_changed_for_rows(changed_rows)
            return True

        insert_index = _single_inserted_row_index(self._rows, next_rows, identity_fn=_stable_row_identity)
        if filters_unchanged and insert_index >= 0:
            changed_rows = _changed_existing_row_indexes(self._rows, next_rows, identity_fn=_stable_row_identity)
            self.beginInsertRows(QModelIndex(), insert_index, insert_index)
            self._all_items = display_items
            self._profile_items = next_profile_items
            self._group_expanded = next_group_expanded
            self._rows = next_rows
            self.endInsertRows()
            self._emit_data_changed_for_rows(changed_rows)
            return True

        remove_index = _single_removed_row_index(self._rows, next_rows, identity_fn=_stable_row_identity)
        if filters_unchanged and remove_index >= 0:
            changed_rows = _changed_existing_row_indexes(self._rows, next_rows, identity_fn=_stable_row_identity)
            self.beginRemoveRows(QModelIndex(), remove_index, remove_index)
            self._all_items = display_items
            self._profile_items = next_profile_items
            self._group_expanded = next_group_expanded
            self._rows = next_rows
            self.endRemoveRows()
            self._emit_data_changed_for_rows(changed_rows)
            return True

        self.beginResetModel()
        self._all_items = display_items
        self._profile_items = next_profile_items
        self._group_expanded = next_group_expanded
        self._active_profile_types = active
        self._search_query = normalized_search
        self._rows = next_rows
        self.endResetModel()
        return True

    def set_active_profile_types(self, profile_types: set[str]) -> None:
        active = _normalized_profile_types(profile_types)
        if self._active_profile_types == active:
            return
        previous_active = self._active_profile_types
        self._active_profile_types = active
        try:
            next_rows = self._build_rows()
        finally:
            self._active_profile_types = previous_active

        old_ids = [_stable_row_identity(row) for row in self._rows]
        next_ids = [_stable_row_identity(row) for row in next_rows]
        if old_ids == next_ids:
            changed_rows = tuple(index for index, row in enumerate(next_rows) if self._rows[index] != row)
            self._active_profile_types = active
            self._rows = next_rows
            self._emit_data_changed_for_rows(changed_rows)
            return

        self.beginResetModel()
        self._active_profile_types = active
        self._rows = next_rows
        self.endResetModel()

    def set_search_query(self, query: str) -> None:
        normalized = _normalized_search_query(query)
        if self._search_query == normalized:
            return
        previous_query = self._search_query
        self._search_query = normalized
        try:
            next_rows = self._build_rows()
        finally:
            self._search_query = previous_query

        old_ids = [_stable_row_identity(row) for row in self._rows]
        next_ids = [_stable_row_identity(row) for row in next_rows]
        if old_ids == next_ids:
            changed_rows = tuple(index for index, row in enumerate(next_rows) if self._rows[index] != row)
            self._search_query = normalized
            self._rows = next_rows
            self._emit_data_changed_for_rows(changed_rows)
            return

        self.beginResetModel()
        self._search_query = normalized
        self._rows = next_rows
        self.endResetModel()

    def set_group_expanded(self, group_key: str, expanded: bool) -> None:
        key = str(group_key or "")
        if not key:
            return
        expanded_value = bool(expanded)
        if self._group_expanded.get(key, True) == expanded_value:
            return
        next_group_expanded = dict(self._group_expanded)
        next_group_expanded[key] = expanded_value
        next_rows = self._build_rows_from(self._all_items, next_group_expanded)
        old_ids = [_stable_row_identity(row) for row in self._rows]
        next_ids = [_stable_row_identity(row) for row in next_rows]

        if old_ids == next_ids:
            changed_rows = tuple(index for index, row in enumerate(next_rows) if self._rows[index] != row)
            self._group_expanded = next_group_expanded
            self._rows = next_rows
            self._emit_data_changed_for_rows(changed_rows)
            return

        old_group_index = _row_index_for_group(self._rows, key)
        next_group_index = _row_index_for_group(next_rows, key)
        if old_group_index >= 0 and old_group_index == next_group_index:
            changed_rows = _changed_existing_row_indexes(
                self._rows,
                next_rows,
                identity_fn=_stable_row_identity,
            )
            if expanded_value and _rows_match_single_group_insert(self._rows, next_rows, old_group_index):
                insert_count = len(next_rows) - len(self._rows)
                self.beginInsertRows(QModelIndex(), old_group_index + 1, old_group_index + insert_count)
                self._group_expanded = next_group_expanded
                self._rows = next_rows
                self.endInsertRows()
                self._emit_data_changed_for_rows(changed_rows)
                return
            if not expanded_value and _rows_match_single_group_remove(self._rows, next_rows, old_group_index):
                remove_count = len(self._rows) - len(next_rows)
                self.beginRemoveRows(QModelIndex(), old_group_index + 1, old_group_index + remove_count)
                self._group_expanded = next_group_expanded
                self._rows = next_rows
                self.endRemoveRows()
                self._emit_data_changed_for_rows(changed_rows)
                return

        self.beginResetModel()
        self._group_expanded = next_group_expanded
        self._rows = next_rows
        self.endResetModel()

    def set_all_groups_expanded(self, expanded: bool) -> tuple[str, ...]:
        expanded_value = bool(expanded)
        group_keys = tuple(str(group_key) for group_key in _grouped_items(self._all_items))
        changed_group_keys = tuple(
            group_key
            for group_key in group_keys
            if self._group_expanded.get(group_key, True) != expanded_value
        )
        if not changed_group_keys:
            return ()
        self.beginResetModel()
        for group_key in group_keys:
            self._group_expanded[group_key] = expanded_value
        self._rows = self._build_rows()
        self.endResetModel()
        return changed_group_keys

    def is_group_expanded(self, group_key: str) -> bool:
        return bool(self._group_expanded.get(str(group_key or ""), True))

    def profile_item_for_key(self, profile_key: str):
        return self._profile_items.get(str(profile_key or "").strip())

    def replace_profile(self, profile_key: str, item: Any) -> bool:
        source_key = str(profile_key or "").strip()
        display_items = build_profile_display_items((item,))
        if not source_key or not display_items:
            return False
        replacement = display_items[0]
        current = self._profile_items.get(source_key)
        if current is None:
            return False

        next_items = tuple(replacement if existing.key == source_key else existing for existing in self._all_items)
        can_update_row = (
            str(current.group or "") == str(replacement.group or "")
            and self._matches_filter(current)
            and self._matches_filter(replacement)
        )
        self._all_items = next_items
        self._profile_items = {entry.key: entry for entry in self._all_items}

        if can_update_row:
            row_index = self._row_index_for_profile_key(source_key)
            if row_index >= 0:
                self._rows[row_index] = _row_for_profile(replacement)
                model_index = self.index(row_index, 0)
                self.dataChanged.emit(model_index, model_index, _profile_data_roles())
                return True

        self.beginResetModel()
        self._group_expanded.setdefault(str(replacement.group or "common"), True)
        self._rows = self._build_rows()
        self.endResetModel()
        return True

    def add_profile(self, item: Any) -> bool:
        display_items = build_profile_display_items((item,))
        if not display_items:
            return False
        profile = display_items[0]
        if not profile.key:
            return False
        if profile.key in self._profile_items:
            return self.replace_profile(profile.key, item)
        next_items = tuple((*self._all_items, profile))
        next_profile_items = {entry.key: entry for entry in next_items}
        next_group_expanded = dict(self._group_expanded)
        next_group_expanded.setdefault(str(profile.group or "common"), True)
        next_rows = self._build_rows_from(next_items, next_group_expanded)
        insert_index = _single_inserted_row_index(self._rows, next_rows)
        if insert_index >= 0:
            changed_rows = _changed_existing_row_indexes(self._rows, next_rows)
            self.beginInsertRows(QModelIndex(), insert_index, insert_index)
            self._all_items = next_items
            self._profile_items = next_profile_items
            self._group_expanded = next_group_expanded
            self._rows = next_rows
            self.endInsertRows()
            self._emit_data_changed_for_rows(changed_rows)
            return True

        self.beginResetModel()
        self._all_items = next_items
        self._profile_items = next_profile_items
        self._group_expanded = next_group_expanded
        self._rows = next_rows
        self.endResetModel()
        return True

    def replace_user_profile_items(self, profile_id: str, items: tuple[Any, ...]) -> bool:
        clean_profile_id = str(profile_id or "").strip()
        replacement_items = build_profile_display_items(tuple(items or ()))
        if not clean_profile_id or not replacement_items:
            return False
        existing_items = tuple(
            item for item in self._all_items
            if str(getattr(item, "user_profile_id", "") or "").strip() == clean_profile_id
        )
        if not existing_items:
            return False
        next_items = tuple(
            item for item in self._all_items
            if str(getattr(item, "user_profile_id", "") or "").strip() != clean_profile_id
        )
        return self.update_profiles(tuple((*next_items, *replacement_items)))

    def remove_user_profile_items(self, profile_id: str) -> bool:
        clean_profile_id = str(profile_id or "").strip()
        if not clean_profile_id:
            return False
        next_items = tuple(
            item for item in self._all_items
            if str(getattr(item, "user_profile_id", "") or "").strip() != clean_profile_id
        )
        if len(next_items) == len(self._all_items):
            return False
        return self.update_profiles(next_items)

    def remove_profile(self, profile_key: str) -> bool:
        key = str(profile_key or "").strip()
        if not key or key not in self._profile_items:
            return False
        next_items = tuple(item for item in self._all_items if item.key != key)
        next_profile_items = {entry.key: entry for entry in next_items}
        next_rows = self._build_rows_from(next_items, self._group_expanded)
        remove_index = _single_removed_row_index(self._rows, next_rows)
        if remove_index >= 0:
            changed_rows = _changed_existing_row_indexes(self._rows, next_rows)
            self.beginRemoveRows(QModelIndex(), remove_index, remove_index)
            self._all_items = next_items
            self._profile_items = next_profile_items
            self._rows = next_rows
            self.endRemoveRows()
            self._emit_data_changed_for_rows(changed_rows)
            return True

        self.beginResetModel()
        self._all_items = next_items
        self._profile_items = next_profile_items
        self._rows = next_rows
        self.endResetModel()
        return True

    def move_profile(
        self,
        source_profile_key: str,
        destination_kind: str,
        destination_profile_key: str = "",
        destination_group_key: str = "",
    ) -> bool:
        source_key = str(source_profile_key or "").strip()
        kind = str(destination_kind or "").strip()
        if not source_key:
            return False
        source = self._profile_items.get(source_key)
        if source is None:
            return False

        destination = self._profile_items.get(str(destination_profile_key or "").strip())
        if kind in {"profile", "profile_after"}:
            if destination is None or destination.key == source.key:
                return False
            target_group = str(destination_group_key or destination.group or source.group or "common")
        elif kind == "folder":
            target_group = str(destination_group_key or "").strip()
        elif kind == "end":
            target_group = str(destination_group_key or source.group or "common").strip()
        else:
            return False
        if not target_group:
            return False

        group_name = _group_name_for_key(target_group, self._all_items)
        source_for_target = replace(source, group=target_group, group_name=group_name, order_is_manual=True)
        target_items = [
            item
            for item in sorted(self._all_items, key=profile_display_sort_key)
            if item.key != source_key and str(item.group or "common") == target_group
        ]

        if kind == "profile":
            insert_index = next((index for index, item in enumerate(target_items) if item.key == destination.key), -1)
            if insert_index < 0:
                return False
            target_items.insert(insert_index, source_for_target)
        elif kind == "profile_after":
            insert_index = next((index for index, item in enumerate(target_items) if item.key == destination.key), -1)
            if insert_index < 0:
                return False
            target_items.insert(insert_index + 1, source_for_target)
        else:
            target_items.append(source_for_target)

        target_order = {item.key: index for index, item in enumerate(target_items)}
        next_items: list[ProfileDisplayItem] = []
        for item in self._all_items:
            if item.key == source_key and item.key not in target_order:
                continue
            if item.key in target_order:
                next_items.append(
                    replace(
                        source_for_target if item.key == source_key else item,
                        group=target_group,
                        group_name=group_name,
                        order=target_order[item.key],
                        order_is_manual=True,
                    )
                )
            else:
                next_items.append(item)

        next_items_tuple = tuple(next_items)
        next_group_expanded = dict(self._group_expanded)
        next_group_expanded.setdefault(target_group, True)
        next_rows = self._build_rows_from(next_items_tuple, next_group_expanded)
        move = _single_row_move(self._rows, next_rows, identity_fn=_stable_row_identity)
        if move is not None:
            source_row, insert_row = move
            destination_child = _move_destination_child(source_row, insert_row)
            if destination_child not in {source_row, source_row + 1}:
                changed_rows = _changed_existing_row_indexes(
                    self._rows,
                    next_rows,
                    identity_fn=_stable_row_identity,
                )
                self.beginMoveRows(QModelIndex(), source_row, source_row, QModelIndex(), destination_child)
                self._all_items = next_items_tuple
                self._profile_items = {item.key: item for item in self._all_items}
                self._group_expanded = next_group_expanded
                self._rows = next_rows
                self.endMoveRows()
                self._emit_data_changed_for_rows(changed_rows)
                return True

        self.beginResetModel()
        self._all_items = next_items_tuple
        self._profile_items = {item.key: item for item in self._all_items}
        self._group_expanded = next_group_expanded
        self._rows = next_rows
        self.endResetModel()
        return True

    def apply_folder_state(self, folder_state: dict[str, Any]) -> bool:
        if not isinstance(folder_state, dict):
            return False
        if not self._all_items:
            return False

        from profile.folders import profile_folder_collapsed, profile_folder_for_profile

        next_items: list[ProfileDisplayItem] = []
        for item in self._all_items:
            folder_key, folder_name, order = profile_folder_for_profile(item, folder_state)
            next_items.append(
                replace(
                    item,
                    group=folder_key,
                    group_name=folder_name,
                    order=int(order) if order is not None else int(item.order or 0),
                    order_is_manual=order is not None,
                    group_collapsed=profile_folder_collapsed(folder_key, folder_state),
                )
            )

        next_items_tuple = tuple(sorted(next_items, key=profile_display_sort_key))
        next_group_expanded = _initial_group_expanded(next_items_tuple)
        next_rows = self._build_rows_from(next_items_tuple, next_group_expanded)
        next_profile_items = {item.key: item for item in next_items_tuple}

        can_keep_visible_rows = [_stable_row_identity(row) for row in self._rows] == [
            _stable_row_identity(row) for row in next_rows
        ]
        if can_keep_visible_rows:
            changed_rows = tuple(index for index, row in enumerate(next_rows) if self._rows[index] != row)
            self._all_items = next_items_tuple
            self._profile_items = next_profile_items
            self._group_expanded = next_group_expanded
            self._rows = next_rows
            self._emit_data_changed_for_rows(changed_rows)
            return True

        self.beginResetModel()
        self._all_items = next_items_tuple
        self._profile_items = next_profile_items
        self._group_expanded = next_group_expanded
        self._rows = next_rows
        self.endResetModel()
        return True

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self._rows)

    def flags(self, index: QModelIndex):
        if not index.isValid():
            return Qt.ItemFlag.ItemIsEnabled
        flags = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        if str(index.data(self.KindRole) or "") == "profile":
            flags |= Qt.ItemFlag.ItemIsDragEnabled
        return flags

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
        if str(index.data(self.KindRole) or "") != "profile":
            return mime
        key = str(index.data(self.ProfileKeyRole) or "")
        if key:
            mime.setData(self.MIME_TYPE, json.dumps({"profile_key": key}).encode("utf-8"))
        return mime

    def data(self, index: QModelIndex, role: int = int(Qt.ItemDataRole.DisplayRole)):
        if not index.isValid() or index.row() < 0 or index.row() >= len(self._rows):
            return None
        row = self._rows[index.row()]
        kind = str(row.get("kind") or "")

        if role == int(Qt.ItemDataRole.DisplayRole):
            return row.get("display_name") or row.get("group_name") or ""
        if role == self.KindRole:
            return kind
        if role == self.ProfileKeyRole:
            return row.get("key", "")
        if role == self.PersistentKeyRole:
            return row.get("persistent_key", "")
        if role == self.DisplayNameRole:
            return row.get("display_name", "")
        if role == self.DescriptionRole:
            return row.get("description", "")
        if role == self.StrategyIdRole:
            return row.get("strategy_id", "")
        if role == self.StrategyNameRole:
            return row.get("strategy_name", "")
        if role == self.MatchLinesRole:
            return tuple(row.get("match_lines", ()) or ())
        if role == self.ListTypeRole:
            return row.get("list_type", "")
        if role == self.RatingRole:
            return row.get("rating", "")
        if role == self.FavoriteRole:
            return bool(row.get("favorite", False))
        if role == self.InPresetRole:
            return bool(row.get("in_preset", False))
        if role == self.EnabledRole:
            return bool(row.get("enabled", False))
        if role == self.GroupRole:
            return row.get("group", "")
        if role == self.GroupNameRole:
            return row.get("group_name", "")
        if role == self.CollapsedRole:
            return bool(row.get("collapsed", False))
        if role == self.CountRole:
            return int(row.get("count", 0) or 0)
        if role == self.IconNameRole:
            return row.get("icon_name", "")
        if role == self.IconColorRole:
            return row.get("icon_color", "")
        if role == self.TooltipRole:
            return row.get("tooltip", "")
        return None

    def _build_rows(self) -> list[dict[str, Any]]:
        return self._build_rows_from(self._all_items, self._group_expanded)

    def _build_rows_from(
        self,
        items: tuple[ProfileDisplayItem, ...],
        group_expanded: dict[str, bool],
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        grouped = _grouped_items(items)
        if not grouped:
            return rows
        for group_key in _ordered_group_keys(grouped):
            group_items = tuple(item for item in grouped.get(group_key, ()) if self._matches_filter(item))
            if not group_items:
                continue
            group_items = tuple(sorted(group_items, key=profile_display_sort_key))
            group_name = str(group_items[0].group_name or group_key.title())
            expanded = group_expanded.get(group_key, True)
            rows.append({
                "kind": "folder",
                "group": group_key,
                "group_name": group_name,
                "collapsed": not expanded,
                "count": len(group_items),
            })
            if not expanded:
                continue
            rows.extend(_row_for_profile(item) for item in group_items)
        return rows

    def _emit_data_changed_for_rows(self, rows: tuple[int, ...]) -> None:
        for row_index in rows:
            if row_index < 0 or row_index >= len(self._rows):
                continue
            model_index = self.index(row_index, 0)
            self.dataChanged.emit(model_index, model_index, _profile_data_roles())

    def _matches_filter(self, item: ProfileDisplayItem) -> bool:
        return self._matches_type_filter(item) and self._matches_search_query(item)

    def _matches_type_filter(self, item: ProfileDisplayItem) -> bool:
        active = self._active_profile_types
        if "all" in active:
            return True
        match_lines = tuple(item.match_lines or ())
        protocol = protocol_label_from_match_lines(match_lines).upper()
        summary = _match_summary(item)
        text = f"{item.display_name} {summary} {item.group}".lower()
        if "tcp" in active and "TCP" in protocol:
            return True
        if "udp" in active and ("UDP" in protocol or "L7" in protocol):
            return True
        if "discord" in active and "discord" in text:
            return True
        if "voice" in active and is_voice_match(match_lines):
            return True
        if "games" in active and "game" in text:
            return True
        return False

    def _matches_search_query(self, item: ProfileDisplayItem) -> bool:
        query = self._search_query
        if not query:
            return True
        search_text = _profile_search_text(item)
        return all(part in search_text for part in query.split())

    def _row_index_for_profile_key(self, profile_key: str) -> int:
        key = str(profile_key or "").strip()
        for index, row in enumerate(self._rows):
            if str(row.get("kind") or "") == "profile" and str(row.get("key") or "") == key:
                return index
        return -1


def _row_for_profile(item: ProfileDisplayItem) -> dict[str, Any]:
    match_lines = tuple(item.match_lines or ())
    ports = ports_label_from_match_lines(match_lines)
    description_parts = [
        part
        for part in (
            protocol_label_from_match_lines(match_lines),
            f"порты: {ports}" if ports else "",
        )
        if part
    ]
    tooltip = _match_summary(item)
    if not item.in_preset:
        tooltip = f"{tooltip}\nПрофиля ещё нет в пресете. Включите его или выберите готовую стратегию."
    elif not item.enabled:
        tooltip = f"{tooltip}\nПрофиль есть в пресете, но сейчас выключен. В файле это записано через --skip."
    icon = resolve_profile_icon(item.display_name, match_lines)
    return {
        "kind": "profile",
        "key": item.key,
        "persistent_key": item.persistent_key,
        "display_name": item.display_name,
        "description": " | ".join(description_parts),
        "strategy_id": item.strategy_id,
        "strategy_name": item.strategy_name,
        "match_lines": match_lines,
        "list_type": item.list_type,
        "rating": item.rating,
        "favorite": item.favorite,
        "in_preset": item.in_preset,
        "enabled": item.enabled,
        "group": item.group,
        "group_name": item.group_name,
        "icon_name": icon.icon_name,
        "icon_color": icon.color if item.in_preset else "#888888",
        "tooltip": tooltip,
    }


def _single_inserted_row_index(
    old_rows: list[dict[str, Any]],
    next_rows: list[dict[str, Any]],
    *,
    identity_fn=None,
) -> int:
    identity_fn = identity_fn or _row_identity
    if len(next_rows) != len(old_rows) + 1:
        return -1
    old_ids = [identity_fn(row) for row in old_rows]
    next_ids = [identity_fn(row) for row in next_rows]
    for index in range(len(next_ids)):
        if next_ids[:index] + next_ids[index + 1 :] == old_ids:
            return index
    return -1


def _single_removed_row_index(
    old_rows: list[dict[str, Any]],
    next_rows: list[dict[str, Any]],
    *,
    identity_fn=None,
) -> int:
    identity_fn = identity_fn or _row_identity
    if len(old_rows) != len(next_rows) + 1:
        return -1
    old_ids = [identity_fn(row) for row in old_rows]
    next_ids = [identity_fn(row) for row in next_rows]
    for index in range(len(old_ids)):
        if old_ids[:index] + old_ids[index + 1 :] == next_ids:
            return index
    return -1


def _changed_existing_row_indexes(
    old_rows: list[dict[str, Any]],
    next_rows: list[dict[str, Any]],
    *,
    identity_fn=None,
) -> tuple[int, ...]:
    identity_fn = identity_fn or _row_identity
    old_by_id = {identity_fn(row): row for row in old_rows}
    changed: list[int] = []
    for index, row in enumerate(next_rows):
        old_row = old_by_id.get(identity_fn(row))
        if old_row is not None and old_row != row:
            changed.append(index)
    return tuple(changed)


def _single_row_move(
    old_rows: list[dict[str, Any]],
    next_rows: list[dict[str, Any]],
    *,
    identity_fn=None,
) -> tuple[int, int] | None:
    identity_fn = identity_fn or _row_identity
    if len(old_rows) != len(next_rows):
        return None
    old_ids = [identity_fn(row) for row in old_rows]
    next_ids = [identity_fn(row) for row in next_rows]
    if old_ids == next_ids:
        return None
    if len(set(old_ids)) != len(old_ids) or set(old_ids) != set(next_ids):
        return None

    old_positions = {identity: index for index, identity in enumerate(old_ids)}
    first_changed = next(
        (
            index
            for index, identity in enumerate(next_ids)
            if old_positions.get(identity) != index
        ),
        -1,
    )
    if first_changed < 0:
        return None

    last_changed = len(next_ids) - 1
    while last_changed > first_changed and old_ids[last_changed] == next_ids[last_changed]:
        last_changed -= 1

    if old_ids[first_changed] == next_ids[last_changed]:
        return first_changed, last_changed
    if old_ids[last_changed] == next_ids[first_changed]:
        return last_changed, first_changed
    return None


def _move_destination_child(source_index: int, insert_index_after_removal: int) -> int:
    if insert_index_after_removal > source_index:
        return insert_index_after_removal + 1
    return insert_index_after_removal


def _row_index_for_group(rows: list[dict[str, Any]], group_key: str) -> int:
    key = str(group_key or "")
    for index, row in enumerate(rows):
        if str(row.get("kind") or "") == "folder" and str(row.get("group") or "") == key:
            return index
    return -1


def _rows_match_single_group_insert(
    old_rows: list[dict[str, Any]],
    next_rows: list[dict[str, Any]],
    group_index: int,
) -> bool:
    insert_count = len(next_rows) - len(old_rows)
    if insert_count <= 0:
        return False
    old_ids = [_stable_row_identity(row) for row in old_rows]
    next_ids = [_stable_row_identity(row) for row in next_rows]
    return (
        old_ids[: group_index + 1] == next_ids[: group_index + 1]
        and old_ids[group_index + 1 :] == next_ids[group_index + 1 + insert_count :]
    )


def _rows_match_single_group_remove(
    old_rows: list[dict[str, Any]],
    next_rows: list[dict[str, Any]],
    group_index: int,
) -> bool:
    remove_count = len(old_rows) - len(next_rows)
    if remove_count <= 0:
        return False
    old_ids = [_stable_row_identity(row) for row in old_rows]
    next_ids = [_stable_row_identity(row) for row in next_rows]
    return (
        old_ids[: group_index + 1] == next_ids[: group_index + 1]
        and old_ids[group_index + 1 + remove_count :] == next_ids[group_index + 1 :]
    )


def _row_identity(row: dict[str, Any]) -> tuple[str, str]:
    kind = str(row.get("kind") or "")
    if kind == "profile":
        return kind, str(row.get("key") or "")
    return kind, str(row.get("group") or "")


def _stable_row_identity(row: dict[str, Any]) -> tuple[str, str]:
    kind = str(row.get("kind") or "")
    if kind == "profile":
        return kind, str(row.get("persistent_key") or row.get("key") or "")
    return kind, str(row.get("group") or "")


def _profile_data_roles() -> list[int]:
    return [
        int(Qt.ItemDataRole.DisplayRole),
        ProfileListModel.ProfileKeyRole,
        ProfileListModel.PersistentKeyRole,
        ProfileListModel.DisplayNameRole,
        ProfileListModel.DescriptionRole,
        ProfileListModel.StrategyIdRole,
        ProfileListModel.StrategyNameRole,
        ProfileListModel.MatchLinesRole,
        ProfileListModel.ListTypeRole,
        ProfileListModel.RatingRole,
        ProfileListModel.FavoriteRole,
        ProfileListModel.InPresetRole,
        ProfileListModel.EnabledRole,
        ProfileListModel.GroupRole,
        ProfileListModel.GroupNameRole,
        ProfileListModel.CollapsedRole,
        ProfileListModel.CountRole,
        ProfileListModel.IconNameRole,
        ProfileListModel.IconColorRole,
        ProfileListModel.TooltipRole,
    ]


def _normalized_profile_types(profile_types: set[str] | None) -> set[str]:
    active = {str(value) for value in (profile_types or {"all"}) if str(value or "").strip()}
    if not active:
        active = {"all"}
    return active


def _normalized_search_query(query: str | None) -> str:
    return " ".join(str(query or "").strip().lower().split())


def _grouped_items(items: tuple[ProfileDisplayItem, ...]) -> dict[str, list[ProfileDisplayItem]]:
    grouped: dict[str, list[ProfileDisplayItem]] = {}
    for item in tuple(items or ()):
        group_key = str(item.group or "common")
        grouped.setdefault(group_key, []).append(item)
    return grouped


def _initial_group_expanded(items: tuple[ProfileDisplayItem, ...]) -> dict[str, bool]:
    result: dict[str, bool] = {}
    for item in tuple(items or ()):
        group_key = str(item.group or "common")
        result.setdefault(group_key, not bool(item.group_collapsed))
    return result


def _ordered_group_keys(grouped: dict[str, list[ProfileDisplayItem]]) -> list[str]:
    default_state = build_default_profile_folders()
    folders = default_state.get("folders", {})
    order_by_key = {
        str(key): _folder_order(folder.get("order"))
        for key, folder in folders.items()
        if isinstance(folder, dict)
    }
    return sorted(grouped, key=lambda key: (order_by_key.get(str(key), 10_000), str(key).lower()))


def _group_name_for_key(group_key: str, items: tuple[ProfileDisplayItem, ...]) -> str:
    key = str(group_key or "").strip() or "common"
    for item in tuple(items or ()):
        if str(item.group or "common") == key and str(item.group_name or "").strip():
            return str(item.group_name or "").strip()
    folder = build_default_profile_folders().get("folders", {}).get(key)
    if isinstance(folder, dict):
        return str(folder.get("name") or key)
    return key.title()


def _folder_order(value: object) -> int:
    try:
        return int(value)
    except Exception:
        return 10_000


def _match_summary(item: ProfileDisplayItem) -> str:
    parts = [
        part
        for part in (
            protocol_label_from_match_lines(tuple(item.match_lines or ())),
            ports_label_from_match_lines(tuple(item.match_lines or ())),
            item.list_type,
        )
        if part
    ]
    return " • ".join(parts) or "без явных условий"


def _profile_search_text(item: ProfileDisplayItem) -> str:
    match_lines = tuple(item.match_lines or ())
    parts = [
        item.display_name,
        item.group,
        item.group_name,
        item.strategy_id,
        item.strategy_name,
        item.list_type,
        _match_summary(item),
        " ".join(match_lines),
    ]
    return " ".join(str(part or "") for part in parts).lower()


__all__ = ["ProfileListModel"]
