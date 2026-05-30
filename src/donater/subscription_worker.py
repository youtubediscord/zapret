from __future__ import annotations

import traceback
from collections.abc import Callable

from PyQt6.QtCore import QObject, pyqtSignal

from log.log import log


class SubscriptionInitWorker(QObject):
    """Фоновый worker для первичной проверки Premium-статуса."""

    finished = pyqtSignal(object, bool)  # activation_info, success
    progress = pyqtSignal(str)

    def __init__(
        self,
        *,
        get_premium_checker: Callable[[], object],
        check_device_activation: Callable[..., dict],
        parent=None,
    ):
        super().__init__(parent)
        self._get_premium_checker = get_premium_checker
        self._check_device_activation = check_device_activation

    def run(self) -> None:
        try:
            self.progress.emit("Инициализация системы подписок...")

            premium_checker = self._get_premium_checker()
            self.progress.emit("Проверка статуса подписки...")

            # На старте используем кэш/оффлайн статус без сети,
            # а сетевую проверку выполняем позже отложенным фоновым таском.
            activation_info = self._check_device_activation(premium_checker, use_cache=True)

            log(f"Статус подписки: {activation_info.get('status', 'unknown')}", "INFO")
            self.finished.emit(activation_info, True)
        except Exception as e:
            log(f"Ошибка инициализации подписок: {e}", "❌ ERROR")
            log(f"Traceback: {traceback.format_exc()}", "DEBUG")
            self.finished.emit(None, False)
