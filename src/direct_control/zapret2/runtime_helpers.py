"""Runtime/helper слой для Zapret2 direct control page."""

from __future__ import annotations

from ui.text_catalog import tr as tr_catalog
from direct_control.zapret2.controller import Zapret2DirectControlPageController
from direct_control.ui.control_page_runtime_shared import (
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
    test_btn,
    folder_btn,
    docs_btn,
    current_preset_caption,
    direct_mode_caption,
    advanced_notice,
    program_settings_card,
    auto_dpi_toggle,
    defender_toggle,
    max_block_toggle,
    reset_program_card,
    reset_program_btn,
    reset_program_desc_label,
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
    if test_btn is not None:
        test_btn.setText(tr_catalog("page.z2_control.button.connection_test", language=language, default="Тест соединения"))
    if folder_btn is not None:
        folder_btn.setText(tr_catalog("page.z2_control.button.open_folder", language=language, default="Открыть папку"))
    if docs_btn is not None:
        docs_btn.setText(tr_catalog("page.z2_control.button.documentation", language=language, default="Документация"))

    current_preset_caption.setText(tr_catalog("page.z2_control.preset.current", language=language, default="Текущий активный пресет"))
    if direct_mode_caption is not None:
        direct_mode_caption.setText(tr_catalog("page.z2_control.direct_mode.caption", language=language, default="Режим прямого запуска"))
    if advanced_notice is not None:
        advanced_notice.setText(
            tr_catalog("page.z2_control.advanced.warning", language=language, default="Изменяйте только если знаете что делаете")
        )

    try:
        title_label = getattr(program_settings_card, "titleLabel", None)
        if title_label is not None:
            title_label.setText(
                tr_catalog("page.z2_control.section.program_settings", language=language, default="Настройки программы")
            )
    except Exception:
        pass

    try:
        if auto_dpi_toggle is not None:
            auto_dpi_toggle.set_texts(
                tr_catalog("page.z2_control.setting.autostart.title", language=language, default="Автозапуск DPI после старта программы"),
                tr_catalog("page.z2_control.setting.autostart.desc", language=language, default="После запуска ZapretGUI автоматически запускать текущий DPI-режим"),
            )
    except Exception:
        pass
    try:
        if defender_toggle is not None:
            defender_toggle.set_texts(
                tr_catalog("page.z2_control.setting.defender.title", language=language, default="Отключить Windows Defender"),
                tr_catalog("page.z2_control.setting.defender.desc", language=language, default="Требуются права администратора"),
            )
    except Exception:
        pass
    try:
        if max_block_toggle is not None:
            max_block_toggle.set_texts(
                tr_catalog("page.z2_control.setting.max_block.title", language=language, default="Блокировать установку MAX"),
                tr_catalog("page.z2_control.setting.max_block.desc", language=language, default="Блокирует запуск/установку MAX и домены в hosts"),
            )
    except Exception:
        pass
    try:
        if reset_program_card is not None and hasattr(reset_program_card, "setTitle"):
            reset_program_card.setTitle(
                tr_catalog("page.z2_control.setting.reset.title", language=language, default="Сбросить программу")
            )
            reset_program_card.setContent(
                tr_catalog("page.z2_control.setting.reset.desc", language=language, default="Очистить кэш проверок запуска (без удаления пресетов/настроек)")
            )
            button = getattr(reset_program_card, "button", None)
            if button is not None:
                button.setText(tr_catalog("page.z2_control.button.reset", language=language, default="Сбросить"))
        elif reset_program_btn is not None:
            reset_program_btn.setText(
                tr_catalog("page.z2_control.button.reset", language=language, default="Сбросить")
            )
            if reset_program_desc_label is not None:
                reset_program_desc_label.setText(
                    tr_catalog("page.z2_control.setting.reset.desc", language=language, default="Очистить кэш проверок запуска (без удаления пресетов/настроек)")
                )
    except Exception:
        pass
    try:
        if advanced_card is not None and hasattr(advanced_card, "set_title"):
            advanced_card.set_title(
                tr_catalog("page.z2_control.card.advanced", language=language, default="ДОПОЛНИТЕЛЬНЫЕ НАСТРОЙКИ")
            )
        title_label = getattr(advanced_card, "titleLabel", None)
        if title_label is not None:
            title_label.setText(tr_catalog("page.z2_control.card.advanced", language=language, default="ДОПОЛНИТЕЛЬНЫЕ НАСТРОЙКИ"))
    except Exception:
        pass
    if blobs_action_card is not None:
        blobs_action_card.title_label.setText(
            tr_catalog("page.z2_control.blobs.title", language=language, default="Блобы")
        )
        blobs_action_card.content_label.setText(
            tr_catalog("page.z2_control.blobs.desc", language=language, default="Бинарные данные (.bin / hex) для стратегий")
        )
        if blobs_open_btn is not None:
            blobs_open_btn.setText(tr_catalog("page.z2_control.button.open", language=language, default="Открыть"))

    update_stop_button_text()
    sync_direct_launch_mode_from_settings()

    try:
        if discord_restart_toggle is not None:
            discord_restart_toggle.set_texts(
                tr_catalog("page.dpi_settings.discord_restart.title", language=language, default="Перезапуск Discord"),
                tr_catalog("page.dpi_settings.discord_restart.desc", language=language, default="Автоперезапуск при смене стратегии"),
            )
    except Exception:
        pass
    try:
        if wssize_toggle is not None:
            wssize_toggle.set_texts(
                tr_catalog("page.dpi_settings.advanced.wssize.title", language=language, default="Включить --wssize"),
                tr_catalog("page.dpi_settings.advanced.wssize.desc", language=language, default="Добавляет параметр размера окна TCP"),
            )
    except Exception:
        pass
    try:
        if debug_log_toggle is not None:
            debug_log_toggle.set_texts(
                tr_catalog("page.dpi_settings.advanced.debug_log.title", language=language, default="Включить лог-файл (--debug)"),
                tr_catalog("page.dpi_settings.advanced.debug_log.desc", language=language, default="Записывает логи winws в папку logs"),
            )
    except Exception:
        pass
