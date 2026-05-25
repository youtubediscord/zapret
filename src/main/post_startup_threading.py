from __future__ import annotations

import threading
from collections.abc import Callable

from PyQt6.QtCore import QTimer

from main import startup_audit


def start_daemon_thread(name: str, target: Callable[[], None]) -> threading.Thread:
    thread_name = str(name or "StartupPostInitWorker")
    thread = threading.Thread(
        target=lambda: _run_audited_target(thread_name, target),
        daemon=True,
        name=thread_name,
    )
    thread.start()
    return thread


def schedule_after(delay_ms: int, callback: Callable[[], None]) -> None:
    delay = int(delay_ms)
    callback_name = getattr(callback, "__name__", "startup_timer")
    startup_audit.audit_timer_queued(str(callback_name), delay)

    def _run_callback() -> None:
        startup_audit.audit_timer_fired(str(callback_name), delay)
        callback()

    QTimer.singleShot(delay, _run_callback)


def _run_audited_target(name: str, target: Callable[[], None]) -> None:
    if not startup_audit.is_startup_audit_enabled():
        target()
        return
    task_id = startup_audit.audit_task_begin(str(name or "StartupPostInitWorker"), "thread")
    try:
        target()
    finally:
        startup_audit.audit_task_end(task_id, str(name or "StartupPostInitWorker"), "thread")
