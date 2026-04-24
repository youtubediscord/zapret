from __future__ import annotations

from PyQt6.QtCore import QObject, pyqtSignal

from log.log import log
from settings.dpi.strategy_settings import get_strategy_launch_method
from winws_runtime.runtime.sync_shutdown import shutdown_runtime_sync


class DirectLaunchStopWorker(QObject):
    """Worker для асинхронной остановки прямого launch-runtime."""

    finished = pyqtSignal(bool, str)
    progress = pyqtSignal(str)

    def __init__(
        self,
        app_instance,
        launch_method,
        *,
        force_cleanup: bool = False,
        cleanup_services: bool = True,
    ):
        super().__init__()
        self.app_instance = app_instance
        self.launch_method = launch_method
        self.force_cleanup = bool(force_cleanup)
        self.cleanup_services = bool(cleanup_services)

    def _get_winws_exe(self) -> str:
        from config.config import get_winws_exe_for_method

        return get_winws_exe_for_method(self.launch_method)

    def run(self):
        try:
            self.progress.emit("Остановка DPI...")

            process_running = self.app_instance.launch_runtime_api.has_residual_processes(silent=True)
            if (not process_running) and not self.force_cleanup:
                self.progress.emit("DPI уже остановлен")
                self.finished.emit(True, "DPI уже был остановлен")
                return
            if not process_running and self.force_cleanup:
                self.progress.emit("Очищаем состояние предыдущего режима...")

            self.progress.emit("Завершение процессов...")

            if self.launch_method == "orchestra":
                success = self._stop_orchestra()
            elif self.launch_method in ("direct_zapret2", "direct_zapret1"):
                success = self._stop_direct()
            else:
                success = self._stop_direct()

            if success:
                self.progress.emit("DPI успешно остановлен")
                self.finished.emit(True, "")
            else:
                self.finished.emit(False, "Не удалось полностью остановить процесс")

        except Exception as e:
            error_msg = f"Ошибка остановки DPI: {str(e)}"
            log(error_msg, "❌ ERROR")
            self.finished.emit(False, error_msg)

    def _stop_direct(self):
        try:
            return self._shutdown_runtime(reason=f"direct_stop_worker:{self.launch_method}")

        except Exception as e:
            log(f"Ошибка прямой остановки: {e}", "❌ ERROR")
            return False

    def _stop_orchestra(self):
        try:
            return self._shutdown_runtime(reason="orchestra_stop_worker")

        except Exception as e:
            log(f"Ошибка остановки оркестратора: {e}", "❌ ERROR")
            return False

    def _shutdown_runtime(self, *, reason: str) -> bool:
        result = shutdown_runtime_sync(
            window=self.app_instance,
            reason=reason,
            include_cleanup=self.cleanup_services,
            cleanup_services=self.cleanup_services,
            update_runtime_state=False,
        )
        return not result.still_running


class DirectPresetSwitchWorker(QObject):
    """Worker для быстрого переключения running direct пресета без общего restart pipeline."""

    finished = pyqtSignal(bool, str, int, str, bool)
    progress = pyqtSignal(str)

    def __init__(self, app_instance, launch_method: str, generation: int, is_generation_current):
        super().__init__()
        self.app_instance = app_instance
        self.launch_method = str(launch_method or "").strip().lower()
        self.generation = int(generation)
        self._is_generation_current = is_generation_current

    def _get_winws_exe(self) -> str:
        from config.config import get_winws_exe_for_method

        return get_winws_exe_for_method(self.launch_method)

    def run(self):
        try:
            if self.launch_method not in ("direct_zapret1", "direct_zapret2"):
                self.finished.emit(
                    False,
                    f"Неподдерживаемый метод direct switch: {self.launch_method}",
                    self.generation,
                    self.launch_method,
                    False,
                )
                return

            self.progress.emit("Применяем пресет...")

            from winws_runtime.runners.runner_factory import get_strategy_runner

            profile = self.app_instance.app_context.direct_flow_coordinator.ensure_launch_profile(
                self.launch_method,
                require_filters=True,
            )

            if not bool(self._is_generation_current(self.generation)):
                self.finished.emit(True, "", self.generation, self.launch_method, True)
                return

            runner = get_strategy_runner(self._get_winws_exe())
            switch_method = getattr(runner, "switch_preset_file_fast", None)
            if callable(switch_method):
                success = bool(
                    switch_method(
                        str(profile.preset_path),
                        profile.display_name,
                    )
                )
            else:
                success = bool(
                    runner.start_from_preset_file(
                        str(profile.preset_path),
                        profile.display_name,
                    )
                )

            if not success:
                short_error = str(getattr(runner, "last_error", "") or "").strip()
                if not short_error:
                    short_error = "Не удалось применить выбранный пресет"
                self.finished.emit(False, short_error, self.generation, self.launch_method, False)
                return

            self.finished.emit(True, "", self.generation, self.launch_method, False)
        except Exception as e:
            self.finished.emit(False, str(e), self.generation, self.launch_method, False)


class StopAndExitWorker(QObject):
    """Worker для остановки DPI и выхода из программы."""

    finished = pyqtSignal()
    progress = pyqtSignal(str)

    def __init__(self, app_instance):
        super().__init__()
        self.app_instance = app_instance
        self.launch_method = get_strategy_launch_method()

    def _get_winws_exe(self) -> str:
        from config.config import get_winws_exe_for_method

        return get_winws_exe_for_method(self.launch_method)

    def run(self):
        try:
            self.progress.emit("Остановка DPI перед закрытием...")
            shutdown_runtime_sync(
                window=self.app_instance,
                reason=f"stop_and_exit_worker:{self.launch_method}",
                include_cleanup=True,
                update_runtime_state=True,
            )

            self.progress.emit("Завершение работы...")
            self.finished.emit()

        except Exception as e:
            log(f"Ошибка при остановке перед закрытием: {e}", "❌ ERROR")
            self.finished.emit()
