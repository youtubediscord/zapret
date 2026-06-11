"""Runtime/settings helper слой Telegram Proxy page."""

from __future__ import annotations

import telegram_proxy.ui.page_runtime as telegram_proxy_page_runtime
from qfluentwidgets import FluentIcon
from ui.accessibility import set_control_accessibility, set_state_text
from ui.fluent_widgets import set_tooltip
from telegram_proxy.ui.build import update_telegram_proxy_pivot_accessibility
from telegram_proxy.ui.text_plan import TELEGRAM_PROXY_SETTINGS_TEXT


def refresh_pivot_texts(pivot) -> None:
    try:
        pivot.setItemText("settings", "Настройки")
        pivot.setItemText("logs", "Логи")
        pivot.setItemText("diag", "Диагностика")
        update_telegram_proxy_pivot_accessibility(pivot)
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
        set_state_text(status_label, f"Статус Telegram Proxy: {plan.status_text}")

    if btn_toggle is not None:
        btn_toggle.setText(plan.toggle_text)
        btn_toggle.setIcon(FluentIcon.CANCEL if "Останов" in plan.toggle_text else FluentIcon.PLAY)
        btn_toggle.setMinimumWidth(140)
        if "Останов" in plan.toggle_text:
            set_control_accessibility(
                btn_toggle,
                name="Остановить Telegram Proxy",
                description="Останавливает локальный Telegram Proxy.",
            )
        else:
            set_control_accessibility(
                btn_toggle,
                name="Запустить Telegram Proxy",
                description="Запускает локальный Telegram Proxy.",
            )


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


