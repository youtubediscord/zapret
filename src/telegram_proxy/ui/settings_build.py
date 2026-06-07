"""Build-helper настроечной панели Telegram Proxy page."""

from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout
from qfluentwidgets import FluentIcon

from ui.fluent_widgets import (
    SettingsCard,
    QuickActionsBar,
    enable_setting_card_group_auto_height,
    insert_widget_into_setting_card_group,
    set_tooltip,
)
from telegram_proxy.ui.text_plan import TELEGRAM_PROXY_SETTINGS_TEXT


@dataclass(slots=True)
class TelegramProxySettingsPanelWidgets:
    status_card: object
    status_dot: object
    status_label: object
    btn_toggle: object
    stats_label: object
    setup_section_label: object
    setup_desc_label: object
    setup_fallback_label: object
    setup_card: object
    setup_open_btn: object
    setup_copy_btn: object
    settings_card: object
    settings_host_row: object
    host_label: object
    host_edit: object
    port_label: object
    port_spin: object
    proxy_mode_row: object
    mtproxy_secret_row: object
    mtproxy_secret_label: object
    mtproxy_secret_edit: object
    mtproxy_generate_btn: object
    auto_deeplink_toggle: object
    upstream_card: object
    upstream_desc_label: object
    upstream_toggle: object
    upstream_catalog: object
    upstream_preset_row: object
    upstream_catalog_hint: object
    upstream_manual_widget: object
    upstream_host_label: object
    upstream_host_edit: object
    upstream_port_label: object
    upstream_port_spin: object
    upstream_user_label: object
    upstream_user_edit: object
    upstream_pass_label: object
    upstream_pass_edit: object
    mtproxy_action_btn: object
    mtproxy_action_widget: object
    upstream_mode_toggle: object
    cloudflare_toggle: object
    cloudflare_domains_row: object
    cloudflare_domains_label: object
    cloudflare_domains_edit: object
    cloudflare_test_btn: object
    cloudflare_dns_btn: object
    cloudflare_worker_toggle: object
    cloudflare_worker_domains_row: object
    cloudflare_worker_domains_label: object
    cloudflare_worker_domains_edit: object
    cloudflare_worker_test_btn: object
    cloudflare_worker_code_btn: object
    manual_section_label: object
    instructions_card: object
    instr1_label: object
    instr2_label: object
    manual_host_port_label: object


