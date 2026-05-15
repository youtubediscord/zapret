"""Runtime/settings helper слой Telegram Proxy page."""

from __future__ import annotations

import telegram_proxy.ui.page_runtime as telegram_proxy_page_runtime
import telegram_proxy.settings as telegram_proxy_settings


def refresh_pivot_texts(pivot) -> None:
    try:
        pivot.setItemText("settings", "Настройки")
        pivot.setItemText("logs", "Логи")
        pivot.setItemText("diag", "Диагностика")
    except Exception:
        pass


def refresh_status_texts(*, manager, status_label, btn_toggle, restarting: bool, starting: bool) -> None:
    running = bool(manager.is_running)
    plan = telegram_proxy_page_runtime.build_status_plan(
        running=running,
        restarting=bool(restarting),
        starting=bool(starting),
        host=manager.host,
        port=manager.port,
    )

    if status_label is not None:
        status_label.setText(plan.status_text)

    if btn_toggle is not None:
        btn_toggle.setText(plan.toggle_text)


def apply_upstream_preset_ui(
    *,
    upstream_toggle,
    upstream_catalog,
    upstream_preset_row,
    upstream_catalog_hint,
    upstream_manual_widget,
    mtproxy_action_widget,
    upstream_mode_toggle,
    index: int,
) -> str:
    upstream_enabled = upstream_toggle.isChecked()
    preset = upstream_catalog.preset_at(index)
    has_bundled_presets = upstream_catalog.has_bundled_presets()
    is_manual = bool(preset is not None and upstream_catalog.is_manual(index))
    is_mtproxy = bool(preset is not None and upstream_catalog.is_mtproxy(index))

    upstream_preset_row.setVisible(upstream_enabled and has_bundled_presets)
    upstream_catalog_hint.setVisible(upstream_enabled and not has_bundled_presets)
    upstream_manual_widget.setVisible(upstream_enabled and is_manual)
    mtproxy_action_widget.setVisible(upstream_enabled and is_mtproxy)
    upstream_mode_toggle.setVisible(upstream_enabled)
    upstream_mode_toggle.setEnabled(upstream_enabled)

    if preset is not None and is_mtproxy:
        return upstream_catalog.mtproxy_link(index)
    return ""


def refresh_upstream_preset_combo(
    *,
    upstream_preset_row,
    upstream_catalog,
    apply_upstream_preset_ui_callback,
    select_index: int | None = None,
) -> tuple[int, str]:
    combo = upstream_preset_row.combo
    combo.blockSignals(True)
    combo.clear()
    for label, preset in upstream_catalog.items():
        combo.addItem(label, userData=preset)

    if not upstream_catalog.choices:
        target_index = -1
    elif select_index is None:
        target_index = combo.currentIndex()
        if target_index < 0:
            target_index = 0
        target_index = min(target_index, len(upstream_catalog.choices) - 1)
    else:
        target_index = min(max(select_index, 0), len(upstream_catalog.choices) - 1)

    combo.setCurrentIndex(target_index)
    combo.blockSignals(False)

    mtproxy_link = ""
    if target_index >= 0:
        mtproxy_link = apply_upstream_preset_ui_callback(target_index)
    return target_index, mtproxy_link


def load_settings_into_ui(
    *,
    upstream_catalog,
    port_spin,
    host_edit,
    update_manual_instructions,
    upstream_toggle,
    upstream_host_edit,
    upstream_port_spin,
    upstream_user_edit,
    upstream_pass_edit,
    refresh_upstream_preset_combo_callback,
    upstream_mode_toggle,
) -> None:
    state = telegram_proxy_settings.load_state(upstream_catalog)

    port_spin.blockSignals(True)
    port_spin.setValue(state.port)
    port_spin.blockSignals(False)

    host_edit.setText(state.host)
    update_manual_instructions()

    upstream_toggle.setChecked(state.upstream_enabled, block_signals=True)

    upstream_host_edit.setText(state.upstream_host)
    upstream_port_spin.blockSignals(True)
    upstream_port_spin.setValue(state.upstream_port)
    upstream_port_spin.blockSignals(False)
    upstream_user_edit.setText(state.upstream_user)
    upstream_pass_edit.setText(state.upstream_password)

    refresh_upstream_preset_combo_callback(select_index=state.upstream_preset_index)

    upstream_mode_toggle.setChecked(state.upstream_mode == "always", block_signals=True)


