from __future__ import annotations

from PyQt6.QtCore import QTimer

from log.log import log

from settings.dpi.strategy_settings import get_strategy_launch_method
from ui.runtime_ui_bridge import ensure_runtime_ui_bridge

from .thread_runtime import start_worker_thread
from .workers import DirectPresetSwitchWorker
from winws_runtime.flow.start_preparation import resolve_launch_method


def process_pending_direct_preset_switch(controller) -> None:
    target_generation = int(controller._direct_preset_switch_requested_generation or 0)
    if target_generation <= int(controller._direct_preset_switch_completed_generation or 0):
        return

    launch_method = str(
        controller._direct_preset_switch_method or get_strategy_launch_method() or ""
    ).strip().lower()
    if launch_method not in ("direct_zapret1", "direct_zapret2"):
        return

    if controller._runner_transition_in_progress(launch_method=launch_method):
        log(
            f"Direct preset switch отложен: runner transition ещё идёт ({launch_method}), поколение {target_generation}",
            "DEBUG",
        )
        controller._schedule_pending_direct_switch_retry()
        return

    try:
        if controller._direct_preset_switch_thread and controller._direct_preset_switch_thread.isRunning():
            return
    except RuntimeError:
        controller._direct_preset_switch_thread = None

    try:
        if controller._dpi_start_thread and controller._dpi_start_thread.isRunning():
            log(
                f"Direct preset switch отложен: основной start pipeline ещё идёт, поколение {target_generation}",
                "DEBUG",
            )
            return
    except RuntimeError:
        controller._dpi_start_thread = None

    try:
        if controller._dpi_stop_thread and controller._dpi_stop_thread.isRunning():
            log(
                f"Direct preset switch отложен: stop pipeline ещё идёт, поколение {target_generation}",
                "DEBUG",
            )
            return
    except RuntimeError:
        controller._dpi_stop_thread = None

    if not controller.is_running():
        log("Direct preset switch пропущен: DPI уже не запущен", "DEBUG")
        controller._direct_preset_switch_completed_generation = target_generation
        return

    bridge = ensure_runtime_ui_bridge(controller.app)
    if bridge is not None:
        bridge.show_active_strategy_page_loading()

    start_worker_thread(
        controller,
        thread_attr="_direct_preset_switch_thread",
        worker_attr="_direct_preset_switch_worker",
        worker=DirectPresetSwitchWorker(
            controller.app,
            launch_method,
            target_generation,
            lambda generation: generation == controller._direct_preset_switch_requested_generation,
        ),
        finished_slot=controller._on_direct_preset_switch_finished,
        progress_slot=controller.app.set_status,
        cleanup_log_label="direct preset switch thread",
    )


def switch_direct_preset_async(controller, launch_method: str | None = None) -> None:
    method = str(launch_method or get_strategy_launch_method() or "").strip().lower()
    if method not in ("direct_zapret1", "direct_zapret2"):
        controller.restart_dpi_async()
        return

    controller._direct_preset_switch_method = method
    controller._direct_preset_switch_requested_generation += 1
    log(
        f"Direct preset switch запросили, актуальное поколение {controller._direct_preset_switch_requested_generation} ({method})",
        "INFO",
    )
    process_pending_direct_preset_switch(controller)


def process_pending_restart_request(controller) -> None:
    target_generation = int(controller._restart_request_generation or 0)
    if target_generation <= int(controller._restart_completed_generation or 0):
        return

    method = resolve_launch_method()
    if controller._runner_transition_in_progress(launch_method=method):
        log(
            f"Перезапуск DPI отложен: runner transition ещё идёт ({method}), актуальное поколение {target_generation}",
            "DEBUG",
        )
        controller._schedule_pending_restart_retry()
        return

    try:
        if controller._dpi_start_thread and controller._dpi_start_thread.isRunning():
            log(
                f"Перезапуск DPI отложен: запуск ещё идёт, актуальное поколение {target_generation}",
                "DEBUG",
            )
            return
    except RuntimeError:
        controller._dpi_start_thread = None

    try:
        if controller._dpi_stop_thread and controller._dpi_stop_thread.isRunning():
            controller._restart_pending_stop_generation = target_generation
            log(
                f"Перезапуск DPI отложен: остановка ещё идёт, актуальное поколение {target_generation}",
                "DEBUG",
            )
            return
    except RuntimeError:
        controller._dpi_stop_thread = None

    try:
        if controller._direct_preset_switch_thread and controller._direct_preset_switch_thread.isRunning():
            log(
                f"Перезапуск DPI отложен: direct preset switch ещё идёт, актуальное поколение {target_generation}",
                "DEBUG",
            )
            controller._schedule_pending_restart_retry()
            return
    except RuntimeError:
        controller._direct_preset_switch_thread = None

    if controller.is_running():
        controller._restart_pending_stop_generation = target_generation
        log(
            f"Перезапуск DPI: сначала останавливаем текущий процесс, актуальное поколение {target_generation}",
            "INFO",
        )
        controller.stop_dpi_async()
        return

    controller._restart_active_start_generation = target_generation
    log(
        f"Перезапуск DPI: запускаем актуальный выбранный пресет, поколение {target_generation}",
        "INFO",
    )
    controller.start_dpi_async()


def handle_direct_preset_switch_finished(controller, success, error_message, generation, launch_method, skipped_as_stale) -> None:
    try:
        store = getattr(controller.app, "ui_state_store", None)
        if store is not None:
            store.set_launch_busy(False)

        bridge = ensure_runtime_ui_bridge(controller.app)
        if bridge is not None:
            bridge.show_active_strategy_page_success()

        controller._direct_preset_switch_completed_generation = max(
            int(controller._direct_preset_switch_completed_generation or 0),
            int(generation or 0),
        )

        if skipped_as_stale:
            log(
                f"Direct preset switch поколения {generation} пропущен как устаревший ({launch_method})",
                "DEBUG",
            )
        elif success:
            log(
                f"Direct preset switch успешно завершён, поколение {generation} ({launch_method})",
                "INFO",
            )
            controller._maybe_restart_discord_after_runtime_apply(skip_first_start=False)
            if int(controller._direct_preset_switch_requested_generation or 0) <= int(controller._direct_preset_switch_completed_generation or 0):
                controller.app.set_status("✅ Пресет успешно применён")
        else:
            log(
                f"Ошибка direct preset switch, поколение {generation} ({launch_method}): {error_message}",
                "❌ ERROR",
            )
            controller.app.set_status(f"❌ Ошибка переключения пресета: {error_message}")
            controller._show_launch_error_top(error_message)
    finally:
        if controller._direct_preset_switch_requested_generation > controller._direct_preset_switch_completed_generation:
            QTimer.singleShot(0, controller._process_pending_direct_preset_switch)


def restart_dpi_async(controller) -> None:
    controller._restart_request_generation += 1
    log(
        f"Перезапуск DPI запросили, актуальное поколение {controller._restart_request_generation}",
        "INFO",
    )
    process_pending_restart_request(controller)
