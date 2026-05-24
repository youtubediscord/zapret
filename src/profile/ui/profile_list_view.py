from __future__ import annotations

import json

from PyQt6.QtCore import QPoint, Qt, pyqtSignal
from PyQt6.QtGui import QDrag
from PyQt6.QtWidgets import QApplication
from qfluentwidgets import ListView

from .profile_list_model import ProfileListModel


class ProfileListView(ListView):
    profile_activated = pyqtSignal(str)
    profile_context_requested = pyqtSignal(str, QPoint)
    folder_context_requested = pyqtSignal(str, QPoint)
    profile_move_requested = pyqtSignal(str, str)
    profile_move_to_end_requested = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._drag_start_pos: QPoint | None = None

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
        drag.exec(Qt.DropAction.MoveAction)
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
            event.acceptProposedAction()
            return
        super().dragMoveEvent(event)

    def dropEvent(self, event):  # noqa: N802
        if not event.mimeData().hasFormat(ProfileListModel.MIME_TYPE):
            super().dropEvent(event)
            return
        source_key = _profile_key_from_mime(event.mimeData())
        if not source_key:
            event.ignore()
            return

        drop_index = self.indexAt(event.position().toPoint())
        if drop_index.isValid() and str(drop_index.data(ProfileListModel.KindRole) or "") == "profile":
            destination_key = str(drop_index.data(ProfileListModel.ProfileKeyRole) or "")
            if destination_key and destination_key != source_key:
                self.profile_move_requested.emit(source_key, destination_key)
                event.acceptProposedAction()
                return

        self.profile_move_to_end_requested.emit(source_key)
        event.acceptProposedAction()


def _profile_key_from_mime(mime) -> str:
    try:
        payload = json.loads(bytes(mime.data(ProfileListModel.MIME_TYPE)).decode("utf-8"))
    except Exception:
        return ""
    return str(payload.get("profile_key") or "").strip()


__all__ = ["ProfileListView"]
