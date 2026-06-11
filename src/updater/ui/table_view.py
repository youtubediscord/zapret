"""Helper-слой отрисовки таблицы серверов для Servers page."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QTableWidgetItem

import updater.update_page_plans as update_page_plans
from ui.accessibility import set_item_accessible_text, set_state_text


_SERVER_TABLE_ACCESSIBILITY_INSTALLED = "updaterServerTableAccessibilityInstalled"


def apply_server_table_headers(table, *, tr_fn) -> None:
    table.setHorizontalHeaderLabels([
        tr_fn("page.servers.table.header.server", "Сервер"),
        tr_fn("page.servers.table.header.status", "Статус"),
        tr_fn("page.servers.table.header.time", "Время"),
        tr_fn("page.servers.table.header.versions", "Версии"),
    ])


def render_server_row(
    table,
    *,
    row: int,
    server_name: str,
    status: dict,
    channel: str,
    language: str,
    accent_hex: str,
) -> None:
    ensure_server_table_current_row_accessibility(table)
    plan = update_page_plans.build_server_row_plan(
        row_server_name=server_name,
        status=status,
        channel=channel,
        language=language,
    )
    row_accessible_text = _server_row_accessible_text(plan)
    name_item = QTableWidgetItem(plan.server_text)
    if plan.server_accent:
        name_item.setForeground(QColor(accent_hex))
    set_item_accessible_text(name_item, row_accessible_text)
    table.setItem(row, 0, name_item)

    status_item = QTableWidgetItem(plan.status_text)
    status_item.setForeground(QColor(*plan.status_color))
    set_item_accessible_text(status_item, row_accessible_text)
    table.setItem(row, 1, status_item)

    time_item = QTableWidgetItem(plan.time_text)
    set_item_accessible_text(time_item, row_accessible_text)
    table.setItem(row, 2, time_item)

    extra_item = QTableWidgetItem(plan.extra_text)
    set_item_accessible_text(extra_item, row_accessible_text)
    table.setItem(row, 3, extra_item)
    if table.currentRow() == row:
        _update_server_table_current_row_accessibility(table, row, table.currentColumn())


def ensure_server_table_current_row_accessibility(table) -> None:
    if table is None:
        return
    try:
        if bool(table.property(_SERVER_TABLE_ACCESSIBILITY_INSTALLED)):
            return
    except Exception:
        pass
    try:
        table.currentCellChanged.connect(
            lambda current_row, current_column, _previous_row, _previous_column, current_table=table: (
                _update_server_table_current_row_accessibility(current_table, current_row, current_column)
            )
        )
        table.setProperty(_SERVER_TABLE_ACCESSIBILITY_INSTALLED, True)
    except Exception:
        pass


def _update_server_table_current_row_accessibility(table, row: int, column: int) -> None:
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
            item = table.item(int(row), 0)
            if item is not None:
                row_text = str(item.data(Qt.ItemDataRole.AccessibleTextRole) or "").strip()
        except Exception:
            row_text = ""
    if row_text:
        set_state_text(table, row_text)


def _server_row_accessible_text(plan) -> str:
    server_text = _strip_status_markers(getattr(plan, "server_text", ""))
    status_text = _strip_status_markers(getattr(plan, "status_text", ""))
    time_text = _strip_status_markers(getattr(plan, "time_text", "")) or "-"
    extra_text = _strip_status_markers(getattr(plan, "extra_text", "")) or "-"
    return f"Сервер {server_text}, статус {status_text}, время {time_text}, версии {extra_text}"


def _strip_status_markers(text: object) -> str:
    value = str(text or "").strip()
    for marker in ("●", "⭐"):
        value = value.replace(marker, "")
    return " ".join(value.split())


def refresh_server_rows(
    table,
    *,
    table_state,
    channel: str,
    language: str,
    accent_hex: str,
) -> None:
    for entry in table_state.iter_entries():
        if entry.row < 0 or entry.row >= table.rowCount():
            continue
        render_server_row(
            table,
            row=entry.row,
            server_name=entry.server_name,
            status=entry.status,
            channel=channel,
            language=language,
            accent_hex=accent_hex,
        )


def reset_server_rows(table, *, table_state) -> None:
    table.setRowCount(0)
    table_state.reset()


def upsert_server_status(
    table,
    *,
    table_state,
    server_name: str,
    status: dict,
    channel: str,
    language: str,
    accent_hex: str,
) -> None:
    result = table_state.upsert(
        server_name,
        status,
        next_row=table.rowCount(),
    )
    if result.created:
        table.insertRow(result.row)
    render_server_row(
        table,
        row=result.row,
        server_name=server_name,
        status=result.status,
        channel=channel,
        language=language,
        accent_hex=accent_hex,
    )
