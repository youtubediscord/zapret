from __future__ import annotations

import json
from typing import Any

from PyQt6.QtCore import QAbstractListModel, QEvent, QMimeData, QModelIndex, QPoint, QThread, QTimer, Qt, pyqtSignal
from PyQt6.QtWidgets import QListView, QVBoxLayout, QWidget

from log.log import log
from profile.icons import resolve_profile_icon
from profile.key_resolution import profile_order_row_identity, remap_profile_item_keys
from profile.match_filters import ports_label_from_match_lines, protocol_label_from_match_lines
from profile.order_view_state import build_profile_order_list_view_state, move_profile_order_items
from profile.ui.profile_list_delegate import ProfileListDelegate
from profile.ui.profile_list_model import ProfileListModel
from profile.ui.profile_list_view import ProfileListView
from ui.latest_value_worker_state import LatestValueWorkerState
from ui.one_shot_worker_runtime import OneShotWorkerRuntime
from ui.smooth_scroll import apply_page_smooth_scroll_preference
from ui.accessibility import set_control_accessibility, set_state_text
from ui.widgets.fluent_scrollbar import install_fluent_scrollbars


class ProfileOrderListViewStateWorker(QThread):
    loaded = pyqtSignal(int, object)
    failed = pyqtSignal(int, str)

    def __init__(
        self,
        request_id: int,
        *,
        items: tuple[Any, ...],
        preserve_order: bool = False,
        parent=None,
    ):
        super().__init__(parent)
        self._request_id = int(request_id)
        self._items = tuple(items or ())
        self._preserve_order = bool(preserve_order)

    def run(self) -> None:
        try:
            state = build_profile_order_list_view_state(
                self._items,
                preserve_order=self._preserve_order,
            )
        except Exception as exc:
            self.failed.emit(self._request_id, str(exc))
            return
        self.loaded.emit(self._request_id, state)


class ProfileOrderListModel(QAbstractListModel):
    MIME_TYPE = ProfileListModel.MIME_TYPE

    def __init__(self, parent=None):
        super().__init__(parent)
        self._items: tuple[Any, ...] = ()

    def set_profiles(self, items: tuple[Any, ...]) -> None:
        self.apply_view_state(build_profile_order_list_view_state(tuple(items or ())))

    def apply_view_state(self, state) -> None:
        next_items = tuple(getattr(state, "items", ()) or ())
        if self._items == next_items:
            return
        if tuple(_profile_order_identity(item) for item in self._items) == tuple(
            _profile_order_identity(item) for item in next_items
        ):
            changed_rows = tuple(
                row_index
                for row_index, (current_item, next_item) in enumerate(zip(self._items, next_items, strict=True))
                if current_item != next_item
            )
            self._items = next_items
            for row_index in changed_rows:
                model_index = self.index(row_index, 0)
                self.dataChanged.emit(model_index, model_index, _profile_order_data_roles())
            return
        if self._apply_single_row_move(next_items):
            return
        self.beginResetModel()
        self._items = next_items
        self.endResetModel()

    def view_state_options(self) -> dict[str, Any]:
        return {
            "items": tuple(self._items or ()),
        }

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

    def _apply_single_row_move(self, next_items: tuple[Any, ...]) -> bool:
        current_identity = [_profile_order_identity(item) for item in self._items]
        next_identity = [_profile_order_identity(item) for item in next_items]
        if len(current_identity) != len(next_identity) or len(current_identity) < 2:
            return False
        if sorted(current_identity) != sorted(next_identity):
            return False
        moved_from = -1
        moved_to = -1
        for source_index, identity in enumerate(current_identity):
            next_index = next_identity.index(identity)
            without_current = list(current_identity)
            item = without_current.pop(source_index)
            without_current.insert(next_index, item)
            if without_current == next_identity:
                moved_from = source_index
                moved_to = next_index
                break
        if moved_from < 0 or moved_to < 0 or moved_from == moved_to:
            return False
        destination_child = moved_to + 1 if moved_to > moved_from else moved_to
        self.beginMoveRows(QModelIndex(), moved_from, moved_from, QModelIndex(), destination_child)
        self._items = next_items
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
        if role == int(Qt.ItemDataRole.AccessibleTextRole):
            return _profile_order_accessible_text(
                item,
                row=index.row(),
                display_name=display_name,
                description=description,
            )
        return None


