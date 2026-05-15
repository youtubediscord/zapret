"""Worker/runtime workflow helper'ы для страницы логов."""

from __future__ import annotations


def run_logs_runtime_init(
    *,
    runtime_initialized: bool,
    runtime_started: bool,
    schedule_fn,
    refresh_logs_fn,
    update_stats_fn,
    start_tail_worker_fn,
    start_winws_worker_fn,
    start_status_timer_fn,
) -> tuple[bool, bool]:
    next_runtime_initialized = bool(runtime_initialized)
    next_runtime_started = bool(runtime_started)

    if not next_runtime_initialized:
        next_runtime_initialized = True
        schedule_fn(0, lambda: refresh_logs_fn(run_cleanup=False))
        schedule_fn(0, update_stats_fn)

    if not next_runtime_started:
        next_runtime_started = True
        start_tail_worker_fn()
        start_winws_worker_fn()
        start_status_timer_fn(3000)

    return next_runtime_initialized, next_runtime_started


def start_tail_worker(
    *,
    current_log_file: str,
    stop_worker_fn,
    build_tail_start_plan_fn,
    set_info_text_fn,
    clear_log_view_fn,
    thread_cls,
    parent,
    create_worker_fn,
    on_new_lines,
    on_thread_finished,
    log_fn,
):
    stop_worker_fn()
    plan = build_tail_start_plan_fn(current_log_file=current_log_file)
    if not plan.should_start:
        return None, None

    clear_log_view_fn()
    set_info_text_fn(plan.info_text)

    try:
        thread = thread_cls(parent)
        worker = create_worker_fn(plan.file_path)
        worker.moveToThread(thread)

        thread.started.connect(worker.run)
        worker.new_lines.connect(on_new_lines)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(on_thread_finished)
        thread.finished.connect(thread.deleteLater)
        thread.start()
        return thread, worker
    except Exception as e:
        log_fn(f"Ошибка запуска log tail worker: {e}", "ERROR")
        return None, None


def handle_thread_stop(*, worker, thread, build_stop_plan_fn, blocking: bool, log_fn, warning_prefix: str):
    stop_plan = build_stop_plan_fn(
        has_worker=worker is not None,
        thread_running=bool(thread and thread.isRunning()) if thread is not None else False,
        blocking=blocking,
    )

    if stop_plan.should_stop_worker and worker:
        try:
            worker.stop()
        except RuntimeError:
            worker = None

    if not thread:
        return worker, thread

    try:
        running = bool(thread.isRunning())
    except RuntimeError:
        return worker, None

    if not stop_plan.should_quit_thread or not running:
        return worker, thread

    thread.quit()
    if not stop_plan.should_wait:
        return worker, thread

    if not thread.wait(stop_plan.wait_timeout_ms):
        log_fn(f"⚠ {warning_prefix} не завершился, принудительно завершаем", "WARNING")
        if stop_plan.should_terminate:
            try:
                thread.terminate()
                thread.wait(stop_plan.terminate_wait_ms)
            except Exception:
                pass
    return worker, thread


def start_winws_output_worker(
    *,
    stop_worker_fn,
    refresh_title_fn,
    build_output_plan_fn,
    launch_method: str,
    orchestra_runner,
    language: str,
    set_status_fn,
    thread_cls,
    parent,
    create_worker_fn,
    on_new_output,
    on_process_ended,
    on_thread_finished,
    log_fn,
):
    stop_worker_fn()
    refresh_title_fn()

    plan = build_output_plan_fn(
        launch_method=launch_method,
        orchestra_runner=orchestra_runner,
        language=language,
    )
    set_status_fn(plan.status_kind, plan.status_text)

    if plan.action != "start_worker" or not plan.process:
        return None, None

    try:
        thread = thread_cls(parent)
        worker = create_worker_fn(plan.process)
        worker.moveToThread(thread)

        thread.started.connect(worker.run)
        worker.new_output.connect(on_new_output)
        worker.process_ended.connect(on_process_ended)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(on_thread_finished)
        thread.finished.connect(thread.deleteLater)
        thread.start()
        return thread, worker
    except Exception as e:
        log_fn(f"Ошибка запуска winws output worker: {e}", "ERROR")
        return None, None
