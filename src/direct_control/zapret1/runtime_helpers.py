"""Runtime/helper слой для Zapret1 direct control page."""

from __future__ import annotations

from ui.text_catalog import tr as tr_catalog
from direct_control.control_runtime_controller import ControlPageController
from direct_control.ui.control_page_runtime_shared import (
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
    strategies_title_label,
    strategies_desc_label,
    program_settings_card,
    auto_dpi_toggle,
    test_action_card,
    test_btn,
    folder_action_card,
    folder_btn,
    docs_action_card,
    docs_btn,
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
    if strategies_title_label is not None:
        strategies_title_label.setText(
            tr_catalog("page.z1_control.strategies.title", language=language, default="Стратегии по категориям")
        )
    if strategies_desc_label is not None:
        strategies_desc_label.setText(
            tr_catalog("page.z1_control.strategies.desc", language=language, default="Выбор стратегии для YouTube, Discord и др.")
        )

    title_label = getattr(getattr(program_settings_card, "titleLabel", None), "setText", None)
    if title_label is not None:
        program_settings_card.titleLabel.setText(
            tr_catalog("page.z1_control.section.program_settings", language=language, default="Настройки программы")
        )
    if auto_dpi_toggle is not None:
        auto_dpi_toggle.set_texts(
            tr_catalog("page.z1_control.setting.autostart.title", language=language, default="Автозапуск DPI после старта программы"),
            tr_catalog("page.z1_control.setting.autostart.desc", language=language, default="После запуска ZapretGUI автоматически запускать текущий DPI-режим"),
        )

    try:
        if test_action_card is not None:
            test_action_card.title_label.setText(
                tr_catalog("page.z1_control.button.connection_test", language=language, default="Тест соединения")
            )
            test_action_card.content_label.setText(
                tr_catalog("page.z1_control.button.connection_test.desc", language=language, default="Проверить доступность сети и состояние обхода")
            )
            test_action_card.button.setText(
                tr_catalog("page.z1_control.button.open", language=language, default="Открыть")
            )
        elif test_btn is not None:
            test_btn.setText(tr_catalog("page.z1_control.button.connection_test", language=language, default="Тест соединения"))

        if folder_action_card is not None:
            folder_action_card.title_label.setText(
                tr_catalog("page.z1_control.button.open_folder", language=language, default="Открыть папку")
            )
            folder_action_card.content_label.setText(
                tr_catalog("page.z1_control.button.open_folder.desc", language=language, default="Перейти в папку программы и служебных файлов")
            )
            folder_action_card.button.setText(
                tr_catalog("page.z1_control.button.open", language=language, default="Открыть")
            )
        elif folder_btn is not None:
            folder_btn.setText(tr_catalog("page.z1_control.button.open_folder", language=language, default="Открыть папку"))

        if docs_action_card is not None:
            docs_action_card.title_label.setText(
                tr_catalog("page.z1_control.button.documentation", language=language, default="Документация")
            )
            docs_action_card.content_label.setText(
                tr_catalog("page.z1_control.button.documentation.desc", language=language, default="Открыть справку и описание возможностей")
            )
            docs_action_card.button.setText(
                tr_catalog("page.z1_control.button.open", language=language, default="Открыть")
            )
        elif docs_btn is not None:
            docs_btn.setText(tr_catalog("page.z1_control.button.documentation", language=language, default="Документация"))
    except Exception:
        pass

    try:
        if hasattr(advanced_card, "set_title"):
            advanced_card.set_title(
                tr_catalog("page.z1_control.card.advanced", language=language, default="ДОПОЛНИТЕЛЬНЫЕ НАСТРОЙКИ")
            )
        title_label = getattr(advanced_card, "titleLabel", None)
        if title_label is not None:
            title_label.setText(
                tr_catalog("page.z1_control.card.advanced", language=language, default="ДОПОЛНИТЕЛЬНЫЕ НАСТРОЙКИ")
            )
    except Exception:
        pass

    try:
        advanced_notice.setText(
            tr_catalog("page.z1_control.advanced.warning", language=language, default="Изменяйте только если знаете что делаете")
        )
    except Exception:
        pass
    try:
        discord_restart_toggle.set_texts(
            tr_catalog("page.z1_control.advanced.discord_restart.title", language=language, default="Перезапуск Discord"),
            tr_catalog("page.z1_control.advanced.discord_restart.desc", language=language, default="Автоперезапуск при смене стратегии"),
        )
    except Exception:
        pass
    try:
        wssize_toggle.set_texts(
            tr_catalog("page.z1_control.advanced.wssize.title", language=language, default="Включить --wssize"),
            tr_catalog("page.z1_control.advanced.wssize.desc", language=language, default="Добавляет параметр размера окна TCP"),
        )
    except Exception:
        pass
    try:
        debug_log_toggle.set_texts(
            tr_catalog("page.z1_control.advanced.debug_log.title", language=language, default="Включить лог-файл (--debug)"),
            tr_catalog("page.z1_control.advanced.debug_log.desc", language=language, default="Записывает логи winws в папку logs"),
        )
    except Exception:
        pass
    if blobs_action_card is not None:
        blobs_action_card.title_label.setText(
            tr_catalog("page.z1_control.blobs.title", language=language, default="Блобы")
        )
        blobs_action_card.content_label.setText(
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
