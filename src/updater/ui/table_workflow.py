"""Helper-слой таблицы серверов для Servers page."""

from __future__ import annotations

from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QTableWidgetItem

import updater.update_page_plans as update_page_plans


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
    plan = update_page_plans.build_server_row_plan(
        row_server_name=server_name,
        status=status,
        channel=channel,
        language=language,
    )
    name_item = QTableWidgetItem(plan.server_text)
    if plan.server_accent:
        name_item.setForeground(QColor(accent_hex))
    table.setItem(row, 0, name_item)

    status_item = QTableWidgetItem(plan.status_text)
    status_item.setForeground(QColor(*plan.status_color))
    table.setItem(row, 1, status_item)
    table.setItem(row, 2, QTableWidgetItem(plan.time_text))
    table.setItem(row, 3, QTableWidgetItem(plan.extra_text))


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
