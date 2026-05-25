from __future__ import annotations

import os
import sys
import threading
import time
from dataclasses import dataclass

from main.runtime_state import startup_elapsed_ms


_AUDIT_LOCK = threading.RLock()
_AUDIT_EVENTS: list["StartupAuditEvent"] = []
_AUDIT_NEXT_ID = 0
_WATCHDOG_INSTALLED = False
_SUMMARY_INSTALLED = False
_WATCHDOG_TIMER = None
_SUMMARY_TIMER = None


@dataclass(frozen=True, slots=True)
class StartupAuditEvent:
    task_id: int
    kind: str
    name: str
    thread_name: str
    started_ms: int
    elapsed_ms: int
    rss_start_mb: float
    rss_end_mb: float


def is_startup_audit_enabled() -> bool:
    raw = os.environ.get("ZAPRET_STARTUP_AUDIT")
    if raw is not None and str(raw).strip() != "":
        return str(raw).strip().lower() not in {"0", "false", "no", "off"}

    args = {str(arg).strip().lower() for arg in sys.argv[1:]}
    if "--no-startup-audit" in args:
        return False
    if "--startup-audit" in args:
        return True

    # Временно включено по умолчанию, чтобы собрать карту первого запуска.
    return True


def audit_task_begin(name: str, kind: str = "task") -> int:
    if not is_startup_audit_enabled():
        return 0

    task_id = _next_task_id()
    _log_audit(
        "begin",
        name=name,
        kind=kind,
        task_id=task_id,
        rss_mb=_process_rss_mb(),
    )
    return task_id


def audit_task_end(task_id: int, name: str, kind: str = "task") -> None:
    if not task_id or not is_startup_audit_enabled():
        return

    end_ms = startup_elapsed_ms()
    rss_end = _process_rss_mb()
    event = StartupAuditEvent(
        task_id=int(task_id),
        kind=str(kind or "task"),
        name=str(name or ""),
        thread_name=threading.current_thread().name,
        started_ms=_TASK_START_MS.pop(int(task_id), end_ms),
        elapsed_ms=0,
        rss_start_mb=_TASK_START_RSS_MB.pop(int(task_id), rss_end),
        rss_end_mb=rss_end,
    )
    event = StartupAuditEvent(
        task_id=event.task_id,
        kind=event.kind,
        name=event.name,
        thread_name=event.thread_name,
        started_ms=event.started_ms,
        elapsed_ms=max(0, end_ms - event.started_ms),
        rss_start_mb=event.rss_start_mb,
        rss_end_mb=event.rss_end_mb,
    )
    with _AUDIT_LOCK:
        _AUDIT_EVENTS.append(event)
    _log_audit(
        "end",
        name=name,
        kind=kind,
        task_id=task_id,
        elapsed_ms=event.elapsed_ms,
        rss_mb=rss_end,
        rss_delta_mb=rss_end - event.rss_start_mb,
    )


def audit_timer_queued(name: str, delay_ms: int) -> None:
    if not is_startup_audit_enabled():
        return
    _log_audit("timer_queued", name=name, kind="timer", delay_ms=int(delay_ms))


def audit_timer_fired(name: str, delay_ms: int) -> None:
    if not is_startup_audit_enabled():
        return
    _log_audit("timer_fired", name=name, kind="timer", delay_ms=int(delay_ms), rss_mb=_process_rss_mb())


def install_startup_audit(*, watchdog_interval_ms: int = 100, lag_threshold_ms: int = 220, summary_after_ms: int = 15_000) -> None:
    if not is_startup_audit_enabled():
        return

    try:
        from PyQt6.QtCore import QTimer
        from PyQt6.QtWidgets import QApplication
    except Exception:
        return

    app = QApplication.instance()
    if app is None:
        return

    _install_watchdog(QTimer, app, watchdog_interval_ms, lag_threshold_ms)
    _install_summary_timer(QTimer, app, summary_after_ms)


def log_startup_audit_summary() -> None:
    if not is_startup_audit_enabled():
        return
    with _AUDIT_LOCK:
        events = tuple(_AUDIT_EVENTS)
    if not events:
        _log_audit("summary", name="tasks", kind="summary", details="no recorded tasks")
        return

    top = sorted(events, key=lambda item: item.elapsed_ms, reverse=True)[:10]
    parts = [
        f"{event.kind}:{event.name}={event.elapsed_ms}ms/rss{event.rss_end_mb - event.rss_start_mb:+.1f}MB/{event.thread_name}"
        for event in top
    ]
    _log_audit("summary", name="top_tasks", kind="summary", details=", ".join(parts))


