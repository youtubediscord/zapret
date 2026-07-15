"""Results/progress/runtime helper слой для Strategy Scan page."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QTableWidgetItem

from ui.fluent_widgets import InfoBarHelper
from app.ui_texts import tr as tr_catalog
import blockcheck.strategy_scan_run_workflow as strategy_scan_run_workflow
from qfluentwidgets import FluentIcon
from ui.accessibility import set_control_accessibility, set_item_accessible_text, set_state_text
from ui.widgets.fluent_item_tooltip import set_fluent_item_tooltip


_STRATEGY_RESULT_TABLE_ACCESSIBILITY_INSTALLED = "strategyResultTableAccessibilityInstalled"


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
    set_state_text(progress_bar, "Ход подбора стратегии: выполняется")
    _set_strategy_scan_status(status_label, progress_plan.status_text)


def append_scan_log(*, log_edit, message: str) -> None:
    log_edit.append(message)


def apply_phase_change(*, status_label, phase: str) -> None:
    _set_strategy_scan_status(status_label, phase)


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
    ensure_strategy_result_table_current_row_accessibility(table)
    row_plan = blockcheck_feature.build_result_presentation(
        result,
        scan_cursor=scan_cursor,
    )
    row_idx = table.rowCount()
    table.insertRow(row_idx)
    row_accessible_text = _strategy_result_accessible_text(row_plan)

    num_item = QTableWidgetItem(row_plan.number_text)
    num_item.setFlags(num_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
    num_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
    set_item_accessible_text(num_item, row_accessible_text)
    table.setItem(row_idx, 0, num_item)

    name_item = QTableWidgetItem(row_plan.strategy_name)
    name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
    set_fluent_item_tooltip(name_item, row_plan.strategy_tooltip)
    set_item_accessible_text(name_item, row_accessible_text, description=row_plan.strategy_tooltip)
    table.setItem(row_idx, 1, name_item)

    status_item = QTableWidgetItem(row_plan.status_text)
    if row_plan.status_tone == "success":
        status_item.setForeground(QColor("#52c477"))
    elif row_plan.status_tone == "timeout":
        status_item.setForeground(QColor("#888888"))
    else:
        status_item.setForeground(QColor("#e05454"))
    status_item.setFlags(status_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
    set_fluent_item_tooltip(status_item, row_plan.status_tooltip)
    set_item_accessible_text(status_item, row_accessible_text, description=row_plan.status_tooltip)
    table.setItem(row_idx, 2, status_item)

    time_item = QTableWidgetItem(row_plan.time_text)
    time_item.setFlags(time_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
    time_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
    set_item_accessible_text(time_item, row_accessible_text)
    table.setItem(row_idx, 3, time_item)

    if row_plan.can_apply:
        apply_btn = push_button_cls()
        apply_btn.setText(tr_fn("page.blockcheck_public.apply", "Применить"))
        apply_btn.setIcon(FluentIcon.ACCEPT)
        apply_btn.setFixedHeight(26)
        set_control_accessibility(
            apply_btn,
            name=f"Применить стратегию {row_plan.strategy_name}",
            description="Применяет найденную рабочую стратегию к текущему preset.",
        )
        apply_btn.clicked.connect(
            lambda checked=False, args=result.strategy_args, name=result.strategy_name:
            on_apply_strategy(args, name)
        )
        table.setCellWidget(row_idx, 4, apply_btn)

    table.scrollToBottom()
    if table.currentRow() == row_idx:
        _update_strategy_result_table_current_row_accessibility(table, row_idx, table.currentColumn())
    return row_plan.stored_row


def ensure_strategy_result_table_current_row_accessibility(table) -> None:
    if table is None:
        return
    try:
        if bool(table.property(_STRATEGY_RESULT_TABLE_ACCESSIBILITY_INSTALLED)):
            return
    except Exception:
        pass
    try:
        table.currentCellChanged.connect(
            lambda current_row, current_column, _previous_row, _previous_column, current_table=table: (
                _update_strategy_result_table_current_row_accessibility(current_table, current_row, current_column)
            )
        )
        table.setProperty(_STRATEGY_RESULT_TABLE_ACCESSIBILITY_INSTALLED, True)
    except Exception:
        pass


def _update_strategy_result_table_current_row_accessibility(table, row: int, column: int) -> None:
    if table is None:
        return
    row_text = ""
    try:
        item = table.item(int(row), int(column))
        if item is not None:
            row_text = str(item.data(Qt.ItemDataRole.AccessibleTextRole) or "").strip()
    except Exception:
        row_text = ""
    if not row_text:
        try:
            item = table.item(int(row), 1)
            if item is not None:
                row_text = str(item.data(Qt.ItemDataRole.AccessibleTextRole) or "").strip()
        except Exception:
            row_text = ""
    if row_text:
        set_state_text(table, row_text)


def _strategy_result_accessible_text(row_plan) -> str:
    number = str(getattr(row_plan, "number_text", "") or "").strip()
    name = str(getattr(row_plan, "strategy_name", "") or "").strip()
    status = str(getattr(row_plan, "status_text", "") or "").strip()
    time_text = str(getattr(row_plan, "time_text", "") or "").strip() or "-"
    parts = []
    if number:
        parts.append(f"Строка {number}")
    parts.append(f"Стратегия {name}, статус {status}, время {time_text}")
    if bool(getattr(row_plan, "can_apply", False)):
        parts.append("Доступно действие: применить")
    return ". ".join(parts) + "."


def _set_strategy_scan_status(status_label, text: object) -> None:
    value = str(text or "").strip()
    status_label.setText(value)
    if value:
        set_state_text(status_label, f"Статус подбора стратегии: {value}")


def apply_finished_scan(
    *,
    blockcheck_feature,
    finish_plan,
    reset_ui,
    scan_protocol: str,
    progress_bar,
    status_label,
    set_support_status,
    parent_widget,
) -> None:
    reset_ui()

    if finish_plan.total_available > 0:
        progress_bar.setRange(0, finish_plan.total_available)

    _set_strategy_scan_status(status_label, finish_plan.status_text)
    progress_bar.setValue(min(finish_plan.total_count, progress_bar.maximum()))
    set_state_text(progress_bar, "Ход подбора стратегии: не выполняется")

    fatal_error = str(getattr(finish_plan, "fatal_error", "") or "")
    if fatal_error:
        InfoBarHelper.error(
            parent_widget,
            tr_catalog(
                "page.blockcheck_public.scan_fatal_error_title",
                default="Подбор стратегии остановлен",
            ),
            fatal_error,
            duration=15000,
        )

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
    worker,
    expected_worker,
    status_label,
    set_support_status,
) -> None:
    if expected_worker is None:
        return
    if worker is expected_worker and worker.is_running:
        warning_text = tr_catalog(
            "page.blockcheck_public.stopping_slow",
            default="Остановка занимает больше времени, ждём завершения фонового сканирования...",
        )
        _set_strategy_scan_status(status_label, warning_text)
        strategy_scan_run_workflow.record_strategy_scan_force_stop_warning(
            worker=worker,
            warning_text=warning_text,
        )
        set_support_status(
            tr_catalog(
                "page.blockcheck_public.support_wait_stop",
                default="Подождите завершения остановки перед новым запуском",
            )
        )
