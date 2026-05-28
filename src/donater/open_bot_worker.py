from __future__ import annotations

from PyQt6.QtCore import QThread, pyqtSignal

from log.log import log


class PremiumOpenBotWorker(QThread):
    """Открывает Premium-бота вне UI-потока."""

    loaded = pyqtSignal(int, object)
    failed = pyqtSignal(int, str)

    def __init__(self, request_id: int, *, premium_feature, parent=None):
        super().__init__(parent)
        self._request_id = int(request_id)
        self._premium = premium_feature

    def run(self) -> None:
        try:
            result = self._premium.open_extend_bot()
        except Exception as exc:
            log(f"PremiumOpenBotWorker: не удалось открыть Premium-бота: {exc}", "ERROR")
            self.failed.emit(self._request_id, str(exc))
            return
        self.loaded.emit(self._request_id, result)


__all__ = ["PremiumOpenBotWorker"]
