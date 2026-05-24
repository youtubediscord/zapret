from __future__ import annotations

from PyQt6.QtCore import QThread, pyqtSignal

from log.log import log


class OrchestraManagedSnapshotLoadWorker(QThread):
    loaded = pyqtSignal(int, object)
    failed = pyqtSignal(int, str)

    def __init__(self, request_id: int, controller, parent=None):
        super().__init__(parent)
        self._request_id = int(request_id)
        self._controller = controller

    def run(self) -> None:
        try:
            snapshot = self._controller.reload_snapshot()
        except Exception as exc:
            log(f"Orchestra managed snapshot worker: ошибка загрузки: {exc}", "ERROR")
            self.failed.emit(self._request_id, str(exc))
            return
        self.loaded.emit(self._request_id, snapshot)


__all__ = ["OrchestraManagedSnapshotLoadWorker"]
