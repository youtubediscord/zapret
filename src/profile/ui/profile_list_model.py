from __future__ import annotations

import json
from typing import Any

from PyQt6.QtCore import QAbstractListModel, QMimeData, QModelIndex, Qt

from profile.display_items import ProfileDisplayItem, build_profile_display_items
from profile.list_view_state import (
    ProfileListViewState,
    apply_profile_folder_state_to_items as _apply_profile_folder_state_to_items,
    build_profile_list_view_state,
    build_profile_rows_from as _build_profile_rows_from,
    initial_group_expanded as _initial_group_expanded,
    moved_profile_display_items as _moved_profile_display_items,
    normalized_profile_types as _normalized_profile_types,
    normalized_search_query as _normalized_search_query,
)


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
        self._profile_row_by_key: dict[str, int] = {}
        self._group_expanded: dict[str, bool] = {}
        self._active_profile_types: set[str] = {"all"}
        self._search_query = ""
        self._show_only_added = False

    def set_profiles(
        self,
        items: tuple[Any, ...],
        *,
        active_profile_types: set[str] | None = None,
        search_query: str | None = None,
    ) -> None:
        state = build_profile_list_view_state(
            tuple(items or ()),
            active_profile_types=self._active_profile_types if active_profile_types is None else active_profile_types,
            search_query=self._search_query if search_query is None else search_query,
            show_only_added=self._show_only_added,
        )
        if (
            self._all_items == state.all_items
            and self._group_expanded == state.group_expanded
            and self._active_profile_types == state.active_profile_types
            and self._search_query == state.search_query
            and self._show_only_added == state.show_only_added
        ):
            return
        self.apply_view_state(state)

    def apply_view_state(self, state: ProfileListViewState) -> None:
        next_all_items = tuple(state.all_items or ())
        next_profile_items = dict(state.profile_items or {})
        next_group_expanded = dict(state.group_expanded or {})
        next_active_profile_types = set(state.active_profile_types or {"all"})
        next_search_query = str(state.search_query or "")
        next_show_only_added = bool(getattr(state, "show_only_added", False))
        next_rows = list(state.rows or [])
        if (
            self._all_items == next_all_items
            and self._profile_items == next_profile_items
            and self._group_expanded == next_group_expanded
            and self._active_profile_types == next_active_profile_types
            and self._search_query == next_search_query
            and self._show_only_added == next_show_only_added
            and self._rows == next_rows
        ):
            return

        def commit() -> None:
            self._all_items = next_all_items
            self._profile_items = next_profile_items
            self._group_expanded = next_group_expanded
            self._active_profile_types = next_active_profile_types
            self._search_query = next_search_query
            self._show_only_added = next_show_only_added

        # Структурные точечные обновления допустимы только при неизменных
        # фильтрах: смена поиска/типов должна вести себя как новый список
        # (reset), а не как случайный insert/remove с сохранённой прокруткой.
        filters_unchanged = (
            self._active_profile_types == next_active_profile_types
            and self._search_query == next_search_query
            and self._show_only_added == next_show_only_added
        )
        self._apply_rows_or_reset(next_rows, commit=commit, allow_structural=filters_unchanged)

    def _apply_rows_or_reset(
        self,
        next_rows: list[dict[str, Any]],
        *,
        commit,
        allow_structural: bool = True,
    ) -> None:
        if self._apply_rows_update(next_rows, commit=commit, allow_structural=allow_structural):
            return
        self.beginResetModel()
        commit()
        self._set_rows(next_rows)
        self.endResetModel()

    def _apply_rows_update(
        self,
        next_rows: list[dict[str, Any]],
        *,
        commit,
        allow_structural: bool = True,
    ) -> bool:
        """Применяет next_rows точечными сигналами вместо полного reset,
        чтобы QListView сохранял позицию прокрутки и текущую строку.

        Покрывает типовые правки списка: изменение данных строк
        (dataChanged), смену идентичности строк на месте (правка имени или
        match-строк меняет persistent_key, но количество и позиции строк те
        же), появление или исчезновение непрерывного блока строк
        (insert/remove: удаление, дублирование, сворачивание папки) и перенос
        одной строки (move). Возвращает False, если изменение не сводится к
        одному из этих случаев — тогда вызывающий делает reset.
        """
        old_ids = [_stable_row_identity(row) for row in self._rows]
        next_ids = [_stable_row_identity(row) for row in next_rows]
        # Полное совпадение identity — data-only обновление, допустимо при
        # любых фильтрах. Смена identity «на месте» — структурная правка
        # (переименование/правка match-строк): при смене фильтров
        # (allow_structural=False) она обязана вести к reset, иначе «новый
        # список» со случайно совпавшей формой унаследует прокрутку старого.
        if old_ids == next_ids or (allow_structural and _is_in_place_identity_change(old_ids, next_ids)):
            changed_rows = tuple(index for index, row in enumerate(next_rows) if self._rows[index] != row)
            commit()
            self._set_rows(next_rows)
            self._emit_data_changed_for_rows(changed_rows)
            return True
        if not allow_structural:
            return False

        changed_rows = _changed_existing_row_indexes(self._rows, next_rows, identity_fn=_stable_row_identity)

        inserted_span = _contiguous_inserted_row_span(old_ids, next_ids)
        if inserted_span is not None:
            first, last = inserted_span
            self.beginInsertRows(QModelIndex(), first, last)
            commit()
            self._set_rows(next_rows)
            self.endInsertRows()
            self._emit_data_changed_for_rows(changed_rows)
            return True

        removed_span = _contiguous_removed_row_span(old_ids, next_ids)
        if removed_span is not None:
            first, last = removed_span
            self.beginRemoveRows(QModelIndex(), first, last)
            commit()
            self._set_rows(next_rows)
            self.endRemoveRows()
            self._emit_data_changed_for_rows(changed_rows)
            return True

        move = _single_row_move(self._rows, next_rows, identity_fn=_stable_row_identity)
        if move is not None:
            source_row, insert_row = move
            destination_child = _move_destination_child(source_row, insert_row)
            if destination_child not in {source_row, source_row + 1}:
                self.beginMoveRows(QModelIndex(), source_row, source_row, QModelIndex(), destination_child)
                commit()
                self._set_rows(next_rows)
                self.endMoveRows()
                self._emit_data_changed_for_rows(changed_rows)
                return True
        return False

    def view_state_options(self) -> dict[str, Any]:
        return {
            "items": tuple(self._all_items or ()),
            "active_profile_types": set(self._active_profile_types or {"all"}),
            "search_query": str(self._search_query or ""),
            "show_only_added": bool(self._show_only_added),
            "group_expanded": dict(self._group_expanded or {}),
        }

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
        next_rows = self._build_rows_from(
            display_items,
            next_group_expanded,
            active_profile_types=active,
            search_query=normalized_search,
        )
        next_profile_items = {item.key: item for item in display_items}
        filters_unchanged = self._active_profile_types == active and self._search_query == normalized_search

        def commit() -> None:
            self._all_items = display_items
            self._profile_items = next_profile_items
            self._group_expanded = next_group_expanded
            self._active_profile_types = active
            self._search_query = normalized_search

        self._apply_rows_or_reset(next_rows, commit=commit, allow_structural=filters_unchanged)
        return True

    def set_active_profile_types(self, profile_types: set[str]) -> None:
        active = _normalized_profile_types(profile_types)
        if self._active_profile_types == active:
            return
        next_rows = self._build_rows_from(self._all_items, self._group_expanded, active_profile_types=active)

        def commit() -> None:
            self._active_profile_types = active

        self._apply_rows_or_reset(next_rows, commit=commit, allow_structural=False)

    def set_search_query(self, query: str) -> None:
        normalized = _normalized_search_query(query)
        if self._search_query == normalized:
            return
        next_rows = self._build_rows_from(self._all_items, self._group_expanded, search_query=normalized)

        def commit() -> None:
            self._search_query = normalized

        self._apply_rows_or_reset(next_rows, commit=commit, allow_structural=False)

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

        def commit() -> None:
            self._group_expanded = next_group_expanded

        # Сворачивание/разворачивание одной группы — это непрерывный блок
        # строк сразу за её заголовком, поэтому общий детектор insert/remove
        # покрывает этот случай без специальной проверки индекса группы.
        self._apply_rows_or_reset(next_rows, commit=commit)

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
        if current == replacement:
            return True

        next_items = tuple(replacement if existing.key == source_key else existing for existing in self._all_items)
        next_group_expanded = dict(self._group_expanded)
        next_group_expanded.setdefault(str(replacement.group or "common"), True)
        next_rows = self._build_rows_from(next_items, next_group_expanded)

        def commit() -> None:
            self._all_items = next_items
            self._profile_items = {entry.key: entry for entry in next_items}
            self._group_expanded = next_group_expanded

        self._apply_rows_or_reset(next_rows, commit=commit)
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
        next_group_expanded = dict(self._group_expanded)
        next_group_expanded.setdefault(str(profile.group or "common"), True)
        next_rows = self._build_rows_from(next_items, next_group_expanded)

        def commit() -> None:
            self._all_items = next_items
            self._profile_items = {entry.key: entry for entry in next_items}
            self._group_expanded = next_group_expanded

        self._apply_rows_or_reset(next_rows, commit=commit)
        return True

    def remove_profile(self, profile_key: str) -> bool:
        key = str(profile_key or "").strip()
        if not key or key not in self._profile_items:
            return False
        next_items = tuple(item for item in self._all_items if item.key != key)
        next_rows = self._build_rows_from(next_items, self._group_expanded)

        def commit() -> None:
            self._all_items = next_items
            self._profile_items = {entry.key: entry for entry in next_items}

        self._apply_rows_or_reset(next_rows, commit=commit)
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

        # Единственная реализация move-семантики — общий планировщик
        # (plan_view_move); модель только применяет его результат.
        next_items = _moved_profile_display_items(
            self._all_items,
            source_key,
            kind,
            str(destination_profile_key or "").strip(),
            str(destination_group_key or "").strip(),
            folder_state=self.__dict__.get("_folder_state"),
        )
        if next_items is None:
            return False

        next_items_tuple = tuple(next_items)
        moved_source = next((item for item in next_items_tuple if item.key == source_key), None)
        target_group = str(getattr(moved_source, "group", "") or "common")
        next_group_expanded = dict(self._group_expanded)
        next_group_expanded.setdefault(target_group, True)
        next_rows = self._build_rows_from(next_items_tuple, next_group_expanded)

        def commit() -> None:
            self._all_items = next_items_tuple
            self._profile_items = {item.key: item for item in next_items_tuple}
            self._group_expanded = next_group_expanded

        self._apply_rows_or_reset(next_rows, commit=commit)
        return True

    def apply_folder_state(self, folder_state: dict[str, Any]) -> bool:
        if not isinstance(folder_state, dict):
            return False
        self.__dict__["_folder_state"] = dict(folder_state)
        if not self._all_items:
            return False

        next_items_tuple = _apply_profile_folder_state_to_items(self._all_items, folder_state)
        next_group_expanded = _initial_group_expanded(next_items_tuple)
        next_rows = self._build_rows_from(next_items_tuple, next_group_expanded)

        def commit() -> None:
            self._all_items = next_items_tuple
            self._profile_items = {item.key: item for item in next_items_tuple}
            self._group_expanded = next_group_expanded

        self._apply_rows_or_reset(next_rows, commit=commit)
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
        if role == int(Qt.ItemDataRole.AccessibleTextRole):
            return _profile_accessible_text(row)
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
        *,
        active_profile_types: set[str] | None = None,
        search_query: str | None = None,
    ) -> list[dict[str, Any]]:
        return _build_profile_rows_from(
            items,
            group_expanded,
            active_profile_types=self._active_profile_types if active_profile_types is None else active_profile_types,
            search_query=self._search_query if search_query is None else search_query,
            show_only_added=self._show_only_added,
        )

    def _set_rows(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows
        self._rebuild_visible_profile_row_index()

    def _rebuild_visible_profile_row_index(self) -> None:
        self._profile_row_by_key = {
            str(row.get("key") or ""): index
            for index, row in enumerate(self._rows)
            if str(row.get("kind") or "") == "profile" and str(row.get("key") or "")
        }

    def _emit_data_changed_for_rows(self, rows: tuple[int, ...]) -> None:
        for row_index in rows:
            if row_index < 0 or row_index >= len(self._rows):
                continue
            model_index = self.index(row_index, 0)
            self.dataChanged.emit(model_index, model_index, _profile_data_roles())

    def _row_index_for_profile_key(self, profile_key: str) -> int:
        key = str(profile_key or "").strip()
        return int(self._profile_row_by_key.get(key, -1))

    def stable_row_identity_at(self, row_index: int) -> tuple[str, str] | None:
        """Стабильная идентичность строки для scroll-anchor или None."""
        if 0 <= int(row_index) < len(self._rows):
            return _stable_row_identity(self._rows[int(row_index)])
        return None

    def row_for_stable_identity(self, identity: tuple[str, str] | None) -> int:
        """Индекс строки с данной стабильной идентичностью или -1."""
        if identity is None:
            return -1
        for index, row in enumerate(self._rows):
            if _stable_row_identity(row) == identity:
                return index
        return -1


def _is_in_place_identity_change(
    old_ids: list[tuple[str, str]],
    next_ids: list[tuple[str, str]],
) -> bool:
    """True, если строки изменили идентичность «на месте»: длина та же,
    kind в каждой позиции совпадает, но набор идентичностей стал другим
    (правка имени/match-строк меняет persistent_key профиля). Такое изменение
    не структурное — достаточно dataChanged, reset не нужен. Перестановка
    прежних идентичностей сюда не попадает — её решает move-детектор."""
    if len(old_ids) != len(next_ids):
        return False
    if set(old_ids) == set(next_ids):
        return False
    return all(old_id[0] == next_id[0] for old_id, next_id in zip(old_ids, next_ids))


def _contiguous_inserted_row_span(
    old_ids: list[tuple[str, str]],
    next_ids: list[tuple[str, str]],
) -> tuple[int, int] | None:
    """Диапазон (first, last) вставленного непрерывного блока строк или None.

    Идентичности строк уникальны, поэтому достаточно сверить общий префикс
    и потребовать, чтобы остаток нового списка совпал со старым хвостом.
    """
    inserted = len(next_ids) - len(old_ids)
    if inserted <= 0:
        return None
    start = 0
    while start < len(old_ids) and old_ids[start] == next_ids[start]:
        start += 1
    if next_ids[start + inserted :] == old_ids[start:]:
        return start, start + inserted - 1
    return None


def _contiguous_removed_row_span(
    old_ids: list[tuple[str, str]],
    next_ids: list[tuple[str, str]],
) -> tuple[int, int] | None:
    """Диапазон (first, last) удалённого непрерывного блока строк или None."""
    return _contiguous_inserted_row_span(next_ids, old_ids)


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
        int(Qt.ItemDataRole.AccessibleTextRole),
    ]


