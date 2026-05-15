"""
Runtime запуска DPI: хранит живые потоки и запускает сценарии start/stop/restart.
"""

from PyQt6.QtCore import QTimer
from settings.mode import normalize_launch_method
from log.log import log

from .restart_flow import (
    handle_presets_switch_finished,
    process_pending_presets_switch,
    process_pending_restart_request,
    restart_dpi_async as restart_dpi_async_impl,
    switch_presets_async as switch_presets_async_impl,
)
from .lifecycle_feedback import (
    cleanup_threads as cleanup_threads_impl,
    on_dpi_start_finished as on_dpi_start_finished_impl,
    on_dpi_stop_finished as on_dpi_stop_finished_impl,
    on_stop_and_exit_finished as on_stop_and_exit_finished_impl,
)
from .start_flow import start_dpi_async as start_dpi_async_impl
from .status_flow import is_running as is_running_impl
from .status_flow import transition_pipeline_in_progress as transition_pipeline_in_progress_impl
from .stop_flow import stop_and_exit_async as stop_and_exit_async_impl
from .stop_flow import stop_dpi_async as stop_dpi_async_impl

class PresetLaunchRuntime:
    """Координатор запуска, остановки и переключения DPI."""
    
    def __init__(self, *, runtime_feature, runtime_api, notify):
        self._runtime_feature = runtime_feature
        self._launch_runtime_api = runtime_api
        self._notify_callback = notify
        self._dpi_start_thread = None
        self._dpi_stop_thread = None
        self._stop_exit_thread = None
        self._presets_switch_thread = None
        self._presets_switch_worker = None
        self._presets_switch_requested_generation = 0
        self._presets_switch_completed_generation = 0
        self._presets_switch_method = ""
        self._pending_launch_warnings: list[str] = []
        self._restart_request_generation = 0
        self._restart_completed_generation = 0
        self._restart_pending_stop_generation = 0
        self._restart_active_start_generation = 0
        self._restart_force_stop_generation = 0
        self._restart_runner_wait_queued = False
        self._preset_switch_runner_wait_queued = False
        # Поколение проверки запуска защищает от старых QTimer-проверок
        # после предыдущих попыток старта.
        self._dpi_start_verify_generation = 0
        self._dpi_start_verify_retry = 0
        self._pending_conflict_request_id = 0
        self._pending_conflict_selected_mode = None
        self._pending_conflict_launch_method = None
        self._first_runtime_apply = True
        self._discord_manager = None

    def _runtime_service(self):
        return self._runtime_feature.objects.runtime_service

    def _runtime_api(self):
        return self._launch_runtime_api

    def _process_monitor_manager(self):
        return self._runtime_feature.objects.process_monitor_manager

    def _runtime_ui_bridge(self):
        return self._runtime_feature.ui_port.runtime_ui_bridge

    def _notify(self, payload: dict | None) -> None:
        self._notify_callback(payload)

    def transition_pipeline_in_progress(self, launch_method: str | None = None) -> bool:
        return transition_pipeline_in_progress_impl(self, launch_method)

    def _schedule_pending_restart_retry(self) -> None:
        if self._restart_runner_wait_queued:
            return
        self._restart_runner_wait_queued = True

        def _retry() -> None:
            self._restart_runner_wait_queued = False
            self._process_pending_restart_request()

        QTimer.singleShot(200, _retry)

    def _schedule_pending_preset_switch_retry(self) -> None:
        if self._preset_switch_runner_wait_queued:
            return
        self._preset_switch_runner_wait_queued = True

        def _retry() -> None:
            self._preset_switch_runner_wait_queued = False
            self._process_pending_presets_switch()

        QTimer.singleShot(200, _retry)

    @staticmethod
    def _expected_process_name(launch_method: str) -> str:
        method = normalize_launch_method(launch_method, default="")
        from settings.mode import is_orchestra_launch_method

        if is_orchestra_launch_method(method):
            return ""
        try:
            from settings.mode import exe_name_for_launch_method


            return exe_name_for_launch_method(method).strip().lower()
        except Exception:
            return ""

    def _begin_runtime_start(self, launch_method: str, selected_mode) -> None:
        self._runtime_service().begin_start(
            launch_method=launch_method,
            expected_process=self._expected_process_name(launch_method),
        )

    def _mark_runtime_running(self, pid: int | None = None) -> None:
        self._runtime_service().mark_running(pid=pid)

    def _mark_runtime_failed(self, error_message: str, *, exit_code: int | None = None) -> None:
        self._runtime_service().mark_start_failed(error_message)

    def _begin_runtime_stop(self) -> None:
        self._runtime_service().begin_stop()

    def _mark_runtime_stopped(self) -> None:
        self._runtime_service().mark_stopped(clear_error=True)

    def _process_pending_presets_switch(self) -> None:
        process_pending_presets_switch(self)

    def switch_presets_async(self, launch_method: str | None = None) -> None:
        switch_presets_async_impl(self, launch_method)

    def _process_pending_restart_request(self) -> None:
        process_pending_restart_request(self)

    def start_dpi_async(
        self,
        selected_mode=None,
        launch_method=None,
        *,
        _skip_conflict_prompt: bool = False,
        _startup_autostart: bool = False,
    ):
        """Асинхронно запускает DPI без блокировки UI

        Args:
            selected_mode: Стратегия для запуска
            launch_method: Метод запуска из settings.mode. Если None - читается из settings.json.
        """
        start_dpi_async_impl(
            self,
            selected_mode=selected_mode,
            launch_method=launch_method,
            skip_conflict_prompt=_skip_conflict_prompt,
            startup_autostart=_startup_autostart,
        )

    def stop_dpi_async(
        self,
        *,
        force_cleanup: bool = False,
        cleanup_services: bool = False,
    ):
        """Асинхронно останавливает DPI без блокировки UI"""
        stop_dpi_async_impl(
            self,
            force_cleanup=force_cleanup,
            cleanup_services=cleanup_services,
        )
    
    def stop_and_exit_async(self):
        """Асинхронно останавливает DPI и закрывает программу"""
        stop_and_exit_async_impl(self)
    
    def _on_dpi_start_finished(self, success, error_message):
        on_dpi_start_finished_impl(self, success, error_message)

    def _on_dpi_stop_finished(self, success, error_message):
        on_dpi_stop_finished_impl(self, success, error_message)

    def _on_presets_switch_finished(self, success, error_message, generation, launch_method, skipped_as_stale):
        handle_presets_switch_finished(
            self,
            success,
            error_message,
            generation,
            launch_method,
            skipped_as_stale,
        )
    
    def _on_stop_and_exit_finished(self):
        on_stop_and_exit_finished_impl(self)
    
    def cleanup_threads(self):
        cleanup_threads_impl(self)

    def is_running(self) -> bool:
        """
        Проверяет запущен ли DPI процесс.

        Returns:
            True если процесс запущен, False иначе
        """
        return is_running_impl(self)

    def restart_dpi_async(self, *, force_full_stop: bool = False):
        """
        Перезапускает DPI по модели "последний запрос побеждает".

        Старые запросы не исполняются повторно: если пользователь быстро
        переключает пресеты, мы запоминаем только последнее поколение
        запроса и продолжаем pipeline от него.
        """
        restart_dpi_async_impl(self, force_full_stop=force_full_stop)