def apply_ui_texts(
    *,
    refresh_pivot_texts_callback,
    refresh_status_texts_callback,
    setup_section_label,
    settings_card,
    advanced_card,
    upstream_card,
    manual_section_label,
    setup_desc_label,
    setup_fallback_label,
    host_label,
    port_label,
    mtproxy_secret_label,
    fake_tls_domain_label,
    dc_ip_label,
    performance_label,
    pool_size_label,
    buffer_kb_label,
    cloudflare_domains_label,
    cloudflare_worker_domains_label,
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
    cloudflare_test_btn,
    cloudflare_dns_btn,
    fake_tls_nginx_btn,
    cloudflare_worker_test_btn,
    cloudflare_worker_code_btn,
    btn_copy_logs,
    btn_open_log_file,
    btn_clear_logs,
    btn_copy_diag,
    btn_run_diag,
    host_edit,
    mtproxy_secret_edit,
    fake_tls_domain_edit,
    dc_ip_edit,
    cloudflare_domains_edit,
    cloudflare_worker_domains_edit,
    upstream_host_edit,
    upstream_user_edit,
    upstream_pass_edit,
    log_edit,
    diag_edit,
    auto_deeplink_toggle,
    advanced_toggle,
    proxy_mode_row,
    proxy_protocol_toggle,
    upstream_toggle,
    upstream_preset_row,
    upstream_catalog_hint,
    upstream_mode_toggle,
    cloudflare_toggle,
    cloudflare_worker_toggle,
    update_manual_instructions_callback,
) -> None:
    try:
        text = TELEGRAM_PROXY_SETTINGS_TEXT
        refresh_pivot_texts_callback()
        refresh_status_texts_callback()

        if setup_section_label is not None:
            setup_section_label.setText(text.setup_title)
        title_label = getattr(settings_card, "titleLabel", None)
        if title_label is not None:
            title_label.setText(text.settings_title)
        title_label = getattr(advanced_card, "titleLabel", None)
        if title_label is not None:
            title_label.setText(text.advanced_title)
        title_label = getattr(upstream_card, "titleLabel", None)
        if title_label is not None and upstream_card is not advanced_card:
            title_label.setText(text.upstream_title)
        if manual_section_label is not None:
            manual_section_label.setText(text.manual_hidden_title)
            manual_section_label.setVisible(False)

        if setup_desc_label is not None:
            setup_desc_label.setText(text.setup_description)
        if setup_fallback_label is not None:
            setup_fallback_label.setText(text.setup_fallback)
        if host_label is not None:
            host_label.setText("Адрес:")
        if port_label is not None:
            port_label.setText("Порт:")
        if mtproxy_secret_label is not None:
            mtproxy_secret_label.setText("Secret:")
        if fake_tls_domain_label is not None:
            fake_tls_domain_label.setText("Fake TLS:")
        if dc_ip_label is not None:
            dc_ip_label.setText("DC -> IP:")
        if performance_label is not None:
            performance_label.setText(text.performance_description)
        if pool_size_label is not None:
            pool_size_label.setText("Пул WSS:")
        if buffer_kb_label is not None:
            buffer_kb_label.setText("Буфер, КБ:")
        if cloudflare_domains_label is not None:
            cloudflare_domains_label.setText("Домены:")
        if cloudflare_worker_domains_label is not None:
            cloudflare_worker_domains_label.setText("Worker:")
        if upstream_desc_label is not None:
            upstream_desc_label.setText("")
            upstream_desc_label.setVisible(False)
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
            instr2_label.setText(text.manual_path)
        if diag_desc_label is not None:
            diag_desc_label.setText(text.diag_description)

        if setup_open_btn is not None:
            setup_open_btn.setText("Открыть")
            set_tooltip(
                setup_open_btn,
                "Открыть ссылку для автоматической настройки прокси внутри Telegram."
            )
        if setup_copy_btn is not None:
            setup_copy_btn.setText("Копировать")
            set_tooltip(
                setup_copy_btn,
                "Сохранить ссылку в буфер обмена, если Telegram не открылся автоматически."
            )
        if mtproxy_action_btn is not None:
            mtproxy_action_btn.setText("Открыть")
            set_tooltip(
                mtproxy_action_btn,
                "MTProxy настраивается в Telegram напрямую. Нажмите для добавления."
            )
        if cloudflare_test_btn is not None and cloudflare_test_btn.isEnabled():
            cloudflare_test_btn.setText("Проверить")
            set_tooltip(cloudflare_test_btn, "Проверить, отвечает ли ваш Cloudflare-домен для Telegram.")
        if cloudflare_dns_btn is not None:
            cloudflare_dns_btn.setText("DNS")
            set_tooltip(cloudflare_dns_btn, "Скопировать DNS-записи для своего Cloudflare-домена.")
        if fake_tls_nginx_btn is not None:
            fake_tls_nginx_btn.setText("Nginx")
            set_tooltip(fake_tls_nginx_btn, "Скопировать stream-конфиг Nginx для MTProxy Fake TLS.")
        if cloudflare_worker_test_btn is not None and cloudflare_worker_test_btn.isEnabled():
            cloudflare_worker_test_btn.setText("Проверить")
            set_tooltip(cloudflare_worker_test_btn, "Проверить, отвечает ли ваш Cloudflare Worker.")
        if cloudflare_worker_code_btn is not None:
            cloudflare_worker_code_btn.setText("Код Worker")
            set_tooltip(cloudflare_worker_code_btn, "Скопировать готовый код для Cloudflare Worker.")
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
        if mtproxy_secret_edit is not None:
            mtproxy_secret_edit.setPlaceholderText("32 символа: 0-9 и a-f")
        if fake_tls_domain_edit is not None:
            fake_tls_domain_edit.setPlaceholderText("front.example.com")
        if dc_ip_edit is not None:
            dc_ip_edit.setPlaceholderText("4:149.154.167.220, 5:91.108.56.100")
        if cloudflare_domains_edit is not None:
            cloudflare_domains_edit.setPlaceholderText("Пусто = авто, или example.com, backup.example.com")
        if cloudflare_worker_domains_edit is not None:
            cloudflare_worker_domains_edit.setPlaceholderText("worker-name.workers.dev")
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
                text.auto_setup_title,
                text.auto_setup_description,
            )
        if advanced_toggle is not None:
            advanced_toggle.set_texts(
                text.advanced_title,
                text.advanced_description,
            )
        if proxy_mode_row is not None:
            proxy_mode_row.set_texts(
                text.proxy_mode_title,
                text.proxy_mode_description,
            )
        if proxy_protocol_toggle is not None:
            proxy_protocol_toggle.set_texts(
                text.proxy_protocol_title,
                text.proxy_protocol_description,
            )
        if upstream_toggle is not None:
            upstream_toggle.set_texts(
                text.upstream_toggle_title,
                text.upstream_toggle_description,
            )
        if upstream_preset_row is not None:
            upstream_preset_row.set_texts(
                text.upstream_preset_title,
                text.upstream_preset_description,
            )
        if upstream_catalog_hint is not None:
            upstream_catalog_hint.setText(text.upstream_catalog_missing)
        if upstream_mode_toggle is not None:
            upstream_mode_toggle.set_texts(
                text.upstream_mode_title,
                text.upstream_mode_description,
            )
        if cloudflare_toggle is not None:
            cloudflare_toggle.set_texts(
                text.cloudflare_toggle_title,
                text.cloudflare_toggle_description,
            )
        if cloudflare_worker_toggle is not None:
            cloudflare_worker_toggle.set_texts(
                text.cloudflare_worker_toggle_title,
                text.cloudflare_worker_toggle_description,
            )

        update_manual_instructions_callback()
    except Exception:
        pass
