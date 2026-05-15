from __future__ import annotations

from PyQt6.QtCore import QTimer

from log.log import log

from .discord_restart_flow import maybe_restart_discord_after_runtime_apply
from .status_feedback import set_runtime_owner_status


def _runner_start_pid(runtime_owner) -> int | None:
    try:
        from winws_runtime.runners.runner_factory import get_current_runner

        runner = get_current_runner()
        if runner is None:
            return None

        snapshot_getter = getattr(runner, "get_runner_state_snapshot", None)
        if callable(snapshot_getter):
            snapshot = snapshot_getter()
            state_value = str(getattr(snapshot, "state", "") or "").strip().lower()
            pid = getattr(snapshot, "pid", None)
            if state_value == "running" and isinstance(pid, int):
                return pid

        process = getattr(runner, "running_process", None)
        pid = getattr(process, "pid", None)
        if isinstance(pid, int):
            return pid
    except Exception:
        return None
    return None


def show_launch_error_top(runtime_owner, message: str) -> None:
    """Показывает человеко-понятную ошибку запуска через верхний InfoBar."""
    bridge = runtime_owner._runtime_ui_bridge()
    if bridge is not None:
        bridge.show_launch_error(message)


def show_launch_warning_top(runtime_owner, message: str) -> None:
    bridge = runtime_owner._runtime_ui_bridge()
    if bridge is not None:
        bridge.show_launch_warning(message)


def verify_dpi_process_running(runtime_owner, verify_gen=None):
    """Неблокирующая проверка старта через канонический monitor/runtime путь."""
    if verify_gen is None:
        verify_gen = runtime_owner._dpi_start_verify_generation

    if verify_gen != runtime_owner._dpi_start_verify_generation:
        return

    max_retries = 25
    retry_delay_ms = 300
    runtime_service = runtime_owner._runtime_service()
    monitor_manager = runtime_owner._process_monitor_manager()

    if monitor_manager is not None and hasattr(monitor_manager, "refresh_now"):
        try:
            monitor_manager.refresh_now()
        except Exception as e:
            log(f"verify_dpi_process_running: refresh_now failed: {e}", "DEBUG")
    elif runtime_service is not None:
        try:
            from winws_runtime.runtime.process_probe import get_canonical_winws_process_pids

            runtime_service.observe_process_details(get_canonical_winws_process_pids())
        except Exception as e:
            log(f"verify_dpi_process_running: direct process refresh failed: {e}", "DEBUG")

    snapshot = runtime_service.snapshot() if runtime_service is not None else None
    phase = str(getattr(snapshot, "phase", "") or "").strip().lower()
    is_actually_running = bool(getattr(snapshot, "running", False)) and phase == "running"

    if is_actually_running:
        on_dpi_process_confirmed(runtime_owner, running=True, verify_gen=verify_gen)
    elif runtime_owner._dpi_start_verify_retry < max_retries:
        runtime_owner._dpi_start_verify_retry += 1
        QTimer.singleShot(retry_delay_ms, lambda g=verify_gen: verify_dpi_process_running(runtime_owner, g))
    else:
        on_dpi_process_confirmed(runtime_owner, running=False, verify_gen=verify_gen)


def on_dpi_process_confirmed(runtime_owner, running: bool, verify_gen=None):
    """Вызывается после подтверждения (или отказа) запуска DPI процесса."""
    if verify_gen is not None and verify_gen != runtime_owner._dpi_start_verify_generation:
        return

    runtime_owner._runtime_service().set_busy(False)

    completed_restart_generation = int(runtime_owner._restart_active_start_generation or 0)
    if completed_restart_generation:
        runtime_owner._restart_completed_generation = max(
            runtime_owner._restart_completed_generation,
            completed_restart_generation,
        )
        runtime_owner._restart_active_start_generation = 0

    if running:
        log("DPI запущен асинхронно", "INFO")
        set_runtime_owner_status(runtime_owner, "✅ DPI успешно запущен")
        runtime_owner._mark_runtime_running(pid=_runner_start_pid(runtime_owner))
        runtime_owner._runtime_feature.flags.mark_intentional_start()
        maybe_restart_discord_after_runtime_apply(runtime_owner, skip_first_start=True)

        pending_warnings = list(getattr(runtime_owner, "_pending_launch_warnings", []) or [])
        runtime_owner._pending_launch_warnings = []
        for warning_text in pending_warnings:
            log(f"Launch warning: {warning_text}", "WARNING")
            QTimer.singleShot(150, lambda text=warning_text: show_launch_warning_top(runtime_owner, text))
    else:
        log("DPI не запустился - процесс не найден после старта", "❌ ERROR")
        set_runtime_owner_status(runtime_owner, "❌ Процесс не запустился. Проверьте логи")
        show_launch_error_top(runtime_owner, "Процесс не запустился. Проверьте логи")

        runtime_owner._pending_launch_warnings = []
        runtime_owner._mark_runtime_failed("Процесс не запустился. Проверьте логи")

    if runtime_owner._restart_request_generation > runtime_owner._restart_completed_generation:
        QTimer.singleShot(0, runtime_owner._process_pending_restart_request)
    if runtime_owner._presets_switch_requested_generation > runtime_owner._presets_switch_completed_generation:
        QTimer.singleShot(0, runtime_owner._process_pending_presets_switch)


