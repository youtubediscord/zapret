from __future__ import annotations

from PyQt6.QtCore import QThread, pyqtSignal

from settings.mode import ZAPRET2_MODE


class AdvancedSettingsLoadWorker(QThread):
    loaded = pyqtSignal(int, dict)

    def __init__(self, request_id: int, profile_feature, parent=None):
        super().__init__(parent)
        self._request_id = int(request_id)
        self._profile = profile_feature

    def run(self) -> None:
        state: dict = {}
        try:
            state = self._profile.get_advanced_settings_state(ZAPRET2_MODE) or {}
        except Exception:
            state = {}
        self.loaded.emit(self._request_id, state)
