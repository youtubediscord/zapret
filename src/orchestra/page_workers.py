from __future__ import annotations

from PyQt6.QtCore import QThread, pyqtSignal

from log.log import log


class OrchestraClearLearnedWorker(QThread):
    loaded = pyqtSignal(int, bool)
    failed = pyqtSignal(int, str)

    def __init__(self, request_id: int, clear_learned_data, parent=None):
        super().__init__(parent)
        self._request_id = int(request_id)
        self._clear_learned_data = clear_learned_data

    def run(self) -> None:
        try:
            result = bool(self._clear_learned_data())
        except Exception as exc:
            log(f"Orchestra clear learned worker: ошибка сброса обучения: {exc}", "ERROR")
            self.failed.emit(self._request_id, str(exc))
            return
        self.loaded.emit(self._request_id, result)


class OrchestraLogHistoryLoadWorker(QThread):
    loaded = pyqtSignal(int, object)
    failed = pyqtSignal(int, str)

    def __init__(self, request_id: int, load_log_history, parent=None):
        super().__init__(parent)
        self._request_id = int(request_id)
        self._load_log_history = load_log_history

    def run(self) -> None:
        try:
            logs = self._load_log_history()
        except Exception as exc:
            log(f"Orchestra log history worker: ошибка загрузки истории логов: {exc}", "ERROR")
            self.failed.emit(self._request_id, str(exc))
            return
        self.loaded.emit(self._request_id, logs)


class OrchestraLogHistoryActionWorker(QThread):
    loaded = pyqtSignal(int, str, object)
    failed = pyqtSignal(int, str, str)

    def __init__(self, request_id: int, *, action: str, log_id: str, run_action, parent=None):
        super().__init__(parent)
        self._request_id = int(request_id)
        self._action = str(action or "").strip()
        self._log_id = str(log_id or "").strip()
        self._run_action = run_action

    def run(self) -> None:
        try:
            result = self._run_action(action=self._action, log_id=self._log_id)
        except Exception as exc:
            log(f"Orchestra log history action worker: ошибка действия {self._action}: {exc}", "ERROR")
            self.failed.emit(self._request_id, self._action, str(exc))
            return
        self.loaded.emit(self._request_id, self._action, result)


class OrchestraLogContextActionWorker(QThread):
    loaded = pyqtSignal(int, str, object)
    failed = pyqtSignal(int, str, str)

    def __init__(
        self,
        request_id: int,
        *,
        action: str,
        domain: str,
        strategy: int,
        protocol: str,
        run_action,
        parent=None,
    ):
        super().__init__(parent)
        self._request_id = int(request_id)
        self._action = str(action or "").strip()
        self._domain = str(domain or "").strip()
        self._strategy = int(strategy or 0)
        self._protocol = str(protocol or "").strip()
        self._run_action = run_action

    def run(self) -> None:
        try:
            result = self._run_action(
                action=self._action,
                domain=self._domain,
                strategy=self._strategy,
                protocol=self._protocol,
            )
        except Exception as exc:
            log(f"Orchestra log context action worker: ошибка действия {self._action}: {exc}", "ERROR")
            self.failed.emit(self._request_id, self._action, str(exc))
            return
        self.loaded.emit(self._request_id, self._action, result)


__all__ = [
    "OrchestraClearLearnedWorker",
    "OrchestraLogContextActionWorker",
    "OrchestraLogHistoryActionWorker",
    "OrchestraLogHistoryLoadWorker",
]
