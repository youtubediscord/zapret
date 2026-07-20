"""Worker/runtime workflow helper'ы для страницы логов."""

from __future__ import annotations

import os


def run_logs_runtime_init(
    *,
    runtime_initialized: bool,
    runtime_started: bool,
    schedule_fn,
    update_stats_fn,
    start_log_source_fn,
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
        start_log_source_fn()

    return next_runtime_initialized, next_runtime_started


def start_live_log_source(
    *,
    active_log_file: str,
    after_sequence: int | None,
    should_reset_view: bool,
    create_bridge_fn,
    on_new_text,
    set_bridge_fn,
    set_cursor_fn,
    set_displayed_file_fn,
    set_info_text_fn,
    clear_log_view_fn,
    append_text_fn,
    log_fn,
):
    bridge = None
    try:
        bridge = create_bridge_fn(
            after_sequence=None if should_reset_view else after_sequence,
            on_new_text=on_new_text,
        )
        snapshot = bridge.snapshot
        set_bridge_fn(bridge)
        if should_reset_view or snapshot.reset_required:
            clear_log_view_fn()
        set_info_text_fn(f"📄 {os.path.basename(active_log_file)}")
        if snapshot.text:
            append_text_fn(snapshot.text)
        set_cursor_fn(snapshot.last_sequence)
        set_displayed_file_fn(active_log_file)
        return bridge
    except Exception as exc:
        if bridge is not None:
            try:
                bridge.close()
            except Exception:
                pass
        log_fn(f"Ошибка подключения живого журнала: {exc}", "ERROR")
        return None


def start_log_file_reader(
    *,
    selected_log_file: str,
    previous_signature,
    set_file_signature_fn,
    build_file_read_plan_fn,
    set_info_text_fn,
    clear_log_view_fn,
    reader_runtime,
    parent,
    create_reader_fn,
    on_new_lines,
    set_displayed_file_fn,
    log_fn,
):
    plan = build_file_read_plan_fn(
        current_log_file=selected_log_file,
        previous_signature=previous_signature,
    )
    if not plan.should_start:
        return False

    if plan.should_clear_view:
        clear_log_view_fn()
    set_info_text_fn(plan.info_text)

    try:
        def create_reader(_request_id):
            return create_reader_fn(plan.file_path, max_bytes=plan.max_bytes)

        def bind_reader(worker):
            worker.new_lines.connect(on_new_lines)

        reader_runtime.start_qobject_worker(
            parent=parent,
            worker_factory=create_reader,
            bind_worker=bind_reader,
        )
        set_file_signature_fn(plan.file_signature)
        set_displayed_file_fn(plan.file_path)
        return True
    except Exception as e:
        log_fn(f"Ошибка запуска чтения файла лога: {e}", "ERROR")
        return False


def stop_log_source(*, live_bridge, reader_runtime, blocking: bool, log_fn, warning_prefix: str):
    if live_bridge is not None:
        try:
            live_bridge.close()
        except Exception as exc:
            log_fn(f"Ошибка отключения живого журнала: {exc}", "DEBUG")
    reader_runtime.stop(
        blocking=blocking,
        log_fn=log_fn,
        warning_prefix=warning_prefix,
    )
    reader_runtime.cancel()
