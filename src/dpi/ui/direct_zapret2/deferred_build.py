"""Build-helper deferred-секций для Zapret2DirectControlPage."""

from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QHBoxLayout, QSizePolicy

from ui.compat_widgets import SettingsCard, ActionButton, ResetActionButton, build_advanced_settings_section, enable_setting_card_group_auto_height
from ui.theme import get_cached_qta_pixmap, get_theme_tokens, get_themed_qta_icon


@dataclass(slots=True)
class Zapret2DeferredBuildWidgets:
    direct_section_label: object
    direct_card: object
    direct_mode_label: object
    direct_mode_caption: object
    direct_open_btn: object
    direct_mode_btn: object
    program_settings_section_label: object | None
    program_settings_card: object
    auto_dpi_toggle: object
    defender_toggle: object
    max_block_toggle: object
    reset_program_card: object
    reset_program_btn: object | None
    reset_program_desc_label: object | None
    advanced_card: object
    advanced_notice: object
    discord_restart_toggle: object | None
    wssize_toggle: object | None
    debug_log_toggle: object | None
    blobs_action_card: object
    blobs_open_btn: object
    extra_section_label: object
    extra_card: object
    test_btn: object
    folder_btn: object
    docs_btn: object


def build_z2_direct_deferred_sections(
    *,
    add_section_title,
    tr_fn,
    content_parent,
    has_fluent_labels: bool,
    strong_body_label_cls,
    caption_label_cls,
    push_button_cls,
    transparent_push_button_cls,
    setting_card_group_cls,
    push_setting_card_cls,
    card_widget_cls,
    fluent_icon,
    reset_action_button_cls,
    settings_card_cls,
    win11_toggle_row_cls,
    on_open_direct_launch_page,
    on_open_direct_mode_dialog,
    on_auto_dpi_toggled,
    on_defender_toggled,
    on_max_blocker_toggled,
    on_confirm_reset_program_clicked,
    on_reset_program_clicked,
    on_discord_restart_changed,
    on_wssize_toggled,
    on_debug_log_toggled,
    on_navigate_to_blobs,
    on_open_connection_test,
    on_open_folder,
    on_open_docs,
) -> Zapret2DeferredBuildWidgets:
    direct_section_label = add_section_title(
        return_widget=True,
        text_key="page.z2_control.section.direct_tuning",
    )

    direct_card = card_widget_cls()
    direct_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
    direct_row = QHBoxLayout(direct_card)
    direct_row.setContentsMargins(16, 14, 16, 14)
    direct_row.setSpacing(12)

    direct_icon_lbl = QLabel()
    direct_icon_lbl.setPixmap(get_cached_qta_pixmap("fa5s.play", color="#60cdff", size=20))
    direct_icon_lbl.setFixedSize(24, 24)
    direct_row.addWidget(direct_icon_lbl, 0, Qt.AlignmentFlag.AlignVCenter)

    direct_col = QVBoxLayout()
    direct_col.setSpacing(2)
    direct_mode_label = strong_body_label_cls(tr_fn("page.z2_control.mode.basic", "Basic"))
    direct_col.addWidget(direct_mode_label)
    direct_mode_caption = caption_label_cls(
        tr_fn("page.z2_control.direct_mode.caption", "Режим прямого запуска")
    )
    direct_col.addWidget(direct_mode_caption)
    direct_row.addLayout(direct_col, 1)

    direct_btns = QHBoxLayout()
    direct_btns.setSpacing(4)
    direct_open_btn = push_button_cls()
    direct_open_btn.setText(tr_fn("page.z2_control.button.open", "Открыть"))
    direct_open_btn.setIcon(fluent_icon.PLAY)
    direct_open_btn.clicked.connect(on_open_direct_launch_page)
    direct_mode_btn = transparent_push_button_cls()
    direct_mode_btn.setText(tr_fn("page.z2_control.button.change_mode", "Изменить режим"))
    direct_mode_btn.clicked.connect(on_open_direct_mode_dialog)
    direct_btns.addWidget(direct_open_btn)
    direct_btns.addWidget(direct_mode_btn)
    direct_row.addLayout(direct_btns)

    program_settings_title = tr_fn("page.z2_control.section.program_settings", "Настройки программы")
    if setting_card_group_cls is not None and push_setting_card_cls is not None and has_fluent_labels:
        program_settings_section_label = None
        program_settings_card = setting_card_group_cls(program_settings_title, content_parent)
    else:
        program_settings_section_label = add_section_title(
            return_widget=True,
            text_key="page.z2_control.section.program_settings",
        )
        program_settings_card = settings_card_cls()

    auto_dpi_toggle = win11_toggle_row_cls(
        "fa5s.bolt",
        tr_fn("page.z2_control.setting.autostart.title", "Автозапуск DPI после старта программы"),
        tr_fn("page.z2_control.setting.autostart.desc", "После запуска ZapretGUI автоматически запускать текущий DPI-режим"),
    )
    auto_dpi_toggle.toggled.connect(on_auto_dpi_toggled)

    defender_toggle = win11_toggle_row_cls(
        "fa5s.shield-alt",
        tr_fn("page.z2_control.setting.defender.title", "Отключить Windows Defender"),
        tr_fn("page.z2_control.setting.defender.desc", "Требуются права администратора"),
    )
    defender_toggle.toggled.connect(on_defender_toggled)

    max_block_toggle = win11_toggle_row_cls(
        "fa5s.ban",
        tr_fn("page.z2_control.setting.max_block.title", "Блокировать установку MAX"),
        tr_fn("page.z2_control.setting.max_block.desc", "Блокирует запуск/установку MAX и домены в hosts"),
    )
    max_block_toggle.toggled.connect(on_max_blocker_toggled)

    add_setting_card = getattr(program_settings_card, "addSettingCard", None)
    if callable(add_setting_card):
        add_setting_card(auto_dpi_toggle)
        add_setting_card(defender_toggle)
        add_setting_card(max_block_toggle)
    else:
        program_settings_card.add_widget(auto_dpi_toggle)
        program_settings_card.add_widget(defender_toggle)
        program_settings_card.add_widget(max_block_toggle)

    reset_program_btn = None
    reset_program_desc_label = None
    if callable(add_setting_card) and push_setting_card_cls is not None:
        reset_program_card = push_setting_card_cls(
            tr_fn("page.z2_control.button.reset", "Сбросить"),
            get_themed_qta_icon("fa5s.undo", color="#ff9800"),
            tr_fn("page.z2_control.setting.reset.title", "Сбросить программу"),
            tr_fn("page.z2_control.setting.reset.desc", "Очистить кэш проверок запуска (без удаления пресетов/настроек)"),
        )
        reset_program_card.clicked.connect(on_confirm_reset_program_clicked)
        add_setting_card(reset_program_card)
    else:
        reset_program_btn = reset_action_button_cls(
            tr_fn("page.z2_control.button.reset", "Сбросить"),
            confirm_text=tr_fn("page.z2_control.button.reset_confirm", "Сбросить?"),
        )
        reset_program_btn.setProperty("noDrag", True)
        reset_program_btn.reset_confirmed.connect(on_reset_program_clicked)
        reset_program_card = settings_card_cls(
            tr_fn("page.z2_control.setting.reset.title", "Сбросить программу")
        )
        reset_program_desc_label = caption_label_cls(
            tr_fn("page.z2_control.setting.reset.desc", "Очистить кэш проверок запуска (без удаления пресетов/настроек)")
        ) if has_fluent_labels else QLabel(
            tr_fn("page.z2_control.setting.reset.desc", "Очистить кэш проверок запуска (без удаления пресетов/настроек)")
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
            "Перезапуск Discord",
            "Автоперезапуск при смене стратегии",
            "#7289da",
        )
        if win11_toggle_row_cls
        else None
    )
    if discord_restart_toggle:
        discord_restart_toggle.toggled.connect(on_discord_restart_changed)

    wssize_toggle = (
        win11_toggle_row_cls(
            "fa5s.ruler-horizontal",
            "Включить --wssize",
            "Добавляет параметр размера окна TCP",
        )
        if win11_toggle_row_cls
        else None
    )
    if wssize_toggle:
        wssize_toggle.toggled.connect(on_wssize_toggled)

    debug_log_toggle = (
        win11_toggle_row_cls(
            "mdi.file-document-outline",
            "Включить лог-файл (--debug)",
            "Записывает логи winws в папку logs",
        )
        if win11_toggle_row_cls
        else None
    )
    if debug_log_toggle:
        debug_log_toggle.toggled.connect(on_debug_log_toggled)

    blobs_action_card = push_setting_card_cls(
        tr_fn("page.z2_control.button.open", "Открыть"),
        get_themed_qta_icon("fa5s.file-archive", color=get_theme_tokens().accent_hex),
        tr_fn("page.z2_control.blobs.title", "Блобы"),
        tr_fn("page.z2_control.blobs.desc", "Бинарные данные (.bin / hex) для стратегий"),
    )
    blobs_action_card.clicked.connect(on_navigate_to_blobs)
    blobs_open_btn = blobs_action_card.button

    advanced_card, advanced_notice = build_advanced_settings_section(
        title=tr_fn("page.z2_control.card.advanced", "ДОПОЛНИТЕЛЬНЫЕ НАСТРОЙКИ"),
        warning_text=tr_fn("page.z2_control.advanced.warning", "Изменяйте только если знаете что делаете"),
        parent=content_parent,
        toggle_rows=[discord_restart_toggle, wssize_toggle, debug_log_toggle],
        action_rows=[blobs_action_card],
    )

    extra_section_label = add_section_title(
        return_widget=True,
        text_key="page.z2_control.section.additional",
    )
    extra_card = settings_card_cls()
    extra_layout = QHBoxLayout()
    extra_layout.setSpacing(8)
    test_btn = ActionButton(
        tr_fn("page.z2_control.button.connection_test", "Тест соединения"),
        "fa5s.wifi",
    )
    test_btn.clicked.connect(on_open_connection_test)
    extra_layout.addWidget(test_btn)
    folder_btn = ActionButton(
        tr_fn("page.z2_control.button.open_folder", "Открыть папку"),
        "fa5s.folder-open",
    )
    folder_btn.clicked.connect(on_open_folder)
    extra_layout.addWidget(folder_btn)
    docs_btn = ActionButton(
        tr_fn("page.z2_control.button.documentation", "Документация"),
        "fa5s.book",
    )
    docs_btn.clicked.connect(on_open_docs)
    extra_layout.addWidget(docs_btn)
    extra_layout.addStretch()
    extra_card.add_layout(extra_layout)

    return Zapret2DeferredBuildWidgets(
        direct_section_label=direct_section_label,
        direct_card=direct_card,
        direct_mode_label=direct_mode_label,
        direct_mode_caption=direct_mode_caption,
        direct_open_btn=direct_open_btn,
        direct_mode_btn=direct_mode_btn,
        program_settings_section_label=program_settings_section_label,
        program_settings_card=program_settings_card,
        auto_dpi_toggle=auto_dpi_toggle,
        defender_toggle=defender_toggle,
        max_block_toggle=max_block_toggle,
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
        extra_section_label=extra_section_label,
        extra_card=extra_card,
        test_btn=test_btn,
        folder_btn=folder_btn,
        docs_btn=docs_btn,
    )
