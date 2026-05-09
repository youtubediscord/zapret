from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import QObject, pyqtSignal

from log.log import log
from main.post_startup_gate import bind_startup_gate, is_window_alive
from main.post_startup_maintenance_workers import collect_deferred_maintenance_payload
from main.post_startup_threading import schedule_after, start_daemon_thread

if TYPE_CHECKING:
    from main.window import LupiDPIApp


class _DeferredMaintenanceBridge(QObject):
    finished = pyqtSignal(dict)


def install_deferred_maintenance(window: "LupiDPIApp") -> None:
    deferred_maintenance_bridge = _DeferredMaintenanceBridge()

    def _on_deferred_maintenance_finished(payload: dict) -> None:
        if not is_window_alive(window):
            return
        try:
            controller = getattr(window, "window_notification_controller", None)
            duration_ms = int(payload.get("duration_ms") or 0)
            if duration_ms > 0:
                window.log_startup_metric("StartupPostInitMaintenanceFinished", f"{duration_ms}ms")

            if controller is not None:
                controller.notify_many(payload.get("notifications") or [])
        except Exception as exc:
            log(f"Ошибка поздней служебной проверки: {exc}", "❌ ERROR")

    deferred_maintenance_bridge.finished.connect(_on_deferred_maintenance_finished)

    def _deferred_maintenance_worker() -> None:
        try:
            payload = collect_deferred_maintenance_payload()
        except Exception as exc:
            log(f"Ошибка поздних служебных проверок: {exc}", "❌ ERROR")
            payload = {
                "notifications": [],
                "telega_found_path": None,
                "duration_ms": 0,
            }
        deferred_maintenance_bridge.finished.emit(payload)

    def _start_deferred_maintenance() -> None:
        if not is_window_alive(window):
            return

        window.log_startup_metric("StartupPostInitMaintenanceStarted", "telega_association_worker")
        start_daemon_thread("DeferredMaintenanceWorker", _deferred_maintenance_worker)

    def _schedule_deferred_maintenance() -> None:
        if not is_window_alive(window):
            return
        delay_ms = 6000
        log(
            f"Проверка Telega Desktop и служебные действия отложены на {delay_ms}ms после post-init",
            "DEBUG",
        )
        schedule_after(
            delay_ms,
            lambda: is_window_alive(window) and _start_deferred_maintenance(),
        )

    bind_startup_gate(
        window.startup_post_init_ready,
        _schedule_deferred_maintenance,
        is_ready=lambda: bool(getattr(window, "_startup_post_init_ready", False)),
    )
