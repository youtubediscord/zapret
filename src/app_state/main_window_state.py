from __future__ import annotations

from dataclasses import dataclass, replace
from threading import RLock
from typing import Callable, Iterable


@dataclass(frozen=True, slots=True)
class AppUiState:
    launch_method: str = ""
    launch_phase: str = "stopped"
    launch_running: bool = False
    launch_busy: bool = False
    launch_busy_text: str = ""
    launch_expected_process: str = ""
    launch_pid: int | None = None
    launch_last_error: str = ""
    current_strategy_summary: str = ""
    autostart_enabled: bool = False
    subscription_is_premium: bool = False
    subscription_days_remaining: int | None = None
    garland_enabled: bool = False
    snowflakes_enabled: bool = False
    window_opacity: int = 100
    active_preset_revision: int = 0
    preset_content_revision: int = 0
    preset_structure_revision: int = 0
    mode_revision: int = 0


UiStateCallback = Callable[[AppUiState, frozenset[str]], None]


class MainWindowStateStore:
    """Единый store состояния окна без зависимости от QWidget/QObject."""

    def __init__(self, initial_state: AppUiState | None = None) -> None:
        self._state = initial_state or AppUiState()
        self._lock = RLock()
        self._subscribers: list[tuple[frozenset[str] | None, UiStateCallback]] = []

    def snapshot(self) -> AppUiState:
        with self._lock:
            return replace(self._state)

    def subscribe(
        self,
        callback: UiStateCallback,
        *,
        fields: Iterable[str] | None = None,
        emit_initial: bool = False,
    ) -> Callable[[], None]:
        watched_fields = frozenset(fields) if fields is not None else None
        with self._lock:
            self._subscribers.append((watched_fields, callback))

        if emit_initial:
            callback(self.snapshot(), frozenset())

        def _unsubscribe() -> None:
            with self._lock:
                try:
                    self._subscribers.remove((watched_fields, callback))
                except ValueError:
                    pass

        return _unsubscribe

    def update(self, **changes) -> bool:
        if not changes:
            return False

        with self._lock:
            state = self._state
            real_changes = {}
            for field_name, value in changes.items():
                if not hasattr(state, field_name):
                    continue
                if getattr(state, field_name) != value:
                    real_changes[field_name] = value

            if not real_changes:
                return False

            self._state = replace(state, **real_changes)
            snapshot = replace(self._state)
            subscribers = list(self._subscribers)

        changed_fields = frozenset(real_changes.keys())
        for watched_fields, callback in subscribers:
            if watched_fields is None or watched_fields & changed_fields:
                callback(snapshot, changed_fields)

        return True

    def set_launch_busy(self, busy: bool, text: str = "") -> bool:
        if not busy:
            text = ""
        return self.update(launch_busy=bool(busy), launch_busy_text=str(text or ""))

    def set_current_strategy_summary(self, summary: str) -> bool:
        return self.update(current_strategy_summary=str(summary or ""))

    def set_autostart(self, enabled: bool) -> bool:
        return self.update(autostart_enabled=bool(enabled))

    def set_subscription(self, is_premium: bool, days_remaining: int | None = None) -> bool:
        normalized_days = None if not is_premium else days_remaining
        return self.update(
            subscription_is_premium=bool(is_premium),
            subscription_days_remaining=normalized_days,
        )

    def set_holiday_overlays(self, garland_enabled: bool, snowflakes_enabled: bool) -> bool:
        return self.update(
            garland_enabled=bool(garland_enabled),
            snowflakes_enabled=bool(snowflakes_enabled),
        )

    def set_window_opacity_value(self, value: int) -> bool:
        return self.update(window_opacity=max(0, min(100, int(value))))

    def bump_active_preset_revision(self) -> bool:
        current = self.snapshot().active_preset_revision
        return self.update(active_preset_revision=int(current) + 1)

    def bump_preset_content_revision(self) -> bool:
        current = self.snapshot().preset_content_revision
        return self.update(preset_content_revision=int(current) + 1)

    def bump_preset_structure_revision(self) -> bool:
        current = self.snapshot().preset_structure_revision
        return self.update(preset_structure_revision=int(current) + 1)

    def bump_mode_revision(self) -> bool:
        current = self.snapshot().mode_revision
        return self.update(mode_revision=int(current) + 1)
