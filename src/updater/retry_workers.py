from __future__ import annotations

from PyQt6.QtCore import QThread, pyqtSignal

from log.log import log


class UpdaterServerRetryWithoutDpiWorker(QThread):
    loaded = pyqtSignal(int, bool, bool, str)
    failed = pyqtSignal(int, str)

    def __init__(self, request_id: int, *, is_any_running, shutdown_sync, parent=None):
        super().__init__(parent)
        self._request_id = int(request_id)
        self._is_any_running = is_any_running
        self._shutdown_sync = shutdown_sync

    def run(self) -> None:
        import updater.commands as updater_commands

        try:
            log("⚠️ Серверы недоступны при запущенном DPI — делаем один повтор без DPI", "🔄 UPDATE")
            should_retry, stopped_dpi, error = updater_commands.retry_server_check_without_dpi(
                is_any_running=self._is_any_running,
                shutdown_sync=self._shutdown_sync,
            )
            if error == "DPI не остановился":
                log("Повтор проверки серверов без DPI пропущен: DPI не остановился", "🔄 UPDATE")
        except Exception as exc:
            log(f"Не удалось временно остановить DPI для проверки серверов: {exc}", "❌ ERROR")
            self.loaded.emit(self._request_id, False, False, str(exc))
            return

        self.loaded.emit(self._request_id, should_retry, stopped_dpi, error)


class UpdaterDpiRestartWorker(QThread):
    loaded = pyqtSignal(int, bool)
    failed = pyqtSignal(int, str)

    def __init__(self, request_id: int, *, is_available, restart, context: str = "", parent=None):
        super().__init__(parent)
        self._request_id = int(request_id)
        self._is_available = is_available
        self._restart = restart
        self._context = str(context or "скачивания обновления")

    def run(self) -> None:
        import updater.commands as updater_commands

        try:
            log(f"🔄 Перезапуск DPI после {self._context}", "🔁 UPDATE")
            restarted = updater_commands.restart_dpi_after_update(
                is_available=self._is_available,
                restart=self._restart,
            )
        except Exception as exc:
            log(f"Не удалось перезапустить DPI: {exc}", "❌ ERROR")
            self.failed.emit(self._request_id, str(exc))
            return
        self.loaded.emit(self._request_id, restarted)


__all__ = ["UpdaterServerRetryWithoutDpiWorker", "UpdaterDpiRestartWorker"]
