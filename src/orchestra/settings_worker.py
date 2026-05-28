from __future__ import annotations

from PyQt6.QtCore import QThread, pyqtSignal

from log.log import log


class OrchestraSettingSaveWorker(QThread):
    saved = pyqtSignal(int, str, object)
    failed = pyqtSignal(int, str, str)

    def __init__(
        self,
        request_id: int,
        orchestra_feature,
        *,
        key: str,
        value,
        parent=None,
    ):
        super().__init__(parent)
        self._request_id = int(request_id)
        self._orchestra = orchestra_feature
        self._key = str(key or "").strip()
        self._value = value

    def run(self) -> None:
        try:
            self._orchestra.set_setting(self._key, self._value)
        except Exception as exc:
            log(f"OrchestraSettingSaveWorker: не удалось сохранить {self._key}: {exc}", "ERROR")
            self.failed.emit(self._request_id, self._key, str(exc))
            return
        self.saved.emit(self._request_id, self._key, self._value)
