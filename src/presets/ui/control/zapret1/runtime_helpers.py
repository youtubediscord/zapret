"""Runtime/helper слой для Zapret1 mode control page."""

from __future__ import annotations

from settings.mode import EXE_NAME_WINWS1, ZAPRET1_MODE
from app.text_catalog import tr as tr_catalog
import presets.ui.control.control_runtime as control_runtime
from presets.ui.control.control_page_runtime_shared import (
    apply_program_settings_toggles,
    apply_status_plan as apply_status_plan_shared,
    set_toggle_checked,
)


def apply_program_settings_snapshot(snapshot, *, auto_dpi_toggle, defender_toggle=None, max_block_toggle=None) -> None:
    apply_program_settings_toggles(
        snapshot,
        auto_dpi_toggle=auto_dpi_toggle,
        defender_toggle=defender_toggle,
        max_block_toggle=max_block_toggle,
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


def apply_winws1_pages_language(
    *,
    language: str,
    start_btn,
    stop_winws_btn,
    stop_and_exit_btn,
    presets_btn,
    preset_setup_open_btn,
    preset_caption_label,
    preset_setup_card,
    program_settings_card,
    auto_dpi_toggle,
    defender_toggle,
    max_block_toggle,
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
    start_btn.setText(tr_catalog("page.winws1_control.button.start", language=language, default="Запустить Zapret"))
    stop_winws_btn.setText(tr_catalog("page.winws1_control.button.stop_winws", language=language, default=f"Остановить {EXE_NAME_WINWS1}"))
    stop_and_exit_btn.setText(tr_catalog("page.winws1_control.button.stop_and_exit", language=language, default="Остановить и закрыть"))
    presets_btn.setText(tr_catalog("page.winws1_control.button.my_presets", language=language, default="Мои пресеты"))
    if preset_setup_open_btn is not None:
        preset_setup_open_btn.setText(tr_catalog("page.winws1_control.button.open", language=language, default="Открыть"))

    if preset_caption_label is not None:
        preset_caption_label.setText(
            tr_catalog("page.winws1_control.preset.current", language=language, default="Текущий активный пресет")
        )
    if preset_setup_card is not None:
        preset_setup_card.setTitle(
            tr_catalog("page.winws1_control.profiles.title", language=language, default="Настройка пресета")
        )
        preset_setup_card.setContent(
            tr_catalog("page.winws1_control.profiles.desc", language=language, default="Открыть профили выбранного пресета и выбрать готовые стратегии")
        )
        preset_setup_card.button.setText(
            tr_catalog("page.winws1_control.button.open", language=language, default="Открыть")
        )

    program_settings_card.titleLabel.setText(
        tr_catalog("page.winws1_control.section.program_settings", language=language, default="Настройки программы")
    )
    if auto_dpi_toggle is not None:
        auto_dpi_toggle.set_texts(
            tr_catalog("page.winws1_control.setting.autostart.title", language=language, default="Автозапуск DPI после старта программы"),
            tr_catalog("page.winws1_control.setting.autostart.desc", language=language, default="После запуска ZapretGUI автоматически запускать текущий DPI-режим"),
        )
    if defender_toggle is not None:
        defender_toggle.set_texts(
            tr_catalog("page.control.setting.defender.title", language=language, default="Отключить Windows Defender"),
            tr_catalog("page.control.setting.defender.desc", language=language, default="Требуются права администратора"),
        )
    if max_block_toggle is not None:
        max_block_toggle.set_texts(
            tr_catalog("page.control.setting.max_block.title", language=language, default="Блокировать установку MAX"),
            tr_catalog("page.control.setting.max_block.desc", language=language, default="Блокирует запуск/установку MAX и домены в hosts"),
        )

    test_card.setTitle(
        tr_catalog("page.winws1_control.button.connection_test", language=language, default="Тест соединения")
    )
    test_card.setContent(
        tr_catalog("page.winws1_control.button.connection_test.desc", language=language, default="Проверить доступность сети и состояние обхода")
    )
    test_card.button.setText(
        tr_catalog("page.winws1_control.button.open", language=language, default="Открыть")
    )

    folder_card.setTitle(
        tr_catalog("page.winws1_control.button.open_folder", language=language, default="Открыть папку")
    )
    folder_card.setContent(
        tr_catalog("page.winws1_control.button.open_folder.desc", language=language, default="Перейти в папку программы и служебных файлов")
    )
    folder_card.button.setText(
        tr_catalog("page.winws1_control.button.open", language=language, default="Открыть")
    )

    docs_card.setTitle(
        tr_catalog("page.winws1_control.button.documentation", language=language, default="Документация")
    )
    docs_card.setContent(
        tr_catalog("page.winws1_control.button.documentation.desc", language=language, default="Открыть справку и описание возможностей")
    )
    docs_card.button.setText(
        tr_catalog("page.winws1_control.button.open", language=language, default="Открыть")
    )

    advanced_card.titleLabel.setText(
        tr_catalog("page.winws1_control.card.advanced", language=language, default="Дополнительные настройки")
    )
    advanced_notice.setText(
        tr_catalog("page.winws1_control.advanced.warning", language=language, default="Изменяйте только если знаете что делаете")
    )
    discord_restart_toggle.set_texts(
        tr_catalog("page.winws1_control.advanced.discord_restart.title", language=language, default="Перезапуск Discord"),
        tr_catalog("page.winws1_control.advanced.discord_restart.desc", language=language, default="Автоперезапуск при смене стратегии"),
    )
    wssize_toggle.set_texts(
        tr_catalog("page.winws1_control.advanced.wssize.title", language=language, default="Включить --wssize"),
        tr_catalog("page.winws1_control.advanced.wssize.desc", language=language, default="Добавляет параметр размера окна TCP"),
    )
    debug_log_toggle.set_texts(
        tr_catalog("page.winws1_control.advanced.debug_log.title", language=language, default="Включить лог-файл (--debug)"),
        tr_catalog("page.winws1_control.advanced.debug_log.desc", language=language, default="Записывает логи winws в папку logs"),
    )
    if blobs_action_card is not None:
        blobs_action_card.setTitle(
            tr_catalog("page.winws1_control.blobs.title", language=language, default="Блобы")
        )
        blobs_action_card.setContent(
            tr_catalog("page.winws1_control.blobs.desc", language=language, default="Бинарные данные (.bin / hex) для стратегий")
        )
        if blobs_open_btn is not None:
            blobs_open_btn.setText(tr_catalog("page.winws1_control.button.open", language=language, default="Открыть"))

    refresh_preset_name()
    phase, last_error = get_current_dpi_runtime_state()
    update_status(phase, last_error)


def show_simple_infobar_result(*, ok: bool, message: str, window, info_bar_cls) -> None:
    if ok:
        return
    info_bar_cls.warning(title="Ошибка", content=f"Не удалось очистить кэш: {message}", parent=window)


def save_wssize_enabled(enabled: bool, *, profile_feature, runtime_feature) -> None:
    profile_feature.set_wssize_enabled(
        bool(enabled),
        launch_method=ZAPRET1_MODE,
    )
    runtime_feature.apply_preset_content(launch_method=ZAPRET1_MODE, reason="wssize_toggled")


def save_debug_log_enabled(enabled: bool, *, profile_feature, runtime_feature) -> None:
    profile_feature.set_debug_log_enabled(
        bool(enabled),
        launch_method=ZAPRET1_MODE,
    )
    runtime_feature.apply_preset_content(launch_method=ZAPRET1_MODE, reason="debug_log_toggled")
