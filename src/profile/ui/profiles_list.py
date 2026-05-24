from __future__ import annotations

from typing import Any

from PyQt6.QtCore import QPoint, Qt, pyqtSignal
from PyQt6.QtWidgets import QListView, QVBoxLayout, QWidget

from profile.ui.profile_list_delegate import ProfileListDelegate
from profile.ui.profile_list_model import ProfileListModel
from profile.ui.profile_list_view import ProfileListView
from profile.ui.widgets.profile_type_selector import ProfileTypeSelector
from ui.smooth_scroll import apply_page_smooth_scroll_preference, apply_smooth_scroll_mode
from ui.widgets.fluent_scrollbar import install_fluent_scrollbars


class ProfilesList(QWidget):
    profile_selected = pyqtSignal(str)
    profile_context_requested = pyqtSignal(str, QPoint)
    profile_move_requested = pyqtSignal(str, str)
    profile_move_to_end_requested = pyqtSignal(str)
    folder_context_requested = pyqtSignal(str, QPoint)
    folder_toggled = pyqtSignal(str, bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._active_profile_types: set[str] = {"all"}
        self._search_query = ""
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
        self._model.set_profiles(tuple(items or ()))
        self._model.set_active_profile_types(self._active_profile_types)
        self._model.set_search_query(self._search_query)

    def clear(self) -> None:
        self._model.set_profiles(())

    def expand_all(self) -> None:
        self._model.set_all_groups_expanded(True)
        for group_key in self._group_keys():
            self.folder_toggled.emit(group_key, True)

    def collapse_all(self) -> None:
        self._model.set_all_groups_expanded(False)
        for group_key in self._group_keys():
            self.folder_toggled.emit(group_key, False)

    def profile_item_for_key(self, profile_key: str):
        return self._model.profile_item_for_key(profile_key)

    def set_search_query(self, query: str) -> None:
        self._search_query = str(query or "")
        self._model.set_search_query(self._search_query)

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
        self._active_profile_types = set(active_profile_types or {"all"})
        self._model.set_active_profile_types(self._active_profile_types)

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
