from __future__ import annotations

from PyQt6.QtCore import QThread, pyqtSignal

from log.log import log


class BlockcheckInitialStateWorker(QThread):
    completed = pyqtSignal(int, object)
    failed = pyqtSignal(int, str)

    def __init__(self, request_id: int, *, parent=None):
        super().__init__(parent)
        self._request_id = int(request_id)

    def run(self) -> None:
        try:
            from blockcheck.page_runtime import load_page_initial_state

            result = load_page_initial_state()
        except Exception as exc:
            log(f"BlockcheckInitialStateWorker: не удалось загрузить начальное состояние: {exc}", "WARNING")
            self.failed.emit(self._request_id, str(exc))
            return
        self.completed.emit(self._request_id, result)
