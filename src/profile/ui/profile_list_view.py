from __future__ import annotations

import json

from PyQt6.QtCore import QPoint, Qt, pyqtSignal
from PyQt6.QtGui import QDrag
from PyQt6.QtWidgets import QApplication
from qfluentwidgets import ListView

from .profile_list_model import ProfileListModel
from ui.accessibility import set_state_text


PROFILE_DROP_MARKER_PROPERTY = "profileDropMarker"
SCREEN_READER_LIST_NAME_PROPERTY = "screenReaderListName"


def set_current_index_if_changed(view, index) -> bool:
    try:
        if view.currentIndex() == index:
            return False
    except Exception:
        pass
    view.setCurrentIndex(index)
    return True


def profile_drop_marker_for_target(row: int, destination_kind: str) -> dict[str, object]:
    kind = str(destination_kind or "").strip()
    try:
        row_index = int(row)
    except Exception:
        row_index = -1
    if row_index < 0:
        return {"row": -1, "mode": ""}
    if kind == "folder":
        return {"row": row_index, "mode": "folder"}
    if kind == "profile":
        return {"row": row_index, "mode": "before"}
    if kind == "profile_after":
        return {"row": row_index, "mode": "after"}
    return {"row": -1, "mode": ""}


def profile_drop_target_for_position(
    row: int,
    destination_kind: str,
    *,
    y: int,
    row_top: int,
    row_height: int,
) -> dict[str, object]:
    kind = str(destination_kind or "").strip()
    try:
        row_index = int(row)
    except Exception:
        row_index = -1
    if row_index < 0:
        return {"marker": {"row": -1, "mode": ""}, "destination_kind": "end", "destination_row": -1}
    if kind == "folder":
        return {"marker": {"row": row_index, "mode": "folder"}, "destination_kind": "folder", "destination_row": row_index}
    if kind == "profile":
        try:
            lower_half = int(y) >= int(row_top) + max(1, int(row_height)) / 2
        except Exception:
            lower_half = False
        if lower_half:
            return {"marker": {"row": row_index, "mode": "after"}, "destination_kind": "profile_after", "destination_row": row_index}
        return {"marker": {"row": row_index, "mode": "before"}, "destination_kind": "profile", "destination_row": row_index}
    return {"marker": {"row": -1, "mode": ""}, "destination_kind": "end", "destination_row": -1}


def profile_canonical_drop_target_for_next_row(
    target: dict[str, object],
    *,
    next_row: int,
    next_kind: str,
) -> dict[str, object]:
    if str((target or {}).get("destination_kind") or "") != "profile_after":
        return dict(target or {})
    if str(next_kind or "").strip() != "profile":
        return dict(target or {})
    try:
        row_index = int(next_row)
    except Exception:
        row_index = -1
    if row_index < 0:
        return dict(target or {})
    return {"marker": {"row": row_index, "mode": "before"}, "destination_kind": "profile", "destination_row": row_index}


