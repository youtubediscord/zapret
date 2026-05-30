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
        load_initial_state,
        apply_launch_method,
        describe_visibility,
        load_orchestra_settings,
        method: str = "",
        parent=None,
    ):
        super().__init__(parent)
        self._request_id = int(request_id)
        self._action = str(action or "").strip()
        self._method = str(method or "").strip()
        self._load_initial_state = load_initial_state
        self._apply_launch_method = apply_launch_method
        self._describe_visibility = describe_visibility
        self._load_orchestra_settings = load_orchestra_settings

    def run(self) -> None:
        try:
            if self._action == "load_initial_state":
                initial = self._load_initial_state()
                result = {
                    "initial": initial,
                    "orchestra_settings": (
                        self._load_orchestra_settings()
                        if initial.visibility.show_orchestra_settings
                        else None
                    ),
                }
            elif self._action == "apply_launch_method":
                launch_method = self._apply_launch_method(self._method)
                visibility = self._describe_visibility(launch_method)
                result = {
                    "launch_method": launch_method,
                    "visibility": visibility,
                    "orchestra_settings": (
                        self._load_orchestra_settings()
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
