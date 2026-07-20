"""Worker/runtime workflow helper'ы для страницы логов."""

from __future__ import annotations


def run_logs_runtime_init(
    *,
    runtime_initialized: bool,
    runtime_started: bool,
    schedule_fn,
    update_stats_fn,
    start_tail_worker_fn,
) -> tuple[bool, bool]:
    next_runtime_initialized = bool(runtime_initialized)
    next_runtime_started = bool(runtime_started)

    if not next_runtime_initialized:
        next_runtime_initialized = True
        # Один overview-worker возвращает и список файлов, и статистику.
        # Второй параллельный запрос при первом открытии не нужен.
        schedule_fn(0, update_stats_fn)

    if not next_runtime_started:
        next_runtime_started = True
        start_tail_worker_fn()

    return next_runtime_initialized, next_runtime_started


def start_tail_worker(
    *,
    current_log_file: str,
    previous_signature,
    set_tail_signature_fn,
    stop_worker_fn,
    build_tail_start_plan_fn,
    set_info_text_fn,
    clear_log_view_fn,
    tail_runtime,
    parent,
    create_worker_fn,
    on_new_lines,
    log_fn,
):
    stop_worker_fn()
    plan = build_tail_start_plan_fn(
        current_log_file=current_log_file,
        previous_signature=previous_signature,
    )
    if not plan.should_start:
        return None, None

    if plan.should_clear_view:
        clear_log_view_fn()
    set_info_text_fn(plan.info_text)

    try:
        def create_tail_worker(_request_id):
            return create_worker_fn(plan.file_path, initial_max_bytes=plan.initial_max_bytes)

        def bind_tail_worker(worker):
            worker.new_lines.connect(on_new_lines)

        tail_runtime.start_qobject_worker(
            parent=parent,
            worker_factory=create_tail_worker,
            bind_worker=bind_tail_worker,
        )
        set_tail_signature_fn(plan.file_signature)
        return True
    except Exception as e:
        log_fn(f"Ошибка запуска log tail worker: {e}", "ERROR")
        return False


def stop_tail_worker(*, tail_runtime, blocking: bool, log_fn, warning_prefix: str):
    tail_runtime.stop(
        blocking=blocking,
        log_fn=log_fn,
        warning_prefix=warning_prefix,
    )
    tail_runtime.cancel()
