from __future__ import annotations

from PyQt6.QtCore import QThread, pyqtSignal

from log.log import log


class ExternalOpenUrlWorker(QThread):
    loaded = pyqtSignal(int, object)
    failed = pyqtSignal(int, str)

    def __init__(self, request_id: int, *, url: str, open_url, parent=None):
        super().__init__(parent)
        self._request_id = int(request_id)
        self._url = str(url or "").strip()
        self._open_url = open_url

    def run(self) -> None:
        try:
            result = self._open_url(self._url)
        except Exception as exc:
            log(f"ExternalOpenUrlWorker: не удалось открыть ссылку: {exc}", "ERROR")
            self.failed.emit(self._request_id, str(exc))
            return
        self.loaded.emit(self._request_id, result)


class ExternalActionWorker(QThread):
    loaded = pyqtSignal(int, str, object)
    failed = pyqtSignal(int, str, str)

    def __init__(self, request_id: int, *, action_name: str, action_fn, log_name: str = "ExternalActionWorker", parent=None):
        super().__init__(parent)
        self._request_id = int(request_id)
        self._action_name = str(action_name or "").strip()
        self._action_fn = action_fn
        self._log_name = str(log_name or "ExternalActionWorker")

    def run(self) -> None:
        try:
            result = self._action_fn()
        except Exception as exc:
            log(f"{self._log_name}: действие {self._action_name} не выполнено: {exc}", "ERROR")
            self.failed.emit(self._request_id, self._action_name, str(exc))
            return
        self.loaded.emit(self._request_id, self._action_name, result)


class ExternalNotificationActionWorker(ExternalActionWorker):
    def __init__(self, request_id: int, *, action_name: str, action_fn, parent=None):
        super().__init__(
            request_id,
            action_name=action_name,
            action_fn=action_fn,
            log_name="ExternalNotificationActionWorker",
            parent=parent,
        )


__all__ = ["ExternalActionWorker", "ExternalOpenUrlWorker", "ExternalNotificationActionWorker"]
