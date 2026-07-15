from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
import weakref

from settings.schema import (
    TRAY_CLOSE_MODE_MINIMIZE_AND_CLOSE,
    TRAY_CLOSE_MODE_MINIMIZE_ONLY,
    TRAY_CLOSE_MODE_NORMAL,
    VALID_TRAY_CLOSE_MODES,
)


@dataclass(frozen=True, slots=True)
class ProgramSettingsSnapshot:
    revision: tuple[bool, bool, str, bool, bool, bool]
    auto_dpi_enabled: bool
    gui_autostart_enabled: bool
    tray_close_mode: str
    defender_disabled: bool
    max_blocked: bool
    russian_state_media_blocked: bool


_warmed_tray_close_mode_lock = RLock()
_warmed_tray_close_mode: str | None = None


def normalize_tray_close_mode(value: object) -> str:
    normalized = str(value or "").strip()
    return normalized if normalized in VALID_TRAY_CLOSE_MODES else TRAY_CLOSE_MODE_NORMAL


def store_warmed_tray_close_mode(mode: str | None) -> None:
    global _warmed_tray_close_mode
    normalized = None if mode is None else normalize_tray_close_mode(mode)
    with _warmed_tray_close_mode_lock:
        _warmed_tray_close_mode = normalized


def peek_warmed_tray_close_mode() -> str | None:
    with _warmed_tray_close_mode_lock:
        return _warmed_tray_close_mode


class ProgramSettingsRuntimeService:
    """Service-owned snapshot for shared program settings toggle state.

    Эти настройки используются сразу несколькими control-страницами. Страницы
    не должны каждая по отдельности считать себя владельцем синхронизации
    состояния через on_page_activated().
    """

    def __init__(self) -> None:
        self._lock = RLock()
        self._tray_close_mode_cache: str | None = peek_warmed_tray_close_mode()
        self._snapshot: ProgramSettingsSnapshot | None = None
        self._subscribers: list[object] = []

    @staticmethod
    def _build_snapshot(
        *,
        auto_dpi_enabled: bool,
        gui_autostart_enabled: bool,
        tray_close_mode: str,
        defender_disabled: bool,
        max_blocked: bool,
        russian_state_media_blocked: bool,
    ) -> ProgramSettingsSnapshot:
        normalized_tray_close_mode = normalize_tray_close_mode(tray_close_mode)
        revision = (
            bool(auto_dpi_enabled),
            bool(gui_autostart_enabled),
            normalized_tray_close_mode,
            bool(defender_disabled),
            bool(max_blocked),
            bool(russian_state_media_blocked),
        )
        return ProgramSettingsSnapshot(
            revision=revision,
            auto_dpi_enabled=bool(auto_dpi_enabled),
            gui_autostart_enabled=bool(gui_autostart_enabled),
            tray_close_mode=normalized_tray_close_mode,
            defender_disabled=bool(defender_disabled),
            max_blocked=bool(max_blocked),
            russian_state_media_blocked=bool(russian_state_media_blocked),
        )

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
            tray_close_mode=window.get("tray_close_mode", TRAY_CLOSE_MODE_NORMAL),
            defender_disabled=bool(program.get("defender_disabled", False)),
            max_blocked=bool(program.get("max_blocked", False)),
            russian_state_media_blocked=bool(program.get("russian_state_media_blocked", False)),
        )

    def read_snapshot(self) -> ProgramSettingsSnapshot:
        return self.refresh_fast()

    def publish_snapshot(self, snapshot: ProgramSettingsSnapshot) -> bool:
        should_notify = False
        with self._lock:
            previous = self._snapshot
            self._tray_close_mode_cache = normalize_tray_close_mode(snapshot.tray_close_mode)
            if previous is None or previous.revision != snapshot.revision:
                self._snapshot = snapshot
                should_notify = True
            else:
                snapshot = previous

        if should_notify:
            self._notify(snapshot)
        return should_notify

    def peek_tray_close_mode(self, *, default: str = TRAY_CLOSE_MODE_NORMAL) -> str:
        with self._lock:
            snapshot = self._snapshot
            cached = self._tray_close_mode_cache
        if snapshot is not None:
            return normalize_tray_close_mode(snapshot.tray_close_mode)
        if cached is not None:
            return normalize_tray_close_mode(cached)
        return normalize_tray_close_mode(default)

    def remember_tray_close_mode(self, mode: str) -> bool:
        normalized_mode = normalize_tray_close_mode(mode)
        with self._lock:
            self._tray_close_mode_cache = normalized_mode
            snapshot = self._snapshot
        if snapshot is None:
            return False
        updated = ProgramSettingsSnapshot(
            revision=(
                bool(snapshot.auto_dpi_enabled),
                bool(snapshot.gui_autostart_enabled),
                normalized_mode,
                bool(snapshot.defender_disabled),
                bool(snapshot.max_blocked),
                bool(snapshot.russian_state_media_blocked),
            ),
            auto_dpi_enabled=bool(snapshot.auto_dpi_enabled),
            gui_autostart_enabled=bool(snapshot.gui_autostart_enabled),
            tray_close_mode=normalized_mode,
            defender_disabled=bool(snapshot.defender_disabled),
            max_blocked=bool(snapshot.max_blocked),
            russian_state_media_blocked=bool(snapshot.russian_state_media_blocked),
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
