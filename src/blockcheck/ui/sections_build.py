"""Build-helper'ы actions/results секций для Blockcheck page."""

from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel
from qfluentwidgets import FluentIcon

from ui.fluent_widgets import set_tooltip
from ui.accessibility import set_control_accessibility, set_state_text
from ui.widgets.fluent_item_tooltip import install_fluent_item_tooltips


@dataclass(slots=True)
class BlockcheckActionsWidgets:
    title_label: object
    actions_bar: object
    start_button: object
    stop_button: object


@dataclass(slots=True)
class BlockcheckResultsWidgets:
    results_card: object
    domains_section_label: object
    results_table: object
    tcp_section_label: object
    tcp_table: object


def build_actions_section(
    *,
    tr_fn,
    strong_body_label_cls,
    quick_actions_bar_cls,
    content_parent,
    push_button_cls,
    qta_module,
    on_start,
    on_stop,
) -> BlockcheckActionsWidgets:
    title_label = strong_body_label_cls(
        tr_fn("page.blockcheck.actions.title", "Действия")
    )
    set_state_text(title_label, f"Раздел BlockCheck: {title_label.text()}")

    actions_bar = quick_actions_bar_cls(content_parent)

    start_btn = push_button_cls(
        tr_fn("page.blockcheck.start", "Запустить"),
        icon=FluentIcon.PLAY,
    )
    start_description = tr_fn(
        "page.blockcheck.action.start.description",
        "Запустить анализ блокировок и проверку DPI для выбранного режима.",
    )
    set_tooltip(start_btn, start_description)
    set_control_accessibility(
        start_btn,
        name="Запустить BlockCheck",
        description=start_description,
    )
    set_state_text(start_btn, "Запустить BlockCheck")
    start_btn.clicked.connect(on_start)
    actions_bar.add_button(start_btn)

    stop_btn = push_button_cls(
        tr_fn("page.blockcheck.stop", "Остановить"),
        icon=FluentIcon.CANCEL,
    )
    stop_description = tr_fn(
        "page.blockcheck.action.stop.description",
        "Остановить текущую проверку и вернуть страницу в обычный режим.",
    )
    set_tooltip(stop_btn, stop_description)
    set_control_accessibility(
        stop_btn,
        name="Остановить BlockCheck",
        description=stop_description,
    )
    set_state_text(stop_btn, "Остановить BlockCheck")
    stop_btn.clicked.connect(on_stop)
    stop_btn.setEnabled(False)
    actions_bar.add_button(stop_btn)

    return BlockcheckActionsWidgets(
        title_label=title_label,
        actions_bar=actions_bar,
        start_button=start_btn,
        stop_button=stop_btn,
    )


def build_results_section(
    *,
    tr_fn,
    settings_card_cls,
    strong_body_label_cls,
    table_widget_cls,
) -> BlockcheckResultsWidgets:
    results_card = settings_card_cls(
        tr_fn("page.blockcheck.results", "Результаты")
    )

    domains_section_label = strong_body_label_cls(
        tr_fn(
            "page.blockcheck.domains_section",
            "Часть 1: Проверка доменов (TLS + HTTP injection)",
        )
    )
    set_state_text(domains_section_label, f"Раздел результатов BlockCheck: {domains_section_label.text()}")
    results_card.add_widget(domains_section_label)

    results_table = table_widget_cls()
    results_table.setColumnCount(8)
    results_table.setHorizontalHeaderLabels([
        tr_fn("page.blockcheck.col_target", "Цель"),
        "HTTP",
        "TLS 1.2",
        "TLS 1.3",
        tr_fn("page.blockcheck.col_dns_isp", "DNS/ISP"),
        "DPI",
        "Ping",
        "Детали",
    ])
    results_table.setEditTriggers(table_widget_cls.EditTrigger.NoEditTriggers)
    results_table.setSelectionBehavior(table_widget_cls.SelectionBehavior.SelectRows)
    results_table.setMinimumHeight(200)
    results_table.verticalHeader().setVisible(False)
    set_control_accessibility(
        results_table,
        name="Результаты BlockCheck по доменам",
        description="Таблица с результатами проверок HTTP, TLS, DNS, DPI, Ping и деталями по доменам.",
    )
    set_state_text(results_table, "Результаты BlockCheck по доменам: пока нет результатов")
    install_fluent_item_tooltips(results_table)

    try:
        from PyQt6.QtWidgets import QHeaderView

        header = results_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for col in range(1, 7):
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(7, QHeaderView.ResizeMode.Stretch)
    except Exception:
        pass

    results_card.add_widget(results_table)

    tcp_section_label = strong_body_label_cls(
        tr_fn("page.blockcheck.tcp_section", "Часть 2: Проверка TCP 16-20KB")
    )
    set_state_text(tcp_section_label, f"Раздел результатов BlockCheck: {tcp_section_label.text()}")
    results_card.add_widget(tcp_section_label)

    tcp_table = table_widget_cls()
    tcp_table.setColumnCount(5)
    tcp_table.setHorizontalHeaderLabels([
        "ID",
        "ASN",
        tr_fn("page.blockcheck.col_provider", "Провайдер"),
        tr_fn("page.blockcheck.col_status", "Статус"),
        tr_fn("page.blockcheck.col_error_details", "Ошибка / Детали"),
    ])
    tcp_table.setEditTriggers(table_widget_cls.EditTrigger.NoEditTriggers)
    tcp_table.setSelectionBehavior(table_widget_cls.SelectionBehavior.SelectRows)
    tcp_table.setMinimumHeight(180)
    tcp_table.verticalHeader().setVisible(False)
    set_control_accessibility(
        tcp_table,
        name="Результаты TCP 16-20KB",
        description="Таблица с TCP-проверкой: ID цели, ASN, провайдер, статус и детали ошибки.",
    )
    set_state_text(tcp_table, "Результаты TCP 16-20KB: пока нет результатов")
    install_fluent_item_tooltips(tcp_table)

    try:
        from PyQt6.QtWidgets import QHeaderView

        tcp_header = tcp_table.horizontalHeader()
        tcp_header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        tcp_header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        tcp_header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        tcp_header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        tcp_header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
    except Exception:
        pass

    tcp_section_label.setVisible(False)
    tcp_table.setVisible(False)
    results_card.add_widget(tcp_table)

    return BlockcheckResultsWidgets(
        results_card=results_card,
        domains_section_label=domains_section_label,
        results_table=results_table,
        tcp_section_label=tcp_section_label,
        tcp_table=tcp_table,
    )
