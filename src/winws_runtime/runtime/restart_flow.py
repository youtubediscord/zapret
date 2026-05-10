from __future__ import annotations

from PyQt6.QtCore import QTimer

from log.log import log

from settings.dpi.strategy_settings import get_strategy_launch_method
from settings.mode import is_preset_launch_method
from ui.runtime_ui_bridge import ensure_runtime_ui_bridge

from .discord_restart_flow import maybe_restart_discord_after_runtime_apply
from .lifecycle_feedback import show_launch_error_top
from .status_flow import runner_transition_in_progress
from .thread_runtime import start_worker_thread
from .control_workers import PresetSwitchWorker
from winws_runtime.flow.start_preparation import resolve_launch_method


def process_pending_presets_switch(controller) -> None:
    target_generation = int(controller._presets_switch_requested_generation or 0)
    if target_generation <= int(controller._presets_switch_completed_generation or 0):
        return

    launch_method = str(
        controller._presets_switch_method or get_strategy_launch_method() or ""
    ).strip().lower()
    if not is_preset_launch_method(launch_method):
        return

    if runner_transition_in_progress(controller, launch_method=launch_method):
        log(
            f"Preset mode switch отложен: runner transition ещё идёт ({launch_method}), поколение {target_generation}",
            "DEBUG",
        )
        controller._schedule_pending_preset_switch_retry()
        return

    try:
        if controller._presets_switch_thread and controller._presets_switch_thread.isRunning():
            return
    except RuntimeError:
        controller._presets_switch_thread = None

    try:
        if controller._dpi_start_thread and controller._dpi_start_thread.isRunning():
            log(
                f"Preset mode switch отложен: основной start pipeline ещё идёт, поколение {target_generation}",
                "DEBUG",
            )
            return
    except RuntimeError:
        controller._dpi_start_thread = None

    try:
        if controller._dpi_stop_thread and controller._dpi_stop_thread.isRunning():
            log(
                f"Preset mode switch отложен: stop pipeline ещё идёт, поколение {target_generation}",
                "DEBUG",
            )
            return
    except RuntimeError:
        controller._dpi_stop_thread = None

    if not controller.is_running():
        log("Preset mode switch пропущен: DPI уже не запущен", "DEBUG")
        controller._presets_switch_completed_generation = target_generation
        return

    bridge = ensure_runtime_ui_bridge(controller.app)
    if bridge is not None:
        bridge.show_active_preset_setup_page_loading()

    start_worker_thread(
        controller,
        thread_attr="_presets_switch_thread",
        worker_attr="_presets_switch_worker",
        worker=PresetSwitchWorker(
            controller.app,
            launch_method,
            target_generation,
            lambda generation: generation == controller._presets_switch_requested_generation,
        ),
        finished_slot=controller._on_presets_switch_finished,
        progress_slot=controller.app.set_status,
        cleanup_log_label="preset mode switch thread",
    )


def switch_presets_async(controller, launch_method: str | None = None) -> None:
    method = str(launch_method or get_strategy_launch_method() or "").strip().lower()
    if not is_preset_launch_method(method):
        controller.restart_dpi_async()
        return

    controller._presets_switch_method = method
    controller._presets_switch_requested_generation += 1
    log(
        f"Preset mode switch запросили, актуальное поколение {controller._presets_switch_requested_generation} ({method})",
        "INFO",
    )
    process_pending_presets_switch(controller)


def process_pending_restart_request(controller) -> None:
    target_generation = int(controller._restart_request_generation or 0)
    if target_generation <= int(controller._restart_completed_generation or 0):
        return

    force_full_stop = int(controller._restart_force_stop_generation or 0) == target_generation

    method = resolve_launch_method()
    if runner_transition_in_progress(controller, launch_method=method):
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
        if controller._presets_switch_thread and controller._presets_switch_thread.isRunning():
            log(
                f"Перезапуск DPI отложен: preset mode switch ещё идёт, актуальное поколение {target_generation}",
                "DEBUG",
            )
            controller._schedule_pending_restart_retry()
            return
    except RuntimeError:
        controller._presets_switch_thread = None

    current_running = bool(controller.is_running())
    if current_running or force_full_stop:
        controller._restart_pending_stop_generation = target_generation
        if force_full_stop and not current_running:
            log(
                f"Перезапуск DPI: смена режима требует полного stop+cleanup, актуальное поколение {target_generation}",
                "INFO",
            )
        else:
            log(
                f"Перезапуск DPI: сначала останавливаем текущий процесс, актуальное поколение {target_generation}",
                "INFO",
            )
        controller.stop_dpi_async(
            force_cleanup=force_full_stop,
            cleanup_services=False,
        )
        return

    controller._restart_active_start_generation = target_generation
    log(
        f"Перезапуск DPI: запускаем актуальный выбранный пресет, поколение {target_generation}",
        "INFO",
    )
    controller.start_dpi_async()


def handle_presets_switch_finished(controller, success, error_message, generation, launch_method, skipped_as_stale) -> None:
    try:
        controller._runtime_service().set_busy(False)

        bridge = ensure_runtime_ui_bridge(controller.app)
        if bridge is not None:
            bridge.show_active_preset_setup_page_success()

        controller._presets_switch_completed_generation = max(
            int(controller._presets_switch_completed_generation or 0),
            int(generation or 0),
        )

        if skipped_as_stale:
            log(
                f"Preset mode switch поколения {generation} пропущен как устаревший ({launch_method})",
                "DEBUG",
            )
        elif success:
            log(
                f"Preset mode switch успешно завершён, поколение {generation} ({launch_method})",
                "INFO",
            )
            maybe_restart_discord_after_runtime_apply(controller, skip_first_start=False)
            if int(controller._presets_switch_requested_generation or 0) <= int(controller._presets_switch_completed_generation or 0):
                controller.app.set_status("✅ Пресет успешно применён")
        else:
            log(
                f"Ошибка preset mode switch, поколение {generation} ({launch_method}): {error_message}",
                "❌ ERROR",
            )
            controller.app.set_status(f"❌ Ошибка переключения пресета: {error_message}")
            show_launch_error_top(controller, error_message)
    finally:
        if controller._presets_switch_requested_generation > controller._presets_switch_completed_generation:
            QTimer.singleShot(0, controller._process_pending_presets_switch)


def restart_dpi_async(controller, *, force_full_stop: bool = False) -> None:
    controller._restart_request_generation += 1
    if force_full_stop:
        controller._restart_force_stop_generation = int(controller._restart_request_generation)
    log(
        f"Перезапуск DPI запросили, актуальное поколение {controller._restart_request_generation}",
        "INFO",
    )
    process_pending_restart_request(controller)
