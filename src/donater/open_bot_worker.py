from __future__ import annotations

from PyQt6.QtCore import QThread, pyqtSignal

from log.log import log


class PremiumOpenBotWorker(QThread):
    """Открывает Premium-бота вне UI-потока."""

    loaded = pyqtSignal(int, object)
    failed = pyqtSignal(int, str)

    def __init__(self, request_id: int, *, parent=None):
        super().__init__(parent)
        self._request_id = int(request_id)

    def run(self) -> None:
        import donater.commands as premium_commands

        try:
            result = premium_commands.open_extend_bot()
        except Exception as exc:
            log(f"PremiumOpenBotWorker: не удалось открыть Premium-бота: {exc}", "ERROR")
            self.failed.emit(self._request_id, str(exc))
            return
        self.loaded.emit(self._request_id, result)


__all__ = ["PremiumOpenBotWorker"]
