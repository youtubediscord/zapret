from __future__ import annotations

from PyQt6.QtCore import QThread, pyqtSignal

from log.log import log


class ProgramSettingsLoadWorker(QThread):
    loaded = pyqtSignal(int, object)
    failed = pyqtSignal(int, str)

    def __init__(
        self,
        request_id: int,
        *,
        program_settings_feature,
        parent=None,
    ):
        super().__init__(parent)
        self._request_id = int(request_id)
        self._program_settings = program_settings_feature

    def run(self) -> None:
        try:
            snapshot = self._program_settings.load_program_settings_snapshot()
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
        program_settings_feature,
        parent=None,
    ):
        super().__init__(parent)
        self._request_id = int(request_id)
        self._program_settings = program_settings_feature

    def run(self) -> None:
        try:
            is_admin = bool(self._program_settings.is_user_admin())
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
        parent=None,
    ):
        super().__init__(parent)
        self._request_id = int(request_id)
        self._action = str(action or "").strip()
        self._enabled = bool(enabled)

    def run(self) -> None:
        import program_settings.commands as program_settings_commands

        def emit_status(message: str) -> None:
            self.status.emit(self._request_id, self._action, str(message or ""))

        try:
            if self._action == "auto_dpi":
                result = program_settings_commands.set_auto_dpi_enabled(self._enabled)
            elif self._action == "hide_to_tray":
                result = program_settings_commands.set_hide_to_tray_on_minimize_close(self._enabled)
            elif self._action == "defender_disabled":
                result = program_settings_commands.set_defender_disabled(
                    self._enabled,
                    status_callback=emit_status,
                )
            elif self._action == "max_block":
                result = program_settings_commands.set_max_block_enabled(
                    self._enabled,
                    status_callback=emit_status,
                )
            else:
                raise ValueError(f"Неизвестная настройка программы: {self._action}")
        except Exception as exc:
            log(f"ProgramSettingsSaveWorker: не удалось сохранить {self._action}: {exc}", "WARNING")
            self.failed.emit(self._request_id, self._action, str(exc))
            return
        self.saved.emit(self._request_id, self._action, result)
