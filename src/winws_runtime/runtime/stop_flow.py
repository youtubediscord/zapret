from __future__ import annotations

from log.log import log
from settings.dpi.strategy_settings import get_strategy_launch_method
from winws_runtime.flow.start_preparation import resolve_method_name

from .control_workers import PresetLaunchStopWorker, StopAndExitWorker
from .thread_runtime import start_worker_thread


def stop_dpi_async(
    controller,
    *,
    force_cleanup: bool = False,
    cleanup_services: bool = False,
) -> None:
    """Останавливает DPI через общий асинхронный pipeline."""
    try:
        if controller._dpi_stop_thread and controller._dpi_stop_thread.isRunning():
            log("Остановка DPI уже выполняется", "DEBUG")
            return
    except RuntimeError:
        controller._dpi_stop_thread = None

    launch_method = get_strategy_launch_method()
    method_name = resolve_method_name(launch_method)
    controller.app.set_status(f"🛑 Остановка DPI ({method_name})...")

    bridge = controller._runtime_ui_bridge()
    if bridge is not None:
        bridge.show_active_preset_setup_page_loading()

    controller._runtime_service().set_busy(True, "Остановка Zapret...")
    controller._begin_runtime_stop()
    controller.app.manually_stopped = True

    start_worker_thread(
        controller,
        thread_attr="_dpi_stop_thread",
        worker_attr="_dpi_stop_worker",
        worker=PresetLaunchStopWorker(
            controller.app,
            launch_method,
            force_cleanup=force_cleanup,
            cleanup_services=cleanup_services,
        ),
        finished_slot=controller._on_dpi_stop_finished,
        progress_slot=controller.app.set_status,
        cleanup_log_label="потока остановки",
    )

    log(f"Запуск асинхронной остановки DPI (метод: {method_name})", "INFO")


def stop_and_exit_async(controller) -> None:
    """Останавливает DPI и закрывает программу через worker-поток."""
    controller.app._is_exiting = True

    start_worker_thread(
        controller,
        thread_attr="_stop_exit_thread",
        worker_attr="_stop_exit_worker",
        worker=StopAndExitWorker(controller.app),
        finished_slot=controller._on_stop_and_exit_finished,
        progress_slot=controller.app.set_status,
        cleanup_log_label="потока stop-and-exit",
    )