class ProfileListView(ListView):
    profile_activated = pyqtSignal(str)
    profile_context_requested = pyqtSignal(str, QPoint)
    folder_context_requested = pyqtSignal(str, QPoint)
    folder_toggle_requested = pyqtSignal(str)
    profile_move_requested = pyqtSignal(str, str, str)
    profile_move_after_requested = pyqtSignal(str, str, str)
    profile_move_to_folder_requested = pyqtSignal(str, str)
    profile_move_to_end_requested = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._drag_start_pos: QPoint | None = None
        self.set_drop_marker(-1, "")

    def set_screen_reader_list_name(self, name: str) -> None:
        value = " ".join(str(name or "").strip().split())
        if value:
            self.setProperty(SCREEN_READER_LIST_NAME_PROPERTY, value)
        self._update_current_row_accessibility(self.currentIndex())

    def currentChanged(self, current, previous):  # noqa: N802
        super().currentChanged(current, previous)
        self._update_current_row_accessibility(current)

    def _update_current_row_accessibility(self, index) -> None:
        list_name = str(self.property(SCREEN_READER_LIST_NAME_PROPERTY) or "").strip()
        if not list_name:
            list_name = str(self.accessibleName() or "").strip()
        row_text = ""
        try:
            if index is not None and index.isValid():
                row_text = str(index.data(Qt.ItemDataRole.AccessibleTextRole) or "").strip()
        except Exception:
            row_text = ""
        if list_name and row_text:
            set_state_text(self, f"{list_name}: {row_text}")
        elif list_name:
            set_state_text(self, list_name)

    def set_drop_marker(self, row: int, destination_kind: str) -> None:
        marker = profile_drop_marker_for_target(row, destination_kind)
        self.set_drop_marker_payload(marker)

    def set_drop_marker_payload(self, marker: dict[str, object]) -> None:
        previous_marker = self.property(PROFILE_DROP_MARKER_PROPERTY)
        if previous_marker == marker:
            return
        self.setProperty(PROFILE_DROP_MARKER_PROPERTY, marker)
        self._update_drop_marker_rows(previous_marker, marker)

    def _update_drop_marker_rows(self, previous_marker, next_marker) -> None:
        model = self.model()
        if model is None:
            return
        updated_rows: set[int] = set()
        for marker in (previous_marker, next_marker):
            if not isinstance(marker, dict):
                continue
            try:
                row = int(marker.get("row", -1) or -1)
            except Exception:
                continue
            if row < 0 or row >= model.rowCount():
                continue
            if row in updated_rows:
                continue
            updated_rows.add(row)
            index = model.index(row, 0)
            if not index.isValid():
                continue
            rect = self.visualRect(index).adjusted(0, -4, 0, 4)
            if rect.isValid():
                self.viewport().update(rect)

    def _drop_target_at(self, point: QPoint) -> tuple[dict[str, object], str, str]:
        drop_index = self.indexAt(point)
        if not drop_index.isValid():
            return {"marker": {"row": -1, "mode": ""}, "destination_kind": "end", "destination_row": -1}, "", ""
        destination_kind = str(drop_index.data(ProfileListModel.KindRole) or "")
        rect = self.visualRect(drop_index)
        target = profile_drop_target_for_position(
            drop_index.row(),
            destination_kind,
            y=point.y(),
            row_top=rect.top(),
            row_height=rect.height(),
        )
        if target["destination_kind"] == "profile_after":
            model = self.model()
            next_row = drop_index.row() + 1
            next_index = model.index(next_row, 0) if model is not None and next_row < model.rowCount() else None
            if next_index is not None and next_index.isValid():
                target = profile_canonical_drop_target_for_next_row(
                    target,
                    next_row=next_row,
                    next_kind=str(next_index.data(ProfileListModel.KindRole) or ""),
                )
                drop_index = next_index if target["destination_kind"] == "profile" else drop_index
        if target["destination_kind"] in {"profile", "profile_after"}:
            return (
                target,
                str(drop_index.data(ProfileListModel.ProfileKeyRole) or ""),
                str(drop_index.data(ProfileListModel.GroupRole) or ""),
            )
        if target["destination_kind"] == "folder":
            group_key = str(drop_index.data(ProfileListModel.GroupRole) or "")
            return target, group_key, group_key
        return target, "", ""

    def wheelEvent(self, event):  # noqa: N802
        scrollbar = self.verticalScrollBar()
        if scrollbar is None:
            super().wheelEvent(event)
            return

        delta = event.angleDelta().y()
        at_top = scrollbar.value() <= scrollbar.minimum()
        at_bottom = scrollbar.value() >= scrollbar.maximum()
        if (delta > 0 and at_top) or (delta < 0 and at_bottom):
            event.accept()
            return

        super().wheelEvent(event)
        event.accept()

    def mousePressEvent(self, event):  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start_pos = event.position().toPoint()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):  # noqa: N802
        if not (event.buttons() & Qt.MouseButton.LeftButton):
            super().mouseMoveEvent(event)
            return
        if self._drag_start_pos is None:
            super().mouseMoveEvent(event)
            return
        if (event.position().toPoint() - self._drag_start_pos).manhattanLength() < QApplication.startDragDistance():
            super().mouseMoveEvent(event)
            return

        index = self.indexAt(self._drag_start_pos)
        if not index.isValid() or str(index.data(ProfileListModel.KindRole) or "") != "profile":
            super().mouseMoveEvent(event)
            return

        model = self.model()
        if model is None:
            super().mouseMoveEvent(event)
            return
        mime = model.mimeData([index])
        if mime is None or not mime.hasFormat(ProfileListModel.MIME_TYPE):
            super().mouseMoveEvent(event)
            return

        drag = QDrag(self)
        drag.setMimeData(mime)
        self._drag_start_pos = None
        try:
            drag.exec(Qt.DropAction.MoveAction)
        finally:
            self.set_drop_marker(-1, "")
        event.accept()

    def mouseReleaseEvent(self, event):  # noqa: N802
        pos = event.position().toPoint()
        index = self.indexAt(pos)
        if event.button() == Qt.MouseButton.RightButton:
            if index.isValid() and str(index.data(ProfileListModel.KindRole) or "") == "folder":
                group_key = str(index.data(ProfileListModel.GroupRole) or "")
                if group_key:
                    set_current_index_if_changed(self, index)
                    self.folder_context_requested.emit(group_key, self.viewport().mapToGlobal(pos))
                    event.accept()
                    return
            if index.isValid() and str(index.data(ProfileListModel.KindRole) or "") == "profile":
                profile_key = str(index.data(ProfileListModel.ProfileKeyRole) or "")
                if profile_key:
                    set_current_index_if_changed(self, index)
                    self.profile_context_requested.emit(profile_key, self.viewport().mapToGlobal(pos))
                    event.accept()
                    return
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event):  # noqa: N802
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            if self._activate_current_index_from_keyboard():
                event.accept()
                return
        if event.key() == Qt.Key.Key_Menu or (
            event.key() == Qt.Key.Key_F10 and event.modifiers() & Qt.KeyboardModifier.ShiftModifier
        ):
            if self._emit_context_requested_for_current_index():
                event.accept()
                return
        super().keyPressEvent(event)

    def _activate_current_index_from_keyboard(self) -> bool:
        index = self.currentIndex()
        if not index.isValid():
            return False
        kind = str(index.data(ProfileListModel.KindRole) or "")
        if kind == "profile":
            profile_key = str(index.data(ProfileListModel.ProfileKeyRole) or "")
            if not profile_key:
                return False
            self.profile_activated.emit(profile_key)
            return True
        if kind == "folder":
            group_key = str(index.data(ProfileListModel.GroupRole) or "")
            if not group_key:
                return False
            self.folder_toggle_requested.emit(group_key)
            return True
        return False

    def _emit_context_requested_for_current_index(self) -> bool:
        index = self.currentIndex()
        if not index.isValid():
            return False
        kind = str(index.data(ProfileListModel.KindRole) or "")
        if kind not in {"profile", "folder"}:
            return False
        rect = self.visualRect(index)
        if rect.isValid():
            point = rect.center()
        else:
            point = QPoint(0, 0)
        global_point = self.viewport().mapToGlobal(point)
        if kind == "profile":
            profile_key = str(index.data(ProfileListModel.ProfileKeyRole) or "")
            if not profile_key:
                return False
            self.profile_context_requested.emit(profile_key, global_point)
            return True
        group_key = str(index.data(ProfileListModel.GroupRole) or "")
        if not group_key:
            return False
        self.folder_context_requested.emit(group_key, global_point)
        return True

    def dragEnterEvent(self, event):  # noqa: N802
        if event.mimeData().hasFormat(ProfileListModel.MIME_TYPE):
            event.acceptProposedAction()
            return
        super().dragEnterEvent(event)

    def dragMoveEvent(self, event):  # noqa: N802
        if event.mimeData().hasFormat(ProfileListModel.MIME_TYPE):
            target, _destination_id, _destination_group_key = self._drop_target_at(event.position().toPoint())
            self.set_drop_marker_payload(dict(target.get("marker") or {}))
            event.acceptProposedAction()
            return
        super().dragMoveEvent(event)

    def dragLeaveEvent(self, event):  # noqa: N802
        self.set_drop_marker(-1, "")
        super().dragLeaveEvent(event)

    def dropEvent(self, event):  # noqa: N802
        if not event.mimeData().hasFormat(ProfileListModel.MIME_TYPE):
            self.set_drop_marker(-1, "")
            super().dropEvent(event)
            return
        source_key = _profile_key_from_mime(event.mimeData())
        if not source_key:
            self.set_drop_marker(-1, "")
            event.ignore()
            return

        target, destination_id, destination_group_key = self._drop_target_at(event.position().toPoint())
        destination_kind = str(target.get("destination_kind") or "")
        if destination_kind == "folder" and destination_id:
            self.profile_move_to_folder_requested.emit(source_key, destination_id)
            self.set_drop_marker(-1, "")
            event.acceptProposedAction()
            return
        if destination_kind == "profile" and destination_id and destination_id != source_key:
            self.profile_move_requested.emit(source_key, destination_id, destination_group_key)
            self.set_drop_marker(-1, "")
            event.acceptProposedAction()
            return
        if destination_kind == "profile_after" and destination_id and destination_id != source_key:
            self.profile_move_after_requested.emit(source_key, destination_id, destination_group_key)
            self.set_drop_marker(-1, "")
            event.acceptProposedAction()
            return
        if destination_kind in {"profile", "profile_after"} and destination_id == source_key:
            self.set_drop_marker(-1, "")
            event.acceptProposedAction()
            return

        self.profile_move_to_end_requested.emit(source_key)
        self.set_drop_marker(-1, "")
        event.acceptProposedAction()


def _profile_key_from_mime(mime) -> str:
    try:
        payload = json.loads(bytes(mime.data(ProfileListModel.MIME_TYPE)).decode("utf-8"))
    except Exception:
        return ""
    return str(payload.get("profile_key") or "").strip()


__all__ = [
    "PROFILE_DROP_MARKER_PROPERTY",
    "ProfileListView",
    "profile_canonical_drop_target_for_next_row",
    "profile_drop_marker_for_target",
    "profile_drop_target_for_position",
]
