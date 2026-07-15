from __future__ import annotations

from dataclasses import replace
from typing import Any

from PyQt6.QtCore import QPoint, QTimer, Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import QListView, QVBoxLayout, QWidget

from log.log import log
from profile.list_view_state import build_profile_list_view_state, moved_profile_display_items
from profile.ui.profile_list_delegate import ProfileListDelegate
from profile.ui.profile_list_filter_state import ProfileListFilterState
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
        show_only_added: bool,
        group_expanded: dict[str, bool] | None,
        folder_state: dict[str, Any] | None = None,
        move_request: dict[str, str] | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self._request_id = int(request_id)
        self._items = tuple(items or ())
        # Снимок фильтров на момент запроса: воркер не читает живой канон.
        self._filters = ProfileListFilterState(
            search_query=str(search_query or ""),
            show_only_added=bool(show_only_added),
            active_profile_types=set(active_profile_types or {"all"}),
        )
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
                active_profile_types=self._filters.active_profile_types,
                search_query=self._filters.search_query,
                show_only_added=self._filters.show_only_added,
                group_expanded=group_expanded,
                folder_state=self._folder_state,
            )
        except Exception as exc:
            self.failed.emit(self._request_id, str(exc))
            return
        self.loaded.emit(self._request_id, state)


def _instance_attr(obj, name: str, default=None):
    """getattr, устойчивый к QWidget.__new__ без __init__ (duck-typed стабы
    в тестах): PyQt кидает RuntimeError вместо AttributeError для
    отсутствующих атрибутов неинициализированного QObject."""
    try:
        return getattr(obj, name, default)
    except RuntimeError:
        return default


