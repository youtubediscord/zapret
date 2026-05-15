"""Build-helper основных секций Strategy Scan page."""

from __future__ import annotations

from dataclasses import dataclass

from ui.theme import get_themed_qta_icon
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QHeaderView

from ui.fluent_widgets import ActionButton, QuickActionsBar, SettingsCard
from ui.pages.base_page import ScrollBlockingTextEdit


@dataclass(slots=True)
class StrategyScanControlWidgets:
    control_card: object
    protocol_combo: object
    games_scope_label: object
    games_scope_combo: object
    mode_combo: object
    target_label: object
    target_input: object
    quick_domain_btn: object
    udp_scope_hint_label: object
    progress_bar: object
    status_label: object
    actions_title_label: object
    actions_bar: object
    start_btn: object
    stop_btn: object


@dataclass(slots=True)
class StrategyScanResultsWidgets:
    results_card: object
    table: object


@dataclass(slots=True)
class StrategyScanLogWidgets:
    log_card: object
    expand_log_btn: object
    support_status_label: object
    prepare_support_btn: object
    log_edit: object


def build_strategy_scan_control_section(
    *,
    tr_fn,
    has_fluent: bool,
    combo_cls,
    caption_label_cls,
    body_label_cls,
    progress_bar_cls,
    push_button_cls,
    line_edit_cls,
    parent,
    on_protocol_changed,
    on_udp_games_scope_changed,
    on_show_quick_domains_menu,
    on_start,
    on_stop,
) -> StrategyScanControlWidgets:
    control_card = SettingsCard(
        tr_fn("page.strategy_scan.control", "Управление сканированием")
    )

    settings_row = QHBoxLayout()
    settings_row.setSpacing(12)

    protocol_label = caption_label_cls(
        tr_fn("page.strategy_scan.protocol", "Протокол:")
    ) if has_fluent else QLabel(tr_fn("page.strategy_scan.protocol", "Протокол:"))
    settings_row.addWidget(protocol_label)

    protocol_combo = combo_cls()
    protocol_combo.addItem(
        tr_fn("page.strategy_scan.protocol_tcp", "TCP/HTTPS"),
        userData="tcp_https",
    )
    protocol_combo.addItem(
        tr_fn("page.strategy_scan.protocol_stun", "STUN Voice (Discord/Telegram)"),
        userData="stun_voice",
    )
    protocol_combo.addItem(
        tr_fn("page.strategy_scan.protocol_games", "UDP Games (Roblox/Amazon/Steam)"),
        userData="udp_games",
    )
    protocol_combo.setCurrentIndex(0)
    protocol_combo.setFixedWidth(150)
    protocol_combo.currentIndexChanged.connect(on_protocol_changed)
    settings_row.addWidget(protocol_combo)

    games_scope_label = caption_label_cls(
        tr_fn("page.strategy_scan.udp_scope", "Охват UDP:")
    ) if has_fluent else QLabel(tr_fn("page.strategy_scan.udp_scope", "Охват UDP:"))
    settings_row.addWidget(games_scope_label)

    games_scope_combo = combo_cls()
    games_scope_combo.addItem(
        tr_fn("page.strategy_scan.udp_scope_all", "Все ipset (по умолчанию)"),
        userData="all",
    )
    games_scope_combo.addItem(
        tr_fn("page.strategy_scan.udp_scope_games_only", "Только игровые ipset"),
        userData="games_only",
    )
    games_scope_combo.setCurrentIndex(0)
    games_scope_combo.setFixedWidth(220)
    games_scope_combo.currentIndexChanged.connect(on_udp_games_scope_changed)
    settings_row.addWidget(games_scope_combo)

    settings_row.addSpacing(16)

    mode_label = caption_label_cls(
        tr_fn("page.strategy_scan.mode", "Режим:")
    ) if has_fluent else QLabel(tr_fn("page.strategy_scan.mode", "Режим:"))
    settings_row.addWidget(mode_label)

    mode_combo = combo_cls()
    mode_combo.addItem(tr_fn("page.strategy_scan.mode_quick", "Быстрый (30)"), "quick")
    mode_combo.addItem(tr_fn("page.strategy_scan.mode_standard", "Стандартный (80)"), "standard")
    mode_combo.addItem(tr_fn("page.strategy_scan.mode_full", "Полный (все)"), "full")
    mode_combo.setCurrentIndex(0)
    mode_combo.setFixedWidth(180)
    settings_row.addWidget(mode_combo)

    settings_row.addSpacing(16)

    target_label = caption_label_cls(
        tr_fn("page.strategy_scan.target", "Цель:")
    ) if has_fluent else QLabel(tr_fn("page.strategy_scan.target", "Цель:"))
    settings_row.addWidget(target_label)

    target_input = line_edit_cls()
    target_input.setText(tr_fn("page.strategy_scan.target.default", "discord.com"))
    target_input.setPlaceholderText(tr_fn("page.strategy_scan.target.placeholder", "discord.com"))
    target_input.setFixedWidth(200)
    target_input.setFixedHeight(33)
    settings_row.addWidget(target_input)

    quick_domain_btn = ActionButton(
        tr_fn("page.strategy_scan.quick_domains", "Быстрый выбор"),
        icon_name="fa5s.list",
    )
    quick_domain_btn.setToolTip(
        tr_fn("page.strategy_scan.quick_domains_hint", "Выберите домен из готового списка")
    )
    quick_domain_btn.clicked.connect(on_show_quick_domains_menu)
    settings_row.addWidget(quick_domain_btn)

    settings_row.addStretch()
    control_card.add_layout(settings_row)

    udp_scope_hint_label = caption_label_cls("") if has_fluent else QLabel("")
    udp_scope_hint_label.setWordWrap(True)
    control_card.add_widget(udp_scope_hint_label)

    progress_bar = progress_bar_cls()
    progress_bar.setVisible(False)
    progress_bar.setFixedHeight(4)
    progress_bar.setRange(0, 100)
    progress_bar.setValue(0)
    control_card.add_widget(progress_bar)

    status_label = caption_label_cls(
        tr_fn("page.strategy_scan.ready", "Готово к сканированию")
    ) if has_fluent else QLabel(tr_fn("page.strategy_scan.ready", "Готово к сканированию"))
    control_card.add_widget(status_label)

    actions_title_label = body_label_cls(
        tr_fn("page.strategy_scan.actions.title", "Действия")
    )

    actions_bar = QuickActionsBar(parent)

    start_btn = push_button_cls()
    start_btn.setText(tr_fn("page.strategy_scan.start", "Начать сканирование"))
    start_btn.setIcon(get_themed_qta_icon("fa5s.search", color="#4CAF50"))
    start_btn.setToolTip(
        tr_fn(
            "page.strategy_scan.action.start.description",
            "Запустить автоматический перебор стратегий обхода DPI для выбранной цели.",
        )
    )
    start_btn.clicked.connect(on_start)
    actions_bar.add_button(start_btn)

    stop_btn = push_button_cls()
    stop_btn.setText(tr_fn("page.strategy_scan.stop", "Остановить"))
    stop_btn.setIcon(get_themed_qta_icon("fa5s.stop", color="#ff9800"))
    stop_btn.setToolTip(
        tr_fn(
            "page.strategy_scan.action.stop.description",
            "Остановить текущее сканирование стратегий и вернуть страницу в обычный режим.",
        )
    )
    stop_btn.setEnabled(False)
    stop_btn.clicked.connect(on_stop)
    actions_bar.add_button(stop_btn)

    return StrategyScanControlWidgets(
        control_card=control_card,
        protocol_combo=protocol_combo,
        games_scope_label=games_scope_label,
        games_scope_combo=games_scope_combo,
        mode_combo=mode_combo,
        target_label=target_label,
        target_input=target_input,
        quick_domain_btn=quick_domain_btn,
        udp_scope_hint_label=udp_scope_hint_label,
        progress_bar=progress_bar,
        status_label=status_label,
        actions_title_label=actions_title_label,
        actions_bar=actions_bar,
        start_btn=start_btn,
        stop_btn=stop_btn,
    )


