"""Monitoring/runtime helper слой для Orchestra page."""

from __future__ import annotations

from queue import Empty

from orchestra.page_controller import OrchestraPageController


def detect_state_transition_from_line(
    *,
    line: str,
    current_state: str,
    idle_state: str,
    learning_state: str,
    running_state: str,
    unlocked_state: str,
    update_status,
) -> None:
    plan = OrchestraPageController.detect_state_from_line(
        line=line,
        current_state=current_state,
        idle_state=idle_state,
        learning_state=learning_state,
        running_state=running_state,
        unlocked_state=unlocked_state,
    )
    if plan.next_state:
        update_status(plan.next_state)


def process_log_queue(*, log_queue, emit_log, batch_size: int = 20) -> None:
    for _ in range(batch_size):
        try:
            text = log_queue.get_nowait()
            emit_log(text)
        except Empty:
            break


def start_monitoring(
    *,
    runner,
    emit_log_callback,
    set_last_log_position,
    log_queue_timer,
    update_timer,
    run_update_now,
) -> None:
    try:
        OrchestraPageController.ensure_output_callback(runner, emit_log_callback)
    except Exception:
        pass

    plan = OrchestraPageController.build_start_monitoring_plan()
    if plan.reset_log_position:
        set_last_log_position(0)
    if plan.queue_timer_interval_ms is not None:
        log_queue_timer.start(plan.queue_timer_interval_ms)
    if plan.update_timer_interval_ms is not None:
        update_timer.start(plan.update_timer_interval_ms)
    if plan.run_update_now:
        run_update_now()


def stop_monitoring(*, log_queue_timer, update_timer) -> None:
    plan = OrchestraPageController.build_stop_monitoring_plan()
    if plan.queue_timer_interval_ms is None:
        log_queue_timer.stop()
    if plan.update_timer_interval_ms is None:
        update_timer.stop()


def run_update_cycle(*, app_window, state_idle: str, update_status, update_learned_domains, update_log_history) -> None:
    try:
        runner_alive = False
        if hasattr(app_window, 'dpi_runtime') and app_window.dpi_runtime:
            runner_alive = bool(app_window.dpi_runtime.is_any_running(silent=True))

        plan = OrchestraPageController.build_update_cycle_plan(runner_alive=runner_alive)
        if plan.next_state == state_idle:
            update_status(state_idle)
        if plan.refresh_learned:
            update_learned_domains()
        if plan.refresh_history:
            update_log_history()
    except Exception:
        pass
