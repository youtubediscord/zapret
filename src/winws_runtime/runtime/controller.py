"""
Контроллер для управления DPI - содержит orchestration-логику запуска и остановки.
"""

import os
import time

from PyQt6.QtCore import QTimer
from app_notifications import advisory_notification, notification_action
from settings.dpi.strategy_settings import get_strategy_launch_method
from log.log import log

from winws_runtime.health.process_health_check import (
    check_conflicting_processes,
    try_kill_conflicting_processes,
    get_conflicting_processes_report,
)
from winws_runtime.flow.start_preparation import (
    prepare_start_request,
    resolve_method_name,
)
from .restart_flow import (
    handle_direct_preset_switch_finished,
    process_pending_direct_preset_switch,
    process_pending_restart_request,
    restart_dpi_async as restart_dpi_async_impl,
    switch_direct_preset_async as switch_direct_preset_async_impl,
)
from .lifecycle_feedback import (
    cleanup_threads as cleanup_threads_impl,
    on_dpi_start_finished as on_dpi_start_finished_impl,
    on_dpi_stop_finished as on_dpi_stop_finished_impl,
    on_stop_and_exit_finished as on_stop_and_exit_finished_impl,
    show_launch_error_top,
    show_launch_warning_top,
)
from .thread_runtime import start_worker_thread
from .control_workers import (
    DirectLaunchStopWorker,
    StopAndExitWorker,
)
from .start_workers import (
    DirectLaunchStartWorker,
)
from ui.runtime_ui_bridge import ensure_runtime_ui_bridge

