from __future__ import annotations

import traceback

from PyQt6.QtCore import QObject, pyqtSignal

from log.log import log


class SubscriptionInitWorker(QObject):
    """Фоновый worker для первичной проверки Premium-статуса."""

    finished = pyqtSignal(object, object, bool)  # donate_checker, activation_info, success
    progress = pyqtSignal(str)

    def run(self) -> None:
        try:
            self.progress.emit("Инициализация системы подписок...")

            from donater.service import get_premium_service

            donate_checker = get_premium_service()
            self.progress.emit("Проверка статуса подписки...")

            # На старте используем кэш/оффлайн статус без сети,
            # а сетевую проверку выполняем позже отложенным фоновым таском.
            activation_info = donate_checker.check_device_activation(use_cache=True)

            log(f"Статус подписки: {activation_info.get('status', 'unknown')}", "INFO")
            self.finished.emit(donate_checker, activation_info, True)
        except Exception as e:
            log(f"Ошибка инициализации подписок: {e}", "❌ ERROR")
            log(f"Traceback: {traceback.format_exc()}", "DEBUG")
            self.finished.emit(None, None, False)
