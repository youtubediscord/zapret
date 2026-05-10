from __future__ import annotations

from log.log import log

from winws_runtime.flow.start_preparation import prepare_start_request

from .conflict_flow import handle_conflicting_processes_before_start
from .lifecycle_feedback import show_launch_error_top
from .start_workers import PresetLaunchStartWorker
from .thread_runtime import start_worker_thread


def fail_start_preparation(controller, message: str) -> None:
    text = str(message or "").strip() or "Не удалось подготовить запуск DPI"
    log(f"Ошибка подготовки запуска: {text}", "❌ ERROR")
    controller.app.set_status(f"❌ {text}")
    show_launch_error_top(controller, text)
    controller._mark_runtime_failed(text)


def prepare_start_preflight(
    controller,
    *,
    selected_mode=None,
    launch_method=None,
    skip_conflict_prompt: bool = False,
) -> bool:
    """Выполняет раннюю проверку перед построением launch request."""
    try:
        if controller._dpi_start_thread and controller._dpi_start_thread.isRunning():
            log("Запуск DPI уже выполняется", "DEBUG")
            return False
    except RuntimeError:
        controller._dpi_start_thread = None

    controller._pending_launch_warnings = []

    if not skip_conflict_prompt and not handle_conflicting_processes_before_start(
        controller,
        selected_mode,
        launch_method,
    ):
        return False

    controller._dpi_start_verify_generation += 1
    return True


def build_start_request(
    controller,
    *,
    selected_mode=None,
    launch_method=None,
):
    """Строит launch request и сохраняет предупреждения подготовки запуска."""
    try:
        request, warnings = prepare_start_request(
            selected_mode,
            launch_method,
            app_context=controller.app.app_context,
        )
    except Exception as e:
        fail_start_preparation(controller, str(e))
        return None

    controller._pending_launch_warnings = list(warnings or [])
    return request


def start_dpi_async(
    controller,
    selected_mode=None,
    launch_method=None,
    *,
    skip_conflict_prompt: bool = False,
    startup_autostart: bool = False,
) -> None:
    """Запускает DPI через общий асинхронный pipeline."""
    if not prepare_start_preflight(
        controller,
        selected_mode=selected_mode,
        launch_method=launch_method,
        skip_conflict_prompt=skip_conflict_prompt,
    ):
        return

    request = build_start_request(
        controller,
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

    controller.app.set_status(f"🚀 Запуск DPI ({request.method_name}): {request.mode_name}")

    if not startup_autostart:
        bridge = controller._runtime_ui_bridge()
        if bridge is not None:
            bridge.show_active_preset_setup_page_loading()
        controller._runtime_service().set_busy(True, "Запуск Zapret...")

    controller._begin_runtime_start(request.launch_method, request.selected_mode)

    start_worker_thread(
        controller,
        thread_attr="_dpi_start_thread",
        worker_attr="_dpi_start_worker",
        worker=PresetLaunchStartWorker(controller.app, request.selected_mode, request.launch_method),
        finished_slot=controller._on_dpi_start_finished,
        progress_slot=controller.app.set_status,
        cleanup_log_label="потока запуска",
    )

    log(f"Запуск асинхронного старта DPI: {request.mode_name} (метод: {request.method_name})", "INFO")