class DirectLaunchController:
    """Основной orchestrator прямого запуска и остановки обхода."""
    
    def __init__(self, app_instance):
        self.app = app_instance
        self._dpi_start_thread = None
        self._dpi_stop_thread = None
        self._stop_exit_thread = None
        self._direct_preset_switch_thread = None
        self._direct_preset_switch_worker = None
        self._direct_preset_switch_requested_generation = 0
        self._direct_preset_switch_completed_generation = 0
        self._direct_preset_switch_method = ""
        self._pending_launch_warnings: list[str] = []
        self._restart_request_generation = 0
        self._restart_completed_generation = 0
        self._restart_pending_stop_generation = 0
        self._restart_active_start_generation = 0
        self._restart_force_stop_generation = 0
        self._restart_runner_wait_queued = False
        self._direct_switch_runner_wait_queued = False
        # Generation token for async start verification.
        # Prevents stale QTimer checks from previous start attempts.
        self._dpi_start_verify_generation = 0
        self._dpi_start_verify_retry = 0
        self._pending_conflict_request_id = 0
        self._pending_conflict_selected_mode = None
        self._pending_conflict_launch_method = None

    def _runtime_service(self):
        return getattr(self.app, "launch_runtime_service", None)

    def _runtime_ui_bridge(self):
        return ensure_runtime_ui_bridge(self.app)

    def transition_pipeline_in_progress(self, launch_method: str | None = None) -> bool:
        method = str(launch_method or "").strip().lower()

        try:
            if self._dpi_start_thread and self._dpi_start_thread.isRunning():
                return True
        except RuntimeError:
            self._dpi_start_thread = None

        try:
            if self._dpi_stop_thread and self._dpi_stop_thread.isRunning():
                return True
        except RuntimeError:
            self._dpi_stop_thread = None

        try:
            if self._direct_preset_switch_thread and self._direct_preset_switch_thread.isRunning():
                if not method or method in {"direct_zapret1", "direct_zapret2"}:
                    return True
        except RuntimeError:
            self._direct_preset_switch_thread = None

        if int(self._restart_request_generation or 0) > int(self._restart_completed_generation or 0):
            return True
        if int(self._restart_active_start_generation or 0) > 0:
            return True
        if int(self._restart_pending_stop_generation or 0) > 0:
            return True
        if int(self._direct_preset_switch_requested_generation or 0) > int(self._direct_preset_switch_completed_generation or 0):
            if not method or method in {"direct_zapret1", "direct_zapret2"}:
                return True

        return False

    @staticmethod
    def _is_runner_transition_state(state_value: object) -> bool:
        return str(state_value or "").strip().lower() in {"starting", "stopping"}

    def _runner_transition_in_progress(self, *, launch_method: str | None = None) -> bool:
        try:
            from winws_runtime.runners.runner_factory import get_current_runner

            runner = get_current_runner()
            if runner is None:
                return False

            if launch_method:
                try:
                    from config.config import get_winws_exe_for_method


                    expected_name = os.path.basename(get_winws_exe_for_method(str(launch_method or "").strip().lower())).strip().lower()
                    runner_name = os.path.basename(str(getattr(runner, "winws_exe", "") or "")).strip().lower()
                    if expected_name and runner_name and expected_name != runner_name:
                        return False
                except Exception:
                    pass

            snapshot_getter = getattr(runner, "get_runner_state_snapshot", None)
            if not callable(snapshot_getter):
                return False

            snapshot = snapshot_getter()
            return self._is_runner_transition_state(getattr(snapshot, "state", ""))
        except Exception:
            return False

    def _schedule_pending_restart_retry(self) -> None:
        if self._restart_runner_wait_queued:
            return
        self._restart_runner_wait_queued = True

        def _retry() -> None:
            self._restart_runner_wait_queued = False
            self._process_pending_restart_request()

        QTimer.singleShot(200, _retry)

    def _schedule_pending_direct_switch_retry(self) -> None:
        if self._direct_switch_runner_wait_queued:
            return
        self._direct_switch_runner_wait_queued = True

        def _retry() -> None:
            self._direct_switch_runner_wait_queued = False
            self._process_pending_direct_preset_switch()

        QTimer.singleShot(200, _retry)

    def _store_pending_conflict_request(self, selected_mode=None, launch_method=None) -> int:
        self._pending_conflict_request_id += 1
        self._pending_conflict_selected_mode = selected_mode
        self._pending_conflict_launch_method = launch_method
        return int(self._pending_conflict_request_id)

    def _has_pending_conflict_request(self, request_id: int) -> bool:
        return int(request_id or 0) == int(self._pending_conflict_request_id or 0)

    def _clear_pending_conflict_request(self, request_id: int | None = None) -> None:
        if request_id is not None and not self._has_pending_conflict_request(int(request_id)):
            return
        self._pending_conflict_selected_mode = None
        self._pending_conflict_launch_method = None

    def _show_conflicting_processes_infobar(self, conflicting: list[dict], request_id: int) -> None:
        controller = getattr(self.app, "window_notification_controller", None)
        if controller is None:
            log("WindowNotificationController недоступен для показа предупреждения о конфликтах", "DEBUG")
            return

        names = ", ".join(str(item.get("name") or item.get("exe") or "неизвестно") for item in conflicting)
        controller.notify(
            advisory_notification(
                level="warning",
                title="Обнаружены конфликтующие программы",
                content=(
                    "Обнаружены программы, которые блокируют WinDivert:\n\n"
                    f"{names}\n\n"
                    "Эти программы перехватывают системные вызовы и не дают "
                    "WinDivert драйверу запуститься."
                ),
                source="launch.conflicting_processes",
                presentation="infobar",
                queue="immediate",
                duration=-1,
                dedupe_key=f"launch.conflicting_processes:{request_id}",
                dedupe_window_ms=0,
                buttons=[
                    notification_action("launch_conflict_kill_start", "Закрыть и продолжить", value=request_id),
                    notification_action("launch_conflict_ignore_start", "Продолжить без закрытия", value=request_id),
                    notification_action("launch_conflict_cancel", "Отмена", value=request_id),
                ],
            )
        )

    def _show_conflict_kill_failed_infobar(self, request_id: int) -> None:
        controller = getattr(self.app, "window_notification_controller", None)
        if controller is None:
            log("WindowNotificationController недоступен для показа ошибки закрытия конфликтов", "DEBUG")
            return

        controller.notify(
            advisory_notification(
                level="warning",
                title="Не удалось закрыть процессы",
                content=(
                    "Некоторые конфликтующие процессы не удалось закрыть.\n"
                    "Запуск DPI может завершиться ошибкой."
                ),
                source="launch.conflicting_processes.kill_failed",
                presentation="infobar",
                queue="immediate",
                duration=-1,
                dedupe_key=f"launch.conflicting_processes.kill_failed:{request_id}",
                dedupe_window_ms=0,
                buttons=[
                    notification_action("launch_conflict_ignore_start", "Продолжить запуск", value=request_id),
                    notification_action("launch_conflict_cancel", "Отмена", value=request_id),
                ],
            )
        )

    def _handle_conflicting_processes_before_start(self, selected_mode=None, launch_method=None) -> bool:
        conflicting = check_conflicting_processes()
        if not conflicting:
            return True

        report = get_conflicting_processes_report()
        log(report, "WARNING")
        request_id = self._store_pending_conflict_request(selected_mode, launch_method)
        self._show_conflicting_processes_infobar(conflicting, request_id)
        self.app.set_status("⚠️ Обнаружены конфликтующие программы. Решите, как продолжить запуск.")
        return False

    def _resume_start_after_conflict_resolution(self, request_id: int, *, close_conflicts: bool) -> None:
        if not self._has_pending_conflict_request(request_id):
            log(f"Пропуск устаревшего действия по конфликтующим процессам: {request_id}", "DEBUG")
            return

        selected_mode = self._pending_conflict_selected_mode
        launch_method = self._pending_conflict_launch_method

        if close_conflicts:
            log("Пользователь выбрал закрыть конфликтующие процессы", "INFO")
            killed = try_kill_conflicting_processes(auto_kill=True)
            if killed:
                log("Конфликтующие процессы закрыты, ожидание 1с...", "INFO")
                time.sleep(1)
            else:
                log("Не удалось закрыть все конфликтующие процессы", "WARNING")
                self._show_conflict_kill_failed_infobar(request_id)
                return
        else:
            log("Пользователь продолжил запуск несмотря на конфликтующие процессы", "WARNING")

        self._clear_pending_conflict_request(request_id)
        self.start_dpi_async(
            selected_mode=selected_mode,
            launch_method=launch_method,
            _skip_conflict_prompt=True,
        )

    def _cancel_start_after_conflict_prompt(self, request_id: int) -> None:
        if not self._has_pending_conflict_request(request_id):
            return
        self._clear_pending_conflict_request(request_id)
        self.app.set_status("Запуск DPI отменён пользователем")
        log("Запуск DPI отменён пользователем из-за конфликтующих процессов", "INFO")

    def _fail_start_preparation(self, message: str) -> None:
        text = str(message or "").strip() or "Не удалось подготовить запуск DPI"
        log(f"Ошибка подготовки запуска: {text}", "❌ ERROR")
        self.app.set_status(f"❌ {text}")
        show_launch_error_top(self, text)
        self._mark_runtime_failed(text)

    @staticmethod
    def _expected_process_name(launch_method: str) -> str:
        method = str(launch_method or "").strip().lower()
        if method == "orchestra":
            return ""
        try:
            from config.config import get_winws_exe_for_method


            return os.path.basename(get_winws_exe_for_method(method)).strip().lower()
        except Exception:
            return ""

    def _begin_runtime_start(self, launch_method: str, selected_mode) -> None:
        runtime_service = self._runtime_service()
        if runtime_service is not None:
            runtime_service.begin_start(
                launch_method=launch_method,
                expected_process=self._expected_process_name(launch_method),
            )

    def _mark_runtime_running(self, pid: int | None = None) -> None:
        runtime_service = self._runtime_service()
        if runtime_service is not None:
            runtime_service.mark_running(pid=pid)

    def _mark_runtime_failed(self, error_message: str, *, exit_code: int | None = None) -> None:
        runtime_service = self._runtime_service()
        if runtime_service is not None:
            runtime_service.mark_start_failed(error_message)

    def _begin_runtime_stop(self) -> None:
        runtime_service = self._runtime_service()
        if runtime_service is not None:
            runtime_service.begin_stop()

    def _mark_runtime_stopped(self) -> None:
        runtime_service = self._runtime_service()
        if runtime_service is not None:
            runtime_service.mark_stopped(clear_error=True)

    def _maybe_restart_discord_after_runtime_apply(self, *, skip_first_start: bool) -> bool:
        """Перезапускает Discord после применения пресета, если это разрешено настройкой."""
        try:
            is_first_start = bool(getattr(self.app, "_first_dpi_start", True))
            if skip_first_start and is_first_start:
                return False

            from discord.discord_restart import get_discord_restart_setting

            if not bool(get_discord_restart_setting(default=True)):
                return False

            discord_manager = getattr(self.app, "discord_manager", None)
            if discord_manager is None:
                return False

            return bool(discord_manager.restart_discord_if_running())
        except Exception as e:
            log(f"Discord restart check error: {e}", "DEBUG")
            return False
        finally:
            if skip_first_start:
                self.app._first_dpi_start = False

    def _process_pending_direct_preset_switch(self) -> None:
        process_pending_direct_preset_switch(self)

    def switch_direct_preset_async(self, launch_method: str | None = None) -> None:
        switch_direct_preset_async_impl(self, launch_method)

    def _process_pending_restart_request(self) -> None:
        process_pending_restart_request(self)

    def _show_launch_error_top(self, message: str) -> None:
        show_launch_error_top(self, message)

    def _show_launch_warning_top(self, message: str) -> None:
        show_launch_warning_top(self, message)

    def _prepare_start_preflight(
        self,
        *,
        selected_mode=None,
        launch_method=None,
        skip_conflict_prompt: bool = False,
    ) -> bool:
        """Выполняет раннюю preflight-стадию перед построением launch request.

        Здесь ещё не создаётся worker и не читается launch profile.
        Задача стадии простая:
        - убедиться, что новый старт не дублирует уже идущий поток;
        - очистить временное launch-состояние от предыдущей попытки;
        - прогнать ранние gate-проверки вроде конфликтующих процессов;
        - инвалидировать старые verification-loop таймеры от предыдущих стартов.
        """
        try:
            if self._dpi_start_thread and self._dpi_start_thread.isRunning():
                log("Запуск DPI уже выполняется", "DEBUG")
                return False
        except RuntimeError:
            self._dpi_start_thread = None

        self._pending_launch_warnings = []

        if not skip_conflict_prompt and not self._handle_conflicting_processes_before_start(selected_mode, launch_method):
            return False

        # Invalidate any pending verification loop from older starts.
        self._dpi_start_verify_generation += 1
        return True

    def _build_start_request(
        self,
        *,
        selected_mode=None,
        launch_method=None,
    ):
        """Строит launch request и фиксирует сопутствующие launch warnings.

        Это вторая стадия after-preflight:
        - превращаем сырые входы selected_mode/launch_method в нормализованный request;
        - сохраняем warning-сообщения, которые worker вернёт позже в lifecycle feedback;
        - если подготовка не удалась, завершаем попытку через общий fail-path.
        """
        try:
            request, warnings = prepare_start_request(
                selected_mode,
                launch_method,
                app_context=self.app.app_context,
            )
        except Exception as e:
            self._fail_start_preparation(str(e))
            return None

        self._pending_launch_warnings = list(warnings or [])
        return request

    def start_dpi_async(self, selected_mode=None, launch_method=None, *, _skip_conflict_prompt: bool = False):
        """Асинхронно запускает DPI без блокировки UI

        Args:
            selected_mode: Стратегия для запуска
            launch_method: Метод запуска ("direct_zapret2", "direct_zapret1", "orchestra" и т.д.). Если None - читается из реестра
        """
        if not self._prepare_start_preflight(
            selected_mode=selected_mode,
            launch_method=launch_method,
            skip_conflict_prompt=_skip_conflict_prompt,
        ):
            return

        request = self._build_start_request(
            selected_mode=selected_mode,
            launch_method=launch_method,
        )
        if request is None:
            return

        if isinstance(request.selected_mode, tuple) and len(request.selected_mode) == 2:
            strategy_id, strategy_name = request.selected_mode
            log(f"Обработка встроенной стратегии: {strategy_name} (ID: {strategy_id})", "DEBUG")
        elif isinstance(request.selected_mode, dict):
            log(f"Обработка стратегии: {request.mode_name}", "DEBUG")
        elif isinstance(request.selected_mode, str):
            log(f"Обработка строковой стратегии: {request.mode_name}", "DEBUG")

        self.app.set_status(f"🚀 Запуск DPI ({request.method_name}): {request.mode_name}")
        
        # Показываем индикатор только на уже загруженной странице стратегий
        # для активного метода запуска, без старого обязательного attr-контракта.
        bridge = self._runtime_ui_bridge()
        if bridge is not None:
            bridge.show_active_strategy_page_loading()
        
        store = getattr(self.app, "ui_state_store", None)
        if store is not None:
            store.set_launch_busy(True, "Запуск Zapret...")

        self._begin_runtime_start(request.launch_method, request.selected_mode)

        start_worker_thread(
            self,
            thread_attr="_dpi_start_thread",
            worker_attr="_dpi_start_worker",
            worker=DirectLaunchStartWorker(self.app, request.selected_mode, request.launch_method),
            finished_slot=self._on_dpi_start_finished,
            progress_slot=self.app.set_status,
            cleanup_log_label="потока запуска",
        )
        
        log(f"Запуск асинхронного старта DPI: {request.mode_name} (метод: {request.method_name})", "INFO")

    def stop_dpi_async(
        self,
        *,
        force_cleanup: bool = False,
        cleanup_services: bool = False,
    ):
        """Асинхронно останавливает DPI без блокировки UI"""
        # Проверка на уже запущенный поток
        try:
            if self._dpi_stop_thread and self._dpi_stop_thread.isRunning():
                log("Остановка DPI уже выполняется", "DEBUG")
                return
        except RuntimeError:
            self._dpi_stop_thread = None
        
        launch_method = get_strategy_launch_method()

        # Показываем состояние остановки
        method_name = resolve_method_name(launch_method)
        self.app.set_status(f"🛑 Остановка DPI ({method_name})...")
        
        bridge = self._runtime_ui_bridge()
        if bridge is not None:
            bridge.show_active_strategy_page_loading()
        
        store = getattr(self.app, "ui_state_store", None)
        if store is not None:
            store.set_launch_busy(True, "Остановка Zapret...")

        self._begin_runtime_stop()

        # Устанавливаем флаг ручной остановки
        self.app.manually_stopped = True

        start_worker_thread(
            self,
            thread_attr="_dpi_stop_thread",
            worker_attr="_dpi_stop_worker",
            worker=DirectLaunchStopWorker(
                self.app,
                launch_method,
                force_cleanup=force_cleanup,
                cleanup_services=cleanup_services,
            ),
            finished_slot=self._on_dpi_stop_finished,
            progress_slot=self.app.set_status,
            cleanup_log_label="потока остановки",
        )

        log(f"Запуск асинхронной остановки DPI (метод: {method_name})", "INFO")
    
    def stop_and_exit_async(self):
        """Асинхронно останавливает DPI и закрывает программу"""
        self.app._is_exiting = True

        start_worker_thread(
            self,
            thread_attr="_stop_exit_thread",
            worker_attr="_stop_exit_worker",
            worker=StopAndExitWorker(self.app),
            finished_slot=self._on_stop_and_exit_finished,
            progress_slot=self.app.set_status,
            cleanup_log_label="потока stop-and-exit",
        )
    
    def _on_dpi_start_finished(self, success, error_message):
        on_dpi_start_finished_impl(self, success, error_message)

    def _on_dpi_stop_finished(self, success, error_message):
        on_dpi_stop_finished_impl(self, success, error_message)

    def _on_direct_preset_switch_finished(self, success, error_message, generation, launch_method, skipped_as_stale):
        handle_direct_preset_switch_finished(
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
        try:
            runtime_service = getattr(self.app, "launch_runtime_service", None)
            if runtime_service is not None:
                snapshot = runtime_service.snapshot()
                phase = str(getattr(snapshot, "phase", "") or "").strip().lower()
                if bool(getattr(snapshot, "running", False)) and phase == "running":
                    return True
        except Exception:
            pass

        try:
            from winws_runtime.runners.runner_factory import get_current_runner

            runner = get_current_runner()
            if runner is not None:
                snapshot_getter = getattr(runner, "get_runner_state_snapshot", None)
                if callable(snapshot_getter):
                    snapshot = snapshot_getter()
                    state_value = str(getattr(snapshot, "state", "") or "").strip().lower()
                    if state_value == "running":
                        return True

                is_runner_running = getattr(runner, "is_running", None)
                if callable(is_runner_running) and bool(is_runner_running()):
                    return True
        except Exception:
            pass

        return bool(self.app.launch_runtime_api.is_any_running(silent=True))

    def restart_dpi_async(self, *, force_full_stop: bool = False):
        """
        Перезапускает DPI по модели "последний запрос побеждает".

        Старые запросы не исполняются повторно: если пользователь быстро
        переключает пресеты, мы запоминаем только последнее поколение
        запроса и продолжаем pipeline от него.
        """
        restart_dpi_async_impl(self, force_full_stop=force_full_stop)
