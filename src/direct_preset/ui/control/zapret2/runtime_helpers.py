"""Runtime/helper слой для Zapret2 direct control page."""

from __future__ import annotations

from ui.text_catalog import tr as tr_catalog
from direct_preset.ui.control.zapret2.controller import Zapret2DirectControlPageController
from direct_preset.ui.control.control_page_runtime_shared import (
    apply_program_settings_toggles,
    apply_status_plan as apply_status_plan_shared,
    run_confirmation_dialog,
    set_toggle_checked,
    show_action_result_plan,
)


def apply_program_settings_snapshot(snapshot, *, auto_dpi_toggle, defender_toggle, max_block_toggle) -> None:
    apply_program_settings_toggles(
        snapshot,
        auto_dpi_toggle=auto_dpi_toggle,
        defender_toggle=defender_toggle,
        max_block_toggle=max_block_toggle,
    )


def apply_advanced_settings_plan(plan, *, discord_restart_toggle, wssize_toggle, debug_log_toggle) -> None:
    try:
        toggle = discord_restart_toggle
        set_checked = getattr(toggle, "setChecked", None)
        if callable(set_checked):
            set_checked(bool(plan.discord_restart), block_signals=True)
    except Exception:
        pass

    try:
        toggle = wssize_toggle
        set_checked = getattr(toggle, "setChecked", None)
        if callable(set_checked):
            set_checked(bool(plan.wssize_enabled), block_signals=True)
    except Exception:
        pass

    try:
        toggle = debug_log_toggle
        set_checked = getattr(toggle, "setChecked", None)
        if callable(set_checked):
            set_checked(bool(plan.debug_log_enabled), block_signals=True)
    except Exception:
        pass


def sync_direct_mode_label(*, language: str, direct_mode_label) -> None:
    if direct_mode_label is None:
        return
    plan = Zapret2DirectControlPageController.build_direct_mode_label_plan(language=language)
    direct_mode_label.setText(plan.label_text)


def apply_status_plan(plan, *, status_title, status_desc, status_dot, start_btn, stop_winws_btn, stop_and_exit_btn, update_stop_button_text) -> None:
    apply_status_plan_shared(
        plan,
        status_title=status_title,
        status_desc=status_desc,
        status_dot=status_dot,
        start_btn=start_btn,
        stop_winws_btn=stop_winws_btn,
        stop_and_exit_btn=stop_and_exit_btn,
        update_stop_button_text=update_stop_button_text,
    )