class ProfileOrderList(QWidget):
    profile_move_requested = pyqtSignal(str, str)
    profile_move_after_requested = pyqtSignal(str, str)
    profile_move_to_end_requested = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._view_state_runtime = OneShotWorkerRuntime()
        self._view_state_state = LatestValueWorkerState(self._view_state_runtime, empty_value=False)
        self._view_state_items: tuple[Any, ...] | None = None
        self._view_state_preserve_order = False
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self._model = ProfileOrderListModel(self)
        self._view = ProfileListView(self)
        order_list_description = (
            "Стрелки выбирают profile. PageUp и PageDown меняют порядок выбранного profile."
        )
        set_control_accessibility(self, name="Порядок profile", description=order_list_description)
        set_control_accessibility(self._view, name="Порядок profile", description=order_list_description)
        self._view.set_screen_reader_list_name("Порядок profile")
        self._view.setModel(self._model)
        set_state_text(self, "Порядок profile: список пока загружается")
        set_state_text(self._view, "Порядок profile: список пока загружается")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setFocusProxy(self._view)
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
        self._view.installEventFilter(self)
        install_fluent_scrollbars(self._view, vertical=True, horizontal=False, reserve_vertical_space=True)
        apply_page_smooth_scroll_preference(self._view)
        layout.addWidget(self._view, 1)

    def eventFilter(self, watched, event):  # noqa: N802
        if watched is self._view and event.type() == QEvent.Type.KeyPress:
            if self._handle_order_key_event(event):
                return True
        return super().eventFilter(watched, event)

    def keyPressEvent(self, event):  # noqa: N802
        if self._handle_order_wrapper_key_event(event):
            return
        super().keyPressEvent(event)

    def _handle_order_wrapper_key_event(self, event) -> bool:
        if event.key() in (Qt.Key.Key_PageUp, Qt.Key.Key_PageDown):
            self._view.setFocus(Qt.FocusReason.OtherFocusReason)
            return self._handle_order_key_event(event)

        if event.key() not in (
            Qt.Key.Key_Down,
            Qt.Key.Key_Up,
            Qt.Key.Key_Home,
            Qt.Key.Key_End,
        ):
            return False

        count = self._model.rowCount()
        if count <= 0:
            return False

        current = self._view.currentIndex()
        row = current.row() if current.isValid() else -1
        if row < 0:
            row = 0
        elif event.key() == Qt.Key.Key_Down:
            row = min(count - 1, row + 1)
        elif event.key() == Qt.Key.Key_Up:
            row = max(0, row - 1)
        elif event.key() == Qt.Key.Key_Home:
            row = 0
        elif event.key() == Qt.Key.Key_End:
            row = count - 1

        self._view.setFocus(Qt.FocusReason.OtherFocusReason)
        self._view.setCurrentIndex(self._model.index(row, 0))
        event.accept()
        return True

    def _handle_order_key_event(self, event) -> bool:
        if event.key() not in (Qt.Key.Key_PageUp, Qt.Key.Key_PageDown):
            return False
        index = self._view.currentIndex()
        if not index.isValid() or str(index.data(ProfileListModel.KindRole) or "") != "profile":
            return False
        source_key = str(index.data(ProfileListModel.ProfileKeyRole) or "")
        if not source_key:
            return False
        step = -1 if event.key() == Qt.Key.Key_PageUp else 1
        destination_row = index.row() + step
        if destination_row < 0 or destination_row >= self._model.rowCount():
            return False
        destination_index = self._model.index(destination_row, 0)
        if not destination_index.isValid():
            return False
        destination_key = str(destination_index.data(ProfileListModel.ProfileKeyRole) or "")
        if not destination_key:
            return False
        if step < 0:
            self.profile_move_requested.emit(source_key, destination_key)
        else:
            self.profile_move_after_requested.emit(source_key, destination_key)
        event.accept()
        return True

    def set_profiles(self, items: tuple[Any, ...]) -> None:
        self._request_view_state_rebuild(items=tuple(items or ()))

    def apply_view_state(self, view_state) -> None:
        self._model.apply_view_state(view_state)
        if self._model.rowCount() <= 0:
            set_state_text(self, "Порядок profile: список пуст")
            set_state_text(self._view, "Порядок profile: список пуст")
        elif not self._view.currentIndex().isValid():
            self._view.setCurrentIndex(self._model.index(0, 0))
        self._view_state_items = None

    def move_profile_item(self, source_profile_key: str, action: str, destination_profile_key: str = "") -> bool:
        next_items = move_profile_order_items(
            self._current_view_state_items(),
            source_profile_key,
            action,
            destination_profile_key,
        )
        if next_items is None:
            return False
        self._request_view_state_rebuild(items=next_items, preserve_order=True)
        return True

    def remap_profile_keys(self, key_map: dict[str, str]) -> bool:
        next_items = remap_profile_item_keys(self._current_view_state_items(), key_map)
        if next_items == self._current_view_state_items():
            return False
        self._request_view_state_rebuild(items=next_items, preserve_order=True)
        return True

    def _request_view_state_rebuild(
        self,
        *,
        items: tuple[Any, ...],
        preserve_order: bool = False,
    ) -> None:
        self._view_state_items = tuple(items or ())
        self._view_state_preserve_order = bool(preserve_order)
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
        preserve_order = bool(self.__dict__.get("_view_state_preserve_order", False))

        runtime.start_qthread_worker(
            worker_factory=lambda request_id: ProfileOrderListViewStateWorker(
                request_id,
                items=items,
                preserve_order=preserve_order,
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
        log(f"ProfileOrderList: не удалось подготовить порядок profile-ов: {error}", "ERROR")

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


def _profile_order_identity(item: Any) -> str:
    return profile_order_row_identity(item)


def _profile_order_accessible_text(
    item: Any,
    *,
    row: int,
    display_name: str,
    description: str,
) -> str:
    parts = [
        f"Позиция {int(row) + 1}",
        str(display_name or "Profile"),
        "включён" if bool(getattr(item, "enabled", False)) else "выключен",
    ]
    strategy_name = str(getattr(item, "strategy_name", "") or "").strip()
    if strategy_name:
        parts.append(f"стратегия: {strategy_name}")
    if description:
        parts.append(description)
    text = ", ".join(parts)
    return f"{text}. PageUp и PageDown меняют порядок profile." if text else ""


def _profile_order_data_roles() -> list[int]:
    return [
        int(Qt.ItemDataRole.DisplayRole),
        int(Qt.ItemDataRole.AccessibleTextRole),
        ProfileListModel.KindRole,
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


__all__ = ["ProfileOrderList", "ProfileOrderListModel", "ProfileOrderListViewStateWorker"]
