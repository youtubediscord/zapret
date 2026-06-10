"""Build-helper верхней части и таблицы Servers page."""

from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtWidgets import QWidget, QLabel, QVBoxLayout, QHBoxLayout, QHeaderView

from qfluentwidgets import (
    BreadcrumbBar,
    CaptionLabel,
    StrongBodyLabel,
    TableWidget,
    TitleLabel,
)

from ui.accessibility import set_control_accessibility, set_state_text


def set_active_server_legend_accessibility(label) -> None:
    text = "Легенда серверов обновлений: активный сервер"
    set_state_text(label, text)


@dataclass(slots=True)
class ServersHeaderWidgets:
    header_widget: QWidget
    breadcrumb: BreadcrumbBar
    page_title_label: object
    servers_header_widget: QWidget
    servers_title_label: object
    legend_active_label: object


def build_servers_header_widgets(*, tr_fn, parent, on_about_clicked) -> ServersHeaderWidgets:
    header = QWidget()
    header_layout = QVBoxLayout(header)
    header_layout.setContentsMargins(0, 0, 0, 8)
    header_layout.setSpacing(4)

    breadcrumb = BreadcrumbBar(parent)
    breadcrumb.addItem("about", tr_fn("page.servers.breadcrumb.about", "О программе"))
    breadcrumb.addItem("servers", tr_fn("page.servers.title", "Серверы"))
    breadcrumb.currentItemChanged.connect(lambda key: on_about_clicked() if key == "about" else None)
    header_layout.addWidget(breadcrumb)

    page_title_label = TitleLabel(tr_fn("page.servers.title", "Серверы"))
    header_layout.addWidget(page_title_label)

    servers_header = QHBoxLayout()
    servers_title_label = StrongBodyLabel(
        tr_fn("page.servers.section.update_servers", "Серверы обновлений")
    )
    servers_header.addWidget(servers_title_label)
    servers_header.addStretch()

    legend_active_label = CaptionLabel(tr_fn("page.servers.legend.active", "⭐ активный"))
    set_active_server_legend_accessibility(legend_active_label)
    servers_header.addWidget(legend_active_label)

    servers_header_widget = QWidget()
    servers_header_widget.setLayout(servers_header)

    return ServersHeaderWidgets(
        header_widget=header,
        breadcrumb=breadcrumb,
        page_title_label=page_title_label,
        servers_header_widget=servers_header_widget,
        servers_title_label=servers_title_label,
        legend_active_label=legend_active_label,
    )


def build_servers_table_widget(*, tr_fn):
    table = TableWidget()
    set_control_accessibility(
        table,
        name=tr_fn("page.servers.table.accessible_name", "Серверы обновлений"),
        description=tr_fn(
            "page.servers.table.accessible_description",
            "Показывает сервер, статус и версии обновлений. Перемещайтесь по строкам стрелками.",
        ),
    )
    table.setColumnCount(4)
    table.setRowCount(0)
    table.setBorderVisible(True)
    table.setBorderRadius(8)
    table.setHorizontalHeaderLabels([
        tr_fn("page.servers.table.header.server", "Сервер"),
        tr_fn("page.servers.table.header.status", "Статус"),
        tr_fn("page.servers.table.header.time", "Время"),
        tr_fn("page.servers.table.header.versions", "Версии"),
    ])
    header = table.horizontalHeader()
    header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
    header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
    header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
    header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
    table.verticalHeader().setVisible(False)
    table.verticalHeader().setDefaultSectionSize(36)
    table.setEditTriggers(TableWidget.EditTrigger.NoEditTriggers)
    table.setSelectionBehavior(TableWidget.SelectionBehavior.SelectRows)
    return table
