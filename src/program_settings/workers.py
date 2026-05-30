from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PyQt6.QtCore import QThread, pyqtSignal

from log.log import log


class ProgramSettingsLoadWorker(QThread):
    loaded = pyqtSignal(int, object)
    failed = pyqtSignal(int, str)

    def __init__(
        self,
        request_id: int,
        *,
        load_program_settings_snapshot: Callable[[], Any],
        parent=None,
    ):
        super().__init__(parent)
        self._request_id = int(request_id)
        self._load_program_settings_snapshot = load_program_settings_snapshot

    def run(self) -> None:
        try:
            snapshot = self._load_program_settings_snapshot()
        except Exception as exc:
            log(f"ProgramSettingsLoadWorker: не удалось загрузить настройки программы: {exc}", "WARNING")
            self.failed.emit(self._request_id, str(exc))
            return
        self.loaded.emit(self._request_id, snapshot)


class ProgramSettingsAdminCheckWorker(QThread):
    loaded = pyqtSignal(int, bool)
    failed = pyqtSignal(int, str)

    def __init__(
        self,
        request_id: int,
        *,
        is_user_admin: Callable[[], bool],
        parent=None,
    ):
        super().__init__(parent)
        self._request_id = int(request_id)
        self._is_user_admin = is_user_admin

    def run(self) -> None:
        try:
            is_admin = bool(self._is_user_admin())
        except Exception as exc:
            log(f"ProgramSettingsAdminCheckWorker: не удалось проверить права администратора: {exc}", "WARNING")
            self.failed.emit(self._request_id, str(exc))
            return
        self.loaded.emit(self._request_id, is_admin)


class ProgramSettingsSaveWorker(QThread):
    saved = pyqtSignal(int, str, object)
    failed = pyqtSignal(int, str, str)
    status = pyqtSignal(int, str, str)

    def __init__(
        self,
        request_id: int,
        *,
        action: str,
        enabled: bool,
        save_action: Callable[..., Any],
        parent=None,
    ):
        super().__init__(parent)
        self._request_id = int(request_id)
        self._action = str(action or "").strip()
        self._enabled = bool(enabled)
        self._save_action = save_action

    def run(self) -> None:
        def emit_status(message: str) -> None:
            self.status.emit(self._request_id, self._action, str(message or ""))

        try:
            result = self._save_action(
                self._enabled,
                status_callback=emit_status,
            )
        except Exception as exc:
            log(f"ProgramSettingsSaveWorker: не удалось сохранить {self._action}: {exc}", "WARNING")
            self.failed.emit(self._request_id, self._action, str(exc))
            return
        self.saved.emit(self._request_id, self._action, result)


class SidebarExpandedStateSaveWorker(QThread):
    saved = pyqtSignal(bool)
    failed = pyqtSignal(str)

    def __init__(
        self,
        *,
        expanded: bool,
        state_key: str,
        save_ui_state_settings: Callable[[dict], Any],
        parent=None,
    ):
        super().__init__(parent)
        self._expanded = bool(expanded)
        self._state_key = str(state_key or "sidebar_expanded")
        self._save_ui_state_settings = save_ui_state_settings

    def run(self) -> None:
        try:
            self._save_ui_state_settings({self._state_key: self._expanded})
        except Exception as exc:
            self.failed.emit(str(exc))
            return
        self.saved.emit(self._expanded)