def _profile_accessible_text(row: dict[str, Any]) -> str:
    kind = str(row.get("kind") or "")
    if kind == "profile":
        name = str(row.get("display_name") or "").strip()
        parts = [name]
        parts.append("включён" if bool(row.get("enabled", False)) else "выключен")
        parts.append("есть в preset" if bool(row.get("in_preset", False)) else "нет в preset")
        strategy_name = str(row.get("strategy_name") or "").strip()
        if strategy_name:
            parts.append(f"стратегия: {strategy_name}")
        if bool(row.get("favorite", False)):
            parts.append("в избранном")
        rating = str(row.get("rating") or "").strip()
        if rating == "work":
            parts.append("работает")
        elif rating == "notwork":
            parts.append("не работает")
        text = ", ".join(part for part in parts if part)
        return f"{text}. Нажмите Enter или Пробел, чтобы открыть profile." if text else ""

    group_name = str(row.get("group_name") or row.get("display_name") or "").strip()
    if group_name:
        count = _safe_int(row.get("count"))
        expanded_text = "свернута" if bool(row.get("collapsed", False)) else "развернута"
        return (
            f"Группа {group_name}, {_profile_count_text(count)}, {expanded_text}. "
            "Нажмите Enter или Пробел, чтобы свернуть или развернуть группу."
        )
    return str(row.get("display_name") or "").strip()


def _profile_count_text(count: int) -> str:
    if count % 10 == 1 and count % 100 != 11:
        return f"{count} профиль"
    if count % 10 in {2, 3, 4} and count % 100 not in {12, 13, 14}:
        return f"{count} профиля"
    return f"{count} профилей"


def _safe_int(value: object) -> int:
    try:
        return int(value or 0)
    except Exception:
        return 0


__all__ = ["ProfileListModel", "ProfileListViewState", "build_profile_list_view_state"]
