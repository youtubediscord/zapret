"""Results/progress/runtime helper слой для Strategy Scan page."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QTableWidgetItem

from ui.fluent_widgets import InfoBarHelper
from app.text_catalog import tr as tr_catalog


def apply_strategy_started_progress(
    *,
    blockcheck_feature,
    strategy_name: str,
    index: int,
    total: int,
    result_rows: list[dict],
    progress_bar,
    status_label,
    scan_cursor: int,
) -> None:
    progress_plan = blockcheck_feature.build_progress_plan(
        strategy_name=strategy_name,
        index=index,
        total=total,
        result_rows=result_rows,
    )
    if progress_plan.total > 0:
        progress_bar.setRange(0, progress_plan.total)
    if progress_bar.value() < scan_cursor:
        progress_bar.setValue(scan_cursor)
    status_label.setText(progress_plan.status_text)


def append_scan_log(*, blockcheck_feature, log_edit, run_log_file, message: str) -> None:
    log_edit.append(message)
    blockcheck_feature.append_run_log(run_log_file, message)


def apply_phase_change(*, blockcheck_feature, status_label, run_log_file, phase: str) -> None:
    status_label.setText(phase)
    blockcheck_feature.append_run_log(run_log_file, f"[PHASE] {phase}")


def add_strategy_result_row(
    *,
    blockcheck_feature,
    table,
    result,
    scan_cursor: int,
    tr_fn,
    push_button_cls,
    on_apply_strategy,
) -> dict:
    row_plan = blockcheck_feature.build_result_presentation(
        result,
        scan_cursor=scan_cursor,
    )
    row_idx = table.rowCount()
    table.insertRow(row_idx)

    num_item = QTableWidgetItem(row_plan.number_text)
    num_item.setFlags(num_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
    num_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
    table.setItem(row_idx, 0, num_item)

    name_item = QTableWidgetItem(row_plan.strategy_name)
    name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
    name_item.setToolTip(row_plan.strategy_tooltip)
    table.setItem(row_idx, 1, name_item)

    status_item = QTableWidgetItem(row_plan.status_text)
    if row_plan.status_tone == "success":
        status_item.setForeground(QColor("#52c477"))
    elif row_plan.status_tone == "timeout":
        status_item.setForeground(QColor("#888888"))
    else:
        status_item.setForeground(QColor("#e05454"))
    status_item.setFlags(status_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
    status_item.setToolTip(row_plan.status_tooltip)
    table.setItem(row_idx, 2, status_item)

    time_item = QTableWidgetItem(row_plan.time_text)
    time_item.setFlags(time_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
    time_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
    table.setItem(row_idx, 3, time_item)

    if row_plan.can_apply:
        apply_btn = push_button_cls()
        apply_btn.setText(tr_fn("page.blockcheck_public.apply", "Применить"))
        apply_btn.setFixedHeight(26)
        apply_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        apply_btn.clicked.connect(
            lambda checked=False, args=result.strategy_args, name=result.strategy_name:
            on_apply_strategy(args, name)
        )
        table.setCellWidget(row_idx, 4, apply_btn)

    table.scrollToBottom()
    return row_plan.stored_row


def apply_finished_scan(
    *,
    blockcheck_feature,
    report,
    worker,
    reset_ui,
    scan_target: str,
    scan_protocol: str,
    scan_udp_games_scope: str,
    scan_mode: str,
    scan_cursor: int,
    result_rows: list[dict],
    progress_bar,
    status_label,
    run_log_file,
    set_support_status,
    parent_widget,
) -> None:
    if worker is not None:
        try:
            worker.deleteLater()
        except Exception:
            pass

    reset_ui()
    finish_plan = blockcheck_feature.finalize_scan_report(
        report,
        scan_target=scan_target,
        scan_protocol=scan_protocol,
        scan_udp_games_scope=scan_udp_games_scope,
        scan_mode=scan_mode,
        scan_cursor=scan_cursor,
        result_rows=result_rows,
    )

    if finish_plan.total_available > 0:
        progress_bar.setRange(0, finish_plan.total_available)

    status_label.setText(finish_plan.status_text)
    progress_bar.setValue(min(finish_plan.total_count, progress_bar.maximum()))
    if finish_plan.log_message:
        blockcheck_feature.append_run_log(run_log_file, finish_plan.log_message)

    if finish_plan.support_status_code == "ready_after_error":
        set_support_status(
            tr_catalog(
                "page.blockcheck_public.support_ready_after_error",
                default="Можно подготовить обращение по логам ошибки",
            )
        )
        return

    if finish_plan.cancelled:
        set_support_status(
            tr_catalog(
                "page.blockcheck_public.support_ready_after_cancel",
                default="Можно подготовить обращение по частичным логам отменённого сканирования",
            )
        )
        return

    set_support_status(
        tr_catalog(
            "page.blockcheck_public.support_ready",
            default="Можно подготовить обращение по этому сканированию",
        )
    )

    try:
        notification_plan = blockcheck_feature.build_finish_notification_plan(
            finish_plan,
            scan_protocol=scan_protocol,
        )
        if notification_plan.kind == "warning" and notification_plan.title_key:
            title_text = tr_catalog(
                notification_plan.title_key,
                default=notification_plan.title_default,
            )
            body_text = (
                notification_plan.body_text
                or tr_catalog(
                    notification_plan.body_key,
                    default=notification_plan.body_default,
                )
            )
            InfoBarHelper.warning(parent_widget, title_text, body_text)
        elif notification_plan.kind == "success" and notification_plan.title_key:
            InfoBarHelper.success(
                parent_widget,
                tr_catalog(
                    notification_plan.title_key,
                    default=notification_plan.title_default,
                ),
                notification_plan.body_text,
            )
    except Exception:
        pass


def apply_force_stop_status(
    *,
    blockcheck_feature,
    worker,
    expected_worker,
    status_label,
    run_log_file,
    set_support_status,
) -> None:
    if expected_worker is None:
        return
    if worker is expected_worker and worker.is_running:
        warning_text = tr_catalog(
            "page.blockcheck_public.stopping_slow",
            default="Остановка занимает больше времени, ждём завершения фонового сканирования...",
        )
        status_label.setText(warning_text)
        blockcheck_feature.append_run_log(run_log_file, f"WARNING: {warning_text}")
        set_support_status(
            tr_catalog(
                "page.blockcheck_public.support_wait_stop",
                default="Подождите завершения остановки перед новым запуском",
            )
        )
