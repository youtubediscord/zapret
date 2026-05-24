from __future__ import annotations

import json

from PyQt6.QtCore import QPoint, Qt, pyqtSignal
from PyQt6.QtGui import QDrag
from PyQt6.QtWidgets import QApplication
from qfluentwidgets import ListView

from .profile_list_model import ProfileListModel


PROFILE_DROP_MARKER_PROPERTY = "profileDropMarker"


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
    return {"row": -1, "mode": ""}


class ProfileListView(ListView):
    profile_activated = pyqtSignal(str)
    profile_context_requested = pyqtSignal(str, QPoint)
    folder_context_requested = pyqtSignal(str, QPoint)
    profile_move_requested = pyqtSignal(str, str)
    profile_move_to_folder_requested = pyqtSignal(str, str)
    profile_move_to_end_requested = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._drag_start_pos: QPoint | None = None
        self.set_drop_marker(-1, "")

    def set_drop_marker(self, row: int, destination_kind: str) -> None:
        marker = profile_drop_marker_for_target(row, destination_kind)
        if self.property(PROFILE_DROP_MARKER_PROPERTY) == marker:
            return
        self.setProperty(PROFILE_DROP_MARKER_PROPERTY, marker)
        self.viewport().update()

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
                    self.setCurrentIndex(index)
                    self.folder_context_requested.emit(group_key, self.viewport().mapToGlobal(pos))
                    event.accept()
                    return
            if index.isValid() and str(index.data(ProfileListModel.KindRole) or "") == "profile":
                profile_key = str(index.data(ProfileListModel.ProfileKeyRole) or "")
                if profile_key:
                    self.setCurrentIndex(index)
                    self.profile_context_requested.emit(profile_key, self.viewport().mapToGlobal(pos))
                    event.accept()
                    return
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event):  # noqa: N802
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            index = self.currentIndex()
            if index.isValid() and str(index.data(ProfileListModel.KindRole) or "") == "profile":
                profile_key = str(index.data(ProfileListModel.ProfileKeyRole) or "")
                if profile_key:
                    self.profile_activated.emit(profile_key)
                    event.accept()
                    return
        super().keyPressEvent(event)

    def dragEnterEvent(self, event):  # noqa: N802
        if event.mimeData().hasFormat(ProfileListModel.MIME_TYPE):
            event.acceptProposedAction()
            return
        super().dragEnterEvent(event)

    def dragMoveEvent(self, event):  # noqa: N802
        if event.mimeData().hasFormat(ProfileListModel.MIME_TYPE):
            drop_index = self.indexAt(event.position().toPoint())
            destination_kind = str(drop_index.data(ProfileListModel.KindRole) or "") if drop_index.isValid() else ""
            self.set_drop_marker(drop_index.row() if drop_index.isValid() else -1, destination_kind)
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

        drop_index = self.indexAt(event.position().toPoint())
        if drop_index.isValid():
            destination_kind = str(drop_index.data(ProfileListModel.KindRole) or "")
            if destination_kind == "folder":
                folder_key = str(drop_index.data(ProfileListModel.GroupRole) or "")
                if folder_key:
                    self.profile_move_to_folder_requested.emit(source_key, folder_key)
                    self.set_drop_marker(-1, "")
                    event.acceptProposedAction()
                    return
            if destination_kind == "profile":
                destination_key = str(drop_index.data(ProfileListModel.ProfileKeyRole) or "")
                if destination_key and destination_key != source_key:
                    self.profile_move_requested.emit(source_key, destination_key)
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


__all__ = ["PROFILE_DROP_MARKER_PROPERTY", "ProfileListView", "profile_drop_marker_for_target"]
