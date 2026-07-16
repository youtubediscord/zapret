from __future__ import annotations

import time

from PyQt6.QtCore import QObject, pyqtSignal

from app.performance_metrics import log_ui_timing_since

from .parser import parse_winws_log_file


class WinwsLogParseWorker(QObject):
    progress = pyqtSignal(int, int)  # bytes_read, bytes_total
    loaded = pyqtSignal(object)  # WinwsLogParseResult
    failed = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(self, *, file_path: str):
        super().__init__()
        self._file_path = file_path
        self._stopped = False

    def run(self) -> None:
        started_at = time.perf_counter()
        try:
            result = parse_winws_log_file(
                self._file_path,
                progress_cb=self._emit_progress,
                cancel_cb=lambda: self._stopped,
            )
            if not self._stopped:
                self.loaded.emit(result)
        except Exception as exc:
            if not self._stopped:
                self.failed.emit(str(exc))
        finally:
            log_ui_timing_since(
                "worker", "winws_log_analyzer", "winws_log_analyzer.parse_worker.total", started_at
            )
            self.finished.emit()

    def _emit_progress(self, bytes_read: int, bytes_total: int) -> None:
        if not self._stopped:
            self.progress.emit(bytes_read, bytes_total)

    def stop(self) -> None:
        self._stopped = True


__all__ = ["WinwsLogParseWorker"]
