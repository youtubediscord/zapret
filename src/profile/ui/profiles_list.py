from __future__ import annotations

from dataclasses import replace
from typing import Any

from PyQt6.QtCore import QPoint, QTimer, Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import QListView, QVBoxLayout, QWidget

from log.log import log
from profile.list_view_state import build_profile_list_view_state
from profile.ui.profile_list_delegate import ProfileListDelegate
from profile.ui.profile_list_model import ProfileListModel
from profile.ui.profile_list_view import ProfileListView
from profile.ui.widgets.profile_type_selector import ProfileTypeSelector
from ui.one_shot_worker_runtime import OneShotWorkerRuntime
from ui.smooth_scroll import apply_page_smooth_scroll_preference, apply_smooth_scroll_mode
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
        group_expanded: dict[str, bool],
        parent=None,
    ):
        super().__init__(parent)
        self._request_id = int(request_id)
        self._items = tuple(items or ())
        self._active_profile_types = set(active_profile_types or {"all"})
        self._search_query = str(search_query or "")
        self._group_expanded = dict(group_expanded or {})

    def run(self) -> None:
        try:
            state = build_profile_list_view_state(
                self._items,
                active_profile_types=self._active_profile_types,
                search_query=self._search_query,
                group_expanded=self._group_expanded,
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

    def __init__(self, parent=None):
        super().__init__(parent)
        self._active_profile_types: set[str] = {"all"}
        self._search_query = ""
        self._view_state_runtime = OneShotWorkerRuntime()
        self._view_state_runtime_worker = None
        self._view_state_rebuild_pending = False
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
        self._model.set_profiles(
            tuple(items or ()),
            active_profile_types=self._active_profile_types,
            search_query=self._search_query,
        )

    def apply_view_state(self, view_state) -> None:
        self._active_profile_types = set(getattr(view_state, "active_profile_types", None) or {"all"})
        self._search_query = str(getattr(view_state, "search_query", "") or "")
        try:
            self._profile_type_selector.set_active_profile_types(self._active_profile_types)
        except Exception:
            pass
        self._model.apply_view_state(view_state)

    def view_state_options(self) -> dict[str, Any]:
        options = self._model.view_state_options()
        options["active_profile_types"] = set(self._active_profile_types or {"all"})
        options["search_query"] = str(self._search_query or "")
        return options

    def update_profiles(self, items: tuple[Any, ...]) -> bool:
        return self._model.update_profiles(
            tuple(items or ()),
            active_profile_types=self._active_profile_types,
            search_query=self._search_query,
        )

    def clear(self) -> None:
        self._model.set_profiles(())

    def expand_all(self) -> None:
        for group_key in self._model.set_all_groups_expanded(True):
            self.folder_toggled.emit(group_key, True)

    def collapse_all(self) -> None:
        for group_key in self._model.set_all_groups_expanded(False):
            self.folder_toggled.emit(group_key, False)

    def profile_item_for_key(self, profile_key: str):
        return self._model.profile_item_for_key(profile_key)

    def replace_profile_item(self, profile_key: str, item) -> bool:
        return self._model.replace_profile(profile_key, item)

    def add_profile_item(self, item) -> bool:
        return self._model.add_profile(item)

    def replace_user_profile_items(self, profile_id: str, items: tuple[Any, ...]) -> bool:
        return self._model.replace_user_profile_items(profile_id, tuple(items or ()))

    def remove_user_profile_items(self, profile_id: str) -> bool:
        return self._model.remove_user_profile_items(profile_id)

    def remove_profile_item(self, profile_key: str) -> bool:
        return self._model.remove_profile(profile_key)

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
        return self._model.move_profile(
            source_profile_key,
            destination_kind,
            destination_profile_key,
            destination_group_key,
        )

    def apply_profile_folder_state(self, folder_state: dict[str, Any]) -> bool:
        return self._model.apply_folder_state(folder_state)

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
        self._model.set_group_expanded(group_key, next_expanded)
        self.folder_toggled.emit(group_key, next_expanded)

    def _apply_profile_type_filter(self, active_profile_types: set[str]) -> None:
        active = set(active_profile_types or {"all"})
        if self._active_profile_types == active:
            return
        self._active_profile_types = active
        self._request_view_state_rebuild()

    def _request_view_state_rebuild(self) -> None:
        runtime = self.__dict__.get("_view_state_runtime")
        if runtime is None:
            runtime = OneShotWorkerRuntime()
            self._view_state_runtime = runtime
        if runtime.is_running():
            self._view_state_rebuild_pending = True
            return
        self._start_view_state_worker()

    def _start_view_state_worker(self) -> None:
        runtime = self.__dict__.get("_view_state_runtime")
        if runtime is None:
            runtime = OneShotWorkerRuntime()
            self._view_state_runtime = runtime
        options = self._model.view_state_options()
        items = tuple(options.get("items") or ())
        group_expanded = dict(options.get("group_expanded") or {})
        active_profile_types = set(self._active_profile_types or {"all"})
        search_query = str(self._search_query or "")

        _request_id, worker = runtime.start_qthread_worker(
            worker_factory=lambda request_id: ProfileListViewStateWorker(
                request_id,
                items=items,
                active_profile_types=active_profile_types,
                search_query=search_query,
                group_expanded=group_expanded,
                parent=self,
            ),
            on_loaded=self._on_view_state_loaded,
            on_failed=self._on_view_state_failed,
            on_finished=self._on_view_state_worker_finished,
        )
        self._view_state_runtime_worker = worker

    def _on_view_state_loaded(self, request_id: int, state) -> None:
        runtime = self.__dict__.get("_view_state_runtime")
        if runtime is None or not runtime.is_current(request_id):
            return
        if self.__dict__.get("_view_state_rebuild_pending", False):
            return
        self.apply_view_state(state)

    def _on_view_state_failed(self, request_id: int, error: str) -> None:
        runtime = self.__dict__.get("_view_state_runtime")
        if runtime is None or not runtime.is_current(request_id):
            return
        log(f"ProfilesList: не удалось подготовить фильтр profile-списка: {error}", "ERROR")

    def _on_view_state_worker_finished(self, worker) -> None:
        if worker is not self.__dict__.get("_view_state_runtime_worker"):
            return
        self._view_state_runtime_worker = None
        if not self.__dict__.get("_view_state_rebuild_pending", False):
            return
        self._view_state_rebuild_pending = False
        try:
            QTimer.singleShot(0, self._start_view_state_worker)
        except Exception:
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


__all__ = ["ProfilesList"]
