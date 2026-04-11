from __future__ import annotations

from ui.main_window_state import AppUiState, MainWindowStateStore


class AppRuntimeState:
    """Единая точка записи и чтения runtime-состояния GUI."""

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

    def is_dpi_running(self) -> bool:
        return bool(self.snapshot().dpi_running)

    def current_dpi_phase(self) -> str:
        return str(self.snapshot().dpi_phase or "").strip().lower()

    def last_dpi_error(self) -> str:
        return str(self.snapshot().dpi_last_error or "").strip()

    def is_autostart_enabled(self) -> bool:
        return bool(self.snapshot().autostart_enabled)

    def apply_runtime_state(
        self,
        *,
        autostart_enabled: bool | None = None,
    ) -> bool:
        store = self._store()
        if store is None:
            return False

        changes: dict[str, object] = {}

        if autostart_enabled is not None:
            changes["autostart_enabled"] = bool(autostart_enabled)

        if not changes:
            return False

        return bool(store.update(**changes))
    def set_autostart(self, enabled: bool) -> bool:
        return self.apply_runtime_state(autostart_enabled=enabled)

    def sync_autostart_from_registry(self) -> bool:
        return self.set_autostart(self.detect_autostart_enabled())

    @staticmethod
    def detect_autostart_enabled() -> bool:
        try:
            from autostart.registry_check import is_autostart_enabled

            return bool(is_autostart_enabled())
        except Exception:
            return False
