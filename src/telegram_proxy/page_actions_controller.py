from __future__ import annotations

import os
import subprocess
import webbrowser
from dataclasses import dataclass


@dataclass(slots=True)
class TelegramProxyDiagnosticsStartPlan:
    button_enabled: bool
    button_text: str
    initial_text: str
    poll_interval_ms: int


@dataclass(slots=True)
class TelegramProxyDiagnosticsPollPlan:
    updated_text: str | None
    should_stop_timer: bool
    should_finish: bool


@dataclass(slots=True)
class TelegramProxyDiagnosticsFinishPlan:
    button_enabled: bool
    button_text: str


@dataclass(slots=True)
class TelegramProxyActionResult:
    ok: bool
    log_line: str
    info_title: str
    info_content: str


class TelegramProxyPageActionsController:
    @staticmethod
    def build_diagnostics_start_plan() -> TelegramProxyDiagnosticsStartPlan:
        return TelegramProxyDiagnosticsStartPlan(
            button_enabled=False,
            button_text="Тестирование...",
            initial_text="Запуск диагностики Telegram DC...\n",
            poll_interval_ms=200,
        )

    @staticmethod
    def build_diagnostics_poll_plan(*, result_text: str | None, thread_done: bool) -> TelegramProxyDiagnosticsPollPlan:
        return TelegramProxyDiagnosticsPollPlan(
            updated_text=result_text if result_text is not None else None,
            should_stop_timer=bool(thread_done),
            should_finish=bool(thread_done),
        )

    @staticmethod
    def build_diagnostics_finish_plan() -> TelegramProxyDiagnosticsFinishPlan:
        return TelegramProxyDiagnosticsFinishPlan(
            button_enabled=True,
            button_text="Запустить диагностику",
        )

    @staticmethod
    def copy_text(text: str, *, success_title: str, success_content: str, success_log: str = "") -> TelegramProxyActionResult:
        from PyQt6.QtGui import QGuiApplication

        payload = str(text or "")
        clipboard = QGuiApplication.clipboard()
        if clipboard is None or not payload:
            return TelegramProxyActionResult(False, "", "", "")
        clipboard.setText(payload)
        return TelegramProxyActionResult(
            ok=True,
            log_line=success_log,
            info_title=success_title,
            info_content=success_content,
        )

    @staticmethod
    def open_log_file(path: str) -> TelegramProxyActionResult:
        target = os.path.normpath(str(path or ""))
        if os.path.exists(target):
            try:
                subprocess.Popen(["explorer", "/select,", target])
                return TelegramProxyActionResult(True, "", "", "")
            except Exception as e:
                return TelegramProxyActionResult(False, f"Failed to open log file: {e}", "", "")
        return TelegramProxyActionResult(False, f"Log file not found: {target}", "", "")

    @staticmethod
    def open_external_link(url: str, *, success_log: str, error_prefix: str) -> TelegramProxyActionResult:
        target = str(url or "").strip()
        if not target:
            return TelegramProxyActionResult(False, f"{error_prefix}: empty url", "", "")
        try:
            webbrowser.open(target)
            return TelegramProxyActionResult(True, success_log, "", "")
        except Exception as e:
            return TelegramProxyActionResult(False, f"{error_prefix}: {e}", "", "")

    @staticmethod
    def ensure_telegram_hosts() -> TelegramProxyActionResult:
        try:
            from telegram_proxy.telegram_hosts import ensure_telegram_hosts

            ensure_telegram_hosts()
            return TelegramProxyActionResult(True, "", "", "")
        except Exception as e:
            return TelegramProxyActionResult(False, f"Telegram hosts check error: {e}", "", "")
