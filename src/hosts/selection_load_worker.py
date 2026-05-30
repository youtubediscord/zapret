from __future__ import annotations

from PyQt6.QtCore import QThread, pyqtSignal

from log.log import log


class HostsSelectionLoadWorker(QThread):
    """Загружает выбранные hosts-профили вне UI-потока."""

    loaded = pyqtSignal(int, object)
    failed = pyqtSignal(int, str)

    def __init__(self, request_id: int, *, load_user_selection, parent=None):
        super().__init__(parent)
        self._request_id = int(request_id)
        self._load_user_selection = load_user_selection

    def run(self) -> None:
        try:
            selection = dict(self._load_user_selection() or {})
        except Exception as exc:
            log(f"HostsSelectionLoadWorker: не удалось загрузить выбор hosts: {exc}", "ERROR")
            self.failed.emit(self._request_id, str(exc))
            return
        self.loaded.emit(self._request_id, selection)
