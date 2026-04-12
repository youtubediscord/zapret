"""Build-helper deferred-секций для Zapret1DirectControlPage."""

from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel, QHBoxLayout, QVBoxLayout, QSizePolicy

from direct_control.shared_builders import (
    build_direct_action_card_common,
    build_connected_direct_action_card_common,
    build_direct_extra_buttons_card_common,
    build_reset_program_action_card_common,
)
from ui.compat_widgets import ActionButton, SettingsCard, build_advanced_settings_section, enable_setting_card_group_auto_height
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
    win11_toggle_row_cls,
    on_open_strategies_page,
    on_auto_dpi_toggled,
    on_confirm_reset_program_clicked,
    on_discord_restart_changed,
    on_wssize_toggled,
    on_debug_log_toggled,
    on_navigate_to_blobs,
    on_open_connection_test,
    on_open_folder,
    on_open_docs,
) -> Zapret1DeferredBuildWidgets:
    _ = push_setting_card_cls
    open_strat_btn = action_button_cls(
        tr_fn("page.z1_control.button.open", "Открыть"),
        "fa5s.play",
    )

    strategies_widgets = build_connected_direct_action_card_common(
        card_widget_cls=card_widget_cls,
        strong_body_label_cls=strong_body_label_cls,
        caption_label_cls=caption_label_cls,
        button=open_strat_btn,
        icon_source=get_cached_qta_pixmap("fa5s.play", color="#60cdff", size=20),
        title_text=tr_fn("page.z1_control.strategies.title", "Стратегии по категориям"),
        content_text=tr_fn("page.z1_control.strategies.desc", "Выбор стратегии для YouTube, Discord и др."),
        parent=content_parent,
        on_click=on_open_strategies_page,
    )

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

    reset_program_card, reset_program_btn, reset_program_desc_label = build_reset_program_action_card_common(
        tr_fn=tr_fn,
        has_fluent_labels=has_fluent,
        caption_label_cls=caption_label_cls,
        action_button_cls=action_button_cls,
        settings_card_cls=settings_card_cls,
        button_key="page.z1_control.button.reset",
        button_default="Сбросить",
        button_icon_name="fa5s.undo",
        title_key="page.z1_control.setting.reset.title",
        title_default="Сбросить программу",
        desc_key="page.z1_control.setting.reset.desc",
        desc_default="Очистить кэш проверок запуска (без удаления пресетов/настроек)",
        on_confirm_reset_program_clicked=on_confirm_reset_program_clicked,
    )

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

    blobs_open_btn = action_button_cls(
        tr_fn("page.z1_control.button.open", "Открыть"),
        "fa5s.file-archive",
    )
    blobs_widgets = build_connected_direct_action_card_common(
        card_widget_cls=card_widget_cls,
        strong_body_label_cls=strong_body_label_cls,
        caption_label_cls=caption_label_cls,
        button=blobs_open_btn,
        icon_source=get_themed_qta_icon("fa5s.file-archive", color="#ff9800"),
        title_text=tr_fn("page.z1_control.blobs.title", "Блобы"),
        content_text=tr_fn("page.z1_control.blobs.desc", "Бинарные данные (.bin / hex) для стратегий"),
        parent=content_parent,
        on_click=on_navigate_to_blobs,
    )

    advanced_card, advanced_notice = build_advanced_settings_section(
        title=tr_fn("page.z1_control.card.advanced", "ДОПОЛНИТЕЛЬНЫЕ НАСТРОЙКИ"),
        warning_text=tr_fn("page.z1_control.advanced.warning", "Изменяйте только если знаете что делаете"),
        parent=content_parent,
        toggle_rows=[discord_restart_toggle, wssize_toggle, debug_log_toggle],
        action_rows=[blobs_widgets.card],
    )

    if setting_card_group_cls is not None and has_fluent:
        extra_group = setting_card_group_cls(
            tr_fn("page.z1_control.section.additional", "Дополнительные действия"),
            content_parent,
        )
        extra_card = extra_group

        test_card_btn = action_button_cls(
            tr_fn("page.z1_control.button.open", "Открыть"),
            "fa5s.wifi",
        )
        test_widgets = build_connected_direct_action_card_common(
            card_widget_cls=card_widget_cls,
            strong_body_label_cls=strong_body_label_cls,
            caption_label_cls=caption_label_cls,
            button=test_card_btn,
            icon_source=get_themed_qta_icon("fa5s.wifi", color="#60cdff"),
            title_text=tr_fn("page.z1_control.button.connection_test", "Тест соединения"),
            content_text=tr_fn("page.z1_control.button.connection_test.desc", "Проверить доступность сети и состояние обхода"),
            parent=content_parent,
            on_click=on_open_connection_test,
        )

        folder_card_btn = action_button_cls(
            tr_fn("page.z1_control.button.open", "Открыть"),
            "fa5s.folder-open",
        )
        folder_widgets = build_connected_direct_action_card_common(
            card_widget_cls=card_widget_cls,
            strong_body_label_cls=strong_body_label_cls,
            caption_label_cls=caption_label_cls,
            button=folder_card_btn,
            icon_source=get_themed_qta_icon("fa5s.folder-open", color="#f5c04d"),
            title_text=tr_fn("page.z1_control.button.open_folder", "Открыть папку"),
            content_text=tr_fn("page.z1_control.button.open_folder.desc", "Перейти в папку программы и служебных файлов"),
            parent=content_parent,
            on_click=on_open_folder,
        )

        docs_card_btn = action_button_cls(
            tr_fn("page.z1_control.button.open", "Открыть"),
            "fa5s.book",
        )
        docs_widgets = build_connected_direct_action_card_common(
            card_widget_cls=card_widget_cls,
            strong_body_label_cls=strong_body_label_cls,
            caption_label_cls=caption_label_cls,
            button=docs_card_btn,
            icon_source=get_themed_qta_icon("fa5s.book", color="#8ab4f8"),
            title_text=tr_fn("page.z1_control.button.documentation", "Документация"),
            content_text=tr_fn("page.z1_control.button.documentation.desc", "Открыть справку и описание возможностей"),
            parent=content_parent,
            on_click=on_open_docs,
        )

        extra_group.addSettingCard(test_widgets.card)
        extra_group.addSettingCard(folder_widgets.card)
        extra_group.addSettingCard(docs_widgets.card)
        enable_setting_card_group_auto_height(extra_group)

        test_btn = None
        folder_btn = None
        docs_btn = None
        test_action_card = test_widgets
        folder_action_card = folder_widgets
        docs_action_card = docs_widgets
    else:
        extra_card, buttons = build_direct_extra_buttons_card_common(
            settings_card_cls=settings_card_cls,
            action_button_cls=action_button_cls,
            actions=[
                (
                    tr_fn("page.z1_control.button.connection_test", "Тест соединения"),
                    "fa5s.wifi",
                    on_open_connection_test,
                ),
                (
                    tr_fn("page.z1_control.button.open_folder", "Открыть папку"),
                    "fa5s.folder-open",
                    on_open_folder,
                ),
                (
                    tr_fn("page.z1_control.button.documentation", "Документация"),
                    "fa5s.book",
                    on_open_docs,
                ),
            ],
        )
        test_btn, folder_btn, docs_btn = buttons

        test_action_card = None
        folder_action_card = None
        docs_action_card = None

    return Zapret1DeferredBuildWidgets(
        strategies_card=strategies_widgets.card,
        strategies_title_label=strategies_widgets.title_label,
        strategies_desc_label=strategies_widgets.content_label,
        open_strat_btn=strategies_widgets.button,
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
        blobs_action_card=blobs_widgets,
        blobs_open_btn=blobs_widgets.button,
        extra_card=extra_card,
        test_btn=test_btn,
        folder_btn=folder_btn,
        docs_btn=docs_btn,
        test_action_card=test_action_card,
        folder_action_card=folder_action_card,
        docs_action_card=docs_action_card,
    )
