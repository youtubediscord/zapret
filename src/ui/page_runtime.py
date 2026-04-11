from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, TypeVar


SnapshotT = TypeVar("SnapshotT")


class PageLoadController:
    """Управляет поколениями фоновых задач страницы.

    Страница может выдавать токен перед запуском асинхронной работы и затем
    проверять, актуален ли он ещё к моменту применения результата. Это даёт
    единый канонический путь для "отмены" устаревшей догрузки без жёсткого
    убийства потоков.
    """

    def __init__(self) -> None:
        self._generation = 0

    def issue(self, reason: str | None = None) -> int:
        _ = reason
        self._generation += 1
        return self._generation

    def cancel(self, reason: str | None = None) -> int:
        _ = reason
        self._generation += 1
        return self._generation

    def is_current(self, token: int) -> bool:
        return int(token) == int(self._generation)


@dataclass(slots=True)
class PageSnapshot(Generic[SnapshotT]):
    revision: object | None
    value: SnapshotT | None


class PageSnapshotCache(Generic[SnapshotT]):
    """Минимальный общий кэш снимка состояния страницы."""

    def __init__(self) -> None:
        self._revision: object | None = None
        self._value: SnapshotT | None = None

    def get(self) -> PageSnapshot[SnapshotT]:
        return PageSnapshot(revision=self._revision, value=self._value)

    def store(self, value: SnapshotT, *, revision: object | None = None) -> PageSnapshot[SnapshotT]:
        self._revision = revision
        self._value = value
        return self.get()

    def clear(self) -> None:
        self._revision = None
        self._value = None

    def has_value(self) -> bool:
        return self._value is not None

    def matches(self, revision: object | None) -> bool:
        return self._value is not None and self._revision == revision
