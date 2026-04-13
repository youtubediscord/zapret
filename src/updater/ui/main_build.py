"""Build-helper верхней части и таблицы Servers page."""

from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtCore import QSize
from PyQt6.QtWidgets import QWidget, QLabel, QVBoxLayout, QHBoxLayout, QHeaderView


try:
    from qfluentwidgets import (
        StrongBodyLabel,
        CaptionLabel,
        TransparentPushButton,
        TableWidget,
        TitleLabel,
    )
except Exception:
    from PyQt6.QtWidgets import QPushButton, QTableWidget as TableWidget

    StrongBodyLabel = QLabel  # type: ignore[assignment]
    CaptionLabel = QLabel  # type: ignore[assignment]
    TransparentPushButton = QPushButton  # type: ignore[assignment]
    TitleLabel = QLabel  # type: ignore[assignment]

from ui.theme import get_themed_qta_icon


@dataclass(slots=True)
class ServersHeaderWidgets:
    header_widget: QWidget
    back_button: object
    page_title_label: object
    servers_header_widget: QWidget
    servers_title_label: object
    legend_active_label: object


def build_servers_header_widgets(*, tr_fn, qta_module, parent, on_back_clicked) -> ServersHeaderWidgets:
    header = QWidget()
    header_layout = QVBoxLayout(header)
    header_layout.setContentsMargins(0, 0, 0, 8)
    header_layout.setSpacing(4)

    back_row = QHBoxLayout()
    back_row.setContentsMargins(0, 0, 0, 0)
    back_row.setSpacing(0)

    back_btn = TransparentPushButton(parent=parent)
    back_btn.setText(tr_fn("page.servers.back.about", "О программе"))
    back_btn.setIcon(get_themed_qta_icon("fa5s.chevron-left", color="#888"))
    back_btn.setIconSize(QSize(12, 12))
    back_btn.clicked.connect(on_back_clicked)
    back_row.addWidget(back_btn)
    back_row.addStretch()
    header_layout.addLayout(back_row)

    page_title_label = TitleLabel(tr_fn("page.servers.title", "Серверы"))
    header_layout.addWidget(page_title_label)

    servers_header = QHBoxLayout()
    servers_title_label = StrongBodyLabel(
        tr_fn("page.servers.section.update_servers", "Серверы обновлений")
    )
    servers_header.addWidget(servers_title_label)
    servers_header.addStretch()

    legend_active_label = CaptionLabel(tr_fn("page.servers.legend.active", "⭐ активный"))
    servers_header.addWidget(legend_active_label)

    servers_header_widget = QWidget()
    servers_header_widget.setLayout(servers_header)

    return ServersHeaderWidgets(
        header_widget=header,
        back_button=back_btn,
        page_title_label=page_title_label,
        servers_header_widget=servers_header_widget,
        servers_title_label=servers_title_label,
        legend_active_label=legend_active_label,
    )


def build_servers_table_widget(*, tr_fn):
    table = TableWidget()
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
