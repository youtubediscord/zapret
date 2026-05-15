"""Build-helper deferred-секций для Zapret1ModeControlPage."""

from __future__ import annotations

from dataclasses import dataclass

from presets.ui.control.shared_builders import (
    build_preset_setup_open_card_common,
    build_push_setting_card_common,
)
from presets.ui.control.windows_features.build import build_windows_feature_toggles
from ui.fluent_widgets import build_advanced_settings_section, enable_setting_card_group_auto_height
from ui.theme import get_themed_qta_icon


@dataclass(slots=True)
class Zapret1DeferredBuildWidgets:
    preset_setup_card: object
    preset_setup_open_btn: object
    program_settings_section_label: object | None
    program_settings_card: object
    auto_dpi_toggle: object
    defender_toggle: object
    max_block_toggle: object
    advanced_card: object
    advanced_notice: object
    discord_restart_toggle: object | None
    wssize_toggle: object | None
    debug_log_toggle: object | None
    blobs_action_card: object | None
    blobs_open_btn: object | None
    extra_card: object
    test_card: object
    folder_card: object
    docs_card: object


def build_winws1_pages_deferred_sections(
    *,
    add_section_title,
    tr_fn,
    content_parent,
    push_setting_card_cls,
    setting_card_group_cls,
    win11_toggle_row_cls,
    on_open_preset_setup_page,
    on_auto_dpi_toggled,
    on_defender_toggled,
    on_max_blocker_toggled,
    on_discord_restart_changed,
    on_wssize_toggled,
    on_debug_log_toggled,
    on_navigate_to_blobs,
    on_open_connection_test,
    on_open_folder,
    on_open_docs,
) -> Zapret1DeferredBuildWidgets:
    preset_setup_entry = build_preset_setup_open_card_common(
        tr_fn=tr_fn,
        push_setting_card_cls=push_setting_card_cls,
        button_key="page.winws1_control.button.open",
        title_key="page.winws1_control.profiles.title",
        desc_key="page.winws1_control.profiles.desc",
        on_open_preset_setup_page=on_open_preset_setup_page,
        parent=content_parent,
    )

    program_settings_title = tr_fn("page.winws1_control.section.program_settings", "Настройки программы")
    program_settings_section_label = None
    program_settings_card = setting_card_group_cls(program_settings_title, content_parent)

    auto_dpi_toggle = win11_toggle_row_cls(
        "fa5s.bolt",
        tr_fn("page.winws1_control.setting.autostart.title", "Автозапуск DPI после старта программы"),
        tr_fn("page.winws1_control.setting.autostart.desc", "После запуска ZapretGUI автоматически запускать текущий DPI-режим"),
    )
    auto_dpi_toggle.toggled.connect(on_auto_dpi_toggled)

    windows_feature_toggles = build_windows_feature_toggles(
        tr_fn=tr_fn,
        win11_toggle_row_cls=win11_toggle_row_cls,
        on_defender_toggled=on_defender_toggled,
        on_max_blocker_toggled=on_max_blocker_toggled,
    )

    program_settings_card.addSettingCard(auto_dpi_toggle)
    program_settings_card.addSettingCard(windows_feature_toggles.defender_toggle)
    program_settings_card.addSettingCard(windows_feature_toggles.max_block_toggle)

    enable_setting_card_group_auto_height(program_settings_card)

    discord_restart_toggle = (
        win11_toggle_row_cls(
            "mdi.discord",
            tr_fn("page.winws1_control.advanced.discord_restart.title", "Перезапуск Discord"),
            tr_fn("page.winws1_control.advanced.discord_restart.desc", "Автоперезапуск при смене стратегии"),
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
            tr_fn("page.winws1_control.advanced.wssize.title", "Включить --wssize"),
            tr_fn("page.winws1_control.advanced.wssize.desc", "Добавляет параметр размера окна TCP"),
        )
        if win11_toggle_row_cls
        else None
    )
    if wssize_toggle is not None:
        wssize_toggle.toggled.connect(on_wssize_toggled)

    debug_log_toggle = (
        win11_toggle_row_cls(
            "mdi.file-document-outline",
            tr_fn("page.winws1_control.advanced.debug_log.title", "Включить лог-файл (--debug)"),
            tr_fn("page.winws1_control.advanced.debug_log.desc", "Записывает логи winws в папку logs"),
        )
        if win11_toggle_row_cls
        else None
    )
    if debug_log_toggle is not None:
        debug_log_toggle.toggled.connect(on_debug_log_toggled)

    blobs_card = build_push_setting_card_common(
        push_setting_card_cls=push_setting_card_cls,
        button_text=tr_fn("page.winws1_control.button.open", "Открыть"),
        icon=get_themed_qta_icon("fa5s.file-archive", color="#ff9800"),
        title_text=tr_fn("page.winws1_control.blobs.title", "Блобы"),
        content_text=tr_fn("page.winws1_control.blobs.desc", "Бинарные данные (.bin / hex) для стратегий"),
        on_click=on_navigate_to_blobs,
        parent=content_parent,
    )

    advanced_card, advanced_notice = build_advanced_settings_section(
        title=tr_fn("page.winws1_control.card.advanced", "Дополнительные настройки"),
        warning_text=tr_fn("page.winws1_control.advanced.warning", "Изменяйте только если знаете что делаете"),
        parent=content_parent,
        toggle_rows=[discord_restart_toggle, wssize_toggle, debug_log_toggle],
        action_rows=[blobs_card],
    )

    extra_card = setting_card_group_cls(
        tr_fn("page.winws1_control.section.additional", "Дополнительные действия"),
        content_parent,
    )
    test_card = build_push_setting_card_common(
        push_setting_card_cls=push_setting_card_cls,
        button_text=tr_fn("page.winws1_control.button.open", "Открыть"),
        icon=get_themed_qta_icon("fa5s.wifi", color="#60cdff"),
        title_text=tr_fn("page.winws1_control.button.connection_test", "Тест соединения"),
        content_text=tr_fn("page.winws1_control.button.connection_test.desc", "Проверить доступность сети и состояние обхода"),
        on_click=on_open_connection_test,
        parent=content_parent,
    )
    folder_card = build_push_setting_card_common(
        push_setting_card_cls=push_setting_card_cls,
        button_text=tr_fn("page.winws1_control.button.open", "Открыть"),
        icon=get_themed_qta_icon("fa5s.folder-open", color="#f5c04d"),
        title_text=tr_fn("page.winws1_control.button.open_folder", "Открыть папку"),
        content_text=tr_fn("page.winws1_control.button.open_folder.desc", "Перейти в папку программы и служебных файлов"),
        on_click=on_open_folder,
        parent=content_parent,
    )
    docs_card = build_push_setting_card_common(
        push_setting_card_cls=push_setting_card_cls,
        button_text=tr_fn("page.winws1_control.button.open", "Открыть"),
        icon=get_themed_qta_icon("fa5s.book", color="#8ab4f8"),
        title_text=tr_fn("page.winws1_control.button.documentation", "Документация"),
        content_text=tr_fn("page.winws1_control.button.documentation.desc", "Открыть справку и описание возможностей"),
        on_click=on_open_docs,
        parent=content_parent,
    )
    extra_card.addSettingCard(test_card)
    extra_card.addSettingCard(folder_card)
    extra_card.addSettingCard(docs_card)
    enable_setting_card_group_auto_height(extra_card)

    return Zapret1DeferredBuildWidgets(
        preset_setup_card=preset_setup_entry.card,
        preset_setup_open_btn=preset_setup_entry.button,
        program_settings_section_label=program_settings_section_label,
        program_settings_card=program_settings_card,
        auto_dpi_toggle=auto_dpi_toggle,
        defender_toggle=windows_feature_toggles.defender_toggle,
        max_block_toggle=windows_feature_toggles.max_block_toggle,
        advanced_card=advanced_card,
        advanced_notice=advanced_notice,
        discord_restart_toggle=discord_restart_toggle,
        wssize_toggle=wssize_toggle,
        debug_log_toggle=debug_log_toggle,
        blobs_action_card=blobs_card,
        blobs_open_btn=blobs_card.button,
        extra_card=extra_card,
        test_card=test_card,
        folder_card=folder_card,
        docs_card=docs_card,
    )
