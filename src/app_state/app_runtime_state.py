from __future__ import annotations

from app_state.main_window_state import AppUiState, MainWindowStateStore


class AppRuntimeState:
    """Узкий facade поверх window-level runtime state.

    Этот слой больше не притворяется универсальным writer-ом для всего UI state.
    Его роль сейчас простая и честная:
    - дать внешним use-site'ам безопасные read-helper'ы для launch/autostart state;
    - дать один явный writer для `autostart_enabled`;
    - не подменять собой `MainWindowStateStore` и не дублировать `winws_runtime.state.LaunchRuntimeService`.
    """

    def __init__(self, app_instance_or_store) -> None:
        self.app = None
        self._direct_store = None
        if isinstance(app_instance_or_store, MainWindowStateStore):
            self._direct_store = app_instance_or_store
        else:
            self.app = app_instance_or_store

    def _store(self) -> MainWindowStateStore | None:
        if isinstance(self._direct_store, MainWindowStateStore):
            return self._direct_store
        store = getattr(self.app, "ui_state_store", None)
        if isinstance(store, MainWindowStateStore):
            return store
        return None

    def snapshot(self) -> AppUiState:
        store = self._store()
        if store is None:
            return AppUiState()
        try:
            return store.snapshot()
        except Exception:
            return AppUiState()

    def is_launch_running(self) -> bool:
        return bool(self.snapshot().launch_running)

    def current_launch_phase(self) -> str:
        return str(self.snapshot().launch_phase or "").strip().lower()

    def last_launch_error(self) -> str:
        return str(self.snapshot().launch_last_error or "").strip()

    def is_autostart_enabled(self) -> bool:
        return bool(self.snapshot().autostart_enabled)

    def set_autostart(self, enabled: bool) -> bool:
        store = self._store()
        if store is None:
            return False
        return bool(store.set_autostart(bool(enabled)))

    def sync_autostart_from_registry(self) -> bool:
        return self.set_autostart(self.detect_autostart_enabled())

    @staticmethod
    def detect_autostart_enabled() -> bool:
        try:
            from autostart.autostart_exe import is_autostart_enabled

            return bool(is_autostart_enabled())
        except Exception:
            return False
