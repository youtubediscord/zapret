"""Build-helper основных секций для Zapret1ModeControlPage."""

from __future__ import annotations

from dataclasses import dataclass

from presets.ui.control.shared_builders import build_deferred_themed_push_setting_card_common
from presets.ui.control.windows_features.build import build_state_media_block_toggle, build_windows_feature_toggles
from ui.fluent_widgets import build_additional_settings_section, enable_setting_card_group_auto_height


@dataclass(slots=True)
class Zapret1SettingsBuildWidgets:
    program_settings_section_label: object | None
    program_settings_card: object
    gui_autostart_toggle: object
    auto_dpi_toggle: object
    tray_close_mode_combo: object
    defender_toggle: object
    max_block_toggle: object
    additional_settings_card: object
    additional_settings_notice: object
    discord_restart_toggle: object | None
    wssize_toggle: object | None
    debug_log_toggle: object | None
    extra_card: object
    test_card: object
    internet_cleanup_card: object
    folder_card: object
    docs_card: object
    state_media_block_toggle: object


def build_winws1_pages_settings_sections(
    *,
    add_section_title,
    tr_fn,
    content_parent,
    push_setting_card_cls,
    setting_card_group_cls,
    win11_toggle_row_cls,
    win11_combo_row_cls,
    on_gui_autostart_toggled,
    on_auto_dpi_toggled,
    on_tray_close_mode_changed,
    on_defender_toggled,
    on_max_blocker_toggled,
    on_state_media_block_toggled,
    on_discord_restart_changed,
    on_wssize_toggled,
    on_debug_log_toggled,
    on_open_connection_test,
    on_open_internet_cleanup,
    on_open_folder,
    on_open_docs,
) -> Zapret1SettingsBuildWidgets:
    program_settings_title = tr_fn("page.winws1_control.section.program_settings", "Настройки программы")
    program_settings_section_label = None
    program_settings_card = setting_card_group_cls(program_settings_title, content_parent)

    gui_autostart_toggle = win11_toggle_row_cls(
        "fa5s.power-off",
        tr_fn("page.control.setting.gui_autostart.title", "Автозапуск ZapretGUI"),
        tr_fn("page.control.setting.gui_autostart.desc", "Запускать программу в трее при входе в Windows"),
    )
    gui_autostart_toggle.toggled.connect(on_gui_autostart_toggled)

    auto_dpi_toggle = win11_toggle_row_cls(
        "fa5s.bolt",
        tr_fn("page.winws1_control.setting.autostart.title", "Автозапуск DPI после старта программы"),
        tr_fn("page.winws1_control.setting.autostart.desc", "После запуска ZapretGUI автоматически запускать текущий DPI-режим"),
    )
    auto_dpi_toggle.toggled.connect(on_auto_dpi_toggled)

    tray_close_mode_combo = win11_combo_row_cls(
        "fa5s.window-minimize",
        tr_fn("page.control.setting.tray_close_mode.title", "Поведение окна и трея"),
        tr_fn("page.control.setting.tray_close_mode.desc", "Выберите, когда ZapretGUI будет скрывать окно в системный трей"),
        items=[
            ("Свернуть и крестик скрывают в трей", "minimize_and_close"),
            ("Только свернуть скрывает в трей", "minimize_only"),
            ("Не скрывать в трей", "normal"),
        ],
    )
    tray_close_mode_combo.combo.setFixedWidth(270)
    tray_close_mode_combo.combo.currentIndexChanged.connect(
        lambda _index: on_tray_close_mode_changed(tray_close_mode_combo.currentData())
    )

    windows_feature_toggles = build_windows_feature_toggles(
        tr_fn=tr_fn,
        win11_toggle_row_cls=win11_toggle_row_cls,
        on_defender_toggled=on_defender_toggled,
        on_max_blocker_toggled=on_max_blocker_toggled,
    )

    program_settings_card.addSettingCard(gui_autostart_toggle)
    program_settings_card.addSettingCard(auto_dpi_toggle)
    program_settings_card.addSettingCard(tray_close_mode_combo)
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

    additional_settings_card, additional_settings_notice = build_additional_settings_section(
        title=tr_fn("page.winws1_control.card.advanced", "Дополнительные настройки"),
        warning_text=tr_fn("page.winws1_control.advanced.warning", "Изменяйте только если знаете что делаете"),
        parent=content_parent,
        toggle_rows=[discord_restart_toggle, wssize_toggle, debug_log_toggle],
        action_rows=[],
    )

    extra_card = setting_card_group_cls(
        tr_fn("page.winws1_control.section.additional", "Дополнительные действия"),
        content_parent,
    )
    test_card = build_deferred_themed_push_setting_card_common(
        push_setting_card_cls=push_setting_card_cls,
        button_text=tr_fn("page.winws1_control.button.open", "Открыть"),
        icon_name="fa5s.wifi",
        icon_color="#60cdff",
        title_text=tr_fn("page.winws1_control.button.connection_test", "Тест соединения"),
        content_text=tr_fn("page.winws1_control.button.connection_test.desc", "Проверить доступность сети и состояние обхода"),
        on_click=on_open_connection_test,
        button_accessible_name=tr_fn("page.winws1_control.button.connection_test.accessible_name", "Открыть тест соединения"),
        parent=content_parent,
    )
    internet_cleanup_card = build_deferred_themed_push_setting_card_common(
        push_setting_card_cls=push_setting_card_cls,
        button_text=tr_fn("page.control.internet_cleanup.button", "Сбросить"),
        icon_name="fa5s.network-wired",
        icon_color="#4cc38a",
        title_text=tr_fn("page.control.internet_cleanup.title", "Сбросить сеть Windows"),
        content_text=tr_fn(
            "page.control.internet_cleanup.desc",
            "Очистить DNS, proxy, Winsock и сетевые параметры. Может понадобиться перезагрузка",
        ),
        on_click=on_open_internet_cleanup,
        button_accessible_name=tr_fn("page.control.internet_cleanup.accessible_name", "Сбросить сеть Windows"),
        parent=content_parent,
    )
    folder_card = build_deferred_themed_push_setting_card_common(
        push_setting_card_cls=push_setting_card_cls,
        button_text=tr_fn("page.winws1_control.button.open", "Открыть"),
        icon_name="fa5s.folder-open",
        icon_color="#f5c04d",
        title_text=tr_fn("page.winws1_control.button.open_folder", "Открыть папку"),
        content_text=tr_fn("page.winws1_control.button.open_folder.desc", "Перейти в папку программы и служебных файлов"),
        on_click=on_open_folder,
        button_accessible_name=tr_fn("page.winws1_control.button.open_folder.accessible_name", "Открыть папку программы"),
        parent=content_parent,
    )
    docs_card = build_deferred_themed_push_setting_card_common(
        push_setting_card_cls=push_setting_card_cls,
        button_text=tr_fn("page.winws1_control.button.open", "Открыть"),
        icon_name="fa5s.book",
        icon_color="#8ab4f8",
        title_text=tr_fn("page.winws1_control.button.documentation", "Документация"),
        content_text=tr_fn("page.winws1_control.button.documentation.desc", "Открыть справку и описание возможностей"),
        on_click=on_open_docs,
        button_accessible_name=tr_fn("page.winws1_control.button.documentation.accessible_name", "Открыть документацию"),
        parent=content_parent,
    )
    state_media_block_toggle = build_state_media_block_toggle(
        tr_fn=tr_fn,
        win11_toggle_row_cls=win11_toggle_row_cls,
        on_state_media_block_toggled=on_state_media_block_toggled,
    )
    extra_card.addSettingCard(test_card)
    extra_card.addSettingCard(internet_cleanup_card)
    extra_card.addSettingCard(folder_card)
    extra_card.addSettingCard(docs_card)
    extra_card.addSettingCard(state_media_block_toggle)
    enable_setting_card_group_auto_height(extra_card)

    return Zapret1SettingsBuildWidgets(
        program_settings_section_label=program_settings_section_label,
        program_settings_card=program_settings_card,
        gui_autostart_toggle=gui_autostart_toggle,
        auto_dpi_toggle=auto_dpi_toggle,
        tray_close_mode_combo=tray_close_mode_combo,
        defender_toggle=windows_feature_toggles.defender_toggle,
        max_block_toggle=windows_feature_toggles.max_block_toggle,
        additional_settings_card=additional_settings_card,
        additional_settings_notice=additional_settings_notice,
        discord_restart_toggle=discord_restart_toggle,
        wssize_toggle=wssize_toggle,
        debug_log_toggle=debug_log_toggle,
        extra_card=extra_card,
        test_card=test_card,
        internet_cleanup_card=internet_cleanup_card,
        folder_card=folder_card,
        docs_card=docs_card,
        state_media_block_toggle=state_media_block_toggle,
    )
