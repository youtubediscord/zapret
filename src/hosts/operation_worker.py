from __future__ import annotations

from PyQt6.QtCore import QObject, pyqtSignal

from log.log import log


class HostsOperationWorker(QObject):
    """Фоновый worker для операций hosts-страницы."""

    finished = pyqtSignal(bool, str)

    def __init__(self, hosts_runtime, operation: str, payload=None, execute_hosts_operation_fn=None):
        super().__init__()
        self._hosts_runtime = hosts_runtime
        self._operation = operation
        self._payload = payload
        self._execute_hosts_operation = execute_hosts_operation_fn
        self._stop_requested = False

    def stop(self) -> None:
        self._stop_requested = True

    def run(self):
        if self._stop_requested:
            self.finished.emit(False, "Операция отменена")
            return
        try:
            if self._execute_hosts_operation is None:
                raise RuntimeError("Hosts operation function is not initialized")
            result = self._execute_hosts_operation(
                self._hosts_runtime,
                self._operation,
                self._payload,
            )
            if self._stop_requested:
                self.finished.emit(False, "Операция отменена")
                return
            self.finished.emit(result.success, result.message)
        except Exception as e:
            log(f"Ошибка в HostsOperationWorker: {e}", "ERROR")
            self.finished.emit(False, str(e))
