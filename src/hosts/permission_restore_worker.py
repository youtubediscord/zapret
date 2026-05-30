from __future__ import annotations

from PyQt6.QtCore import QThread, pyqtSignal

from log.log import log


class HostsPermissionRestoreWorker(QThread):
    """Восстанавливает права доступа к hosts вне UI-потока."""

    loaded = pyqtSignal(int, object)
    failed = pyqtSignal(int, str)

    def __init__(self, request_id: int, *, restore_hosts_permissions, parent=None):
        super().__init__(parent)
        self._request_id = int(request_id)
        self._restore_hosts_permissions = restore_hosts_permissions

    def run(self) -> None:
        try:
            result = self._restore_hosts_permissions()
        except Exception as exc:
            log(f"HostsPermissionRestoreWorker: не удалось восстановить права hosts: {exc}", "ERROR")
            self.failed.emit(self._request_id, str(exc))
            return
        self.loaded.emit(self._request_id, result)


__all__ = ["HostsPermissionRestoreWorker"]
