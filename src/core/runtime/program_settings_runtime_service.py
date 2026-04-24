from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
import weakref


@dataclass(frozen=True, slots=True)
class ProgramSettingsSnapshot:
    revision: tuple[bool, bool, bool]
    auto_dpi_enabled: bool
    defender_disabled: bool
    max_blocked: bool


class ProgramSettingsRuntimeService:
    """Service-owned snapshot for shared program settings toggle state.

    Эти настройки используются сразу несколькими control-страницами. Страницы
    не должны каждая по отдельности считать себя владельцем синхронизации
    состояния через on_page_activated().
    """

    def __init__(self) -> None:
        self._lock = RLock()
        self._snapshot: ProgramSettingsSnapshot | None = None
        self._subscribers: list[object] = []

    @staticmethod
    def _read_auto_dpi_enabled() -> bool:
        try:
            from settings.store import get_dpi_autostart


            return bool(get_dpi_autostart())
        except Exception:
            return False

    @staticmethod
    def _read_defender_disabled() -> bool:
        try:
            from altmenu.defender_manager import WindowsDefenderManager

            return bool(WindowsDefenderManager().is_defender_disabled())
        except Exception:
            return False

    @staticmethod
    def _read_max_blocked() -> bool:
        try:
            from altmenu.max_blocker import is_max_blocked

            return bool(is_max_blocked())
        except Exception:
            return False

    def _read_snapshot(self) -> ProgramSettingsSnapshot:
        auto_dpi_enabled = self._read_auto_dpi_enabled()
        defender_disabled = self._read_defender_disabled()
        max_blocked = self._read_max_blocked()
        revision = (
            bool(auto_dpi_enabled),
            bool(defender_disabled),
            bool(max_blocked),
        )
        return ProgramSettingsSnapshot(
            revision=revision,
            auto_dpi_enabled=auto_dpi_enabled,
            defender_disabled=defender_disabled,
            max_blocked=max_blocked,
        )

    @staticmethod
    def _make_callback_ref(callback):
        try:
            return weakref.WeakMethod(callback)
        except TypeError:
            try:
                return weakref.ref(callback)
            except TypeError:
                return lambda: callback

    def _resolve_callback(self, ref):
        try:
            return ref()
        except Exception:
            return None

    def _notify(self, snapshot: ProgramSettingsSnapshot) -> None:
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

    def load_snapshot(self, *, refresh: bool = False) -> ProgramSettingsSnapshot:
        with self._lock:
            snapshot = self._snapshot
        if snapshot is None or refresh:
            return self.refresh()
        return snapshot

    def refresh(self) -> ProgramSettingsSnapshot:
        snapshot = self._read_snapshot()

        should_notify = False
        with self._lock:
            previous = self._snapshot
            if previous is None or previous.revision != snapshot.revision:
                self._snapshot = snapshot
                should_notify = True
            else:
                snapshot = previous

        if should_notify:
            self._notify(snapshot)
        return snapshot

    def subscribe(self, callback, *, emit_initial: bool = False):
        ref = self._make_callback_ref(callback)
        with self._lock:
            self._subscribers.append(ref)

        if emit_initial:
            try:
                callback(self.load_snapshot())
            except Exception:
                pass

        def _unsubscribe() -> None:
            with self._lock:
                self._subscribers = [item for item in self._subscribers if item is not ref]

        return _unsubscribe
