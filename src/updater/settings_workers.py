from __future__ import annotations

from PyQt6.QtCore import QThread, pyqtSignal

from log.log import log


class UpdaterAutoCheckSaveWorker(QThread):
    loaded = pyqtSignal(int, bool)
    failed = pyqtSignal(int, str)

    def __init__(self, request_id: int, *, enabled: bool, parent=None):
        super().__init__(parent)
        self._request_id = int(request_id)
        self._enabled = bool(enabled)

    def run(self) -> None:
        import updater.commands as updater_commands

        try:
            updater_commands.set_auto_update_enabled(self._enabled)
        except Exception as exc:
            log(f"UpdaterAutoCheckSaveWorker: настройка автопроверки не сохранена: {exc}", "ERROR")
            self.failed.emit(self._request_id, str(exc))
            return
        self.loaded.emit(self._request_id, self._enabled)


class UpdaterAutoCheckLoadWorker(QThread):
    loaded = pyqtSignal(int, bool)
    failed = pyqtSignal(int, str)

    def __init__(self, request_id: int, *, parent=None):
        super().__init__(parent)
        self._request_id = int(request_id)

    def run(self) -> None:
        import updater.commands as updater_commands

        try:
            enabled = bool(updater_commands.is_auto_update_enabled())
        except Exception as exc:
            log(f"UpdaterAutoCheckLoadWorker: настройка автопроверки не загружена: {exc}", "ERROR")
            self.failed.emit(self._request_id, str(exc))
            return
        self.loaded.emit(self._request_id, enabled)


class UpdaterChannelOpenWorker(QThread):
    loaded = pyqtSignal(int, object)
    failed = pyqtSignal(int, str)

    def __init__(self, request_id: int, *, channel: str, parent=None):
        super().__init__(parent)
        self._request_id = int(request_id)
        self._channel = str(channel or "")

    def run(self) -> None:
        import updater.commands as updater_commands

        try:
            result = updater_commands.open_update_channel(self._channel)
        except Exception as exc:
            log(f"UpdaterChannelOpenWorker: канал обновлений не открыт: {exc}", "ERROR")
            self.failed.emit(self._request_id, str(exc))
            return
        self.loaded.emit(self._request_id, result)