def apply_direct_language(
    *,
    language: str,
    start_btn,
    stop_and_exit_btn,
    presets_btn,
    direct_open_btn,
    direct_mode_btn,
    blobs_open_btn,
    test_card,
    folder_card,
    docs_card,
    current_preset_caption,
    direct_mode_caption,
    advanced_notice,
    program_settings_card,
    auto_dpi_toggle,
    defender_toggle,
    max_block_toggle,
    advanced_card,
    blobs_action_card,
    discord_restart_toggle,
    wssize_toggle,
    debug_log_toggle,
    update_stop_button_text,
    sync_direct_launch_mode_from_settings,
) -> None:
    start_btn.setText(tr_catalog("page.z2_control.button.start", language=language, default="Запустить Zapret"))
    stop_and_exit_btn.setText(tr_catalog("page.z2_control.button.stop_and_exit", language=language, default="Остановить и закрыть программу"))
    presets_btn.setText(tr_catalog("page.z2_control.button.my_presets", language=language, default="Мои пресеты"))
    if direct_open_btn is not None:
        direct_open_btn.setText(tr_catalog("page.z2_control.button.open", language=language, default="Открыть"))
    if direct_mode_btn is not None:
        direct_mode_btn.setText(tr_catalog("page.z2_control.button.change_mode", language=language, default="Изменить режим"))
    if blobs_open_btn is not None:
        blobs_open_btn.setText(tr_catalog("page.z2_control.button.open", language=language, default="Открыть"))

    current_preset_caption.setText(tr_catalog("page.z2_control.preset.current", language=language, default="Текущий активный пресет"))
    if direct_mode_caption is not None:
        direct_mode_caption.setText(tr_catalog("page.z2_control.direct_mode.caption", language=language, default="Режим прямого запуска"))
    if advanced_notice is not None:
        advanced_notice.setText(
            tr_catalog("page.z2_control.advanced.warning", language=language, default="Изменяйте только если знаете что делаете")
        )

    program_settings_card.titleLabel.setText(
        tr_catalog("page.z2_control.section.program_settings", language=language, default="Настройки программы")
    )

    auto_dpi_toggle.set_texts(
        tr_catalog("page.z2_control.setting.autostart.title", language=language, default="Автозапуск DPI после старта программы"),
        tr_catalog("page.z2_control.setting.autostart.desc", language=language, default="После запуска ZapretGUI автоматически запускать текущий DPI-режим"),
    )
    defender_toggle.set_texts(
        tr_catalog("page.z2_control.setting.defender.title", language=language, default="Отключить Windows Defender"),
        tr_catalog("page.z2_control.setting.defender.desc", language=language, default="Требуются права администратора"),
    )
    max_block_toggle.set_texts(
        tr_catalog("page.z2_control.setting.max_block.title", language=language, default="Блокировать установку MAX"),
        tr_catalog("page.z2_control.setting.max_block.desc", language=language, default="Блокирует запуск/установку MAX и домены в hosts"),
    )
    advanced_card.titleLabel.setText(
        tr_catalog("page.z2_control.card.advanced", language=language, default="Дополнительные настройки")
    )
    if blobs_action_card is not None:
        blobs_action_card.setTitle(
            tr_catalog("page.z2_control.blobs.title", language=language, default="Блобы")
        )
        blobs_action_card.setContent(
            tr_catalog("page.z2_control.blobs.desc", language=language, default="Бинарные данные (.bin / hex) для стратегий")
        )
        if blobs_open_btn is not None:
            blobs_open_btn.setText(tr_catalog("page.z2_control.button.open", language=language, default="Открыть"))

    test_card.setTitle(
        tr_catalog("page.z2_control.button.connection_test", language=language, default="Тест соединения")
    )
    test_card.setContent(
        tr_catalog("page.z2_control.button.connection_test.desc", language=language, default="Проверить доступность сети и состояние обхода")
    )
    test_card.button.setText(
        tr_catalog("page.z2_control.button.open", language=language, default="Открыть")
    )
    folder_card.setTitle(
        tr_catalog("page.z2_control.button.open_folder", language=language, default="Открыть папку")
    )
    folder_card.setContent(
        tr_catalog("page.z2_control.button.open_folder.desc", language=language, default="Перейти в папку программы и служебных файлов")
    )
    folder_card.button.setText(
        tr_catalog("page.z2_control.button.open", language=language, default="Открыть")
    )
    docs_card.setTitle(
        tr_catalog("page.z2_control.button.documentation", language=language, default="Документация")
    )
    docs_card.setContent(
        tr_catalog("page.z2_control.button.documentation.desc", language=language, default="Открыть справку и описание возможностей")
    )
    docs_card.button.setText(
        tr_catalog("page.z2_control.button.open", language=language, default="Открыть")
    )

    update_stop_button_text()
    sync_direct_launch_mode_from_settings()

    discord_restart_toggle.set_texts(
        tr_catalog("page.dpi_settings.discord_restart.title", language=language, default="Перезапуск Discord"),
        tr_catalog("page.dpi_settings.discord_restart.desc", language=language, default="Автоперезапуск при смене стратегии"),
    )
    wssize_toggle.set_texts(
        tr_catalog("page.dpi_settings.advanced.wssize.title", language=language, default="Включить --wssize"),
        tr_catalog("page.dpi_settings.advanced.wssize.desc", language=language, default="Добавляет параметр размера окна TCP"),
    )
    debug_log_toggle.set_texts(
        tr_catalog("page.dpi_settings.advanced.debug_log.title", language=language, default="Включить лог-файл (--debug)"),
        tr_catalog("page.dpi_settings.advanced.debug_log.desc", language=language, default="Записывает логи winws в папку logs"),
    )
