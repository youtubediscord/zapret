from __future__ import annotations

from PyQt6.QtCore import QThread, pyqtSignal

from log.log import log


class BlockcheckInitialStateWorker(QThread):
    completed = pyqtSignal(int, object)
    failed = pyqtSignal(int, str)

    def __init__(self, request_id: int, *, parent=None):
        super().__init__(parent)
        self._request_id = int(request_id)

    def run(self) -> None:
        try:
            from blockcheck.page_runtime import load_page_initial_state

            result = load_page_initial_state()
        except Exception as exc:
            log(f"BlockcheckInitialStateWorker: не удалось загрузить начальное состояние: {exc}", "WARNING")
            self.failed.emit(self._request_id, str(exc))
            return
        self.completed.emit(self._request_id, result)


class BlockcheckSupportPrepareWorker(QThread):
    completed = pyqtSignal(int, object)
    failed = pyqtSignal(int, str)

    def __init__(
        self,
        request_id: int,
        *,
        run_log_file: str | None,
        mode_label: str,
        extra_domains: list[str],
        parent=None,
    ):
        super().__init__(parent)
        self._request_id = int(request_id)
        self._run_log_file = run_log_file
        self._mode_label = str(mode_label or "BlockCheck")
        self._extra_domains = list(extra_domains or [])

    def run(self) -> None:
        try:
            from blockcheck.page_runtime import prepare_support

            result = prepare_support(
                run_log_file=self._run_log_file,
                mode_label=self._mode_label,
                extra_domains=self._extra_domains,
            )
        except Exception as exc:
            log(f"BlockcheckSupportPrepareWorker: не удалось подготовить обращение: {exc}", "WARNING")
            self.failed.emit(self._request_id, str(exc))
            return
        self.completed.emit(self._request_id, result)


class BlockcheckUserDomainActionWorker(QThread):
    completed = pyqtSignal(int, str, object, object)
    failed = pyqtSignal(int, str, str, object)

    def __init__(self, request_id: int, *, action: str, domain: str, parent=None):
        super().__init__(parent)
        self._request_id = int(request_id)
        self._action = str(action or "").strip().lower()
        self._domain = str(domain or "").strip()

    def run(self) -> None:
        import blockcheck.page_runtime as blockcheck_page_runtime

        context = {"domain": self._domain}
        try:
            if self._action == "add":
                result = blockcheck_page_runtime.add_user_domain(self._domain)
            elif self._action == "remove":
                blockcheck_page_runtime.remove_user_domain(self._domain)
                result = self._domain
            else:
                raise ValueError(f"Неизвестное действие домена BlockCheck: {self._action}")
        except Exception as exc:
            log(f"BlockcheckUserDomainActionWorker: не удалось выполнить {self._action}: {exc}", "WARNING")
            self.failed.emit(self._request_id, self._action, str(exc), context)
            return
        self.completed.emit(self._request_id, self._action, result, context)


class StrategyScanSupportPrepareWorker(QThread):
    completed = pyqtSignal(int, object)
    failed = pyqtSignal(int, str)

    def __init__(
        self,
        request_id: int,
        *,
        run_log_file,
        target: str,
        protocol_label: str,
        mode_label: str,
        scan_protocol: str,
        parent=None,
    ):
        super().__init__(parent)
        self._request_id = int(request_id)
        self._run_log_file = run_log_file
        self._target = str(target or "")
        self._protocol_label = str(protocol_label or "")
        self._mode_label = str(mode_label or "")
        self._scan_protocol = str(scan_protocol or "")

    def run(self) -> None:
        try:
            from blockcheck.strategy_scan_logs import prepare_support

            result = prepare_support(
                run_log_file=self._run_log_file,
                target=self._target,
                protocol_label=self._protocol_label,
                mode_label=self._mode_label,
                scan_protocol=self._scan_protocol,
            )
        except Exception as exc:
            log(f"StrategyScanSupportPrepareWorker: не удалось подготовить обращение: {exc}", "WARNING")
            self.failed.emit(self._request_id, str(exc))
            return
        self.completed.emit(self._request_id, result)
