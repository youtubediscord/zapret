from __future__ import annotations

import time

from PyQt6.QtCore import QObject, pyqtSignal

from log.log import log


class LogsOverviewWorker(QObject):
    loaded = pyqtSignal(object, object)
    failed = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(self, *, list_logs_fn, build_stats_fn, run_cleanup: bool):
        super().__init__()
        self._list_logs_fn = list_logs_fn
        self._build_stats_fn = build_stats_fn
        self._run_cleanup = bool(run_cleanup)
        self._stopped = False

    def run(self) -> None:
        started_at = time.perf_counter()
        try:
            logs_state = self._list_logs_fn(run_cleanup=self._run_cleanup)
            stats_state = self._build_stats_fn()
            if not self._stopped:
                self.loaded.emit(logs_state, stats_state)
        except Exception as exc:
            if not self._stopped:
                self.failed.emit(str(exc))
        finally:
            try:
                elapsed_ms = (time.perf_counter() - started_at) * 1000.0
                log(f"logs_feature.overview_worker.total: {elapsed_ms:.1f}ms", "DEBUG")
            except Exception:
                pass
            self.finished.emit()

    def stop(self) -> None:
        self._stopped = True


__all__ = ["LogsOverviewWorker"]
