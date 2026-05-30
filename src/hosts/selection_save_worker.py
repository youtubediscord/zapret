from __future__ import annotations

from PyQt6.QtCore import QThread, pyqtSignal

from log.log import log


class HostsSelectionSaveWorker(QThread):
    """Сохраняет выбранные hosts-профили вне UI-потока."""

    loaded = pyqtSignal(int, bool)
    failed = pyqtSignal(int, str)

    def __init__(self, request_id: int, selection: dict[str, str], *, save_user_selection, parent=None):
        super().__init__(parent)
        self._request_id = int(request_id)
        self._selection = dict(selection or {})
        self._save_user_selection = save_user_selection

    def run(self) -> None:
        try:
            saved = bool(self._save_user_selection(self._selection))
        except Exception as exc:
            log(f"HostsSelectionSaveWorker: не удалось сохранить выбор hosts: {exc}", "ERROR")
            self.failed.emit(self._request_id, str(exc))
            return
        self.loaded.emit(self._request_id, saved)
