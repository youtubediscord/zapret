from __future__ import annotations

from PyQt6.QtCore import QThread, pyqtSignal

from log.log import log


class OrchestraClearLearnedWorker(QThread):
    loaded = pyqtSignal(int, bool)
    failed = pyqtSignal(int, str)

    def __init__(self, request_id: int, controller, parent=None):
        super().__init__(parent)
        self._request_id = int(request_id)
        self._controller = controller

    def run(self) -> None:
        try:
            result = bool(self._controller.clear_learned_data())
        except Exception as exc:
            log(f"Orchestra clear learned worker: ошибка сброса обучения: {exc}", "ERROR")
            self.failed.emit(self._request_id, str(exc))
            return
        self.loaded.emit(self._request_id, result)


__all__ = ["OrchestraClearLearnedWorker"]