def apply_ui_texts(
    *,
    refresh_pivot_texts_callback,
    refresh_status_texts_callback,
    setup_section_label,
    settings_card,
    upstream_card,
    manual_section_label,
    setup_desc_label,
    host_label,
    port_label,
    upstream_desc_label,
    upstream_host_label,
    upstream_port_label,
    upstream_user_label,
    upstream_pass_label,
    mtproxy_desc_label,
    instr1_label,
    instr2_label,
    diag_desc_label,
    setup_open_btn,
    setup_copy_btn,
    mtproxy_action_btn,
    btn_copy_logs,
    btn_open_log_file,
    btn_clear_logs,
    btn_copy_diag,
    btn_run_diag,
    host_edit,
    upstream_host_edit,
    upstream_user_edit,
    upstream_pass_edit,
    log_edit,
    diag_edit,
    auto_deeplink_toggle,
    upstream_toggle,
    upstream_preset_row,
    upstream_catalog_hint,
    upstream_mode_toggle,
    update_manual_instructions_callback,
) -> None:
    try:
        refresh_pivot_texts_callback()
        refresh_status_texts_callback()

        if setup_section_label is not None:
            setup_section_label.setText("Быстрая настройка Telegram")
        title_label = getattr(settings_card, "titleLabel", None)
        if title_label is not None:
            title_label.setText("Настройки")
        title_label = getattr(upstream_card, "titleLabel", None)
        if title_label is not None:
            title_label.setText("Внешний прокси (upstream)")
        if manual_section_label is not None:
            manual_section_label.setText("Ручная настройка")

        if setup_desc_label is not None:
            setup_desc_label.setText(
                "Нажмите кнопку ниже - Telegram автоматически добавит прокси. "
                "Настройка требуется один раз.\nЕсли Telegram не открывается попробуйте скопировать ссылку и отправить в любой чат Telegram или кому-то в ЛС — после чего нажмите на отправленную ссылку и подтвердите добавление прокси в Telegram клиент.\nРекомендуем полностью ПЕРЕЗАПУСТИТЬ клиент для более корректного работа прокси после включения Zapret 2 GUI!"
            )
        if host_label is not None:
            host_label.setText("Адрес:")
        if port_label is not None:
            port_label.setText("Порт:")
        if upstream_desc_label is not None:
            upstream_desc_label.setText(
                "SOCKS5 прокси-сервер для DC заблокированных вашим провайдером.\n"
                "Используется как резервный канал когда WSS relay и прямое подключение не работают."
            )
        if upstream_host_label is not None:
            upstream_host_label.setText("Хост:")
        if upstream_port_label is not None:
            upstream_port_label.setText("Порт:")
        if upstream_user_label is not None:
            upstream_user_label.setText("Логин:")
        if upstream_pass_label is not None:
            upstream_pass_label.setText("Пароль:")
        if mtproxy_desc_label is not None:
            mtproxy_desc_label.setText("MTProxy настраивается в Telegram напрямую. Нажмите для добавления.")
        if instr1_label is not None:
            instr1_label.setText("Если автоматическая настройка не сработала:")
        if instr2_label is not None:
            instr2_label.setText("  Telegram -> Настройки -> Продвинутые -> Тип соединения -> Прокси")
        if diag_desc_label is not None:
            diag_desc_label.setText(
                "Проверка соединений к Telegram DC, WSS relay эндпоинтов (kws1-kws5), "
                "SOCKS5 прокси и определение типа блокировки."
            )

        if setup_open_btn is not None:
            setup_open_btn.setText("Открыть")
            setup_open_btn.setToolTip(
                "Открыть ссылку для автоматической настройки прокси внутри Telegram."
            )
        if setup_copy_btn is not None:
            setup_copy_btn.setText("Копировать")
            setup_copy_btn.setToolTip(
                "Сохранить ссылку в буфер обмена, если Telegram не открылся автоматически."
            )
        if mtproxy_action_btn is not None:
            mtproxy_action_btn.setText("Открыть")
            mtproxy_action_btn.setToolTip(
                "MTProxy настраивается в Telegram напрямую. Нажмите для добавления."
            )
        if btn_copy_logs is not None:
            btn_copy_logs.setText("Копировать все")
        if btn_open_log_file is not None:
            btn_open_log_file.setText("Открыть файл лога")
        if btn_clear_logs is not None:
            btn_clear_logs.setText("Очистить")
        if btn_copy_diag is not None:
            btn_copy_diag.setText("Копировать результат")
        if btn_run_diag is not None and btn_run_diag.isEnabled():
            btn_run_diag.setText("Запустить диагностику")

        if host_edit is not None:
            host_edit.setPlaceholderText("127.0.0.1")
        if upstream_host_edit is not None:
            upstream_host_edit.setPlaceholderText("192.168.1.100 или proxy.example.com")
        if upstream_user_edit is not None:
            upstream_user_edit.setPlaceholderText("username")
        if upstream_pass_edit is not None:
            upstream_pass_edit.setPlaceholderText("password")
        if log_edit is not None:
            log_edit.setPlaceholderText("Лог подключений появится здесь...")
        if diag_edit is not None:
            diag_edit.setPlaceholderText("Нажмите 'Запустить диагностику'...")

        if auto_deeplink_toggle is not None:
            auto_deeplink_toggle.set_texts(
                "Авто-настройка Telegram",
                "При первом запуске прокси автоматически открыть ссылку настройки в Telegram",
            )
        if upstream_toggle is not None:
            upstream_toggle.set_texts(
                "Использовать внешний прокси",
                "Маршрутизировать заблокированные DC через внешний SOCKS5 прокси",
            )
        if upstream_preset_row is not None:
            upstream_preset_row.set_texts(
                "Сервер",
                "Выберите сервер из списка или переключитесь на ручной ввод",
            )
        if upstream_catalog_hint is not None:
            upstream_catalog_hint.setText(
                "В этой сборке список предустановленных прокси не загружен. "
                "Доступен только ручной ввод."
            )
        if upstream_mode_toggle is not None:
            upstream_mode_toggle.set_texts(
                "Весь трафик через прокси",
                "Если выключено — только заблокированные DC. Если включено — весь трафик Telegram.",
            )

        update_manual_instructions_callback()
    except Exception:
        pass
