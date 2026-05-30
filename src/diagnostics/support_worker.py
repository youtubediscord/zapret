from __future__ import annotations

from collections.abc import Callable

from PyQt6.QtCore import QThread, pyqtSignal

from log.log import log


class ConnectionSupportPrepareWorker(QThread):
    completed = pyqtSignal(int, object)
    failed = pyqtSignal(int, str)

    def __init__(
        self,
        request_id: int,
        *,
        selection: str,
        prepare_connection_support: Callable[..., object],
        parent=None,
    ):
        super().__init__(parent)
        self._request_id = int(request_id)
        self._selection = str(selection or "")
        self._prepare_connection_support = prepare_connection_support

    def run(self) -> None:
        try:
            result = self._prepare_connection_support(selection=self._selection)
        except Exception as exc:
            log(f"ConnectionSupportPrepareWorker: не удалось подготовить обращение: {exc}", "WARNING")
            self.failed.emit(self._request_id, str(exc))
            return
        self.completed.emit(self._request_id, result)
