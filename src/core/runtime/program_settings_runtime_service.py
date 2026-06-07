from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
import weakref


@dataclass(frozen=True, slots=True)
class ProgramSettingsSnapshot:
    revision: tuple[bool, bool, bool, bool, bool]
    auto_dpi_enabled: bool
    gui_autostart_enabled: bool
    hide_to_tray_on_minimize_close: bool
    defender_disabled: bool
    max_blocked: bool


_warmed_hide_to_tray_lock = RLock()
_warmed_hide_to_tray_on_minimize_close: bool | None = None


def store_warmed_hide_to_tray_on_minimize_close(enabled: bool | None) -> None:
    global _warmed_hide_to_tray_on_minimize_close
    normalized = None if enabled is None else bool(enabled)
    with _warmed_hide_to_tray_lock:
        _warmed_hide_to_tray_on_minimize_close = normalized


def peek_warmed_hide_to_tray_on_minimize_close() -> bool | None:
    with _warmed_hide_to_tray_lock:
        return _warmed_hide_to_tray_on_minimize_close


class ProgramSettingsRuntimeService:
    """Service-owned snapshot for shared program settings toggle state.

    Эти настройки используются сразу несколькими control-страницами. Страницы
    не должны каждая по отдельности считать себя владельцем синхронизации
    состояния через on_page_activated().
    """

    def __init__(self) -> None:
        self._lock = RLock()
        self._hide_to_tray_on_minimize_close_cache: bool | None = (
            peek_warmed_hide_to_tray_on_minimize_close()
        )
        self._snapshot: ProgramSettingsSnapshot | None = None
        self._subscribers: list[object] = []

    @staticmethod
    def _build_snapshot(
        *,
        auto_dpi_enabled: bool,
        gui_autostart_enabled: bool,
        hide_to_tray_on_minimize_close: bool,
        defender_disabled: bool,
        max_blocked: bool,
    ) -> ProgramSettingsSnapshot:
        revision = (
            bool(auto_dpi_enabled),
            bool(gui_autostart_enabled),
            bool(hide_to_tray_on_minimize_close),
            bool(defender_disabled),
            bool(max_blocked),
        )
        return ProgramSettingsSnapshot(
            revision=revision,
            auto_dpi_enabled=bool(auto_dpi_enabled),
            gui_autostart_enabled=bool(gui_autostart_enabled),
            hide_to_tray_on_minimize_close=bool(hide_to_tray_on_minimize_close),
            defender_disabled=bool(defender_disabled),
            max_blocked=bool(max_blocked),
        )

    @staticmethod
    def _read_defender_disabled() -> bool:
        try:
            from windows_features.defender_manager import WindowsDefenderManager

            return bool(WindowsDefenderManager().is_defender_disabled())
        except Exception:
            return False

    @staticmethod
    def _read_max_blocked() -> bool:
        try:
            from windows_features.max_blocker import is_max_blocked

            return bool(is_max_blocked())
        except Exception:
            return False

    def _read_fast_snapshot(self) -> ProgramSettingsSnapshot:
        try:
            from settings.store import read_settings

            settings = read_settings()
        except Exception:
            settings = {}
        program = settings.get("program") if isinstance(settings, dict) else {}
        if not isinstance(program, dict):
            program = {}
        window = settings.get("window") if isinstance(settings, dict) else {}
        if not isinstance(window, dict):
            window = {}

        return self._build_snapshot(
            auto_dpi_enabled=bool(program.get("dpi_autostart", True)),
            gui_autostart_enabled=bool(program.get("gui_autostart_enabled", False)),
            hide_to_tray_on_minimize_close=bool(window.get("hide_to_tray_on_minimize_close", False)),
            defender_disabled=bool(program.get("defender_disabled", False)),
            max_blocked=bool(program.get("max_blocked", False)),
        )

    def _read_system_status_snapshot(self) -> ProgramSettingsSnapshot:
        defender_disabled = self._read_defender_disabled()
        max_blocked = self._read_max_blocked()
        with self._lock:
            snapshot = self._snapshot
        if snapshot is None:
            snapshot = self._read_fast_snapshot()
        return self._build_snapshot(
            auto_dpi_enabled=bool(snapshot.auto_dpi_enabled),
            gui_autostart_enabled=bool(snapshot.gui_autostart_enabled),
            hide_to_tray_on_minimize_close=bool(snapshot.hide_to_tray_on_minimize_close),
            defender_disabled=defender_disabled,
            max_blocked=max_blocked,
        )

    def read_snapshot(self) -> ProgramSettingsSnapshot:
        return self.refresh_fast()

    def publish_snapshot(self, snapshot: ProgramSettingsSnapshot) -> bool:
        should_notify = False
        with self._lock:
            previous = self._snapshot
            self._hide_to_tray_on_minimize_close_cache = bool(
                snapshot.hide_to_tray_on_minimize_close
            )
            if previous is None or previous.revision != snapshot.revision:
                self._snapshot = snapshot
                should_notify = True
            else:
                snapshot = previous

        if should_notify:
            self._notify(snapshot)
        return should_notify

    def peek_hide_to_tray_on_minimize_close(self, *, default: bool = False) -> bool:
        with self._lock:
            snapshot = self._snapshot
            cached = self._hide_to_tray_on_minimize_close_cache
        if snapshot is not None:
            return bool(snapshot.hide_to_tray_on_minimize_close)
        if cached is not None:
            return bool(cached)
        return bool(default)

    def remember_hide_to_tray_on_minimize_close(self, enabled: bool) -> bool:
        enabled = bool(enabled)
        with self._lock:
            self._hide_to_tray_on_minimize_close_cache = enabled
            snapshot = self._snapshot
        if snapshot is None:
            return False
        updated = ProgramSettingsSnapshot(
            revision=(
                bool(snapshot.auto_dpi_enabled),
                bool(snapshot.gui_autostart_enabled),
                enabled,
                bool(snapshot.defender_disabled),
                bool(snapshot.max_blocked),
            ),
            auto_dpi_enabled=bool(snapshot.auto_dpi_enabled),
            gui_autostart_enabled=bool(snapshot.gui_autostart_enabled),
            hide_to_tray_on_minimize_close=enabled,
            defender_disabled=bool(snapshot.defender_disabled),
            max_blocked=bool(snapshot.max_blocked),
        )
        return self.publish_snapshot(updated)

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
        _ = refresh
        return self.refresh_fast()

    def refresh(self) -> ProgramSettingsSnapshot:
        return self.refresh_fast()

    def refresh_fast(self) -> ProgramSettingsSnapshot:
        snapshot = self._read_fast_snapshot()
        self.publish_snapshot(snapshot)
        return snapshot

    def refresh_system_status(self) -> ProgramSettingsSnapshot:
        snapshot = self._read_system_status_snapshot()
        self.publish_snapshot(snapshot)
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
