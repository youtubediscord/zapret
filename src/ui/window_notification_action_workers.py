from __future__ import annotations

from PyQt6.QtCore import QThread, pyqtSignal

from log.log import log


class NotificationActionWorker(QThread):
    loaded = pyqtSignal(int, str, object)
    failed = pyqtSignal(int, str, str)

    def __init__(self, request_id: int, *, action_name: str, action_fn, parent=None):
        super().__init__(parent)
        self._request_id = int(request_id)
        self._action_name = str(action_name or "").strip()
        self._action_fn = action_fn

    def run(self) -> None:
        try:
            result = self._action_fn()
        except Exception as exc:
            log(f"NotificationActionWorker: действие {self._action_name} не выполнено: {exc}", "ERROR")
            self.failed.emit(self._request_id, self._action_name, str(exc))
            return
        self.loaded.emit(self._request_id, self._action_name, result)


__all__ = ["NotificationActionWorker"]