class _PendingViewStateMutation:
    """Накопитель точечных правок view-state между запросом и стартом воркера.

    Единственное место, где живут pending-значения items / group_expanded /
    folder_state / move_request: виджет не держит теневых копий состояния
    модели, а pending items читаются только через `_current_view_state_items`.
    """

    __slots__ = ("items", "group_expanded", "folder_state", "move_request", "reset_group_expanded")

    def __init__(self) -> None:
        self.items: tuple[Any, ...] | None = None
        self.group_expanded: dict[str, bool] | None = None
        self.folder_state: dict[str, Any] | None = None
        self.move_request: dict[str, str] | None = None
        self.reset_group_expanded = False

    def take_reset_group_expanded(self) -> bool:
        value = bool(self.reset_group_expanded)
        self.reset_group_expanded = False
        return value

    def take_folder_state(self) -> dict[str, Any] | None:
        value = self.folder_state
        self.folder_state = None
        return value

    def take_move_request(self) -> dict[str, str] | None:
        value = self.move_request
        self.move_request = None
        return value


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

    def __init__(self, parent=None, *, filter_state: ProfileListFilterState | None = None):
        super().__init__(parent)
        # Канон фильтров (намерение пользователя): общий объект со страницей;
        # standalone-виджет создаёт собственный.
        self._filters = filter_state if filter_state is not None else ProfileListFilterState()
        self._view_state_runtime = OneShotWorkerRuntime()
        self._view_state_state = LatestValueWorkerState(self._view_state_runtime, empty_value=False)
        self._pending_view_state = _PendingViewStateMutation()
        # Scroll-anchor: reset «того же списка» (правка профиля, fallback-пути)
        # восстанавливает позицию прокрутки; реальная смена списка
        # (build_profiles / смена preset / смена фильтров) — начинает сверху.
        self._scroll_to_top_on_reset = False
        self._scroll_anchor: tuple[tuple[str, str], int] | None = None
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
            "Выберите profile стрелками вверх и вниз. Enter или Пробел открывает выбранный profile, "
            "клавиша меню открывает действия."
        )
        set_control_accessibility(self, name="Список профилей", description=profile_list_description)
        set_state_text(self, "Список профилей: список пока загружается")
        set_control_accessibility(self._view, name="Список профилей", description=profile_list_description)
        self._view.set_screen_reader_list_name("Список профилей")
        self._view.setModel(self._model)
        # Точечные правки списка модель применяет insert/remove/move-сигналами,
        # и QListView сам сохраняет позицию прокрутки. Полный reset «того же
        # списка» восстанавливает позицию по scroll-anchor (identity верхней
        # видимой строки + пиксельное смещение); реальная смена списка
        # (другой preset, фильтры) — начинает сверху.
        self._model.modelAboutToBeReset.connect(self._on_model_about_to_be_reset)
        self._model.modelReset.connect(self._on_model_reset)
        set_state_text(self._view, "Список профилей: список пока загружается")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setFocusProxy(self._view)
        self._view.setSelectionMode(QListView.SelectionMode.NoSelection)
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

    def keyPressEvent(self, event):  # noqa: N802
        if self._handle_profile_list_keyboard_event(event):
            return
        super().keyPressEvent(event)

    def _handle_profile_list_keyboard_event(self, event) -> bool:
        key = event.key()
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space, Qt.Key.Key_Menu) or (
            key == Qt.Key.Key_F10 and event.modifiers() & Qt.KeyboardModifier.ShiftModifier
        ):
            self._view.setFocus(Qt.FocusReason.OtherFocusReason)
            self._view.keyPressEvent(event)
            return bool(event.isAccepted())

        if key not in (
            Qt.Key.Key_Down,
            Qt.Key.Key_Up,
            Qt.Key.Key_Home,
            Qt.Key.Key_End,
            Qt.Key.Key_PageDown,
            Qt.Key.Key_PageUp,
        ):
            return False

        count = self._model.rowCount()
        if count <= 0:
            return False

        current = self._view.currentIndex()
        row = current.row() if current.isValid() else -1
        if row < 0:
            row = 0
        elif key == Qt.Key.Key_Down:
            row = min(count - 1, row + 1)
        elif key == Qt.Key.Key_Up:
            row = max(0, row - 1)
        elif key == Qt.Key.Key_Home:
            row = 0
        elif key == Qt.Key.Key_End:
            row = count - 1
        elif key == Qt.Key.Key_PageDown:
            row = min(count - 1, row + 10)
        elif key == Qt.Key.Key_PageUp:
            row = max(0, row - 10)

        self._view.setFocus(Qt.FocusReason.OtherFocusReason)
        self._view.setCurrentIndex(self._model.index(row, 0))
        event.accept()
        return True

    def set_smooth_scroll_enabled(self, enabled: bool) -> None:
        apply_smooth_scroll_mode(self._view, enabled)

    def _filter_state(self) -> ProfileListFilterState:
        """Канон фильтров; лениво создаётся для duck-typed стабов из тестов."""
        filters = _instance_attr(self, "_filters")
        if filters is None:
            filters = ProfileListFilterState()
            self._filters = filters
        return filters

    @property
    def _search_query(self) -> str:
        """Тонкий test-facing доступ к канону фильтров."""
        return str(self._filter_state().search_query or "")

    @_search_query.setter
    def _search_query(self, value: str) -> None:
        self._filter_state().search_query = str(value or "")

    @property
    def _show_only_added(self) -> bool:
        """Тонкий test-facing доступ к канону фильтров."""
        return bool(self._filter_state().show_only_added)

    @_show_only_added.setter
    def _show_only_added(self, value: bool) -> None:
        self._filter_state().show_only_added = bool(value)

    @property
    def _active_profile_types(self) -> set[str]:
        """Тонкий test-facing доступ к канону фильтров."""
        return set(self._filter_state().active_profile_types or {"all"})

    @_active_profile_types.setter
    def _active_profile_types(self, value: set[str]) -> None:
        self._filter_state().active_profile_types = set(value or {"all"})

    def _pending_view_state_mutation(self) -> _PendingViewStateMutation:
        """Pending-мутации view-state; лениво создаётся для стабов из тестов."""
        pending = _instance_attr(self, "_pending_view_state")
        if pending is None:
            pending = _PendingViewStateMutation()
            self._pending_view_state = pending
        return pending

    def _view_state_runtime_obj(self) -> OneShotWorkerRuntime:
        runtime = _instance_attr(self, "_view_state_runtime")
        if runtime is None:
            runtime = OneShotWorkerRuntime()
            self._view_state_runtime = runtime
        return runtime

    def build_profiles(self, items: tuple[Any, ...]) -> None:
        # Новый список целиком (смена preset): якорь прежнего списка не
        # применяется, после reset начинаем сверху.
        self._scroll_to_top_on_reset = True
        self._request_view_state_rebuild(
            items=tuple(items or ()),
            reset_group_expanded=True,
        )

    def apply_view_state(self, view_state) -> None:
        scroll_to_top = (
            _instance_attr(self, "_scroll_to_top_on_reset", False)
            or not self._view_state_filters_match(view_state)
        )
        # Канон синхронизируется с применённым снимком: view_state «выигрывает»
        # у намерения на момент применения, страница затем возвращает свежий
        # запрос/фильтр, если они успели разойтись (см. _apply_payload).
        filters = self._filter_state()
        filters.active_profile_types = set(getattr(view_state, "active_profile_types", None) or {"all"})
        filters.search_query = str(getattr(view_state, "search_query", "") or "")
        filters.show_only_added = bool(getattr(view_state, "show_only_added", False))
        pending = self._pending_view_state_mutation()
        pending.group_expanded = dict(getattr(view_state, "group_expanded", None) or {})
        try:
            self._profile_type_selector.set_active_profile_types(set(filters.active_profile_types))
        except Exception:
            pass
        self._scroll_to_top_on_reset = scroll_to_top
        try:
            self._model.apply_view_state(view_state)
        finally:
            self._scroll_to_top_on_reset = False
        if self._model.rowCount() <= 0:
            state_text = self._empty_profile_list_state_text()
            set_state_text(self, state_text)
            set_state_text(self._view, state_text)
        elif not self._view.currentIndex().isValid():
            self._set_current_index_without_scroll(self._model.index(0, 0))
        pending.items = None

    def _set_current_index_without_scroll(self, index) -> None:
        # setCurrentIndex с включённым autoScroll прокручивает список к
        # элементу; после точечного удаления текущей строки или reset модели
        # это перекидывало бы список наверх.
        auto_scroll = self._view.hasAutoScroll()
        self._view.setAutoScroll(False)
        try:
            self._view.setCurrentIndex(index)
        finally:
            self._view.setAutoScroll(auto_scroll)

    def _view_state_filters_match(self, view_state) -> bool:
        """Совпадают ли фильтры нового состояния с текущими фильтрами модели.

        Смена поиска/типов/«только добавленные» — это «новый список»: якорь
        прокрутки не применяется, после reset начинаем сверху."""
        try:
            options = self._model.view_state_options()
        except Exception:
            return True
        return (
            set(options.get("active_profile_types") or {"all"})
            == set(getattr(view_state, "active_profile_types", None) or {"all"})
            and str(options.get("search_query") or "") == str(getattr(view_state, "search_query", "") or "")
            and bool(options.get("show_only_added")) == bool(getattr(view_state, "show_only_added", False))
        )

    def _applied_view_filters_differ(self) -> bool:
        """Расходится ли применённый снимок фильтров модели с каноном.

        Применённое состояние отстаёт от намерения, пока view-state готовится
        в воркере или пришёл из устаревшего payload — тогда повторный запрос
        с тем же намерением всё равно нужен."""
        try:
            options = self._model.view_state_options()
        except Exception:
            return False
        filters = self._filter_state()
        return (
            set(options.get("active_profile_types") or {"all"})
            != set(filters.active_profile_types or {"all"})
            or str(options.get("search_query") or "") != str(filters.search_query or "")
            or bool(options.get("show_only_added")) != bool(filters.show_only_added)
        )

    def _on_model_about_to_be_reset(self) -> None:
        self._scroll_anchor = None
        if _instance_attr(self, "_scroll_to_top_on_reset", False):
            return
        self._scroll_anchor = self._capture_scroll_anchor()

    def _on_model_reset(self) -> None:
        anchor = self._scroll_anchor
        self._scroll_anchor = None
        if anchor is not None and self._restore_scroll_anchor(*anchor):
            return
        self._view.scrollToTop()

    def _capture_scroll_anchor(self) -> tuple[tuple[str, str], int] | None:
        """Якорь прокрутки: identity верхней видимой строки + её пиксельное
        смещение относительно верха viewport (обычно ≤ 0)."""
        if self._view.verticalScrollBar().value() <= 0:
            return None
        index = self._view.indexAt(QPoint(0, 0))
        if not index.isValid():
            return None
        identity = self._model.stable_row_identity_at(index.row())
        if identity is None:
            return None
        return identity, int(self._view.visualRect(index).top())

    def _restore_scroll_anchor(self, identity: tuple[str, str], offset: int) -> bool:
        """Возвращает якорную строку на прежнее место после reset «того же
        списка». Если строка исчезла — False, вызывающий уходит наверх."""
        row = self._model.row_for_stable_identity(identity)
        if row < 0:
            return False
        self._view.scrollTo(self._model.index(row, 0), QListView.ScrollHint.PositionAtTop)
        scrollbar = self._view.verticalScrollBar()
        scrollbar.setValue(max(0, scrollbar.value() - int(offset)))
        return True

    def _empty_profile_list_state_text(self) -> str:
        filters = self._filter_state()
        if str(filters.search_query or "").strip():
            return "Список профилей: по фильтру ничего не найдено"
        if bool(filters.show_only_added):
            return "Список профилей: добавленных профилей не найдено"
        active_profile_types = set(filters.active_profile_types or {"all"})
        if active_profile_types and "all" not in active_profile_types:
            return "Список профилей: по выбранным типам ничего не найдено"
        return "Список профилей: список пуст"

    def view_state_options(self) -> dict[str, Any]:
        options = self._model.view_state_options()
        filters = self._filter_state()
        options["active_profile_types"] = set(filters.active_profile_types or {"all"})
        options["search_query"] = str(filters.search_query or "")
        options["show_only_added"] = bool(filters.show_only_added)
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

    def _display_key_for(self, profile_key: str) -> str:
        """Переводит стабильную ссылку (persistent_key) в текущий позиционный
        ключ элемента. Прямое совпадение проходит как раньше; неоднозначная
        ссылка возвращается как есть — вызывающий уйдёт в полный refresh."""
        key = str(profile_key or "").strip()
        if not key:
            return ""
        items = self._current_view_state_items()
        if any(str(getattr(entry, "key", "") or "") == key for entry in items):
            return key
        matches = [
            str(getattr(entry, "key", "") or "")
            for entry in items
            if str(getattr(entry, "persistent_key", "") or "") == key
        ]
        return matches[0] if len(matches) == 1 else key

    def profile_item_for_key(self, profile_key: str):
        return self._model.profile_item_for_key(self._display_key_for(profile_key))

    def replace_profile_item(self, profile_key: str, item) -> bool:
        source_key = self._display_key_for(profile_key)
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
        replaced_positions = tuple(
            position
            for position, item in enumerate(current_items)
            if str(getattr(item, "user_profile_id", "") or "").strip() == clean_profile_id
        )
        if not replaced_positions:
            return False
        if len(replaced_positions) == len(replacement_items):
            # Замена на месте: элементы остаются на прежних позициях,
            # прокрутка и порядок списка не страдают.
            items_list = list(current_items)
            for position, replacement in zip(replaced_positions, replacement_items):
                items_list[position] = replacement
            self._request_view_state_rebuild(items=tuple(items_list))
            return True
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
        key = self._display_key_for(profile_key)
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
        filters = self._filter_state()
        if filters.search_query == value and not self._filter_rebuild_needed():
            return
        filters.search_query = value
        self._request_view_state_rebuild()

    def set_show_only_added(self, enabled: bool) -> None:
        value = bool(enabled)
        filters = self._filter_state()
        if filters.show_only_added == value and not self._filter_rebuild_needed():
            return
        filters.show_only_added = value
        self._request_view_state_rebuild()

    def _filter_rebuild_needed(self) -> bool:
        """Нужен ли повторный запрос view-state при неизменном каноне фильтров.

        Канон — общий объект со страницей, и страница пишет в него ДО вызова
        виджета, поэтому «значение совпало» не означает «применено». Rebuild
        нужен, когда применённый снимок модели отстаёт от канона ИЛИ когда
        воркер ещё занят: его in-flight результат снят с устаревших фильтров,
        и без pending он затёр бы свежее намерение (см. _on_view_state_loaded)."""
        return self._applied_view_filters_differ() or self._view_state_state_obj().is_busy()

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
        filters = self._filter_state()
        if set(filters.active_profile_types or {"all"}) == active and not self._applied_view_filters_differ():
            return
        filters.active_profile_types = active
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
        pending = self._pending_view_state_mutation().group_expanded
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
        pending = self._pending_view_state_mutation()
        if group_expanded is not None:
            pending.group_expanded = dict(group_expanded)
        if isinstance(folder_state, dict):
            pending.folder_state = dict(folder_state)
        if items is not None:
            pending.items = tuple(items or ())
        if isinstance(move_request, dict):
            pending.move_request = dict(move_request)
        if reset_group_expanded:
            pending.group_expanded = None
            pending.reset_group_expanded = True
        state = self._view_state_state_obj()
        if state.is_busy():
            state.pending = True
            return
        self._start_view_state_worker()

    def _start_view_state_worker(self) -> None:
        runtime = self._view_state_runtime_obj()
        options = self._model.view_state_options()
        pending = self._pending_view_state_mutation()
        items = tuple(pending.items or options.get("items") or ())
        if pending.take_reset_group_expanded():
            group_expanded = None
        else:
            group_expanded = dict(pending.group_expanded or options.get("group_expanded") or {})
        folder_state = pending.take_folder_state()
        move_request = pending.take_move_request()
        filters = self._filter_state()
        active_profile_types = set(filters.active_profile_types or {"all"})
        search_query = str(filters.search_query or "")
        show_only_added = bool(filters.show_only_added)

        runtime.start_qthread_worker(
            worker_factory=lambda request_id: ProfileListViewStateWorker(
                request_id,
                items=items,
                active_profile_types=active_profile_types,
                search_query=search_query,
                show_only_added=show_only_added,
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
        state = _instance_attr(self, "_view_state_state")
        if state is None:
            state = LatestValueWorkerState(self._view_state_runtime_obj(), empty_value=False)
            self._view_state_state = state
        return state

    def _current_view_state_items(self) -> tuple[Any, ...]:
        """Единственная точка чтения items: pending-мутация, иначе модель."""
        pending = self._pending_view_state_mutation().items
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
        runtime = _instance_attr(self, "_view_state_runtime")
        if runtime is None or not runtime.is_current(request_id):
            return
        if self._view_state_state_obj().has_pending():
            return
        self.apply_view_state(state)

    def _on_view_state_failed(self, request_id: int, error: str) -> None:
        runtime = _instance_attr(self, "_view_state_runtime")
        if runtime is None or not runtime.is_current(request_id):
            return
        # Флаг «после reset — наверх» взводится в build_profiles и штатно
        # снимается в finally apply_view_state; при падении воркера apply не
        # случится, и без сброса все последующие reset «того же списка»
        # прыгали бы наверх.
        self._scroll_to_top_on_reset = False
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
        runtime = _instance_attr(self, "_view_state_runtime")
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


def _moved_profile_items(
    items: tuple[Any, ...],
    source_profile_key: str,
    destination_kind: str,
    destination_profile_key: str = "",
    destination_group_key: str = "",
) -> tuple[Any, ...] | None:
    # Делегирование единственной реализации оптимистичного перемещения
    # (list_view_state.moved_profile_display_items) — та же математика,
    # что и у персиста.
    return moved_profile_display_items(
        items,
        source_profile_key,
        destination_kind,
        destination_profile_key,
        destination_group_key,
    )


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
