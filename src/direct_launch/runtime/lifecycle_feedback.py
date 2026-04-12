from __future__ import annotations

from PyQt6.QtCore import QTimer

from app_notifications import advisory_notification, notification_action
from log import log
from ui.main_window_page_dispatch import show_active_strategy_page_success


def show_launch_error_top(controller, message: str) -> None:
    """Показывает человеко-понятную ошибку запуска через верхний InfoBar."""
    text = str(message or "").strip()
    if not text:
        return
    try:
        while text.startswith(("❌", "⚠️", "⚠")):
            text = text[1:].strip()
    except Exception:
        pass
    if not text:
        text = "Не удалось запустить DPI"

    try:
        notification_controller = getattr(controller.app, "window_notification_controller", None)
        if notification_controller is not None:
            auto_fix_action = None
            if text.startswith("[AUTOFIX:"):
                end_idx = text.find("]")
                if end_idx > 0:
                    auto_fix_action = text[9:end_idx]
                    text = text[end_idx + 1 :].strip()

            buttons = []
            duration = 10000
            if auto_fix_action:
                buttons.append(notification_action("autofix", "Исправить", value=auto_fix_action))
                duration = -1

            notification_controller.notify(
                advisory_notification(
                    level="error",
                    title="Ошибка",
                    content=text,
                    source="launch.dpi_error",
                    presentation="infobar",
                    queue="immediate",
                    duration=duration,
                    buttons=buttons,
                    dedupe_key=f"launch.dpi_error:{' '.join(text.split()).lower()}",
                )
            )
    except Exception as e:
        log(f"Не удалось показать InfoBar ошибки запуска: {e}", "DEBUG")


def show_launch_warning_top(controller, message: str) -> None:
    text = str(message or "").strip()
    if not text:
        return
    try:
        while text.startswith(("⚠️", "⚠")):
            text = text[1:].strip()
    except Exception:
        pass
    if not text:
        return

    try:
        notification_controller = getattr(controller.app, "window_notification_controller", None)
        if notification_controller is not None:
            notification_controller.notify(
                advisory_notification(
                    level="warning",
                    title="Предупреждение",
                    content=text,
                    source="launch.dpi_warning",
                    presentation="infobar",
                    queue="immediate",
                    duration=9000,
                    dedupe_key=f"launch.dpi_warning:{' '.join(text.split()).lower()}",
                )
            )
    except Exception as e:
        log(f"Не удалось показать InfoBar предупреждения запуска: {e}", "DEBUG")


def verify_dpi_process_running(controller, verify_gen=None):
    """Неблокирующая проверка старта через канонический monitor/runtime путь."""
    if verify_gen is None:
        verify_gen = controller._dpi_start_verify_generation

    if verify_gen != controller._dpi_start_verify_generation:
        return

    max_retries = 25
    retry_delay_ms = 300
    runtime_service = getattr(controller.app, "launch_runtime_service", None)
    monitor_manager = getattr(controller.app, "process_monitor_manager", None)

    if monitor_manager is not None and hasattr(monitor_manager, "refresh_now"):
        try:
            monitor_manager.refresh_now()
        except Exception as e:
            log(f"verify_dpi_process_running: refresh_now failed: {e}", "DEBUG")
    elif runtime_service is not None:
        try:
            from direct_launch.runtime import get_canonical_winws_process_pids

            runtime_service.observe_process_details(get_canonical_winws_process_pids())
        except Exception as e:
            log(f"verify_dpi_process_running: canonical fallback refresh failed: {e}", "DEBUG")

    snapshot = runtime_service.snapshot() if runtime_service is not None else None
    phase = str(getattr(snapshot, "phase", "") or "").strip().lower()
    is_actually_running = bool(getattr(snapshot, "running", False)) and phase == "running"

    if is_actually_running:
        on_dpi_process_confirmed(controller, running=True, verify_gen=verify_gen)
    elif controller._dpi_start_verify_retry < max_retries:
        controller._dpi_start_verify_retry += 1
        QTimer.singleShot(retry_delay_ms, lambda g=verify_gen: verify_dpi_process_running(controller, g))
    else:
        on_dpi_process_confirmed(controller, running=False, verify_gen=verify_gen)


def on_dpi_process_confirmed(controller, running: bool, verify_gen=None):
    """Вызывается после подтверждения (или отказа) запуска DPI процесса."""
    if verify_gen is not None and verify_gen != controller._dpi_start_verify_generation:
        return

    store = getattr(controller.app, "ui_state_store", None)
    if store is not None:
        store.set_launch_busy(False)

    completed_restart_generation = int(controller._restart_active_start_generation or 0)
    if completed_restart_generation:
        controller._restart_completed_generation = max(
            controller._restart_completed_generation,
            completed_restart_generation,
        )
        controller._restart_active_start_generation = 0

    if running:
        log("DPI запущен асинхронно", "INFO")
        controller.app.set_status("✅ DPI успешно запущен")
        controller._mark_runtime_running()
        controller.app.intentional_start = True
        controller._maybe_restart_discord_after_runtime_apply(skip_first_start=True)

        pending_warnings = list(getattr(controller, "_pending_launch_warnings", []) or [])
        controller._pending_launch_warnings = []
        for warning_text in pending_warnings:
            log(f"Launch warning: {warning_text}", "WARNING")
            QTimer.singleShot(150, lambda text=warning_text: show_launch_warning_top(controller, text))
    else:
        log("DPI не запустился - процесс не найден после старта", "❌ ERROR")
        controller.app.set_status("❌ Процесс не запустился. Проверьте логи")
        show_launch_error_top(controller, "Процесс не запустился. Проверьте логи")

        controller._pending_launch_warnings = []
        controller._mark_runtime_failed("Процесс не запустился. Проверьте логи")

    if controller._restart_request_generation > controller._restart_completed_generation:
        QTimer.singleShot(0, controller._process_pending_restart_request)
    if controller._direct_preset_switch_requested_generation > controller._direct_preset_switch_completed_generation:
        QTimer.singleShot(0, controller._process_pending_direct_preset_switch)


