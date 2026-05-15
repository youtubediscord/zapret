from __future__ import annotations

from log.log import log

from winws_runtime.flow.start_preparation import prepare_start_request

from .conflict_flow import handle_conflicting_processes_before_start
from .lifecycle_feedback import show_launch_error_top
from .status_feedback import runtime_owner_status_callback, set_runtime_owner_status
from .start_workers import PresetLaunchStartWorker
from .thread_runtime import start_worker_thread


def fail_start_preparation(runtime_owner, message: str) -> None:
    text = str(message or "").strip() or "Не удалось подготовить запуск DPI"
    log(f"Ошибка подготовки запуска: {text}", "❌ ERROR")
    set_runtime_owner_status(runtime_owner, f"❌ {text}")
    show_launch_error_top(runtime_owner, text)
    runtime_owner._mark_runtime_failed(text)


def prepare_start_preflight(
    runtime_owner,
    *,
    selected_mode=None,
    launch_method=None,
    skip_conflict_prompt: bool = False,
) -> bool:
    """Выполняет раннюю проверку перед построением launch request."""
    try:
        if runtime_owner._dpi_start_thread and runtime_owner._dpi_start_thread.isRunning():
            log("Запуск DPI уже выполняется", "DEBUG")
            return False
    except RuntimeError:
        runtime_owner._dpi_start_thread = None

    runtime_owner._pending_launch_warnings = []

    if not skip_conflict_prompt and not handle_conflicting_processes_before_start(
        runtime_owner,
        selected_mode,
        launch_method,
    ):
        return False

    runtime_owner._dpi_start_verify_generation += 1
    return True


def build_start_request(
    runtime_owner,
    *,
    selected_mode=None,
    launch_method=None,
):
    """Строит launch request и сохраняет предупреждения подготовки запуска."""
    try:
        request, warnings = prepare_start_request(
            selected_mode,
            launch_method,
            presets_feature=runtime_owner._runtime_feature.dependencies.presets_feature,
        )
    except Exception as e:
        fail_start_preparation(runtime_owner, str(e))
        return None

    runtime_owner._pending_launch_warnings = list(warnings or [])
    return request


def start_dpi_async(
    runtime_owner,
    selected_mode=None,
    launch_method=None,
    *,
    skip_conflict_prompt: bool = False,
    startup_autostart: bool = False,
) -> None:
    """Запускает DPI через общий асинхронный pipeline."""
    if not prepare_start_preflight(
        runtime_owner,
        selected_mode=selected_mode,
        launch_method=launch_method,
        skip_conflict_prompt=skip_conflict_prompt,
    ):
        return

    request = build_start_request(
        runtime_owner,
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

    set_runtime_owner_status(runtime_owner, f"🚀 Запуск DPI ({request.method_name}): {request.mode_name}")

    if not startup_autostart:
        runtime_owner._runtime_service().set_busy(True, "Запуск Zapret...")

    runtime_owner._begin_runtime_start(request.launch_method, request.selected_mode)

    start_worker_thread(
        runtime_owner,
        thread_attr="_dpi_start_thread",
        worker_attr="_dpi_start_worker",
        worker=PresetLaunchStartWorker(
            request.selected_mode,
            request.launch_method,
            runtime_feature=runtime_owner._runtime_feature,
            runtime_api=runtime_owner._runtime_api(),
        ),
        finished_slot=runtime_owner._on_dpi_start_finished,
        progress_slot=runtime_owner_status_callback(runtime_owner),
        cleanup_log_label="потока запуска",
    )

    log(f"Запуск асинхронного старта DPI: {request.mode_name} (метод: {request.method_name})", "INFO")
