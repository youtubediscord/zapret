from __future__ import annotations

from PyQt6.QtCore import QThread, pyqtSignal

from log.log import log


class HostsStateLoadWorker(QThread):
    loaded = pyqtSignal(int, object)
    failed = pyqtSignal(int, str)

    def __init__(self, request_id: int, controller, hosts_runtime, parent=None):
        super().__init__(parent)
        self._request_id = int(request_id)
        self._controller = controller
        self._hosts_runtime = hosts_runtime

    def run(self) -> None:
        try:
            state = self._controller.get_hosts_state(self._hosts_runtime)
        except Exception as exc:
            log(f"HostsStateLoadWorker: ошибка загрузки состояния hosts: {exc}", "ERROR")
            self.failed.emit(self._request_id, str(exc))
            return
        self.loaded.emit(self._request_id, state)


__all__ = ["HostsStateLoadWorker"]
