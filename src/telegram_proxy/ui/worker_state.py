from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from ui.latest_value_worker_state import LatestValueWorkerState
from ui.queued_worker_state import QueuedWorkerState


@dataclass(slots=True)
class TelegramProxyPageWorkerState(LatestValueWorkerState):
    """Состояние одного фонового действия страницы.

    Runtime запускает worker-а, то есть фоновую задачу. Этот объект хранит
    булевый отложенный запрос поверх общего LatestValueWorkerState.
    """

    empty_value: object = False
    pending: object = False

    def start_or_mark_pending(self, start: Callable[[], None]) -> bool:
        return self.request_or_start(True, lambda _value: start())

    def schedule_next(self, single_shot: Callable[[int, Callable[[], None]], None], start: Callable[[], None]) -> None:
        if self.start_scheduled:
            self.pending = True
            return
        LatestValueWorkerState.schedule_start(
            self,
            single_shot,
            lambda: self.run_scheduled(start),
        )

    def schedule_start(self, single_shot: Callable[[int, Callable[[], None]], None], start: Callable[[], None]) -> None:
        self.pending = True
        self.schedule_next(single_shot, start)

    def run_scheduled(self, start: Callable[[], None], *, cleanup_in_progress: bool = False) -> None:
        if not bool(self.take_pending_for_scheduled_start(cleanup_in_progress=cleanup_in_progress)):
            return
        start()

    def schedule_after_finish(
        self,
        worker,
        *,
        is_current_worker_finish: Callable[[object, object], bool],
        schedule_next: Callable[[], None],
        cleanup_in_progress: bool = False,
    ) -> None:
        if not is_current_worker_finish(self.runtime, worker):
            return
        if self.has_pending() and not cleanup_in_progress:
            schedule_next()


TelegramProxyPageQueuedWorkerState = QueuedWorkerState
