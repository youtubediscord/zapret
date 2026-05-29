from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PyQt6.QtCore import QThread, pyqtSignal

from log.log import log


class UpdaterAutoCheckSaveWorker(QThread):
    loaded = pyqtSignal(int, bool)
    failed = pyqtSignal(int, str)

    def __init__(self, request_id: int, *, enabled: bool, set_auto_update_enabled: Callable[[bool], Any], parent=None):
        super().__init__(parent)
        self._request_id = int(request_id)
        self._enabled = bool(enabled)
        self._set_auto_update_enabled = set_auto_update_enabled

    def run(self) -> None:
        try:
            self._set_auto_update_enabled(self._enabled)
        except Exception as exc:
            log(f"UpdaterAutoCheckSaveWorker: настройка автопроверки не сохранена: {exc}", "ERROR")
            self.failed.emit(self._request_id, str(exc))
            return
        self.loaded.emit(self._request_id, self._enabled)


class UpdaterAutoCheckLoadWorker(QThread):
    loaded = pyqtSignal(int, bool)
    failed = pyqtSignal(int, str)

    def __init__(self, request_id: int, *, is_auto_update_enabled: Callable[[], bool], parent=None):
        super().__init__(parent)
        self._request_id = int(request_id)
        self._is_auto_update_enabled = is_auto_update_enabled

    def run(self) -> None:
        try:
            enabled = bool(self._is_auto_update_enabled())
        except Exception as exc:
            log(f"UpdaterAutoCheckLoadWorker: настройка автопроверки не загружена: {exc}", "ERROR")
            self.failed.emit(self._request_id, str(exc))
            return
        self.loaded.emit(self._request_id, enabled)


class UpdaterChannelOpenWorker(QThread):
    loaded = pyqtSignal(int, object)
    failed = pyqtSignal(int, str)

    def __init__(self, request_id: int, *, channel: str, open_update_channel: Callable[[str], Any], parent=None):
        super().__init__(parent)
        self._request_id = int(request_id)
        self._channel = str(channel or "")
        self._open_update_channel = open_update_channel

    def run(self) -> None:
        try:
            result = self._open_update_channel(self._channel)
        except Exception as exc:
            log(f"UpdaterChannelOpenWorker: канал обновлений не открыт: {exc}", "ERROR")
            self.failed.emit(self._request_id, str(exc))
            return
        self.loaded.emit(self._request_id, result)
