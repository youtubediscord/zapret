from __future__ import annotations

from PyQt6.QtCore import QThread, pyqtSignal

from settings.mode import DEFAULT_LAUNCH_METHOD


class AdditionalSettingsLoadWorker(QThread):
    loaded = pyqtSignal(int, dict)

    def __init__(self, request_id: int, profile_feature, *, launch_method: str = DEFAULT_LAUNCH_METHOD, parent=None):
        super().__init__(parent)
        self._request_id = int(request_id)
        self._profile = profile_feature
        self._launch_method = str(launch_method or DEFAULT_LAUNCH_METHOD)

    def run(self) -> None:
        state: dict = {}
        try:
            state = self._profile.get_additional_settings_state(launch_method=self._launch_method) or {}
        except Exception:
            state = {}
        self.loaded.emit(self._request_id, state)