def process_memory_details() -> str:
    if not is_startup_audit_enabled():
        return ""
    return f"rss={_process_rss_mb():.1f}MB"


_TASK_START_MS: dict[int, int] = {}
_TASK_START_RSS_MB: dict[int, float] = {}


def _next_task_id() -> int:
    global _AUDIT_NEXT_ID
    with _AUDIT_LOCK:
        _AUDIT_NEXT_ID += 1
        task_id = _AUDIT_NEXT_ID
        _TASK_START_MS[task_id] = startup_elapsed_ms()
        _TASK_START_RSS_MB[task_id] = _process_rss_mb()
        return task_id


def _install_watchdog(qtimer_cls, parent, interval_ms: int, threshold_ms: int) -> None:
    global _WATCHDOG_INSTALLED, _WATCHDOG_TIMER
    if _WATCHDOG_INSTALLED:
        return
    _WATCHDOG_INSTALLED = True

    last_tick = time.perf_counter()
    timer = qtimer_cls(parent)
    timer.setInterval(max(20, int(interval_ms)))

    def _tick() -> None:
        nonlocal last_tick
        now = time.perf_counter()
        delta_ms = int((now - last_tick) * 1000)
        last_tick = now
        lag_ms = delta_ms - max(20, int(interval_ms))
        if lag_ms >= int(threshold_ms):
            _log_audit(
                "gui_lag",
                name="qt_event_loop",
                kind="gui",
                elapsed_ms=lag_ms,
                rss_mb=_process_rss_mb(),
            )

    timer.timeout.connect(_tick)
    timer.start()
    _WATCHDOG_TIMER = timer
    _log_audit("watchdog_started", name="qt_event_loop", kind="gui", delay_ms=int(interval_ms))


def _install_summary_timer(qtimer_cls, parent, delay_ms: int) -> None:
    global _SUMMARY_INSTALLED, _SUMMARY_TIMER
    if _SUMMARY_INSTALLED:
        return
    _SUMMARY_INSTALLED = True
    timer = qtimer_cls(parent)
    timer.setSingleShot(True)
    timer.timeout.connect(log_startup_audit_summary)
    timer.start(max(1000, int(delay_ms)))
    _SUMMARY_TIMER = timer
    _log_audit("summary_queued", name="top_tasks", kind="summary", delay_ms=int(delay_ms))


def _process_rss_mb() -> float:
    try:
        import psutil

        return float(psutil.Process().memory_info().rss) / (1024.0 * 1024.0)
    except Exception:
        return 0.0


def _log_audit(
    action: str,
    *,
    name: str,
    kind: str,
    task_id: int | None = None,
    delay_ms: int | None = None,
    elapsed_ms: int | None = None,
    rss_mb: float | None = None,
    rss_delta_mb: float | None = None,
    details: str = "",
) -> None:
    try:
        from log.log import log

        fields = [
            f"action={action}",
            f"kind={kind}",
            f"name={name}",
            f"at={startup_elapsed_ms()}ms",
            f"thread={threading.current_thread().name}",
        ]
        if task_id is not None:
            fields.append(f"id={int(task_id)}")
        if delay_ms is not None:
            fields.append(f"delay={int(delay_ms)}ms")
        if elapsed_ms is not None:
            fields.append(f"elapsed={int(elapsed_ms)}ms")
        if rss_mb is not None:
            fields.append(f"rss={float(rss_mb):.1f}MB")
        if rss_delta_mb is not None:
            fields.append(f"rss_delta={float(rss_delta_mb):+.1f}MB")
        if details:
            fields.append(str(details))
        log("[STARTUP_AUDIT] " + " ".join(fields), "⏱ STARTUP")
    except Exception:
        pass


__all__ = [
    "audit_task_begin",
    "audit_task_end",
    "audit_timer_fired",
    "audit_timer_queued",
    "install_startup_audit",
    "is_startup_audit_enabled",
    "log_startup_audit_summary",
    "process_memory_details",
]
