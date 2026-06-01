"""Workflow запуска и остановки подбора стратегии BlockCheck."""

from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Callable


@dataclass(frozen=True)
class StrategyScanRunStartResult:
    worker: object
    target: str
    scan_protocol: str
    udp_games_scope: str
    mode: str
    scan_cursor: int
    keep_current_results: bool
    status_text: str


def start_strategy_scan_run(
    *,
    blockcheck_feature,
    create_strategy_scan_worker,
    raw_target_input: str,
    raw_protocol_value,
    raw_udp_scope_value,
    mode_index: int,
    previous_target: str,
    previous_protocol: str,
    previous_scope: str,
    result_rows_count: int,
    table_row_count: int,
    starting_status_text: str,
    parent,
    on_run_log_started,
    on_strategy_started,
    on_strategy_result,
    on_log,
    on_phase_changed,
    on_finished,
) -> StrategyScanRunStartResult:
    """Готовит состояние и worker подбора стратегии."""
    selection = blockcheck_feature.build_selection_state(
        protocol_value=raw_protocol_value,
        udp_scope_value=raw_udp_scope_value,
        mode_index=mode_index,
    )
    start_plan = blockcheck_feature.plan_scan_start(
        raw_target_input=raw_target_input,
        scan_protocol=selection.scan_protocol,
        udp_games_scope=selection.udp_games_scope,
        mode=selection.mode,
        previous_target=previous_target,
        previous_protocol=previous_protocol,
        previous_scope=previous_scope,
        result_rows_count=result_rows_count,
        table_row_count=table_row_count,
        starting_status_text=starting_status_text,
    )

    worker = create_strategy_scan_worker(
        target=start_plan.target,
        mode=start_plan.mode,
        start_index=start_plan.scan_cursor,
        scan_protocol=start_plan.scan_protocol,
        udp_games_scope=start_plan.udp_games_scope,
        parent=None,
    )
    worker.run_log_started.connect(on_run_log_started)
    worker.strategy_started.connect(on_strategy_started)
    worker.strategy_result.connect(on_strategy_result)
    worker.scan_log.connect(on_log)
    worker.phase_changed.connect(on_phase_changed)
    worker.scan_finished.connect(on_finished)

    return StrategyScanRunStartResult(
        worker=worker,
        target=start_plan.target,
        scan_protocol=start_plan.scan_protocol,
        udp_games_scope=start_plan.udp_games_scope,
        mode=start_plan.mode,
        scan_cursor=start_plan.scan_cursor,
        keep_current_results=start_plan.keep_current_results,
        status_text=start_plan.status_text,
    )


def start_strategy_scan_worker(worker, *, parent, run_runtime) -> None:
    """Запускает уже подготовленный worker подбора стратегии."""
    run_runtime.start_qobject_worker(
        parent=parent,
        worker_factory=lambda _request_id: worker,
    )


def record_strategy_scan_result(
    *,
    blockcheck_feature,
    scan_target: str,
    scan_protocol: str,
    scan_udp_games_scope: str,
    scan_cursor: int,
) -> int:
    """Сохраняет позицию продолжения после результата стратегии."""
    next_cursor = int(scan_cursor) + 1
    blockcheck_feature.save_resume_state(
        scan_target,
        scan_protocol,
        next_cursor,
        scan_udp_games_scope,
    )
    return next_cursor


def record_strategy_scan_force_stop_warning(
    *,
    worker,
    warning_text: str,
) -> None:
    """Записывает предупреждение о долгой остановке подбора стратегии."""
    if worker is None:
        return
    try:
        worker.record_run_log_message(f"WARNING: {warning_text}")
    except Exception:
        pass


def request_strategy_scan_stop(
    *,
    worker,
    schedule_stop_check: Callable[[object | None], None],
) -> None:
    """Запрашивает остановку worker-а подбора стратегии."""
    expected_worker = None
    if worker is not None:
        worker.stop()
        expected_worker = worker
    schedule_stop_check(expected_worker)
