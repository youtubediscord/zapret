from __future__ import annotations

from PyQt6.QtCore import QThread, pyqtSignal

from log.log import log


class LogsSupportPrepareWorker(QThread):
    loaded = pyqtSignal(int, object)
    failed = pyqtSignal(int, str)

    def __init__(
        self,
        request_id: int,
        logs_feature,
        *,
        current_log_file: str,
        orchestra_runner,
        parent=None,
    ):
        super().__init__(parent)
        self._request_id = int(request_id)
        self._logs = logs_feature
        self._current_log_file = str(current_log_file or "")
        self._orchestra_runner = orchestra_runner

    def run(self) -> None:
        try:
            result = self._logs.prepare_support_bundle(
                current_log_file=self._current_log_file,
                orchestra_runner=self._orchestra_runner,
            )
        except Exception as exc:
            log(f"LogsSupportPrepareWorker: обращение по логам не подготовлено: {exc}", "ERROR")
            self.failed.emit(self._request_id, str(exc))
            return
        self.loaded.emit(self._request_id, result)