def on_dpi_start_finished(runtime_owner, success, error_message):
    """Обрабатывает завершение асинхронного запуска DPI."""
    completed_restart_generation = int(runtime_owner._restart_active_start_generation or 0)
    try:
        runtime_owner._runtime_service().set_busy(False)

        if success:
            runtime_owner._mark_runtime_running(pid=_runner_start_pid(runtime_owner))
            runtime_owner._dpi_start_verify_retry = 0
            verify_gen = runtime_owner._dpi_start_verify_generation
            verify_dpi_process_running(runtime_owner, verify_gen)
        else:
            if completed_restart_generation:
                runtime_owner._restart_completed_generation = max(
                    runtime_owner._restart_completed_generation,
                    completed_restart_generation,
                )
                runtime_owner._restart_active_start_generation = 0
            log(f"Ошибка асинхронного запуска DPI: {error_message}", "❌ ERROR")
            set_runtime_owner_status(runtime_owner, f"❌ Ошибка запуска: {error_message}")
            show_launch_error_top(runtime_owner, error_message)
            runtime_owner._mark_runtime_failed(error_message)

            if runtime_owner._restart_request_generation > runtime_owner._restart_completed_generation:
                QTimer.singleShot(0, runtime_owner._process_pending_restart_request)
            if runtime_owner._presets_switch_requested_generation > runtime_owner._presets_switch_completed_generation:
                QTimer.singleShot(0, runtime_owner._process_pending_presets_switch)

    except Exception as e:
        log(f"Ошибка при обработке результата запуска DPI: {e}", "❌ ERROR")
        runtime_owner._runtime_service().set_busy(False)
        set_runtime_owner_status(runtime_owner, f"Ошибка: {e}")


def on_dpi_stop_finished(runtime_owner, success, error_message):
    """Обрабатывает завершение асинхронной остановки DPI."""
    restart_generation_after_stop = int(runtime_owner._restart_pending_stop_generation or 0)
    try:
        runtime_owner._runtime_service().set_busy(False)

        if success:
            is_still_running = runtime_owner._runtime_api().has_residual_processes(silent=True)

            if not is_still_running:
                log("DPI остановлен асинхронно", "INFO")
                if error_message:
                    set_runtime_owner_status(runtime_owner, f"✅ {error_message}")
                else:
                    set_runtime_owner_status(runtime_owner, "✅ DPI успешно остановлен")
                runtime_owner._mark_runtime_stopped()
                if restart_generation_after_stop >= int(runtime_owner._restart_force_stop_generation or 0):
                    runtime_owner._restart_force_stop_generation = 0

                if restart_generation_after_stop > runtime_owner._restart_completed_generation:
                    runtime_owner._restart_pending_stop_generation = 0
                    runtime_owner._restart_active_start_generation = max(
                        restart_generation_after_stop,
                        runtime_owner._restart_request_generation,
                    )
                    runtime_owner.start_dpi_async()
                    return
            else:
                log("DPI всё ещё работает после попытки остановки", "⚠ WARNING")
                set_runtime_owner_status(runtime_owner, "⚠ Процесс всё ещё работает")
                runtime_owner._mark_runtime_running()
                runtime_owner._restart_pending_stop_generation = 0
        else:
            log(f"Ошибка асинхронной остановки DPI: {error_message}", "❌ ERROR")
            set_runtime_owner_status(runtime_owner, f"❌ Ошибка остановки: {error_message}")

            is_running = runtime_owner._runtime_api().has_residual_processes(silent=True)
            if is_running:
                runtime_owner._mark_runtime_running()
            else:
                runtime_owner._mark_runtime_stopped()
            if restart_generation_after_stop >= int(runtime_owner._restart_force_stop_generation or 0):
                runtime_owner._restart_force_stop_generation = 0

            runtime_owner._restart_pending_stop_generation = 0

    except Exception as e:
        log(f"Ошибка при обработке результата остановки DPI: {e}", "❌ ERROR")
        set_runtime_owner_status(runtime_owner, f"Ошибка: {e}")
    finally:
        if runtime_owner._presets_switch_requested_generation > runtime_owner._presets_switch_completed_generation:
            QTimer.singleShot(0, runtime_owner._process_pending_presets_switch)


def on_stop_and_exit_finished(runtime_owner):
    """Завершает приложение после остановки DPI."""
    set_runtime_owner_status(runtime_owner, "Завершение...")
    from PyQt6.QtWidgets import QApplication

    try:
        QApplication.closeAllWindows()
        QApplication.processEvents()
    except Exception:
        pass

    QApplication.quit()


def cleanup_threads(runtime_owner):
    """Очищает все потоки при закрытии приложения."""
    try:
        if runtime_owner._dpi_start_thread and runtime_owner._dpi_start_thread.isRunning():
            log("Останавливаем поток запуска DPI...", "DEBUG")
            runtime_owner._dpi_start_thread.quit()
            if not runtime_owner._dpi_start_thread.wait(2000):
                log("⚠ Поток запуска DPI не завершился, принудительно завершаем", "WARNING")
                try:
                    runtime_owner._dpi_start_thread.terminate()
                    runtime_owner._dpi_start_thread.wait(500)
                except Exception:
                    pass

        if runtime_owner._dpi_stop_thread and runtime_owner._dpi_stop_thread.isRunning():
            log("Останавливаем поток остановки DPI...", "DEBUG")
            runtime_owner._dpi_stop_thread.quit()
            if not runtime_owner._dpi_stop_thread.wait(2000):
                log("⚠ Поток остановки DPI не завершился, принудительно завершаем", "WARNING")
                try:
                    runtime_owner._dpi_stop_thread.terminate()
                    runtime_owner._dpi_stop_thread.wait(500)
                except Exception:
                    pass

        runtime_owner._dpi_start_thread = None
        runtime_owner._dpi_stop_thread = None

    except Exception as e:
        log(f"Ошибка при очистке потоков DPI runtime: {e}", "❌ ERROR")
