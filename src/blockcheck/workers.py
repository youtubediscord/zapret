from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PyQt6.QtCore import QThread, pyqtSignal

from log.log import log


class BlockcheckInitialStateWorker(QThread):
    completed = pyqtSignal(int, object)
    failed = pyqtSignal(int, str)

    def __init__(self, request_id: int, *, load_page_initial_state: Callable[[], Any], parent=None):
        super().__init__(parent)
        self._request_id = int(request_id)
        self._load_page_initial_state = load_page_initial_state

    def run(self) -> None:
        try:
            result = self._load_page_initial_state()
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
        prepare_support: Callable[..., Any],
        parent=None,
    ):
        super().__init__(parent)
        self._request_id = int(request_id)
        self._run_log_file = run_log_file
        self._mode_label = str(mode_label or "BlockCheck")
        self._extra_domains = list(extra_domains or [])
        self._prepare_support = prepare_support

    def run(self) -> None:
        try:
            result = self._prepare_support(
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

    def __init__(
        self,
        request_id: int,
        *,
        action: str,
        domain: str,
        run_user_domain_action: Callable[[str, str], Any],
        parent=None,
    ):
        super().__init__(parent)
        self._request_id = int(request_id)
        self._action = str(action or "").strip().lower()
        self._domain = str(domain or "").strip()
        self._run_user_domain_action = run_user_domain_action

    def run(self) -> None:
        context = {"domain": self._domain}
        try:
            result = self._run_user_domain_action(self._action, self._domain)
        except Exception as exc:
            log(f"BlockcheckUserDomainActionWorker: не удалось выполнить {self._action}: {exc}", "WARNING")
            self.failed.emit(self._request_id, self._action, str(exc), context)
            return
        self.completed.emit(self._request_id, self._action, result, context)


class StrategyScanQuickTargetsWorker(QThread):
    completed = pyqtSignal(int, object)
    failed = pyqtSignal(int, str)

    def __init__(
        self,
        request_id: int,
        *,
        scan_protocol: str,
        current_value: str,
        build_quick_target_menu_plan: Callable[..., Any],
        parent=None,
    ):
        super().__init__(parent)
        self._request_id = int(request_id)
        self._scan_protocol = str(scan_protocol or "").strip()
        self._current_value = str(current_value or "")
        self._build_quick_target_menu_plan = build_quick_target_menu_plan

    def run(self) -> None:
        try:
            plan = self._build_quick_target_menu_plan(
                scan_protocol=self._scan_protocol,
                current_value=self._current_value,
            )
        except Exception as exc:
            log(f"StrategyScanQuickTargetsWorker: не удалось загрузить быстрые цели: {exc}", "WARNING")
            self.failed.emit(self._request_id, str(exc))
            return
        self.completed.emit(self._request_id, plan)


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
        prepare_strategy_scan_support: Callable[..., Any],
        parent=None,
    ):
        super().__init__(parent)
        self._request_id = int(request_id)
        self._run_log_file = run_log_file
        self._target = str(target or "")
        self._protocol_label = str(protocol_label or "")
        self._mode_label = str(mode_label or "")
        self._scan_protocol = str(scan_protocol or "")
        self._prepare_strategy_scan_support = prepare_strategy_scan_support

    def run(self) -> None:
        try:
            result = self._prepare_strategy_scan_support(
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


class StrategyScanResumeSaveWorker(QThread):
    completed = pyqtSignal(int, object)
    failed = pyqtSignal(int, str)

    def __init__(
        self,
        request_id: int,
        *,
        scan_target: str,
        scan_protocol: str,
        next_index: int,
        udp_games_scope: str,
        save_resume_state: Callable[..., Any],
        parent=None,
    ):
        super().__init__(parent)
        self._request_id = int(request_id)
        self._scan_target = str(scan_target or "")
        self._scan_protocol = str(scan_protocol or "")
        self._next_index = int(next_index)
        self._udp_games_scope = str(udp_games_scope or "all")
        self._save_resume_state = save_resume_state

    def run(self) -> None:
        try:
            self._save_resume_state(
                self._scan_target,
                self._scan_protocol,
                self._next_index,
                self._udp_games_scope,
            )
        except Exception as exc:
            log(f"StrategyScanResumeSaveWorker: не удалось сохранить прогресс: {exc}", "WARNING")
            self.failed.emit(self._request_id, str(exc))
            return
        self.completed.emit(self._request_id, {"next_index": self._next_index})


class StrategyScanFinalizeWorker(QThread):
    completed = pyqtSignal(int, object)
    failed = pyqtSignal(int, str)

    def __init__(
        self,
        request_id: int,
        *,
        report,
        scan_target: str,
        scan_protocol: str,
        scan_udp_games_scope: str,
        scan_mode: str,
        scan_cursor: int,
        result_rows: list[dict],
        finalize_scan_report: Callable[..., Any],
        parent=None,
    ):
        super().__init__(parent)
        self._request_id = int(request_id)
        self._report = report
        self._scan_target = str(scan_target or "")
        self._scan_protocol = str(scan_protocol or "")
        self._scan_udp_games_scope = str(scan_udp_games_scope or "all")
        self._scan_mode = str(scan_mode or "")
        self._scan_cursor = int(scan_cursor)
        self._result_rows = [dict(row) for row in (result_rows or [])]
        self._finalize_scan_report = finalize_scan_report

    def run(self) -> None:
        try:
            finish_plan = self._finalize_scan_report(
                self._report,
                scan_target=self._scan_target,
                scan_protocol=self._scan_protocol,
                scan_udp_games_scope=self._scan_udp_games_scope,
                scan_mode=self._scan_mode,
                scan_cursor=self._scan_cursor,
                result_rows=self._result_rows,
            )
        except Exception as exc:
            log(f"StrategyScanFinalizeWorker: не удалось завершить сканирование: {exc}", "WARNING")
            self.failed.emit(self._request_id, str(exc))
            return
        self.completed.emit(self._request_id, finish_plan)
