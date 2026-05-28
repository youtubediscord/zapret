from __future__ import annotations

from PyQt6.QtCore import QThread, pyqtSignal

from log.log import log


class DpiSettingsWorker(QThread):
    completed = pyqtSignal(int, str, object)
    failed = pyqtSignal(int, str, str)

    def __init__(
        self,
        request_id: int,
        *,
        action: str,
        method: str = "",
        parent=None,
    ):
        super().__init__(parent)
        self._request_id = int(request_id)
        self._action = str(action or "").strip()
        self._method = str(method or "").strip()

    def run(self) -> None:
        import settings.dpi.commands as dpi_commands

        try:
            if self._action == "load_initial_state":
                initial = dpi_commands.load_initial_state()
                result = {
                    "initial": initial,
                    "orchestra_settings": (
                        dpi_commands.load_orchestra_settings()
                        if initial.visibility.show_orchestra_settings
                        else None
                    ),
                }
            elif self._action == "apply_launch_method":
                launch_method = dpi_commands.apply_launch_method(self._method)
                visibility = dpi_commands.describe_visibility(launch_method)
                result = {
                    "launch_method": launch_method,
                    "visibility": visibility,
                    "orchestra_settings": (
                        dpi_commands.load_orchestra_settings()
                        if visibility.show_orchestra_settings
                        else None
                    ),
                }
            else:
                raise ValueError(f"Неизвестное действие DPI-настроек: {self._action}")
        except Exception as exc:
            log(f"DpiSettingsWorker: не удалось выполнить {self._action}: {exc}", "WARNING")
            self.failed.emit(self._request_id, self._action, str(exc))
            return
        self.completed.emit(self._request_id, self._action, result)
