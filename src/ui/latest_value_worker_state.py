from __future__ import annotations

from dataclasses import dataclass


_NO_PENDING_UPDATE = object()


@dataclass(slots=True)
class LatestValueWorkerState:
    runtime: object
    empty_value: object = ""
    pending: object = ""
    start_scheduled: bool = False

    def is_busy(self) -> bool:
        if self.start_scheduled:
            return True
        is_running = getattr(self.runtime, "is_running", None)
        if callable(is_running):
            return bool(is_running())
        return False

    def request_or_start(self, value, start) -> bool:
        if self.is_busy():
            self.pending = value
            return False
        self.pending = self.empty_value
        start(value)
        return True

    def has_pending(self) -> bool:
        return self.pending != self.empty_value

    def schedule_pending_after_finish(
        self,
        worker,
        *,
        is_current_worker_finish,
        single_shot,
        run_scheduled,
        cleanup_in_progress: bool = False,
        should_schedule_pending=None,
        clear_pending_before_schedule: bool = False,
    ) -> None:
        if not is_current_worker_finish(self.runtime, worker):
            return
        if cleanup_in_progress or not self.has_pending():
            return
        if callable(should_schedule_pending) and not should_schedule_pending(self.pending):
            self.pending = self.empty_value
            return
        if clear_pending_before_schedule:
            self.pending = self.empty_value
        self.schedule_start(single_shot, run_scheduled, cleanup_in_progress=cleanup_in_progress)

    def schedule_start(
        self,
        single_shot,
        run_scheduled,
        *,
        cleanup_in_progress: bool = False,
        pending_when_already_scheduled=_NO_PENDING_UPDATE,
    ) -> None:
        if cleanup_in_progress:
            return
        if self.start_scheduled:
            if pending_when_already_scheduled is not _NO_PENDING_UPDATE:
                self.pending = pending_when_already_scheduled
            return
        self.start_scheduled = True
        single_shot(0, run_scheduled)

    def take_pending_for_scheduled_start(self, *, cleanup_in_progress: bool = False):
        self.start_scheduled = False
        pending = self.pending
        self.pending = self.empty_value
        if cleanup_in_progress:
            return self.empty_value
        return pending

    def reset(self) -> None:
        self.pending = self.empty_value
        self.start_scheduled = False
