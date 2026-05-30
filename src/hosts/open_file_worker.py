from __future__ import annotations

from PyQt6.QtCore import QThread, pyqtSignal

from log.log import log


class HostsOpenFileWorker(QThread):
    """Открывает файл hosts вне UI-потока."""

    loaded = pyqtSignal(int, object)
    failed = pyqtSignal(int, str)

    def __init__(self, request_id: int, *, open_hosts_file, parent=None):
        super().__init__(parent)
        self._request_id = int(request_id)
        self._open_hosts_file = open_hosts_file

    def run(self) -> None:
        try:
            result = self._open_hosts_file()
        except Exception as exc:
            log(f"HostsOpenFileWorker: не удалось открыть hosts: {exc}", "ERROR")
            self.failed.emit(self._request_id, str(exc))
            return
        self.loaded.emit(self._request_id, result)


__all__ = ["HostsOpenFileWorker"]
