"""Runtime/helper слой для Zapret1 mode control page."""

from __future__ import annotations

from settings.mode import EXE_NAME_WINWS1, ZAPRET1_MODE
from app.ui_texts import tr as tr_catalog
import presets.ui.control.control_runtime as control_runtime
from presets.ui.control.control_page_runtime_shared import (
    apply_program_settings_toggles,
    apply_status_plan as apply_status_plan_shared,
    set_button_text_accessibility,
    set_toggle_checked,
)
from presets.ui.control.additional_settings_runtime import (
    build_additional_settings_state,
    create_additional_settings_save_worker,
    create_additional_settings_worker,
    create_refresh_runtime,
    create_top_summary_worker,
)


def apply_program_settings_snapshot(
    snapshot,
    *,
    auto_dpi_toggle,
    gui_autostart_toggle=None,
    tray_close_mode_combo=None,
    defender_toggle=None,
    max_block_toggle=None,
    state_media_block_toggle=None,
) -> None:
    apply_program_settings_toggles(
        snapshot,
        auto_dpi_toggle=auto_dpi_toggle,
        gui_autostart_toggle=gui_autostart_toggle,
        tray_close_mode_combo=tray_close_mode_combo,
        defender_toggle=defender_toggle,
        max_block_toggle=max_block_toggle,
        state_media_block_toggle=state_media_block_toggle,
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
    program_settings_card,
    auto_dpi_toggle,
    gui_autostart_toggle,
    tray_close_mode_combo,
    defender_toggle,
    max_block_toggle,
    state_media_block_toggle,
    test_card,
    internet_cleanup_card,
    folder_card,
    docs_card,
    additional_settings_card,
    additional_settings_notice,
    discord_restart_toggle,
    wssize_toggle,
    debug_log_toggle,
    refresh_preset_name,
    get_current_dpi_runtime_state,
    update_status,
) -> None:
    set_button_text_accessibility(
        start_btn,
        tr_catalog("page.winws1_control.button.start", language=language, default="Запустить Zapret"),
        description="Запускает обход блокировок в выбранном режиме.",
    )
    set_button_text_accessibility(
        stop_winws_btn,
        tr_catalog("page.winws1_control.button.stop_winws", language=language, default=f"Остановить {EXE_NAME_WINWS1}"),
        description="Останавливает запущенный процесс обхода блокировок.",
    )
    set_button_text_accessibility(
        stop_and_exit_btn,
        tr_catalog("page.winws1_control.button.stop_and_exit", language=language, default="Остановить и закрыть"),
        description="Останавливает обход блокировок и закрывает программу.",
    )

    program_settings_card.titleLabel.setText(
        tr_catalog("page.winws1_control.section.program_settings", language=language, default="Настройки программы")
    )
    if auto_dpi_toggle is not None:
        auto_dpi_toggle.set_texts(
            tr_catalog("page.winws1_control.setting.autostart.title", language=language, default="Автозапуск DPI после старта программы"),
            tr_catalog("page.winws1_control.setting.autostart.desc", language=language, default="После запуска ZapretGUI автоматически запускать текущий DPI-режим"),
        )
    if gui_autostart_toggle is not None:
        gui_autostart_toggle.set_texts(
            tr_catalog("page.control.setting.gui_autostart.title", language=language, default="Автозапуск ZapretGUI"),
            tr_catalog("page.control.setting.gui_autostart.desc", language=language, default="Запускать программу в трее при входе в Windows"),
        )
    if tray_close_mode_combo is not None:
        tray_close_mode_combo.set_texts(
            tr_catalog("page.control.setting.tray_close_mode.title", language=language, default="Поведение окна и трея"),
            tr_catalog("page.control.setting.tray_close_mode.desc", language=language, default="Выберите, когда ZapretGUI будет скрывать окно в системный трей"),
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
    if state_media_block_toggle is not None:
        state_media_block_toggle.set_texts(
            tr_catalog(
                "page.control.setting.state_media_block.title",
                language=language,
                default="Блокировать государственные СМИ РФ",
            ),
            tr_catalog(
                "page.control.setting.state_media_block.desc",
                language=language,
                default="Добавляет базовый список государственных новостных сайтов в hosts",
            ),
        )

    connection_test_title = tr_catalog("page.winws1_control.button.connection_test", language=language, default="Тест соединения")
    connection_test_desc = tr_catalog("page.winws1_control.button.connection_test.desc", language=language, default="Проверить доступность сети и состояние обхода")
    test_card.setTitle(connection_test_title)
    test_card.setContent(connection_test_desc)
    set_button_text_accessibility(
        test_card.button,
        tr_catalog("page.winws1_control.button.open", language=language, default="Открыть"),
        accessible_name=tr_catalog("page.winws1_control.button.connection_test.accessible_name", language=language, default="Открыть тест соединения"),
        description=connection_test_desc,
    )

    internet_cleanup_title = tr_catalog("page.control.internet_cleanup.title", language=language, default="Сбросить сеть Windows")
    internet_cleanup_desc = tr_catalog(
        "page.control.internet_cleanup.desc",
        language=language,
        default="Очистить DNS, proxy, Winsock и сетевые параметры. Может понадобиться перезагрузка",
    )
    internet_cleanup_card.setTitle(internet_cleanup_title)
    internet_cleanup_card.setContent(internet_cleanup_desc)
    set_button_text_accessibility(
        internet_cleanup_card.button,
        tr_catalog("page.control.internet_cleanup.button", language=language, default="Сбросить"),
        accessible_name=tr_catalog("page.control.internet_cleanup.accessible_name", language=language, default="Сбросить сеть Windows"),
        description=internet_cleanup_desc,
    )

    folder_title = tr_catalog("page.winws1_control.button.open_folder", language=language, default="Открыть папку")
    folder_desc = tr_catalog("page.winws1_control.button.open_folder.desc", language=language, default="Перейти в папку программы и служебных файлов")
    folder_card.setTitle(folder_title)
    folder_card.setContent(folder_desc)
    set_button_text_accessibility(
        folder_card.button,
        tr_catalog("page.winws1_control.button.open", language=language, default="Открыть"),
        accessible_name=tr_catalog("page.winws1_control.button.open_folder.accessible_name", language=language, default="Открыть папку программы"),
        description=folder_desc,
    )

    docs_title = tr_catalog("page.winws1_control.button.documentation", language=language, default="Документация")
    docs_desc = tr_catalog("page.winws1_control.button.documentation.desc", language=language, default="Открыть справку и описание возможностей")
    docs_card.setTitle(docs_title)
    docs_card.setContent(docs_desc)
    set_button_text_accessibility(
        docs_card.button,
        tr_catalog("page.winws1_control.button.open", language=language, default="Открыть"),
        accessible_name=tr_catalog("page.winws1_control.button.documentation.accessible_name", language=language, default="Открыть документацию"),
        description=docs_desc,
    )

    additional_settings_card.titleLabel.setText(
        tr_catalog("page.winws1_control.card.advanced", language=language, default="Дополнительные настройки")
    )
    additional_settings_notice.setText(
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

    refresh_preset_name()
    phase, last_error = get_current_dpi_runtime_state()
    update_status(phase, last_error)


def show_simple_infobar_result(*, ok: bool, message: str, window, info_bar_cls) -> None:
    if ok:
        return
    info_bar_cls.warning(title="Ошибка", content=f"Не удалось очистить кэш: {message}", parent=window)
