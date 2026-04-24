"""Runtime/helper слой для Zapret1 direct control page."""

from __future__ import annotations

from ui.text_catalog import tr as tr_catalog
from direct_preset.ui.control.control_runtime_controller import ControlPageController
from direct_preset.ui.control.control_page_runtime_shared import (
    apply_program_settings_toggles,
    apply_status_plan as apply_status_plan_shared,
    set_toggle_checked,
)


def apply_program_settings_snapshot(snapshot, *, auto_dpi_toggle) -> None:
    apply_program_settings_toggles(
        snapshot,
        auto_dpi_toggle=auto_dpi_toggle,
    )


def apply_status_plan(plan, *, status_title, status_desc, status_dot, start_btn, stop_winws_btn, stop_and_exit_btn) -> None:
    apply_status_plan_shared(
        plan,
        status_title=status_title,
        status_desc=status_desc,
        status_dot=status_dot,
        start_btn=start_btn,
        stop_winws_btn=stop_winws_btn,
        stop_and_exit_btn=stop_and_exit_btn,
        update_stop_button_text=lambda: None,
    )


def apply_z1_direct_language(
    *,
    language: str,
    start_btn,
    stop_winws_btn,
    stop_and_exit_btn,
    presets_btn,
    open_strat_btn,
    preset_caption_label,
    strategies_card,
    program_settings_card,
    auto_dpi_toggle,
    test_card,
    folder_card,
    docs_card,
    advanced_card,
    advanced_notice,
    discord_restart_toggle,
    wssize_toggle,
    debug_log_toggle,
    blobs_action_card,
    blobs_open_btn,
    refresh_preset_name,
    get_current_dpi_runtime_state,
    update_status,
) -> None:
    start_btn.setText(tr_catalog("page.z1_control.button.start", language=language, default="Запустить Zapret"))
    stop_winws_btn.setText(tr_catalog("page.z1_control.button.stop_winws", language=language, default="Остановить winws.exe"))
    stop_and_exit_btn.setText(tr_catalog("page.z1_control.button.stop_and_exit", language=language, default="Остановить и закрыть"))
    presets_btn.setText(tr_catalog("page.z1_control.button.my_presets", language=language, default="Мои пресеты"))
    if open_strat_btn is not None:
        open_strat_btn.setText(tr_catalog("page.z1_control.button.open", language=language, default="Открыть"))

    if preset_caption_label is not None:
        preset_caption_label.setText(
            tr_catalog("page.z1_control.preset.current", language=language, default="Текущий активный пресет")
        )
    if strategies_card is not None:
        strategies_card.setTitle(
            tr_catalog("page.z1_control.strategies.title", language=language, default="Стратегии по категориям")
        )
        strategies_card.setContent(
            tr_catalog("page.z1_control.strategies.desc", language=language, default="Выбор стратегии для YouTube, Discord и др.")
        )
        strategies_card.button.setText(
            tr_catalog("page.z1_control.button.open", language=language, default="Открыть")
        )

    program_settings_card.titleLabel.setText(
        tr_catalog("page.z1_control.section.program_settings", language=language, default="Настройки программы")
    )
    if auto_dpi_toggle is not None:
        auto_dpi_toggle.set_texts(
            tr_catalog("page.z1_control.setting.autostart.title", language=language, default="Автозапуск DPI после старта программы"),
            tr_catalog("page.z1_control.setting.autostart.desc", language=language, default="После запуска ZapretGUI автоматически запускать текущий DPI-режим"),
        )

    test_card.setTitle(
        tr_catalog("page.z1_control.button.connection_test", language=language, default="Тест соединения")
    )
    test_card.setContent(
        tr_catalog("page.z1_control.button.connection_test.desc", language=language, default="Проверить доступность сети и состояние обхода")
    )
    test_card.button.setText(
        tr_catalog("page.z1_control.button.open", language=language, default="Открыть")
    )

    folder_card.setTitle(
        tr_catalog("page.z1_control.button.open_folder", language=language, default="Открыть папку")
    )
    folder_card.setContent(
        tr_catalog("page.z1_control.button.open_folder.desc", language=language, default="Перейти в папку программы и служебных файлов")
    )
    folder_card.button.setText(
        tr_catalog("page.z1_control.button.open", language=language, default="Открыть")
    )

    docs_card.setTitle(
        tr_catalog("page.z1_control.button.documentation", language=language, default="Документация")
    )
    docs_card.setContent(
        tr_catalog("page.z1_control.button.documentation.desc", language=language, default="Открыть справку и описание возможностей")
    )
    docs_card.button.setText(
        tr_catalog("page.z1_control.button.open", language=language, default="Открыть")
    )

    advanced_card.titleLabel.setText(
        tr_catalog("page.z1_control.card.advanced", language=language, default="Дополнительные настройки")
    )
    advanced_notice.setText(
        tr_catalog("page.z1_control.advanced.warning", language=language, default="Изменяйте только если знаете что делаете")
    )
    discord_restart_toggle.set_texts(
        tr_catalog("page.z1_control.advanced.discord_restart.title", language=language, default="Перезапуск Discord"),
        tr_catalog("page.z1_control.advanced.discord_restart.desc", language=language, default="Автоперезапуск при смене стратегии"),
    )
    wssize_toggle.set_texts(
        tr_catalog("page.z1_control.advanced.wssize.title", language=language, default="Включить --wssize"),
        tr_catalog("page.z1_control.advanced.wssize.desc", language=language, default="Добавляет параметр размера окна TCP"),
    )
    debug_log_toggle.set_texts(
        tr_catalog("page.z1_control.advanced.debug_log.title", language=language, default="Включить лог-файл (--debug)"),
        tr_catalog("page.z1_control.advanced.debug_log.desc", language=language, default="Записывает логи winws в папку logs"),
    )
    if blobs_action_card is not None:
        blobs_action_card.setTitle(
            tr_catalog("page.z1_control.blobs.title", language=language, default="Блобы")
        )
        blobs_action_card.setContent(
            tr_catalog("page.z1_control.blobs.desc", language=language, default="Бинарные данные (.bin / hex) для стратегий")
        )
        if blobs_open_btn is not None:
            blobs_open_btn.setText(tr_catalog("page.z1_control.button.open", language=language, default="Открыть"))

    refresh_preset_name()
    phase, last_error = get_current_dpi_runtime_state()
    update_status(phase, last_error)


def show_simple_infobar_result(*, ok: bool, message: str, window, info_bar_cls) -> None:
    if ok:
        return
    info_bar_cls.warning(title="Ошибка", content=f"Не удалось очистить кэш: {message}", parent=window)
