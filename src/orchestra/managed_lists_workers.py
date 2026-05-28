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


class OrchestraWhitelistActionWorker(QThread):
    loaded = pyqtSignal(int, str, object, object)
    failed = pyqtSignal(int, str, str, object)

    def __init__(
        self,
        request_id: int,
        controller,
        *,
        action: str,
        domain: str = "",
        user_domains: list[str] | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self._request_id = int(request_id)
        self._controller = controller
        self._action = str(action or "").strip()
        self._domain = str(domain or "").strip().lower()
        self._user_domains = list(user_domains or [])

    def run(self) -> None:
        context = {
            "domain": self._domain,
            "user_domains": tuple(self._user_domains),
        }
        try:
            if self._action == "add":
                result = self._controller.add_domain(domain=self._domain)
            elif self._action == "remove":
                result = self._controller.remove_domain(domain=self._domain)
            elif self._action == "clear_user":
                result = self._controller.clear_user_domains(user_domains=self._user_domains)
            else:
                raise ValueError(f"Неизвестное действие whitelist: {self._action}")
            snapshot = self._controller.snapshot(refresh=True)
        except Exception as exc:
            log(f"Orchestra whitelist action worker: ошибка действия {self._action}: {exc}", "ERROR")
            self.failed.emit(self._request_id, self._action, str(exc), context)
            return
        self.loaded.emit(self._request_id, self._action, {"result": result, "snapshot": snapshot}, context)


__all__ = ["OrchestraManagedSnapshotLoadWorker", "OrchestraWhitelistActionWorker"]
