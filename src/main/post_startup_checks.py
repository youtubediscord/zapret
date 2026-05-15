from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import QObject, pyqtSignal

from log.log import is_verbose_logging_enabled, log
from main.post_startup_gate import bind_startup_gate, is_window_alive
from main.post_startup_check_workers import collect_startup_checks_payload
from main.post_startup_threading import start_daemon_thread

if TYPE_CHECKING:
    from main.window import LupiDPIApp


class _StartupChecksBridge(QObject):
    finished = pyqtSignal(dict)


def install_startup_checks(
    window: "LupiDPIApp",
    *,
    notify_many,
    set_status,
    log_startup_metric,
) -> None:
    startup_bridge = _StartupChecksBridge()

    def _on_startup_checks_finished(payload: dict) -> None:
        if not is_window_alive(window):
            return
        try:
            notifications = payload.get("notifications") or []
            duration_ms = int(payload.get("duration_ms") or 0)

            if duration_ms > 0:
                log_startup_metric("StartupPostInitChecksFinished", f"{duration_ms}ms")

            notify_many([item for item in notifications if isinstance(item, dict)])

            log("✅ Все проверки пройдены", "🔹 main")
        except Exception as exc:
            log(f"Ошибка при обработке результатов проверок: {exc}", "❌ ERROR")

    startup_bridge.finished.connect(_on_startup_checks_finished)

    def _startup_checks_worker() -> None:
        try:
            payload = collect_startup_checks_payload(
                verbose_logging_enabled=is_verbose_logging_enabled(),
            )
            startup_bridge.finished.emit(payload)
        except Exception as exc:
            log(f"Ошибка при асинхронных проверках: {exc}", "❌ ERROR")
            try:
                set_status(f"Ошибка проверок: {exc}")
            except Exception:
                pass
            startup_bridge.finished.emit(
                {
                    "notifications": [],
                    "duration_ms": 0,
                }
            )

    def _start_startup_checks() -> None:
        log_startup_metric("StartupPostInitChecksStarted", "startup_checks_worker")
        start_daemon_thread("StartupChecksWorker", _startup_checks_worker)

    bind_startup_gate(
        window.startup_interactive_ready,
        _start_startup_checks,
        is_ready=lambda: bool(window.startup_state.interactive_logged),
    )
