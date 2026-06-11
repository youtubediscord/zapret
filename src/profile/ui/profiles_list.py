from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace
from typing import Any

from PyQt6.QtCore import QPoint, QTimer, Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import QListView, QVBoxLayout, QWidget

from log.log import log
from profile.display_items import profile_display_sort_key
from profile.list_view_state import build_profile_list_view_state, group_name_for_key
from profile.ui.profile_list_delegate import ProfileListDelegate
from profile.ui.profile_list_model import ProfileListModel
from profile.ui.profile_list_view import ProfileListView
from profile.ui.widgets.profile_type_selector import ProfileTypeSelector
from ui.latest_value_worker_state import LatestValueWorkerState
from ui.one_shot_worker_runtime import OneShotWorkerRuntime
from ui.smooth_scroll import apply_page_smooth_scroll_preference, apply_smooth_scroll_mode
from ui.accessibility import set_control_accessibility, set_state_text
from ui.widgets.fluent_scrollbar import install_fluent_scrollbars


class ProfileListViewStateWorker(QThread):
    loaded = pyqtSignal(int, object)
    failed = pyqtSignal(int, str)

    def __init__(
        self,
        request_id: int,
        *,
        items: tuple[Any, ...],
        active_profile_types: set[str],
        search_query: str,
        group_expanded: dict[str, bool] | None,
        folder_state: dict[str, Any] | None = None,
        move_request: dict[str, str] | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self._request_id = int(request_id)
        self._items = tuple(items or ())
        self._active_profile_types = set(active_profile_types or {"all"})
        self._search_query = str(search_query or "")
        self._group_expanded = dict(group_expanded) if isinstance(group_expanded, dict) else None
        self._folder_state = dict(folder_state) if isinstance(folder_state, dict) else None
        self._move_request = dict(move_request or {}) if isinstance(move_request, dict) else None

    def run(self) -> None:
        try:
            items = self._items
            group_expanded = self._group_expanded
            if self._move_request:
                items = _moved_profile_items(
                    items,
                    str(self._move_request.get("source_profile_key") or ""),
                    str(self._move_request.get("destination_kind") or ""),
                    str(self._move_request.get("destination_profile_key") or ""),
                    str(self._move_request.get("destination_group_key") or ""),
                )
                if items is None:
                    raise ValueError("Не удалось подготовить локальное перемещение profile")
                group_expanded = _group_expanded_with_target(
                    group_expanded,
                    str(self._move_request.get("destination_group_key") or ""),
                    items,
                )
            state = build_profile_list_view_state(
                items,
                active_profile_types=self._active_profile_types,
                search_query=self._search_query,
                group_expanded=group_expanded,
                folder_state=self._folder_state,
            )
        except Exception as exc:
            self.failed.emit(self._request_id, str(exc))
            return
        self.loaded.emit(self._request_id, state)


class ProfilesList(QWidget):
    profile_selected = pyqtSignal(str)
    profile_context_requested = pyqtSignal(str, QPoint)
    profile_move_requested = pyqtSignal(str, str, str)
    profile_move_after_requested = pyqtSignal(str, str, str)
    profile_move_to_folder_requested = pyqtSignal(str, str)
    profile_move_to_end_requested = pyqtSignal(str)
    folder_context_requested = pyqtSignal(str, QPoint)
    folder_toggled = pyqtSignal(str, bool)
    folders_toggled = pyqtSignal(object, bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._active_profile_types: set[str] = {"all"}
        self._search_query = ""
        self._view_state_runtime = OneShotWorkerRuntime()
        self._view_state_state = LatestValueWorkerState(self._view_state_runtime, empty_value=False)
        self._view_state_group_expanded: dict[str, bool] | None = None
        self._view_state_folder_state: dict[str, Any] | None = None
        self._view_state_items: tuple[Any, ...] | None = None
        self._view_state_move_request: dict[str, str] | None = None
        self._view_state_reset_group_expanded = False
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self._profile_type_selector = ProfileTypeSelector(self)
        self._profile_type_selector.profile_types_changed.connect(self._apply_profile_type_filter)
        layout.addWidget(self._profile_type_selector)

        self._model = ProfileListModel(self)
        self._view = ProfileListView(self)
        profile_list_description = (
            "Выберите profile стрелками вверх и вниз. Enter открывает выбранный profile, "
            "клавиша меню открывает действия."
        )
        set_control_accessibility(self, name="Список профилей", description=profile_list_description)
        set_state_text(self, "Список профилей: список пока загружается")
        set_control_accessibility(self._view, name="Список профилей", description=profile_list_description)
        self._view.set_screen_reader_list_name("Список профилей")
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
        self._delegate.action_triggered.connect(self._on_delegate_action)
        self._view.setItemDelegate(self._delegate)
        self._view.clicked.connect(self._on_view_clicked)
        self._view.profile_activated.connect(self.profile_selected)
        self._view.profile_context_requested.connect(self.profile_context_requested)
        self._view.folder_context_requested.connect(self.folder_context_requested)
        self._view.folder_toggle_requested.connect(
            lambda group_key: self._on_delegate_action("toggle_folder", group_key)
        )
        self._view.profile_move_requested.connect(self.profile_move_requested)
        self._view.profile_move_after_requested.connect(self.profile_move_after_requested)
        self._view.profile_move_to_folder_requested.connect(self.profile_move_to_folder_requested)
        self._view.profile_move_to_end_requested.connect(self.profile_move_to_end_requested)
        # Страница обычно показывает все profile-ы, поэтому вертикальная прокрутка
        # почти всегда есть. Запас справа включается только при реальном scroll range,
        # чтобы карточки не заходили под fluent-scrollbar.
        self._scrollbars = install_fluent_scrollbars(
            self._view,
            vertical=True,
            horizontal=False,
            reserve_vertical_space=True,
        )
        apply_page_smooth_scroll_preference(self._view)
        layout.addWidget(self._view, 1)

    def set_smooth_scroll_enabled(self, enabled: bool) -> None:
        apply_smooth_scroll_mode(self._view, enabled)

    def build_profiles(self, items: tuple[Any, ...]) -> None:
        self._request_view_state_rebuild(
            items=tuple(items or ()),
            reset_group_expanded=True,
        )

    def apply_view_state(self, view_state) -> None:
        self._active_profile_types = set(getattr(view_state, "active_profile_types", None) or {"all"})
        self._search_query = str(getattr(view_state, "search_query", "") or "")
        self._view_state_group_expanded = dict(getattr(view_state, "group_expanded", None) or {})
        try:
            self._profile_type_selector.set_active_profile_types(self._active_profile_types)
        except Exception:
            pass
        self._model.apply_view_state(view_state)
        self._view_state_items = None

    def view_state_options(self) -> dict[str, Any]:
        options = self._model.view_state_options()
        options["active_profile_types"] = set(self._active_profile_types or {"all"})
        options["search_query"] = str(self._search_query or "")
        return options

    def update_profiles(self, items: tuple[Any, ...]) -> bool:
        self._request_view_state_rebuild(items=tuple(items or ()))
        return True

    def clear(self) -> None:
        self._model.set_profiles(())

    def expand_all(self) -> None:
        self._request_all_groups_expanded(True)

    def collapse_all(self) -> None:
        self._request_all_groups_expanded(False)

    def profile_item_for_key(self, profile_key: str):
        return self._model.profile_item_for_key(profile_key)

    def replace_profile_item(self, profile_key: str, item) -> bool:
        source_key = str(profile_key or "").strip()
        replacement_key = str(getattr(item, "key", "") or source_key).strip()
        if not source_key or not replacement_key:
            return False
        items = self._current_view_state_items()
        if not any(str(getattr(entry, "key", "") or "") == source_key for entry in items):
            return False
        next_items = tuple(
            item if str(getattr(entry, "key", "") or "") == source_key else entry
            for entry in items
        )
        self._request_view_state_rebuild(items=next_items)
        return True

    def add_profile_item(self, item) -> bool:
        profile_key = str(getattr(item, "key", "") or "").strip()
        if not profile_key:
            return False
        items = self._current_view_state_items()
        if any(str(getattr(entry, "key", "") or "") == profile_key for entry in items):
            return self.replace_profile_item(profile_key, item)
        self._request_view_state_rebuild(items=tuple((*items, item)))
        return True

    def replace_user_profile_items(self, profile_id: str, items: tuple[Any, ...]) -> bool:
        clean_profile_id = str(profile_id or "").strip()
        replacement_items = tuple(items or ())
        if not clean_profile_id or not replacement_items:
            return False
        current_items = self._current_view_state_items()
        if not any(
            str(getattr(item, "user_profile_id", "") or "").strip() == clean_profile_id
            for item in current_items
        ):
            return False
        next_items = tuple(
            item
            for item in current_items
            if str(getattr(item, "user_profile_id", "") or "").strip() != clean_profile_id
        )
        self._request_view_state_rebuild(items=tuple((*next_items, *replacement_items)))
        return True

    def remove_user_profile_items(self, profile_id: str) -> bool:
        clean_profile_id = str(profile_id or "").strip()
        if not clean_profile_id:
            return False
        current_items = self._current_view_state_items()
        next_items = tuple(
            item
            for item in current_items
            if str(getattr(item, "user_profile_id", "") or "").strip() != clean_profile_id
        )
        if len(next_items) == len(current_items):
            return False
        self._request_view_state_rebuild(items=next_items)
        return True

    def remove_profile_item(self, profile_key: str) -> bool:
        key = str(profile_key or "").strip()
        if not key:
            return False
        items = self._current_view_state_items()
        next_items = tuple(item for item in items if str(getattr(item, "key", "") or "") != key)
        if len(next_items) == len(items):
            return False
        self._request_view_state_rebuild(items=next_items)
        return True

    def set_profile_enabled(self, profile_key: str, enabled: bool) -> bool:
        item = self.profile_item_for_key(profile_key)
        if item is None:
            return False
        return self.replace_profile_item(profile_key, replace(item, enabled=bool(enabled)))

    def duplicate_profile_item(self, source_profile_key: str, duplicate_profile_key: str) -> bool:
        source = self.profile_item_for_key(source_profile_key)
        duplicate_key = str(duplicate_profile_key or "").strip()
        if source is None or not duplicate_key:
            return False
        duplicate = replace(
            source,
            key=duplicate_key,
            profile_index=int(getattr(source, "profile_index", -1) or -1) + 1,
            order=int(getattr(source, "order", 0) or 0) + 1,
        )
        return self.add_profile_item(duplicate)

    def move_profile_item(
        self,
        source_profile_key: str,
        destination_kind: str,
        destination_profile_key: str = "",
        destination_group_key: str = "",
    ) -> bool:
        source_key = str(source_profile_key or "").strip()
        kind = str(destination_kind or "").strip()
        destination_key = str(destination_profile_key or "").strip()
        group_key = str(destination_group_key or "").strip()
        if not self._can_queue_profile_move(source_key, kind, destination_key, group_key):
            return False
        self._request_view_state_rebuild(
            move_request={
                "source_profile_key": source_key,
                "destination_kind": kind,
                "destination_profile_key": destination_key,
                "destination_group_key": group_key,
            },
        )
        return True

    def apply_profile_folder_state(self, folder_state: dict[str, Any]) -> bool:
        if not isinstance(folder_state, dict):
            return False
        self._request_view_state_rebuild(
            folder_state=folder_state,
            reset_group_expanded=True,
        )
        return True

    def set_search_query(self, query: str) -> None:
        value = str(query or "")
        if self._search_query == value:
            return
        self._search_query = value
        self._request_view_state_rebuild()

    def _on_view_clicked(self, index) -> None:
        if not index.isValid():
            return
        if str(index.data(ProfileListModel.KindRole) or "") != "profile":
            return
        profile_key = str(index.data(ProfileListModel.ProfileKeyRole) or "")
        if profile_key:
            self.profile_selected.emit(profile_key)

    def _on_delegate_action(self, action: str, value: str) -> None:
        if action != "toggle_folder":
            return
        group_key = str(value or "")
        if not group_key:
            return
        next_expanded = not self._model.is_group_expanded(group_key)
        group_expanded = self._current_group_expanded()
        group_expanded[group_key] = next_expanded
        self._request_view_state_rebuild(group_expanded=group_expanded)
        self.folder_toggled.emit(group_key, next_expanded)

    def _apply_profile_type_filter(self, active_profile_types: set[str]) -> None:
        active = set(active_profile_types or {"all"})
        if self._active_profile_types == active:
            return
        self._active_profile_types = active
        self._request_view_state_rebuild()

    def _request_all_groups_expanded(self, expanded: bool) -> None:
        group_expanded = self._current_group_expanded()
        expanded_value = bool(expanded)
        changed_keys = tuple(
            group_key
            for group_key, current in group_expanded.items()
            if bool(current) != expanded_value
        )
        if not changed_keys:
            return
        for group_key in changed_keys:
            group_expanded[group_key] = expanded_value
        self._request_view_state_rebuild(group_expanded=group_expanded)
        self.folders_toggled.emit(
            {group_key: expanded_value for group_key in changed_keys},
            expanded_value,
        )

    def _current_group_expanded(self) -> dict[str, bool]:
        pending = self.__dict__.get("_view_state_group_expanded")
        if isinstance(pending, dict):
            return {
                str(group_key): bool(expanded)
                for group_key, expanded in pending.items()
                if str(group_key)
            }
        try:
            options = self._model.view_state_options()
        except Exception:
            options = {}
        return {
            str(group_key): bool(expanded)
            for group_key, expanded in dict(options.get("group_expanded") or {}).items()
            if str(group_key)
        }

    def _request_view_state_rebuild(
        self,
        *,
        group_expanded: dict[str, bool] | None = None,
        folder_state: dict[str, Any] | None = None,
        items: tuple[Any, ...] | None = None,
        move_request: dict[str, str] | None = None,
        reset_group_expanded: bool = False,
    ) -> None:
        if group_expanded is not None:
            self._view_state_group_expanded = dict(group_expanded)
        if isinstance(folder_state, dict):
            self._view_state_folder_state = dict(folder_state)
        if items is not None:
            self._view_state_items = tuple(items or ())
        if isinstance(move_request, dict):
            self._view_state_move_request = dict(move_request)
        if reset_group_expanded:
            self._view_state_group_expanded = None
            self._view_state_reset_group_expanded = True
        runtime = self.__dict__.get("_view_state_runtime")
        if runtime is None:
            runtime = OneShotWorkerRuntime()
            self._view_state_runtime = runtime
        state = self._view_state_state_obj()
        if state.is_busy():
            state.pending = True
            return
        self._start_view_state_worker()

    def _start_view_state_worker(self) -> None:
        runtime = self.__dict__.get("_view_state_runtime")
        if runtime is None:
            runtime = OneShotWorkerRuntime()
            self._view_state_runtime = runtime
        options = self._model.view_state_options()
        items = tuple(self.__dict__.get("_view_state_items") or options.get("items") or ())
        if bool(self.__dict__.pop("_view_state_reset_group_expanded", False)):
            group_expanded = None
        else:
            group_expanded = dict(
                self.__dict__.get("_view_state_group_expanded")
                or options.get("group_expanded")
                or {}
            )
        folder_state = self.__dict__.pop("_view_state_folder_state", None)
        move_request = self.__dict__.pop("_view_state_move_request", None)
        active_profile_types = set(self._active_profile_types or {"all"})
        search_query = str(self._search_query or "")

        runtime.start_qthread_worker(
            worker_factory=lambda request_id: ProfileListViewStateWorker(
                request_id,
                items=items,
                active_profile_types=active_profile_types,
                search_query=search_query,
                group_expanded=group_expanded,
                folder_state=folder_state,
                move_request=move_request,
                parent=self,
            ),
            on_loaded=self._on_view_state_loaded,
            on_failed=self._on_view_state_failed,
            on_finished=self._on_view_state_worker_finished,
        )

    def _view_state_state_obj(self) -> LatestValueWorkerState:
        state = self.__dict__.get("_view_state_state")
        runtime = self.__dict__.get("_view_state_runtime")
        if state is None:
            if runtime is None:
                runtime = OneShotWorkerRuntime()
                self._view_state_runtime = runtime
            pending = bool(self.__dict__.pop("_view_state_rebuild_pending", False))
            state = LatestValueWorkerState(runtime, empty_value=False, pending=pending)
            self.__dict__["_view_state_state"] = state
        return state

    def _current_view_state_items(self) -> tuple[Any, ...]:
        pending = self.__dict__.get("_view_state_items")
        if isinstance(pending, tuple):
            return pending
        try:
            options = self._model.view_state_options()
        except Exception:
            options = {}
        return tuple(options.get("items") or ())

    def _can_queue_profile_move(
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
        items = self._current_view_state_items()
        if not any(str(getattr(item, "key", "") or "") == source_key for item in items):
            return False

        destination_key = str(destination_profile_key or "").strip()
        if kind in {"profile", "profile_after"}:
            return bool(
                destination_key
                and destination_key != source_key
                and any(str(getattr(item, "key", "") or "") == destination_key for item in items)
            )
        if kind == "folder":
            return bool(str(destination_group_key or "").strip())
        if kind == "end":
            return True
        return False

    def _on_view_state_loaded(self, request_id: int, state) -> None:
        runtime = self.__dict__.get("_view_state_runtime")
        if runtime is None or not runtime.is_current(request_id):
            return
        if self._view_state_state_obj().has_pending():
            return
        self.apply_view_state(state)

    def _on_view_state_failed(self, request_id: int, error: str) -> None:
        runtime = self.__dict__.get("_view_state_runtime")
        if runtime is None or not runtime.is_current(request_id):
            return
        log(f"ProfilesList: не удалось подготовить фильтр profile-списка: {error}", "ERROR")

    def _on_view_state_worker_finished(self, worker) -> None:
        state = self._view_state_state_obj()
        state.schedule_pending_after_finish(
            worker,
            is_current_worker_finish=self._is_current_view_state_worker_finish,
            single_shot=QTimer.singleShot,
            run_scheduled=self._run_scheduled_view_state_worker_start,
        )

    def _is_current_view_state_worker_finish(self, runtime, worker) -> bool:
        try:
            return int(getattr(worker, "_request_id", -1)) == int(getattr(runtime, "request_id", -2))
        except (TypeError, ValueError):
            return False

    def _run_scheduled_view_state_worker_start(self) -> None:
        state = self._view_state_state_obj()
        pending = state.take_pending_for_scheduled_start()
        if not pending:
            return
        runtime = self.__dict__.get("_view_state_runtime")
        if runtime is not None and runtime.is_running():
            state.pending = True
            return
        self._start_view_state_worker()

    def _group_keys(self) -> tuple[str, ...]:
        keys: list[str] = []
        for row in range(self._model.rowCount()):
            index = self._model.index(row, 0)
            if str(index.data(ProfileListModel.KindRole) or "") != "folder":
                continue
            key = str(index.data(ProfileListModel.GroupRole) or "")
            if key:
                keys.append(key)
        return tuple(dict.fromkeys(keys))


def _profile_item_with(item: Any, **changes):
    try:
        return replace(item, **changes)
    except Exception:
        data = dict(getattr(item, "__dict__", {}) or {})
        data.update(changes)
        return SimpleNamespace(**data)


def _moved_profile_items(
    items: tuple[Any, ...],
    source_profile_key: str,
    destination_kind: str,
    destination_profile_key: str = "",
    destination_group_key: str = "",
) -> tuple[Any, ...] | None:
    source_key = str(source_profile_key or "").strip()
    kind = str(destination_kind or "").strip()
    if not source_key:
        return None
    items = tuple(items or ())
    source = next((item for item in items if str(getattr(item, "key", "") or "") == source_key), None)
    if source is None:
        return None

    destination_key = str(destination_profile_key or "").strip()
    destination = next((item for item in items if str(getattr(item, "key", "") or "") == destination_key), None)
    if kind in {"profile", "profile_after"}:
        if destination is None or str(getattr(destination, "key", "") or "") == source_key:
            return None
        target_group = str(
            destination_group_key
            or getattr(destination, "group", "")
            or getattr(source, "group", "")
            or "common"
        )
    elif kind == "folder":
        target_group = str(destination_group_key or "").strip()
    elif kind == "end":
        target_group = str(destination_group_key or getattr(source, "group", "") or "common").strip()
    else:
        return None
    if not target_group:
        return None

    group_name = group_name_for_key(target_group, items)
    source_for_target = _profile_item_with(
        source,
        group=target_group,
        group_name=group_name,
        order_is_manual=True,
    )
    target_items = [
        item
        for item in sorted(items, key=profile_display_sort_key)
        if str(getattr(item, "key", "") or "") != source_key
        and str(getattr(item, "group", "") or "common") == target_group
    ]

    if kind == "profile":
        insert_index = next(
            (
                index
                for index, item in enumerate(target_items)
                if str(getattr(item, "key", "") or "") == destination_key
            ),
            -1,
        )
        if insert_index < 0:
            return None
        target_items.insert(insert_index, source_for_target)
    elif kind == "profile_after":
        insert_index = next(
            (
                index
                for index, item in enumerate(target_items)
                if str(getattr(item, "key", "") or "") == destination_key
            ),
            -1,
        )
        if insert_index < 0:
            return None
        target_items.insert(insert_index + 1, source_for_target)
    else:
        target_items.append(source_for_target)

    target_order = {str(getattr(item, "key", "") or ""): index for index, item in enumerate(target_items)}
    next_items: list[Any] = []
    for item in items:
        item_key = str(getattr(item, "key", "") or "")
        if item_key == source_key and item_key not in target_order:
            continue
        if item_key in target_order:
            next_items.append(
                _profile_item_with(
                    source_for_target if item_key == source_key else item,
                    group=target_group,
                    group_name=group_name,
                    order=target_order[item_key],
                    order_is_manual=True,
                )
            )
        else:
            next_items.append(item)
    return tuple(next_items)


def _group_expanded_with_target(
    group_expanded: dict[str, bool] | None,
    destination_group_key: str,
    items: tuple[Any, ...],
) -> dict[str, bool]:
    next_group_expanded = dict(group_expanded or {})
    target_group = str(destination_group_key or "").strip()
    if target_group:
        next_group_expanded.setdefault(target_group, True)
    for item in tuple(items or ()):
        next_group_expanded.setdefault(str(getattr(item, "group", "") or "common"), True)
    return next_group_expanded


__all__ = ["ProfilesList"]