def build_strategy_scan_results_section(*, tr_fn, table_cls) -> StrategyScanResultsWidgets:
    results_card = SettingsCard(
        tr_fn("page.strategy_scan.results", "Результаты")
    )

    table = table_cls()
    table.setColumnCount(5)
    headers = [
        "#",
        tr_fn("page.strategy_scan.col_strategy", "Стратегия"),
        tr_fn("page.strategy_scan.col_status", "Статус"),
        tr_fn("page.strategy_scan.col_time", "Время (мс)"),
        tr_fn("page.strategy_scan.col_action", "Действие"),
    ]
    table.setHorizontalHeaderLabels(headers)
    table.setEditTriggers(table_cls.EditTrigger.NoEditTriggers)
    table.setSelectionBehavior(table_cls.SelectionBehavior.SelectRows)
    table.setMinimumHeight(250)
    table.verticalHeader().setVisible(False)

    try:
        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        table.setColumnWidth(0, 50)
    except Exception:
        pass

    results_card.add_widget(table)
    return StrategyScanResultsWidgets(
        results_card=results_card,
        table=table,
    )


def build_strategy_scan_log_section(*, tr_fn, has_fluent: bool, push_button_cls, parent, on_toggle_log_expand, on_prepare_support) -> StrategyScanLogWidgets:
    log_card = SettingsCard(
        tr_fn("page.strategy_scan.log", "Подробный лог")
    )

    expand_log_btn = push_button_cls()
    expand_log_btn.setText("Развернуть")
    expand_log_btn.setFixedWidth(120)
    expand_log_btn.clicked.connect(on_toggle_log_expand)

    log_header = QHBoxLayout()
    support_status_label = QLabel("") if not has_fluent else None
    if has_fluent:
        from qfluentwidgets import CaptionLabel

        support_status_label = CaptionLabel("")
    support_status_label.setWordWrap(True)
    log_header.addWidget(support_status_label, 1)
    log_header.addStretch()

    prepare_support_btn = ActionButton(
        tr_fn("page.strategy_scan.prepare_support", "Подготовить обращение"),
        icon_name="fa5b.github",
    )
    prepare_support_btn.clicked.connect(on_prepare_support)
    log_header.addWidget(prepare_support_btn)
    log_header.addWidget(expand_log_btn)
    log_card.add_layout(log_header)

    log_edit = ScrollBlockingTextEdit()
    log_edit.setReadOnly(True)
    log_edit.setMinimumHeight(180)
    log_edit.setMaximumHeight(300)
    log_edit.setFont(QFont("Consolas", 9))
    log_card.add_widget(log_edit)

    return StrategyScanLogWidgets(
        log_card=log_card,
        expand_log_btn=expand_log_btn,
        support_status_label=support_status_label,
        prepare_support_btn=prepare_support_btn,
        log_edit=log_edit,
    )
