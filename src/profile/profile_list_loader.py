from __future__ import annotations

import time

from PyQt6.QtCore import QThread, pyqtSignal

from log.log import log


class ProfileListLoadWorker(QThread):
    loaded = pyqtSignal(int, object)
    failed = pyqtSignal(int, str)

    def __init__(self, request_id: int, profile_service, parent=None):
        super().__init__(parent)
        self._request_id = int(request_id)
        self._service = profile_service

    def run(self) -> None:
        started_at = time.perf_counter()
        try:
            payload = self._service.list_profiles()
        except Exception as exc:
            log(f"ProfileListLoadWorker: не удалось загрузить profile payload: {exc}", "ERROR")
            self.failed.emit(self._request_id, str(exc))
            return
        elapsed_ms = (time.perf_counter() - started_at) * 1000.0
        log(f"profile_feature.worker.list_profiles.total: {elapsed_ms:.1f}ms", "DEBUG")
        self.loaded.emit(self._request_id, payload)
