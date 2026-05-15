from __future__ import annotations

from log.log import log
from settings.dpi.strategy_settings import get_strategy_launch_method
from winws_runtime.flow.start_preparation import resolve_method_name

from .control_workers import PresetLaunchStopWorker, StopAndExitWorker
from .status_feedback import runtime_owner_status_callback, set_runtime_owner_status
from .thread_runtime import start_worker_thread


def stop_dpi_async(
    runtime_owner,
    *,
    force_cleanup: bool = False,
    cleanup_services: bool = False,
) -> None:
    """Останавливает DPI через общий асинхронный pipeline."""
    try:
        if runtime_owner._dpi_stop_thread and runtime_owner._dpi_stop_thread.isRunning():
            log("Остановка DPI уже выполняется", "DEBUG")
            return
    except RuntimeError:
        runtime_owner._dpi_stop_thread = None

    launch_method = get_strategy_launch_method()
    method_name = resolve_method_name(launch_method)
    set_runtime_owner_status(runtime_owner, f"🛑 Остановка DPI ({method_name})...")

    runtime_owner._runtime_service().set_busy(True, "Остановка Zapret...")
    runtime_owner._begin_runtime_stop()
    runtime_owner._runtime_feature.flags.mark_manual_stop()

    start_worker_thread(
        runtime_owner,
        thread_attr="_dpi_stop_thread",
        worker_attr="_dpi_stop_worker",
        worker=PresetLaunchStopWorker(
            launch_method,
            runtime_feature=runtime_owner._runtime_feature,
            runtime_api=runtime_owner._runtime_api(),
            force_cleanup=force_cleanup,
            cleanup_services=cleanup_services,
        ),
        finished_slot=runtime_owner._on_dpi_stop_finished,
        progress_slot=runtime_owner_status_callback(runtime_owner),
        cleanup_log_label="потока остановки",
    )

    log(f"Запуск асинхронной остановки DPI (метод: {method_name})", "INFO")


def stop_and_exit_async(runtime_owner) -> None:
    """Останавливает DPI и закрывает программу через worker-поток."""
    runtime_owner._runtime_feature.lifecycle.mark_stop_and_exit_requested()

    start_worker_thread(
        runtime_owner,
        thread_attr="_stop_exit_thread",
        worker_attr="_stop_exit_worker",
        worker=StopAndExitWorker(
            runtime_feature=runtime_owner._runtime_feature,
        ),
        finished_slot=runtime_owner._on_stop_and_exit_finished,
        progress_slot=runtime_owner_status_callback(runtime_owner),
        cleanup_log_label="потока stop-and-exit",
    )
