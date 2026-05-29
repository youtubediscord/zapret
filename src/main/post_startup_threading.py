from __future__ import annotations

import threading
from dataclasses import dataclass, field
from collections.abc import Callable
from queue import Queue

from PyQt6.QtCore import QTimer

from main import startup_audit


@dataclass(slots=True)
class _SubsystemTaskQueue:
    name: str
    tasks: Queue = field(default_factory=Queue)
    thread: threading.Thread | None = None

    def ensure_started(self) -> threading.Thread:
        if self.thread is not None and self.thread.is_alive():
            return self.thread
        thread_name = f"StartupQueue-{self.name}"
        self.thread = threading.Thread(
            target=self._run,
            daemon=True,
            name=thread_name,
        )
        self.thread.start()
        return self.thread

    def put(self, task_name: str, target: Callable[[], None]) -> threading.Thread:
        thread = self.ensure_started()
        self.tasks.put((str(task_name or self.name), target))
        return thread

    def _run(self) -> None:
        while True:
            task_name, target = self.tasks.get()
            try:
                _run_audited_target(task_name, target)
            finally:
                self.tasks.task_done()


_SUBSYSTEM_QUEUES: dict[str, _SubsystemTaskQueue] = {}
_SUBSYSTEM_QUEUES_LOCK = threading.RLock()


def start_daemon_thread(name: str, target: Callable[[], None]) -> threading.Thread:
    thread_name = str(name or "StartupPostInitWorker")
    thread = threading.Thread(
        target=lambda: _run_audited_target(thread_name, target),
        daemon=True,
        name=thread_name,
    )
    thread.start()
    return thread


def enqueue_subsystem_task(
    queue_name: str,
    task_name: str,
    target: Callable[[], None],
) -> threading.Thread:
    """Ставит фоновую startup-задачу в отдельную очередь подсистемы."""
    normalized_queue_name = str(queue_name or "default").strip() or "default"
    with _SUBSYSTEM_QUEUES_LOCK:
        task_queue = _SUBSYSTEM_QUEUES.get(normalized_queue_name)
        if task_queue is None:
            task_queue = _SubsystemTaskQueue(normalized_queue_name)
            _SUBSYSTEM_QUEUES[normalized_queue_name] = task_queue
        return task_queue.put(task_name, target)


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
