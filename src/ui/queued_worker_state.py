from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Generic, Optional, TypeVar


T = TypeVar("T")


@dataclass(slots=True)
class QueuedWorkerState(Generic[T]):
    """Очередь одного фонового действия UI.

    Runtime запускает worker-а, то есть фоновую задачу. Этот объект хранит
    только список отложенных задач и флаг запуска на следующий проход Qt-событий.
    """

    runtime: object
    pending: list[T] | None = None
    start_scheduled: bool = False

    def __post_init__(self) -> None:
        if self.pending is None:
            self.pending = []

    def is_busy(self) -> bool:
        if self.start_scheduled:
            return True
        is_running = getattr(self.runtime, "is_running", None)
        if callable(is_running):
            return bool(is_running())
        return False

    def has_pending(self) -> bool:
        return bool(self.pending)

    def append(self, item: T) -> bool:
        self.pending.append(item)
        return True

    def append_unique(self, item: T, *, key: Callable[[T], object]) -> bool:
        item_key = key(item)
        if item_key and any(key(existing) == item_key for existing in self.pending):
            return False
        self.pending.append(item)
        return True

    def replace_by_key(self, item: T, *, key: Callable[[T], object]) -> bool:
        item_key = key(item)
        self.pending[:] = [
            existing
            for existing in self.pending
            if key(existing) != item_key
        ]
        self.pending.append(item)
        return True

    def pop_next(self) -> Optional[T]:
        if not self.pending:
            return None
        return self.pending.pop(0)

    def start_or_queue(self, item: T, start: Callable[[T], None], queue_item: Callable[[T], bool]) -> bool:
        if self.is_busy():
            queue_item(item)
            return False
        start(item)
        return True

    def schedule_start(
        self,
        item: T,
        single_shot: Callable[[int, Callable[[], None]], None],
        start: Callable[[T], None],
        *,
        queue_item: Callable[[T], bool],
        is_cleanup_in_progress: Callable[[], bool],
    ) -> bool:
        if is_cleanup_in_progress():
            return False
        if self.start_scheduled:
            queue_item(item)
            return False
        self.start_scheduled = True
        single_shot(0, lambda value=item: self.run_scheduled(value, start, is_cleanup_in_progress))
        return True

    def run_scheduled(
        self,
        item: T,
        start: Callable[[T], None],
        is_cleanup_in_progress: Callable[[], bool],
    ) -> None:
        self.start_scheduled = False
        if is_cleanup_in_progress():
            return
        start(item)

    def pop_next_after_finish(
        self,
        worker,
        *,
        is_current_worker_finish: Callable[[object, object], bool],
        cleanup_in_progress: bool = False,
    ) -> Optional[T]:
        if not is_current_worker_finish(self.runtime, worker):
            return None
        if cleanup_in_progress:
            return None
        return self.pop_next()

    def schedule_next_after_finish(
        self,
        worker,
        *,
        is_current_worker_finish: Callable[[object, object], bool],
        single_shot: Callable[[int, Callable[[], None]], None],
        start: Callable[[T], None],
        queue_item: Callable[[T], bool],
        is_cleanup_in_progress: Callable[[], bool],
    ) -> Optional[T]:
        item = self.pop_next_after_finish(
            worker,
            is_current_worker_finish=is_current_worker_finish,
            cleanup_in_progress=is_cleanup_in_progress(),
        )
        if item is None:
            return None
        self.schedule_start(
            item,
            single_shot,
            start,
            queue_item=queue_item,
            is_cleanup_in_progress=is_cleanup_in_progress,
        )
        return item

    def reset(self) -> None:
        self.pending.clear()
        self.start_scheduled = False
