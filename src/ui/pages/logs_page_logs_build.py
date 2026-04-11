"""Build-helper основной вкладки логов."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class LogsTabWidgets:
    controls_card: object
    log_combo: object
    refresh_btn: object
    controls_actions_title: object
    controls_actions_bar: object
    copy_btn: object
    clear_btn: object
    folder_btn: object
    log_card: object
    log_text: object
    stats_label: object
    errors_card: object
    warning_icon_label: object
    errors_title_label: object
    errors_count_label: object
    clear_errors_btn: object
    errors_text: object
    winws_card: object
    terminal_icon_label: object
    winws_title_label: object
    winws_status_label: object
    clear_winws_btn: object
    winws_text: object


def build_logs_tab_ui(
    *,
    parent_layout,
    content_parent,
    ui_language: str,
    tr_catalog_fn,
    settings_card_cls,
    qvbox_layout_cls,
    qhbox_layout_cls,
    qlabel_cls,
    caption_label_cls,
    strong_body_label_cls,
    combo_box_cls,
    tool_button_cls,
    push_button_cls,
    fluent_push_button_cls,
    text_edit_cls,
    quick_actions_bar_cls,
    qfont_cls,
    qtextedit_cls,
    qta_module,
    get_theme_tokens_fn,
    errors_text_min_height: int,
    errors_text_max_height: int,
    on_log_selected,
    on_refresh,
    on_spin_tick,
    on_copy,
    on_clear_view,
    on_open_folder,
    on_clear_errors,
    on_update_errors_height,
    on_clear_winws_output,
    refresh_timer_parent,
) -> LogsTabWidgets:
    tokens = get_theme_tokens_fn()

    controls_card = settings_card_cls(
        tr_catalog_fn("page.logs.card.controls", language=ui_language, default="Управление логами")
    )
    controls_main = qvbox_layout_cls()
    controls_main.setSpacing(12)

    row1 = qhbox_layout_cls()
    row1.setSpacing(8)

    log_combo = combo_box_cls()
    log_combo.setMinimumWidth(350)
    log_combo.currentIndexChanged.connect(on_log_selected)
    row1.addWidget(log_combo, 1)

    refresh_btn = tool_button_cls()
    refresh_icon_normal = qta_module.icon('fa5s.sync-alt', color=tokens.fg)
    spin_timer = refresh_timer_parent._spin_timer = refresh_timer_parent._spin_timer if hasattr(refresh_timer_parent, "_spin_timer") else None
    if spin_timer is None:
        from PyQt6.QtCore import QTimer
        spin_timer = QTimer(refresh_timer_parent)
        refresh_timer_parent._spin_timer = spin_timer
    spin_timer.setInterval(33)
    refresh_timer_parent._spin_angle = 0
    spin_timer.timeout.connect(on_spin_tick)
    refresh_timer_parent._refresh_icon_normal = refresh_icon_normal
    refresh_btn.setIcon(refresh_icon_normal)
    refresh_btn.setFixedSize(36, 36)
    refresh_btn.setCursor(refresh_timer_parent.cursor() if hasattr(refresh_timer_parent, "cursor") else refresh_btn.cursor())
    refresh_btn.clicked.connect(on_refresh)
    row1.addWidget(refresh_btn)
    controls_main.addLayout(row1)

    info_row = qhbox_layout_cls()
    info_row.setSpacing(8)
    info_row.addStretch()
    info_label = caption_label_cls()
    info_row.addWidget(info_label)
    controls_main.addLayout(info_row)

    controls_card.add_layout(controls_main)
    parent_layout.addWidget(controls_card)

    controls_actions_title = strong_body_label_cls(
        tr_catalog_fn("page.logs.actions.title", language=ui_language, default="Действия")
    )
    parent_layout.addWidget(controls_actions_title)

    controls_actions_bar = quick_actions_bar_cls(content_parent)

    copy_btn = push_button_cls()
    copy_btn.setText(tr_catalog_fn("page.logs.button.copy", language=ui_language, default="Копировать"))
    copy_btn.setIcon(qta_module.icon("fa5s.copy", color=tokens.accent_hex))
    copy_btn.clicked.connect(on_copy)
    controls_actions_bar.add_button(copy_btn)

    clear_btn = push_button_cls()
    clear_btn.setText(tr_catalog_fn("page.logs.button.clear", language=ui_language, default="Очистить"))
    clear_btn.setIcon(qta_module.icon("fa5s.eraser", color="#ff9800"))
    clear_btn.clicked.connect(on_clear_view)
    controls_actions_bar.add_button(clear_btn)

    folder_btn = push_button_cls()
    folder_btn.setText(tr_catalog_fn("page.logs.button.folder", language=ui_language, default="Папка"))
    folder_btn.setIcon(qta_module.icon("fa5s.folder-open", color=tokens.accent_hex))
    folder_btn.clicked.connect(on_open_folder)
    controls_actions_bar.add_button(folder_btn)

    parent_layout.addWidget(controls_actions_bar)

    log_card = settings_card_cls(
        tr_catalog_fn("page.logs.card.content", language=ui_language, default="Содержимое")
    )
    log_layout = qvbox_layout_cls()

    log_text = text_edit_cls()
    log_text.setReadOnly(True)
    log_text.setLineWrapMode(qtextedit_cls.LineWrapMode.NoWrap)
    log_text.setFont(qfont_cls("Consolas", 9))
    log_text.setMinimumHeight(260)
    log_layout.addWidget(log_text)

    stats_label = caption_label_cls()
    log_layout.addWidget(stats_label)

    log_card.add_layout(log_layout)
    parent_layout.addWidget(log_card)

    errors_card = settings_card_cls()
    errors_layout = qvbox_layout_cls()
    errors_header = qhbox_layout_cls()

    warning_icon = qlabel_cls()
    errors_header.addWidget(warning_icon)

    errors_title_label = strong_body_label_cls(
        tr_catalog_fn("page.logs.errors.title", language=ui_language, default="Ошибки и предупреждения")
    )
    errors_header.addWidget(errors_title_label)
    errors_header.addSpacing(8)

    errors_count_label = caption_label_cls(
        tr_catalog_fn("page.logs.errors.count", language=ui_language, default="Ошибок: {count}").format(count=0)
    )
    errors_header.addWidget(errors_count_label)
    errors_header.addStretch()

    clear_errors_btn = fluent_push_button_cls()
    clear_errors_btn.setText(tr_catalog_fn("page.logs.button.clear", language=ui_language, default="Очистить"))
    clear_errors_btn.setIcon(qta_module.icon("fa5s.trash", color=tokens.fg))
    clear_errors_btn.clicked.connect(on_clear_errors)
    errors_header.addWidget(clear_errors_btn)

    errors_layout.addLayout(errors_header)

    errors_text = text_edit_cls()
    errors_text.setReadOnly(True)
    errors_text.setLineWrapMode(qtextedit_cls.LineWrapMode.NoWrap)
    errors_text.setFont(qfont_cls("Consolas", 9))
    errors_text.setMinimumHeight(errors_text_min_height)
    errors_text.setMaximumHeight(errors_text_max_height)
    errors_text.document().contentsChanged.connect(on_update_errors_height)
    errors_layout.addWidget(errors_text)

    errors_card.add_layout(errors_layout)
    parent_layout.addWidget(errors_card)

    winws_card = settings_card_cls()
    winws_layout = qvbox_layout_cls()
    winws_header = qhbox_layout_cls()

    terminal_icon = qlabel_cls()
    winws_header.addWidget(terminal_icon)

    winws_title_label = strong_body_label_cls(
        tr_catalog_fn(
            "page.logs.winws.title_template",
            language=ui_language,
            default="Вывод {exe_name}",
        ).format(exe_name="winws.exe")
    )
    winws_header.addWidget(winws_title_label)
    winws_header.addSpacing(16)

    winws_status_label = caption_label_cls(
        tr_catalog_fn("page.logs.winws.status.not_running", language=ui_language, default="Процесс не запущен")
    )
    winws_header.addWidget(winws_status_label)
    winws_header.addStretch()

    clear_winws_btn = fluent_push_button_cls()
    clear_winws_btn.setText(tr_catalog_fn("page.logs.button.clear", language=ui_language, default="Очистить"))
    clear_winws_btn.setIcon(qta_module.icon("fa5s.trash", color=tokens.fg))
    clear_winws_btn.clicked.connect(on_clear_winws_output)
    winws_header.addWidget(clear_winws_btn)

    winws_layout.addLayout(winws_header)

    winws_text = text_edit_cls()
    winws_text.setReadOnly(True)
    winws_text.setLineWrapMode(qtextedit_cls.LineWrapMode.NoWrap)
    winws_text.setFont(qfont_cls("Consolas", 9))
    winws_text.setFixedHeight(150)
    winws_layout.addWidget(winws_text)

    winws_card.add_layout(winws_layout)
    parent_layout.addWidget(winws_card)

    return LogsTabWidgets(
        controls_card=controls_card,
        log_combo=log_combo,
        refresh_btn=refresh_btn,
        controls_actions_title=controls_actions_title,
        controls_actions_bar=controls_actions_bar,
        copy_btn=copy_btn,
        clear_btn=clear_btn,
        folder_btn=folder_btn,
        log_card=log_card,
        log_text=log_text,
        stats_label=stats_label,
        errors_card=errors_card,
        warning_icon_label=warning_icon,
        errors_title_label=errors_title_label,
        errors_count_label=errors_count_label,
        clear_errors_btn=clear_errors_btn,
        errors_text=errors_text,
        winws_card=winws_card,
        terminal_icon_label=terminal_icon,
        winws_title_label=winws_title_label,
        winws_status_label=winws_status_label,
        clear_winws_btn=clear_winws_btn,
        winws_text=winws_text,
    )
