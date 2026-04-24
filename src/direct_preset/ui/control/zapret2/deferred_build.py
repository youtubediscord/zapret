"""Build-helper deferred-секций для Zapret2DirectControlPage."""

from __future__ import annotations

from dataclasses import dataclass

from direct_preset.ui.control.shared_builders import (
    build_push_setting_card_common,
)
from ui.compat_widgets import build_advanced_settings_section, enable_setting_card_group_auto_height
from ui.theme import get_cached_qta_pixmap, get_theme_tokens, get_themed_qta_icon


@dataclass(slots=True)
class Zapret2DeferredBuildWidgets:
    direct_section_label: object
    direct_card: object
    direct_open_btn: object
    direct_mode_btn: object
    direct_mode_label: object
    direct_mode_caption: object
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
    blobs_action_card: object
    blobs_open_btn: object
    extra_section_label: object | None
    extra_card: object
    test_card: object
    folder_card: object
    docs_card: object


def build_z2_direct_deferred_sections(
    *,
    add_section_title,
    tr_fn,
    content_parent,
    setting_card_group_cls,
    push_setting_card_cls,
    win11_toggle_row_cls,
    on_open_direct_launch_page,
    on_open_direct_mode_dialog,
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
) -> Zapret2DeferredBuildWidgets:
    direct_section_label = add_section_title(
        return_widget=True,
        text_key="page.z2_control.section.direct_tuning",
    )

    direct_card = setting_card_group_cls(
        tr_fn("page.z2_control.section.direct_tuning", "Прямой запуск"),
        content_parent,
    )
    direct_open_card = build_push_setting_card_common(
        push_setting_card_cls=push_setting_card_cls,
        button_text=tr_fn("page.z2_control.button.open", "Открыть"),
        icon=get_cached_qta_pixmap("fa5s.play", color="#60cdff", size=20),
        title_text=tr_fn("page.z2_control.direct_mode.card.title", "Открыть прямой запуск"),
        content_text=tr_fn("page.z2_control.direct_mode.card.desc", "Перейти к настройке target'ов и стратегий"),
        on_click=on_open_direct_launch_page,
        parent=content_parent,
    )
    direct_mode_card = build_push_setting_card_common(
        push_setting_card_cls=push_setting_card_cls,
        button_text=tr_fn("page.z2_control.button.change_mode", "Изменить режим"),
        icon=get_cached_qta_pixmap("fa5s.sliders-h", color="#8ab4f8", size=20),
        title_text=tr_fn("page.z2_control.mode.basic", "Basic"),
        content_text=tr_fn("page.z2_control.direct_mode.caption", "Режим прямого запуска"),
        on_click=on_open_direct_mode_dialog,
        parent=content_parent,
    )
    direct_card.addSettingCard(direct_open_card)
    direct_card.addSettingCard(direct_mode_card)

    program_settings_title = tr_fn("page.z2_control.section.program_settings", "Настройки программы")
    program_settings_section_label = None
    program_settings_card = setting_card_group_cls(program_settings_title, content_parent)

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

    program_settings_card.addSettingCard(auto_dpi_toggle)
    program_settings_card.addSettingCard(defender_toggle)
    program_settings_card.addSettingCard(max_block_toggle)

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

    blobs_card = build_push_setting_card_common(
        push_setting_card_cls=push_setting_card_cls,
        button_text=tr_fn("page.z2_control.button.open", "Открыть"),
        icon=get_themed_qta_icon("fa5s.file-archive", color=get_theme_tokens().accent_hex),
        title_text=tr_fn("page.z2_control.blobs.title", "Блобы"),
        content_text=tr_fn("page.z2_control.blobs.desc", "Бинарные данные (.bin / hex) для стратегий"),
        on_click=on_navigate_to_blobs,
        parent=content_parent,
    )

    advanced_card, advanced_notice = build_advanced_settings_section(
        title=tr_fn("page.z2_control.card.advanced", "Дополнительные настройки"),
        warning_text=tr_fn("page.z2_control.advanced.warning", "Изменяйте только если знаете что делаете"),
        parent=content_parent,
        toggle_rows=[discord_restart_toggle, wssize_toggle, debug_log_toggle],
        action_rows=[blobs_card],
    )

    extra_section_label = None
    extra_card = setting_card_group_cls(
        tr_fn("page.z2_control.section.additional", "Дополнительные действия"),
        content_parent,
    )
    test_card = build_push_setting_card_common(
        push_setting_card_cls=push_setting_card_cls,
        button_text=tr_fn("page.z2_control.button.open", "Открыть"),
        icon=get_themed_qta_icon("fa5s.wifi", color="#60cdff"),
        title_text=tr_fn("page.z2_control.button.connection_test", "Тест соединения"),
        content_text=tr_fn("page.z2_control.button.connection_test.desc", "Проверить доступность сети и состояние обхода"),
        on_click=on_open_connection_test,
        parent=content_parent,
    )
    folder_card = build_push_setting_card_common(
        push_setting_card_cls=push_setting_card_cls,
        button_text=tr_fn("page.z2_control.button.open", "Открыть"),
        icon=get_themed_qta_icon("fa5s.folder-open", color="#f5c04d"),
        title_text=tr_fn("page.z2_control.button.open_folder", "Открыть папку"),
        content_text=tr_fn("page.z2_control.button.open_folder.desc", "Перейти в папку программы и служебных файлов"),
        on_click=on_open_folder,
        parent=content_parent,
    )
    docs_card = build_push_setting_card_common(
        push_setting_card_cls=push_setting_card_cls,
        button_text=tr_fn("page.z2_control.button.open", "Открыть"),
        icon=get_themed_qta_icon("fa5s.book", color="#8ab4f8"),
        title_text=tr_fn("page.z2_control.button.documentation", "Документация"),
        content_text=tr_fn("page.z2_control.button.documentation.desc", "Открыть справку и описание возможностей"),
        on_click=on_open_docs,
        parent=content_parent,
    )
    extra_card.addSettingCard(test_card)
    extra_card.addSettingCard(folder_card)
    extra_card.addSettingCard(docs_card)
    enable_setting_card_group_auto_height(extra_card)

    return Zapret2DeferredBuildWidgets(
        direct_section_label=direct_section_label,
        direct_card=direct_card,
        direct_open_btn=direct_open_card.button,
        direct_mode_btn=direct_mode_card.button,
        direct_mode_label=direct_mode_card.titleLabel,
        direct_mode_caption=direct_mode_card.contentLabel,
        program_settings_section_label=program_settings_section_label,
        program_settings_card=program_settings_card,
        auto_dpi_toggle=auto_dpi_toggle,
        defender_toggle=defender_toggle,
        max_block_toggle=max_block_toggle,
        advanced_card=advanced_card,
        advanced_notice=advanced_notice,
        discord_restart_toggle=discord_restart_toggle,
        wssize_toggle=wssize_toggle,
        debug_log_toggle=debug_log_toggle,
        blobs_action_card=blobs_card,
        blobs_open_btn=blobs_card.button,
        extra_section_label=extra_section_label,
        extra_card=extra_card,
        test_card=test_card,
        folder_card=folder_card,
        docs_card=docs_card,
    )
