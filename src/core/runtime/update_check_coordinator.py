from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
import time
import weakref


@dataclass(frozen=True, slots=True)
class UpdateCheckSnapshot:
    revision: int
    phase: str
    source: str
    started_at: float
    completed_at: float
    has_update: bool
    version: str
    release_notes: str
    error: str
    skipped: bool
    message: str


class UpdateCheckCoordinator:
    """Единый владелец запуска, очередности и результата проверки обновлений.

    Конкретную сетевую работу выполняют фоновые исполнители, но только координатор
    решает, может ли начаться проверка, принимает её результат по токену и сообщает
    его всем экранам. Это не даёт запуску программы и странице расходиться по состоянию.
    """

    def __init__(self) -> None:
        self._lock = RLock()
        self._revision = 0
        self._snapshot = UpdateCheckSnapshot(
            revision=0,
            phase="idle",
            source="",
            started_at=0.0,
            completed_at=0.0,
            has_update=False,
            version="",
            release_notes="",
            error="",
            skipped=False,
            message="",
        )
        self._subscribers: list[object] = []

    @staticmethod
    def _make_callback_ref(callback):
        try:
            return weakref.WeakMethod(callback)
        except TypeError:
            try:
                return weakref.ref(callback)
            except TypeError:
                return lambda: callback

    @staticmethod
    def _resolve_callback(ref):
        try:
            return ref()
        except Exception:
            return None

    def snapshot(self) -> UpdateCheckSnapshot:
        with self._lock:
            return self._snapshot

    def begin(self, *, source: str) -> int | None:
        normalized_source = str(source or "unknown").strip() or "unknown"
        with self._lock:
            current = self._snapshot
            if current.phase == "checking":
                return None
            if (
                normalized_source == "startup"
                and current.source == "manual"
                and current.phase == "completed"
            ):
                return None

            self._revision += 1
            snapshot = UpdateCheckSnapshot(
                revision=self._revision,
                phase="checking",
                source=normalized_source,
                started_at=time.time(),
                completed_at=0.0,
                has_update=False,
                version="",
                release_notes="",
                error="",
                skipped=False,
                message="",
            )
            self._snapshot = snapshot

        self._notify(snapshot)
        return snapshot.revision

    def finish(self, result: dict, *, source: str, token: int) -> bool:
        normalized_source = str(source or "unknown").strip() or "unknown"
        payload = dict(result or {})

        with self._lock:
            current = self._snapshot
            if (
                current.phase != "checking"
                or current.source != normalized_source
                or current.revision != int(token)
            ):
                return False

            skipped = bool(payload.get("skipped"))
            error = str(payload.get("error") or "")
            phase = "skipped" if skipped else "error" if error else "completed"
            checked_at = payload.get("checked_at")
            try:
                completed_at = max(float(checked_at or 0.0), 0.0)
            except (TypeError, ValueError):
                completed_at = 0.0
            if not skipped and completed_at <= 0:
                completed_at = time.time()

            self._revision += 1
            snapshot = UpdateCheckSnapshot(
                revision=self._revision,
                phase=phase,
                source=normalized_source,
                started_at=current.started_at if current.source == normalized_source else 0.0,
                completed_at=completed_at,
                has_update=bool(payload.get("has_update")) and not error and not skipped,
                version=str(payload.get("version") or ""),
                release_notes=str(payload.get("release_notes") or ""),
                error=error,
                skipped=skipped,
                message=str(payload.get("skip_reason") or payload.get("message") or ""),
            )
            self._snapshot = snapshot

        self._notify(snapshot)
        return True

    def subscribe(self, callback, *, emit_initial: bool = False):
        ref = self._make_callback_ref(callback)
        with self._lock:
            self._subscribers.append(ref)
            snapshot = self._snapshot

        if emit_initial:
            try:
                callback(snapshot)
            except Exception:
                pass

        def _unsubscribe() -> None:
            with self._lock:
                self._subscribers = [item for item in self._subscribers if item is not ref]

        return _unsubscribe

    def _notify(self, snapshot: UpdateCheckSnapshot) -> None:
        callbacks: list = []
        with self._lock:
            alive_refs: list[object] = []
            for ref in self._subscribers:
                callback = self._resolve_callback(ref)
                if callback is None:
                    continue
                alive_refs.append(ref)
                callbacks.append(callback)
            self._subscribers = alive_refs

        for callback in callbacks:
            try:
                callback(snapshot)
            except Exception:
                pass


__all__ = ["UpdateCheckCoordinator", "UpdateCheckSnapshot"]
