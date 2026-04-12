"""Build-helper deferred-секций для Zapret1DirectControlPage."""

from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel, QHBoxLayout, QVBoxLayout, QSizePolicy

from ui.compat_widgets import ActionButton, ResetActionButton, SettingsCard, build_advanced_settings_section, enable_setting_card_group_auto_height
from ui.theme import get_cached_qta_pixmap, get_themed_qta_icon


@dataclass(slots=True)
class Zapret1DeferredBuildWidgets:
    strategies_card: object
    strategies_title_label: object
    strategies_desc_label: object
    open_strat_btn: object
    program_settings_section_label: object | None
    program_settings_card: object
    auto_dpi_toggle: object
    reset_program_card: object
    reset_program_btn: object | None
    reset_program_desc_label: object | None
    advanced_card: object
    advanced_notice: object
    discord_restart_toggle: object | None
    wssize_toggle: object | None
    debug_log_toggle: object | None
    blobs_action_card: object | None
    blobs_open_btn: object | None
    extra_card: object
    test_btn: object | None
    folder_btn: object | None
    docs_btn: object | None
    test_action_card: object | None
    folder_action_card: object | None
    docs_action_card: object | None


def build_z1_direct_deferred_sections(
    *,
    add_section_title,
    tr_fn,
    content_parent,
    has_fluent: bool,
    push_setting_card_cls,
    card_widget_cls,
    strong_body_label_cls,
    caption_label_cls,
    action_button_cls,
    setting_card_group_cls,
    settings_card_cls,
    reset_action_button_cls,
    win11_toggle_row_cls,
    on_open_strategies_page,
    on_auto_dpi_toggled,
    on_confirm_reset_program_clicked,
    on_reset_program_clicked,
    on_discord_restart_changed,
    on_wssize_toggled,
    on_debug_log_toggled,
    on_navigate_to_blobs,
    on_open_connection_test,
    on_open_folder,
    on_open_docs,
) -> Zapret1DeferredBuildWidgets:
    if push_setting_card_cls is not None:
        strategies_card = push_setting_card_cls(
            tr_fn("page.z1_control.button.open", "Открыть"),
            get_themed_qta_icon("fa5s.play", color="#60cdff"),
            tr_fn("page.z1_control.strategies.title", "Стратегии по категориям"),
            tr_fn("page.z1_control.strategies.desc", "Выбор стратегии для YouTube, Discord и др."),
            content_parent,
        )
        strategies_card.clicked.connect(on_open_strategies_page)
        strategies_title_label = strategies_card.titleLabel
        strategies_desc_label = strategies_card.contentLabel
        open_strat_btn = strategies_card.button
    else:
        strategies_card = card_widget_cls()
        strategies_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        strat_row = QHBoxLayout(strategies_card)
        strat_row.setContentsMargins(16, 14, 16, 14)
        strat_row.setSpacing(12)

        strat_icon_lbl = QLabel()
        strat_icon_lbl.setPixmap(get_cached_qta_pixmap("fa5s.play", color="#60cdff", size=20))
        strat_icon_lbl.setFixedSize(24, 24)
        strat_row.addWidget(strat_icon_lbl, 0, Qt.AlignmentFlag.AlignVCenter)

        strat_col = QVBoxLayout()
        strat_col.setSpacing(2)
        strategies_title_label = strong_body_label_cls(
            tr_fn("page.z1_control.strategies.title", "Стратегии по категориям")
        )
        strategies_desc_label = caption_label_cls(
            tr_fn("page.z1_control.strategies.desc", "Выбор стратегии для YouTube, Discord и др.")
        )
        strat_col.addWidget(strategies_title_label)
        strat_col.addWidget(strategies_desc_label)
        strat_row.addLayout(strat_col, 1)

        open_strat_btn = action_button_cls(
            tr_fn("page.z1_control.button.open", "Открыть"),
            "fa5s.play",
        )
        open_strat_btn.clicked.connect(on_open_strategies_page)
        strat_row.addWidget(open_strat_btn, 0, Qt.AlignmentFlag.AlignVCenter)

    program_settings_title = tr_fn("page.z1_control.section.program_settings", "Настройки программы")
    if setting_card_group_cls is not None and has_fluent:
        program_settings_section_label = None
        program_settings_card = setting_card_group_cls(program_settings_title, content_parent)
    else:
        program_settings_section_label = add_section_title(text_key="page.z1_control.section.program_settings")
        program_settings_card = settings_card_cls()

    auto_dpi_toggle = win11_toggle_row_cls(
        "fa5s.bolt",
        tr_fn("page.z1_control.setting.autostart.title", "Автозапуск DPI после старта программы"),
        tr_fn("page.z1_control.setting.autostart.desc", "После запуска ZapretGUI автоматически запускать текущий DPI-режим"),
    )
    auto_dpi_toggle.toggled.connect(on_auto_dpi_toggled)

    add_setting_card = getattr(program_settings_card, "addSettingCard", None)
    if callable(add_setting_card):
        add_setting_card(auto_dpi_toggle)
    else:
        program_settings_card.add_widget(auto_dpi_toggle)

    reset_program_btn = None
    reset_program_desc_label = None
    if callable(add_setting_card) and push_setting_card_cls is not None:
        reset_program_card = push_setting_card_cls(
            tr_fn("page.z1_control.button.reset", "Сбросить"),
            get_themed_qta_icon("fa5s.undo", color="#ff9800"),
            tr_fn("page.z1_control.setting.reset.title", "Сбросить программу"),
            tr_fn("page.z1_control.setting.reset.desc", "Очистить кэш проверок запуска (без удаления пресетов/настроек)"),
        )
        reset_program_card.clicked.connect(on_confirm_reset_program_clicked)
        add_setting_card(reset_program_card)
    else:
        reset_program_btn = reset_action_button_cls(
            tr_fn("page.z1_control.button.reset", "Сбросить"),
            confirm_text=tr_fn("page.z1_control.button.reset_confirm", "Сбросить?"),
        )
        reset_program_btn.setProperty("noDrag", True)
        reset_program_btn.reset_confirmed.connect(on_reset_program_clicked)
        reset_program_card = settings_card_cls(
            tr_fn("page.z1_control.setting.reset.title", "Сбросить программу")
        )
        reset_program_desc_label = caption_label_cls(
            tr_fn("page.z1_control.setting.reset.desc", "Очистить кэш проверок запуска (без удаления пресетов/настроек)")
        ) if has_fluent else QLabel(
            tr_fn("page.z1_control.setting.reset.desc", "Очистить кэш проверок запуска (без удаления пресетов/настроек)")
        )
        reset_program_desc_label.setWordWrap(True)
        reset_program_card.add_widget(reset_program_desc_label)
        reset_layout = QHBoxLayout()
        reset_layout.setSpacing(8)
        reset_layout.addWidget(reset_program_btn)
        reset_layout.addStretch()
        reset_program_card.add_layout(reset_layout)

    enable_setting_card_group_auto_height(program_settings_card)

    discord_restart_toggle = (
        win11_toggle_row_cls(
            "mdi.discord",
            tr_fn("page.z1_control.advanced.discord_restart.title", "Перезапуск Discord"),
            tr_fn("page.z1_control.advanced.discord_restart.desc", "Автоперезапуск при смене стратегии"),
            "#7289da",
        )
        if win11_toggle_row_cls
        else None
    )
    if discord_restart_toggle is not None:
        discord_restart_toggle.toggled.connect(on_discord_restart_changed)

    wssize_toggle = (
        win11_toggle_row_cls(
            "fa5s.ruler-horizontal",
            tr_fn("page.z1_control.advanced.wssize.title", "Включить --wssize"),
            tr_fn("page.z1_control.advanced.wssize.desc", "Добавляет параметр размера окна TCP"),
        )
        if win11_toggle_row_cls
        else None
    )
    if wssize_toggle is not None:
        wssize_toggle.toggled.connect(on_wssize_toggled)

    debug_log_toggle = (
        win11_toggle_row_cls(
            "mdi.file-document-outline",
            tr_fn("page.z1_control.advanced.debug_log.title", "Включить лог-файл (--debug)"),
            tr_fn("page.z1_control.advanced.debug_log.desc", "Записывает логи winws в папку logs"),
        )
        if win11_toggle_row_cls
        else None
    )
    if debug_log_toggle is not None:
        debug_log_toggle.toggled.connect(on_debug_log_toggled)

    if push_setting_card_cls is not None:
        blobs_action_card = push_setting_card_cls(
            tr_fn("page.z1_control.button.open", "Открыть"),
            get_themed_qta_icon("fa5s.file-archive", color="#ff9800"),
            tr_fn("page.z1_control.blobs.title", "Блобы"),
            tr_fn("page.z1_control.blobs.desc", "Бинарные данные (.bin / hex) для стратегий"),
        )
        blobs_action_card.clicked.connect(on_navigate_to_blobs)
        blobs_open_btn = blobs_action_card.button
    else:
        blobs_action_card = None
        blobs_open_btn = None

    advanced_card, advanced_notice = build_advanced_settings_section(
        title=tr_fn("page.z1_control.card.advanced", "ДОПОЛНИТЕЛЬНЫЕ НАСТРОЙКИ"),
        warning_text=tr_fn("page.z1_control.advanced.warning", "Изменяйте только если знаете что делаете"),
        parent=content_parent,
        toggle_rows=[discord_restart_toggle, wssize_toggle, debug_log_toggle],
        action_rows=[blobs_action_card],
    )

    if setting_card_group_cls is not None and push_setting_card_cls is not None and has_fluent:
        extra_group = setting_card_group_cls(
            tr_fn("page.z1_control.section.additional", "Дополнительные действия"),
            content_parent,
        )
        extra_card = extra_group

        test_action_card = push_setting_card_cls(
            tr_fn("page.z1_control.button.open", "Открыть"),
            get_themed_qta_icon("fa5s.wifi", color="#60cdff"),
            tr_fn("page.z1_control.button.connection_test", "Тест соединения"),
            tr_fn("page.z1_control.button.connection_test.desc", "Проверить доступность сети и состояние обхода"),
        )
        test_action_card.clicked.connect(on_open_connection_test)

        folder_action_card = push_setting_card_cls(
            tr_fn("page.z1_control.button.open", "Открыть"),
            get_themed_qta_icon("fa5s.folder-open", color="#f5c04d"),
            tr_fn("page.z1_control.button.open_folder", "Открыть папку"),
            tr_fn("page.z1_control.button.open_folder.desc", "Перейти в папку программы и служебных файлов"),
        )
        folder_action_card.clicked.connect(on_open_folder)

        docs_action_card = push_setting_card_cls(
            tr_fn("page.z1_control.button.open", "Открыть"),
            get_themed_qta_icon("fa5s.book", color="#8ab4f8"),
            tr_fn("page.z1_control.button.documentation", "Документация"),
            tr_fn("page.z1_control.button.documentation.desc", "Открыть справку и описание возможностей"),
        )
        docs_action_card.clicked.connect(on_open_docs)

        extra_group.addSettingCard(test_action_card)
        extra_group.addSettingCard(folder_action_card)
        extra_group.addSettingCard(docs_action_card)
        enable_setting_card_group_auto_height(extra_group)

        test_btn = None
        folder_btn = None
        docs_btn = None
    else:
        extra_card = settings_card_cls()
        extra_layout = QHBoxLayout()
        extra_layout.setSpacing(8)

        test_btn = action_button_cls(
            tr_fn("page.z1_control.button.connection_test", "Тест соединения"),
            "fa5s.wifi",
        )
        test_btn.clicked.connect(on_open_connection_test)
        extra_layout.addWidget(test_btn)

        folder_btn = action_button_cls(
            tr_fn("page.z1_control.button.open_folder", "Открыть папку"),
            "fa5s.folder-open",
        )
        folder_btn.clicked.connect(on_open_folder)
        extra_layout.addWidget(folder_btn)

        docs_btn = action_button_cls(
            tr_fn("page.z1_control.button.documentation", "Документация"),
            "fa5s.book",
        )
        docs_btn.clicked.connect(on_open_docs)
        extra_layout.addWidget(docs_btn)

        extra_layout.addStretch()
        extra_card.add_layout(extra_layout)

        test_action_card = None
        folder_action_card = None
        docs_action_card = None

    return Zapret1DeferredBuildWidgets(
        strategies_card=strategies_card,
        strategies_title_label=strategies_title_label,
        strategies_desc_label=strategies_desc_label,
        open_strat_btn=open_strat_btn,
        program_settings_section_label=program_settings_section_label,
        program_settings_card=program_settings_card,
        auto_dpi_toggle=auto_dpi_toggle,
        reset_program_card=reset_program_card,
        reset_program_btn=reset_program_btn,
        reset_program_desc_label=reset_program_desc_label,
        advanced_card=advanced_card,
        advanced_notice=advanced_notice,
        discord_restart_toggle=discord_restart_toggle,
        wssize_toggle=wssize_toggle,
        debug_log_toggle=debug_log_toggle,
        blobs_action_card=blobs_action_card,
        blobs_open_btn=blobs_open_btn,
        extra_card=extra_card,
        test_btn=test_btn,
        folder_btn=folder_btn,
        docs_btn=docs_btn,
        test_action_card=test_action_card,
        folder_action_card=folder_action_card,
        docs_action_card=docs_action_card,
    )