def on_dpi_start_finished(controller, success, error_message):
    """Обрабатывает завершение асинхронного запуска DPI."""
    completed_restart_generation = int(controller._restart_active_start_generation or 0)
    try:
        if hasattr(controller.app, "main_window"):
            show_active_strategy_page_success(controller.app.main_window)

        if success:
            controller._dpi_start_verify_retry = 0
            verify_gen = controller._dpi_start_verify_generation
            verify_dpi_process_running(controller, verify_gen)
        else:
            if completed_restart_generation:
                controller._restart_completed_generation = max(
                    controller._restart_completed_generation,
                    completed_restart_generation,
                )
                controller._restart_active_start_generation = 0
            log(f"Ошибка асинхронного запуска DPI: {error_message}", "❌ ERROR")
            controller.app.set_status(f"❌ Ошибка запуска: {error_message}")
            show_launch_error_top(controller, error_message)
            controller._mark_runtime_failed(error_message)

            if controller._restart_request_generation > controller._restart_completed_generation:
                QTimer.singleShot(0, controller._process_pending_restart_request)
            if controller._direct_preset_switch_requested_generation > controller._direct_preset_switch_completed_generation:
                QTimer.singleShot(0, controller._process_pending_direct_preset_switch)

    except Exception as e:
        log(f"Ошибка при обработке результата запуска DPI: {e}", "❌ ERROR")
        controller.app.set_status(f"Ошибка: {e}")


def on_dpi_stop_finished(controller, success, error_message):
    """Обрабатывает завершение асинхронной остановки DPI."""
    restart_generation_after_stop = int(controller._restart_pending_stop_generation or 0)
    try:
        store = getattr(controller.app, "ui_state_store", None)
        if store is not None:
            store.set_launch_busy(False)

        if hasattr(controller.app, "main_window"):
            show_active_strategy_page_success(controller.app.main_window)

        if success:
            is_still_running = controller.app.launch_runtime_api.is_any_running(silent=True)

            if not is_still_running:
                log("DPI остановлен асинхронно", "INFO")
                if error_message:
                    controller.app.set_status(f"✅ {error_message}")
                else:
                    controller.app.set_status("✅ DPI успешно остановлен")
                controller._mark_runtime_stopped()

                if restart_generation_after_stop > controller._restart_completed_generation:
                    controller._restart_pending_stop_generation = 0
                    controller._restart_active_start_generation = max(
                        restart_generation_after_stop,
                        controller._restart_request_generation,
                    )
                    controller.start_dpi_async()
                    return
            else:
                log("DPI всё ещё работает после попытки остановки", "⚠ WARNING")
                controller.app.set_status("⚠ Процесс всё ещё работает")
                controller._mark_runtime_running()
                controller._restart_pending_stop_generation = 0
        else:
            log(f"Ошибка асинхронной остановки DPI: {error_message}", "❌ ERROR")
            controller.app.set_status(f"❌ Ошибка остановки: {error_message}")

            is_running = controller.app.launch_runtime_api.is_any_running(silent=True)
            if is_running:
                controller._mark_runtime_running()
            else:
                controller._mark_runtime_stopped()

            controller._restart_pending_stop_generation = 0

    except Exception as e:
        log(f"Ошибка при обработке результата остановки DPI: {e}", "❌ ERROR")
        controller.app.set_status(f"Ошибка: {e}")
    finally:
        if controller._direct_preset_switch_requested_generation > controller._direct_preset_switch_completed_generation:
            QTimer.singleShot(0, controller._process_pending_direct_preset_switch)


def on_stop_and_exit_finished(controller):
    """Завершает приложение после остановки DPI."""
    controller.app.set_status("Завершение...")
    from PyQt6.QtWidgets import QApplication

    try:
        QApplication.closeAllWindows()
        QApplication.processEvents()
    except Exception:
        pass

    QApplication.quit()


def cleanup_threads(controller):
    """Очищает все потоки при закрытии приложения."""
    try:
        if controller._dpi_start_thread and controller._dpi_start_thread.isRunning():
            log("Останавливаем поток запуска DPI...", "DEBUG")
            controller._dpi_start_thread.quit()
            if not controller._dpi_start_thread.wait(2000):
                log("⚠ Поток запуска DPI не завершился, принудительно завершаем", "WARNING")
                try:
                    controller._dpi_start_thread.terminate()
                    controller._dpi_start_thread.wait(500)
                except Exception:
                    pass

        if controller._dpi_stop_thread and controller._dpi_stop_thread.isRunning():
            log("Останавливаем поток остановки DPI...", "DEBUG")
            controller._dpi_stop_thread.quit()
            if not controller._dpi_stop_thread.wait(2000):
                log("⚠ Поток остановки DPI не завершился, принудительно завершаем", "WARNING")
                try:
                    controller._dpi_stop_thread.terminate()
                    controller._dpi_stop_thread.wait(500)
                except Exception:
                    pass

        controller._dpi_start_thread = None
        controller._dpi_stop_thread = None

    except Exception as e:
        log(f"Ошибка при очистке потоков DPI контроллера: {e}", "❌ ERROR")