def build_telegram_proxy_settings_panel(
    layout: QVBoxLayout,
    *,
    content_parent,
    status_dot_cls,
    strong_body_label_cls,
    caption_label_cls,
    body_label_cls,
    push_button_cls,
    primary_push_button_cls,
    setting_card_group_cls,
    line_edit_cls,
    spin_box_cls,
    password_line_edit_cls,
    win11_toggle_row_cls,
    win11_combo_row_cls,
    on_toggle_proxy,
    on_open_in_telegram,
    on_copy_link,
    on_open_mtproxy,
    on_generate_mtproxy_secret,
    on_test_cloudflare,
    on_copy_cloudflare_dns,
    on_test_cloudflare_worker,
    on_copy_cloudflare_worker_code,
    upstream_catalog,
) -> TelegramProxySettingsPanelWidgets:
    text = TELEGRAM_PROXY_SETTINGS_TEXT
    status_card = SettingsCard()

    status_header = QHBoxLayout()
    status_dot = status_dot_cls()
    status_label = strong_body_label_cls("Остановлен")
    status_header.addWidget(status_dot)
    status_header.addWidget(status_label)
    status_header.addStretch()

    btn_toggle = push_button_cls("Запустить", icon=FluentIcon.PLAY)
    btn_toggle.setFixedWidth(140)
    btn_toggle.clicked.connect(on_toggle_proxy)
    status_header.addWidget(btn_toggle)
    status_card.add_layout(status_header)

    stats_label = caption_label_cls("")
    status_card.add_widget(stats_label)
    layout.addWidget(status_card)

    setup_section_label = strong_body_label_cls(text.setup_title)
    layout.addWidget(setup_section_label)

    setup_desc_label = caption_label_cls(text.setup_description)
    setup_desc_label.setWordWrap(True)
    layout.addWidget(setup_desc_label)

    setup_card = QuickActionsBar(content_parent)

    setup_open_btn = primary_push_button_cls("Открыть", icon=FluentIcon.SEND)
    setup_open_btn.setMinimumWidth(132)
    set_tooltip(setup_open_btn, "Открыть ссылку для автоматической настройки прокси внутри Telegram.")
    setup_open_btn.clicked.connect(on_open_in_telegram)
    setup_card.add_button(setup_open_btn)

    setup_copy_btn = push_button_cls("Копировать", icon=FluentIcon.COPY)
    setup_copy_btn.setMinimumWidth(132)
    set_tooltip(setup_copy_btn, "Сохранить ссылку в буфер обмена, если Telegram не открылся автоматически.")
    setup_copy_btn.clicked.connect(on_copy_link)
    setup_card.add_button(setup_copy_btn)

    layout.addWidget(setup_card)

    setup_fallback_label = caption_label_cls(text.setup_fallback)
    setup_fallback_label.setWordWrap(True)
    layout.addWidget(setup_fallback_label)

    settings_card = setting_card_group_cls(text.settings_title, content_parent)
    settings_host_row = QWidget(settings_card)

    host_port_row = QHBoxLayout(settings_host_row)
    host_port_row.setContentsMargins(16, 8, 16, 6)
    host_port_row.setSpacing(12)
    host_label = body_label_cls("Адрес:")
    host_port_row.addWidget(host_label)
    host_edit = line_edit_cls()
    host_edit.setMinimumWidth(200)
    host_edit.setText("127.0.0.1")
    host_edit.setPlaceholderText("127.0.0.1")
    host_edit.setClearButtonEnabled(True)
    set_tooltip(
        host_edit,
        "IP-адрес для прослушивания. 127.0.0.1 — только локально, "
        "0.0.0.0 или IP вашей сети — доступ с других устройств (телефон и т.д.)"
    )
    host_port_row.addWidget(host_edit)

    host_port_row.addSpacing(16)

    port_label = body_label_cls("Порт:")
    host_port_row.addWidget(port_label)
    port_spin = spin_box_cls()
    port_spin.setRange(1024, 65535)
    port_spin.setValue(1353)
    port_spin.setFixedWidth(140)
    host_port_row.addWidget(port_spin)
    host_port_row.addStretch()
    insert_widget_into_setting_card_group(settings_card, 1, settings_host_row)

    proxy_mode_row = win11_combo_row_cls(
        icon_name="mdi.swap-horizontal",
        title=text.proxy_mode_title,
        description=text.proxy_mode_description,
        items=[
            ("SOCKS5", "socks5"),
            ("MTProxy", "mtproxy"),
        ],
    )
    proxy_mode_row.combo.setFixedWidth(170)
    settings_card.addSettingCard(proxy_mode_row)

    mtproxy_secret_row = QWidget(settings_card)
    mtproxy_secret_layout = QHBoxLayout(mtproxy_secret_row)
    mtproxy_secret_layout.setContentsMargins(16, 8, 16, 6)
    mtproxy_secret_layout.setSpacing(12)
    mtproxy_secret_label = body_label_cls("Secret:")
    mtproxy_secret_layout.addWidget(mtproxy_secret_label)
    mtproxy_secret_edit = line_edit_cls()
    mtproxy_secret_edit.setMinimumWidth(280)
    mtproxy_secret_edit.setPlaceholderText("32 символа: 0-9 и a-f")
    mtproxy_secret_edit.setClearButtonEnabled(True)
    set_tooltip(mtproxy_secret_edit, "Секрет MTProxy. Telegram использует его как ключ подключения.")
    mtproxy_secret_layout.addWidget(mtproxy_secret_edit)
    mtproxy_generate_btn = push_button_cls("Создать", icon=FluentIcon.SYNC)
    mtproxy_generate_btn.setMinimumWidth(120)
    set_tooltip(mtproxy_generate_btn, "Создать новый случайный secret для MTProxy.")
    mtproxy_generate_btn.clicked.connect(on_generate_mtproxy_secret)
    mtproxy_secret_layout.addWidget(mtproxy_generate_btn)
    mtproxy_secret_layout.addStretch()
    mtproxy_secret_row.setVisible(False)
    settings_card.addSettingCard(mtproxy_secret_row)

    auto_deeplink_toggle = win11_toggle_row_cls(
        "mdi.telegram",
        text.auto_setup_title,
        text.auto_setup_description,
    )
    auto_deeplink_toggle.setChecked(True)
    settings_card.addSettingCard(auto_deeplink_toggle)
    enable_setting_card_group_auto_height(settings_card)

    layout.addWidget(settings_card)

    upstream_card = setting_card_group_cls(text.upstream_title, content_parent)

    upstream_desc_label = caption_label_cls("")
    upstream_desc_label.setWordWrap(True)
    upstream_desc_label.setVisible(False)
    insert_widget_into_setting_card_group(upstream_card, 1, upstream_desc_label)

    upstream_toggle = win11_toggle_row_cls(
        "mdi.server-network",
        text.upstream_toggle_title,
        text.upstream_toggle_description,
    )
    upstream_toggle.setChecked(False)
    upstream_card.addSettingCard(upstream_toggle)

    upstream_preset_row = win11_combo_row_cls(
        icon_name="mdi.server-network",
        title=text.upstream_preset_title,
        description=text.upstream_preset_description,
        items=upstream_catalog.items(),
    )
    upstream_preset_row.combo.setFixedWidth(250)
    upstream_card.addSettingCard(upstream_preset_row)

    upstream_catalog_hint = caption_label_cls(text.upstream_catalog_missing)
    upstream_catalog_hint.setWordWrap(True)
    upstream_catalog_hint.setVisible(False)
    insert_widget_into_setting_card_group(upstream_card, 2, upstream_catalog_hint)

    upstream_manual_widget = QWidget(upstream_card)
    manual_layout = QVBoxLayout(upstream_manual_widget)
    manual_layout.setContentsMargins(0, 0, 0, 0)
    manual_layout.setSpacing(8)

    upstream_hp_row = QHBoxLayout()
    upstream_host_label = body_label_cls("Хост:")
    upstream_hp_row.addWidget(upstream_host_label)
    upstream_host_edit = line_edit_cls()
    upstream_host_edit.setMinimumWidth(250)
    upstream_host_edit.setPlaceholderText("192.168.1.100 или proxy.example.com")
    upstream_host_edit.setClearButtonEnabled(True)
    upstream_hp_row.addWidget(upstream_host_edit)
    upstream_hp_row.addSpacing(16)
    upstream_port_label = body_label_cls("Порт:")
    upstream_hp_row.addWidget(upstream_port_label)
    upstream_port_spin = spin_box_cls()
    upstream_port_spin.setRange(1, 65535)
    upstream_port_spin.setValue(1080)
    upstream_port_spin.setFixedWidth(140)
    upstream_hp_row.addWidget(upstream_port_spin)
    upstream_hp_row.addStretch()
    manual_layout.addLayout(upstream_hp_row)

    upstream_auth_row = QHBoxLayout()
    upstream_user_label = body_label_cls("Логин:")
    upstream_auth_row.addWidget(upstream_user_label)
    upstream_user_edit = line_edit_cls()
    upstream_user_edit.setMinimumWidth(200)
    upstream_user_edit.setPlaceholderText("username")
    upstream_auth_row.addWidget(upstream_user_edit)
    upstream_auth_row.addSpacing(16)
    upstream_pass_label = body_label_cls("Пароль:")
    upstream_auth_row.addWidget(upstream_pass_label)
    upstream_pass_edit = password_line_edit_cls()
    upstream_pass_edit.setMinimumWidth(200)
    upstream_pass_edit.setPlaceholderText("password")
    upstream_auth_row.addWidget(upstream_pass_edit)
    upstream_auth_row.addStretch()
    manual_layout.addLayout(upstream_auth_row)

    upstream_manual_widget.setVisible(True)
    upstream_card.addSettingCard(upstream_manual_widget)

    mtproxy_action_btn = push_button_cls("Открыть", icon=FluentIcon.SEND)
    mtproxy_action_btn.setMinimumWidth(132)
    set_tooltip(mtproxy_action_btn, "MTProxy настраивается в Telegram напрямую. Нажмите для добавления.")
    mtproxy_action_btn.clicked.connect(on_open_mtproxy)
    mtproxy_action_widget = mtproxy_action_btn
    mtproxy_action_widget.setVisible(False)
    upstream_card.addSettingCard(mtproxy_action_widget)

    upstream_mode_toggle = win11_toggle_row_cls(
        "mdi.swap-horizontal",
        text.upstream_mode_title,
        text.upstream_mode_description,
    )
    upstream_mode_toggle.setChecked(True)
    upstream_card.addSettingCard(upstream_mode_toggle)

    cloudflare_toggle = win11_toggle_row_cls(
        "mdi.cloud",
        text.cloudflare_toggle_title,
        text.cloudflare_toggle_description,
    )
    cloudflare_toggle.setChecked(False)
    upstream_card.addSettingCard(cloudflare_toggle)

    cloudflare_domains_row = QWidget(upstream_card)
    cloudflare_domains_layout = QHBoxLayout(cloudflare_domains_row)
    cloudflare_domains_layout.setContentsMargins(16, 8, 16, 6)
    cloudflare_domains_layout.setSpacing(12)
    cloudflare_domains_label = body_label_cls("Домены:")
    cloudflare_domains_layout.addWidget(cloudflare_domains_label)
    cloudflare_domains_edit = line_edit_cls()
    cloudflare_domains_edit.setMinimumWidth(320)
    cloudflare_domains_edit.setPlaceholderText("Пусто = авто, или example.com, backup.example.com")
    cloudflare_domains_edit.setClearButtonEnabled(True)
    set_tooltip(cloudflare_domains_edit, "Cloudflare-домены для запасного WSS-пути. Оставьте пустым для авто-списка.")
    cloudflare_domains_layout.addWidget(cloudflare_domains_edit)
    cloudflare_test_btn = push_button_cls("Проверить", icon=FluentIcon.SEARCH)
    cloudflare_test_btn.setMinimumWidth(116)
    set_tooltip(cloudflare_test_btn, "Проверить, отвечает ли ваш Cloudflare-домен для Telegram.")
    cloudflare_test_btn.clicked.connect(on_test_cloudflare)
    cloudflare_domains_layout.addWidget(cloudflare_test_btn)
    cloudflare_dns_btn = push_button_cls("DNS", icon=FluentIcon.COPY)
    cloudflare_dns_btn.setMinimumWidth(84)
    set_tooltip(cloudflare_dns_btn, "Скопировать DNS-записи kws1, kws2, kws3, kws4, kws5 и kws203.")
    cloudflare_dns_btn.clicked.connect(on_copy_cloudflare_dns)
    cloudflare_domains_layout.addWidget(cloudflare_dns_btn)
    cloudflare_domains_layout.addStretch()
    cloudflare_domains_row.setVisible(False)
    upstream_card.addSettingCard(cloudflare_domains_row)

    cloudflare_worker_toggle = win11_toggle_row_cls(
        "mdi.cloud-outline",
        text.cloudflare_worker_toggle_title,
        text.cloudflare_worker_toggle_description,
    )
    cloudflare_worker_toggle.setChecked(False)
    upstream_card.addSettingCard(cloudflare_worker_toggle)

    cloudflare_worker_domains_row = QWidget(upstream_card)
    cloudflare_worker_domains_layout = QHBoxLayout(cloudflare_worker_domains_row)
    cloudflare_worker_domains_layout.setContentsMargins(16, 8, 16, 6)
    cloudflare_worker_domains_layout.setSpacing(12)
    cloudflare_worker_domains_label = body_label_cls("Worker:")
    cloudflare_worker_domains_layout.addWidget(cloudflare_worker_domains_label)
    cloudflare_worker_domains_edit = line_edit_cls()
    cloudflare_worker_domains_edit.setMinimumWidth(320)
    cloudflare_worker_domains_edit.setPlaceholderText("worker-name.workers.dev")
    cloudflare_worker_domains_edit.setClearButtonEnabled(True)
    set_tooltip(cloudflare_worker_domains_edit, "Домены Cloudflare Worker для отдельного запасного пути.")
    cloudflare_worker_domains_layout.addWidget(cloudflare_worker_domains_edit)
    cloudflare_worker_test_btn = push_button_cls("Проверить", icon=FluentIcon.SEARCH)
    cloudflare_worker_test_btn.setMinimumWidth(116)
    set_tooltip(cloudflare_worker_test_btn, "Проверить, отвечает ли ваш Cloudflare Worker.")
    cloudflare_worker_test_btn.clicked.connect(on_test_cloudflare_worker)
    cloudflare_worker_domains_layout.addWidget(cloudflare_worker_test_btn)
    cloudflare_worker_code_btn = push_button_cls("Код Worker", icon=FluentIcon.COPY)
    cloudflare_worker_code_btn.setMinimumWidth(120)
    set_tooltip(cloudflare_worker_code_btn, "Скопировать готовый код для Cloudflare Worker.")
    cloudflare_worker_code_btn.clicked.connect(on_copy_cloudflare_worker_code)
    cloudflare_worker_domains_layout.addWidget(cloudflare_worker_code_btn)
    cloudflare_worker_domains_layout.addStretch()
    cloudflare_worker_domains_row.setVisible(False)
    upstream_card.addSettingCard(cloudflare_worker_domains_row)

    enable_setting_card_group_auto_height(upstream_card)

    layout.addWidget(upstream_card)

    manual_section_label = strong_body_label_cls(text.manual_hidden_title)
    manual_section_label.setVisible(False)
    layout.addWidget(manual_section_label)

    instructions_card = SettingsCard()
    instr1_label = caption_label_cls("Если автоматическая настройка не сработала:")
    instr1_label.setWordWrap(True)
    instructions_card.add_widget(instr1_label)

    instr2_label = caption_label_cls("  Telegram -> Настройки -> Продвинутые -> Тип соединения -> Прокси")
    instr2_label.setWordWrap(True)
    instructions_card.add_widget(instr2_label)

    manual_host_port_label = caption_label_cls("  Тип: SOCKS5  |  Хост: 127.0.0.1  |  Порт: 1353")
    manual_host_port_label.setWordWrap(True)
    instructions_card.add_widget(manual_host_port_label)

    layout.addWidget(instructions_card)
    instructions_card.setVisible(False)
    layout.addStretch()

    return TelegramProxySettingsPanelWidgets(
        status_card=status_card,
        status_dot=status_dot,
        status_label=status_label,
        btn_toggle=btn_toggle,
        stats_label=stats_label,
        setup_section_label=setup_section_label,
        setup_desc_label=setup_desc_label,
        setup_fallback_label=setup_fallback_label,
        setup_card=setup_card,
        setup_open_btn=setup_open_btn,
        setup_copy_btn=setup_copy_btn,
        settings_card=settings_card,
        settings_host_row=settings_host_row,
        host_label=host_label,
        host_edit=host_edit,
        port_label=port_label,
        port_spin=port_spin,
        proxy_mode_row=proxy_mode_row,
        mtproxy_secret_row=mtproxy_secret_row,
        mtproxy_secret_label=mtproxy_secret_label,
        mtproxy_secret_edit=mtproxy_secret_edit,
        mtproxy_generate_btn=mtproxy_generate_btn,
        auto_deeplink_toggle=auto_deeplink_toggle,
        upstream_card=upstream_card,
        upstream_desc_label=upstream_desc_label,
        upstream_toggle=upstream_toggle,
        upstream_catalog=upstream_catalog,
        upstream_preset_row=upstream_preset_row,
        upstream_catalog_hint=upstream_catalog_hint,
        upstream_manual_widget=upstream_manual_widget,
        upstream_host_label=upstream_host_label,
        upstream_host_edit=upstream_host_edit,
        upstream_port_label=upstream_port_label,
        upstream_port_spin=upstream_port_spin,
        upstream_user_label=upstream_user_label,
        upstream_user_edit=upstream_user_edit,
        upstream_pass_label=upstream_pass_label,
        upstream_pass_edit=upstream_pass_edit,
        mtproxy_action_btn=mtproxy_action_btn,
        mtproxy_action_widget=mtproxy_action_widget,
        upstream_mode_toggle=upstream_mode_toggle,
        cloudflare_toggle=cloudflare_toggle,
        cloudflare_domains_row=cloudflare_domains_row,
        cloudflare_domains_label=cloudflare_domains_label,
        cloudflare_domains_edit=cloudflare_domains_edit,
        cloudflare_test_btn=cloudflare_test_btn,
        cloudflare_dns_btn=cloudflare_dns_btn,
        cloudflare_worker_toggle=cloudflare_worker_toggle,
        cloudflare_worker_domains_row=cloudflare_worker_domains_row,
        cloudflare_worker_domains_label=cloudflare_worker_domains_label,
        cloudflare_worker_domains_edit=cloudflare_worker_domains_edit,
        cloudflare_worker_test_btn=cloudflare_worker_test_btn,
        cloudflare_worker_code_btn=cloudflare_worker_code_btn,
        manual_section_label=manual_section_label,
        instructions_card=instructions_card,
        instr1_label=instr1_label,
        instr2_label=instr2_label,
        manual_host_port_label=manual_host_port_label,
    )
