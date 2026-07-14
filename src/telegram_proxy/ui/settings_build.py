"""Build-helper настроечной панели Telegram Proxy page."""

from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout
from qfluentwidgets import FluentIcon

from ui.accessibility import remove_line_edit_buttons_from_tab_order, set_control_accessibility, set_state_text
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
    setup_zastogram_btn: object
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
    fake_tls_domain_row: object
    fake_tls_domain_label: object
    fake_tls_domain_edit: object
    fake_tls_nginx_btn: object
    auto_deeplink_toggle: object
    advanced_toggle: object
    advanced_card: object
    upstream_card: object
    upstream_desc_label: object
    upstream_toggle: object
    upstream_catalog: object
    upstream_preset_row: object
    upstream_runtime_state_label: object
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
    upstream_udp_toggle: object
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
    dc_ip_row: object
    dc_ip_label: object
    dc_ip_edit: object
    performance_label: object
    pool_size_label: object
    pool_size_spin: object
    buffer_kb_label: object
    buffer_kb_spin: object
    proxy_protocol_toggle: object
    manual_section_label: object
    instructions_card: object
    instr1_label: object
    instr2_label: object
    manual_host_port_label: object


@dataclass(slots=True)
class TelegramProxyAdvancedSettingsWidgets:
    advanced_card: object
    upstream_card: object
    mtproxy_secret_row: object
    mtproxy_secret_label: object
    mtproxy_secret_edit: object
    mtproxy_generate_btn: object
    fake_tls_domain_row: object
    fake_tls_domain_label: object
    fake_tls_domain_edit: object
    fake_tls_nginx_btn: object
    upstream_desc_label: object
    upstream_toggle: object
    upstream_catalog: object
    upstream_preset_row: object
    upstream_runtime_state_label: object
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
    upstream_udp_toggle: object
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
    dc_ip_row: object
    dc_ip_label: object
    dc_ip_edit: object
    performance_label: object
    pool_size_label: object
    pool_size_spin: object
    buffer_kb_label: object
    buffer_kb_spin: object
    proxy_protocol_toggle: object
    manual_section_label: object
    instructions_card: object
    instr1_label: object
    instr2_label: object
    manual_host_port_label: object


def _insert_before_trailing_stretch(layout: QVBoxLayout, widget) -> None:
    index = max(layout.count() - 1, 0)
    layout.insertWidget(index, widget)


def _set_spinbox_value_accessibility(spinbox, *, name: str, description: str) -> None:
    def _sync(value=None) -> None:
        if value is None:
            try:
                value = spinbox.value()
            except Exception:
                value = ""
        state = f"{name}, значение: {value}"
        set_control_accessibility(spinbox, name=state, description=description)
        set_state_text(spinbox, state)

    _sync()
    if bool(getattr(spinbox, "_telegram_proxy_accessibility_value_connected", False)):
        return
    try:
        spinbox.valueChanged.connect(_sync)
        setattr(spinbox, "_telegram_proxy_accessibility_value_connected", True)
    except Exception:
        pass


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
    on_open_zastogram,
    on_open_mtproxy,
    on_generate_mtproxy_secret,
    on_copy_fake_tls_nginx_config,
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
    set_control_accessibility(
        setup_open_btn,
        name="Открыть Telegram Proxy в Telegram",
        description="Открывает ссылку для автоматической настройки прокси внутри Telegram.",
    )
    set_state_text(setup_open_btn, "Открыть Telegram Proxy в Telegram")
    setup_open_btn.clicked.connect(on_open_in_telegram)
    setup_card.add_button(setup_open_btn)

    setup_copy_btn = push_button_cls("Копировать", icon=FluentIcon.COPY)
    setup_copy_btn.setMinimumWidth(132)
    set_tooltip(setup_copy_btn, "Сохранить ссылку в буфер обмена, если Telegram не открылся автоматически.")
    set_control_accessibility(
        setup_copy_btn,
        name="Копировать ссылку Telegram Proxy",
        description="Сохраняет ссылку Telegram Proxy в буфер обмена, если Telegram не открылся автоматически.",
    )
    set_state_text(setup_copy_btn, "Копировать ссылку Telegram Proxy")
    setup_copy_btn.clicked.connect(on_copy_link)
    setup_card.add_button(setup_copy_btn)

    setup_zastogram_btn = push_button_cls("Zastogram", icon=FluentIcon.GITHUB)
    setup_zastogram_btn.setMinimumWidth(132)
    set_tooltip(setup_zastogram_btn, "Открыть страницу ZaStoGram Desktop на GitHub.")
    set_control_accessibility(
        setup_zastogram_btn,
        name="Открыть ZaStoGram Desktop на GitHub",
        description="Открывает страницу проекта ZaStoGram Desktop на GitHub в браузере.",
    )
    set_state_text(setup_zastogram_btn, "Открыть ZaStoGram Desktop на GitHub")
    setup_zastogram_btn.clicked.connect(on_open_zastogram)
    setup_card.add_button(setup_zastogram_btn)

    layout.addWidget(setup_card)

    setup_fallback_label = caption_label_cls(text.setup_fallback)
    setup_fallback_label.setWordWrap(True)
    setup_fallback_label.setVisible(bool(text.setup_fallback))
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
    remove_line_edit_buttons_from_tab_order(host_edit)
    set_control_accessibility(
        host_edit,
        name="Адрес Telegram Proxy",
        description=(
            "IP-адрес для прослушивания Telegram Proxy. 127.0.0.1 — только локально, "
            "0.0.0.0 или IP вашей сети — доступ с других устройств."
        ),
    )
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
    _set_spinbox_value_accessibility(
        port_spin,
        name="Порт Telegram Proxy",
        description="Порт, на котором Telegram Proxy принимает подключения.",
    )
    host_port_row.addWidget(port_spin)
    host_port_row.addStretch()
    insert_widget_into_setting_card_group(settings_card, 1, settings_host_row)

    proxy_mode_row = win11_combo_row_cls(
        icon_name="mdi.swap-horizontal",
        title=text.proxy_mode_title,
        description=text.proxy_mode_description,
        items=[
            ("SOCKS5 (рекомендуется)", "socks5"),
            ("MTProxy (продвинутый)", "mtproxy"),
        ],
    )
    proxy_mode_row.combo.setFixedWidth(250)
    settings_card.addSettingCard(proxy_mode_row)

    auto_deeplink_toggle = win11_toggle_row_cls(
        "mdi.telegram",
        text.auto_setup_title,
        text.auto_setup_description,
    )
    auto_deeplink_toggle.setChecked(True)
    settings_card.addSettingCard(auto_deeplink_toggle)

    advanced_toggle = win11_toggle_row_cls(
        "mdi.tune-variant",
        text.advanced_title,
        text.advanced_description,
    )
    advanced_toggle.setChecked(False)
    settings_card.addSettingCard(advanced_toggle)
    enable_setting_card_group_auto_height(settings_card)

    layout.addWidget(settings_card)

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
        setup_zastogram_btn=setup_zastogram_btn,
        settings_card=settings_card,
        settings_host_row=settings_host_row,
        host_label=host_label,
        host_edit=host_edit,
        port_label=port_label,
        port_spin=port_spin,
        proxy_mode_row=proxy_mode_row,
        mtproxy_secret_row=None,
        mtproxy_secret_label=None,
        mtproxy_secret_edit=None,
        mtproxy_generate_btn=None,
        fake_tls_domain_row=None,
        fake_tls_domain_label=None,
        fake_tls_domain_edit=None,
        fake_tls_nginx_btn=None,
        auto_deeplink_toggle=auto_deeplink_toggle,
        advanced_toggle=advanced_toggle,
        advanced_card=None,
        upstream_card=None,
        upstream_desc_label=None,
        upstream_toggle=None,
        upstream_catalog=upstream_catalog,
        upstream_preset_row=None,
        upstream_runtime_state_label=None,
        upstream_catalog_hint=None,
        upstream_manual_widget=None,
        upstream_host_label=None,
        upstream_host_edit=None,
        upstream_port_label=None,
        upstream_port_spin=None,
        upstream_user_label=None,
        upstream_user_edit=None,
        upstream_pass_label=None,
        upstream_pass_edit=None,
        mtproxy_action_btn=None,
        mtproxy_action_widget=None,
        upstream_mode_toggle=None,
        upstream_udp_toggle=None,
        cloudflare_toggle=None,
        cloudflare_domains_row=None,
        cloudflare_domains_label=None,
        cloudflare_domains_edit=None,
        cloudflare_test_btn=None,
        cloudflare_dns_btn=None,
        cloudflare_worker_toggle=None,
        cloudflare_worker_domains_row=None,
        cloudflare_worker_domains_label=None,
        cloudflare_worker_domains_edit=None,
        cloudflare_worker_test_btn=None,
        cloudflare_worker_code_btn=None,
        dc_ip_row=None,
        dc_ip_label=None,
        dc_ip_edit=None,
        performance_label=None,
        pool_size_label=None,
        pool_size_spin=None,
        buffer_kb_label=None,
        buffer_kb_spin=None,
        proxy_protocol_toggle=None,
        manual_section_label=None,
        instructions_card=None,
        instr1_label=None,
        instr2_label=None,
        manual_host_port_label=None,
    )


def build_telegram_proxy_advanced_settings_panel(
    layout: QVBoxLayout,
    *,
    content_parent,
    strong_body_label_cls,
    caption_label_cls,
    body_label_cls,
    push_button_cls,
    setting_card_group_cls,
    line_edit_cls,
    spin_box_cls,
    password_line_edit_cls,
    win11_toggle_row_cls,
    win11_combo_row_cls,
    on_open_mtproxy,
    on_generate_mtproxy_secret,
    on_copy_fake_tls_nginx_config,
    on_test_cloudflare,
    on_copy_cloudflare_dns,
    on_test_cloudflare_worker,
    on_copy_cloudflare_worker_code,
    upstream_catalog,
) -> TelegramProxyAdvancedSettingsWidgets:
    text = TELEGRAM_PROXY_SETTINGS_TEXT
    advanced_card = setting_card_group_cls(text.advanced_title, content_parent)
    advanced_card.setVisible(False)

    mtproxy_secret_row = QWidget(advanced_card)
    mtproxy_secret_layout = QHBoxLayout(mtproxy_secret_row)
    mtproxy_secret_layout.setContentsMargins(16, 8, 16, 6)
    mtproxy_secret_layout.setSpacing(12)
    mtproxy_secret_label = body_label_cls("Secret:")
    mtproxy_secret_layout.addWidget(mtproxy_secret_label)
    mtproxy_secret_edit = line_edit_cls()
    mtproxy_secret_edit.setMinimumWidth(280)
    mtproxy_secret_edit.setPlaceholderText("32 символа: 0-9 и a-f")
    mtproxy_secret_edit.setClearButtonEnabled(True)
    remove_line_edit_buttons_from_tab_order(mtproxy_secret_edit)
    set_tooltip(mtproxy_secret_edit, "Секрет MTProxy. Telegram использует его как ключ подключения.")
    set_control_accessibility(
        mtproxy_secret_edit,
        name="Secret MTProxy",
        description="Секрет MTProxy. Telegram использует его как ключ подключения.",
    )
    mtproxy_secret_layout.addWidget(mtproxy_secret_edit)
    mtproxy_generate_btn = push_button_cls("Создать", icon=FluentIcon.SYNC)
    mtproxy_generate_btn.setMinimumWidth(120)
    set_tooltip(mtproxy_generate_btn, "Создать новый случайный secret для MTProxy.")
    set_control_accessibility(
        mtproxy_generate_btn,
        name="Создать secret MTProxy",
        description="Создать новый случайный secret для MTProxy.",
    )
    mtproxy_generate_btn.clicked.connect(on_generate_mtproxy_secret)
    mtproxy_secret_layout.addWidget(mtproxy_generate_btn)
    mtproxy_secret_layout.addStretch()
    mtproxy_secret_row.setVisible(False)
    advanced_card.addSettingCard(mtproxy_secret_row)

    fake_tls_domain_row = QWidget(advanced_card)
    fake_tls_domain_layout = QHBoxLayout(fake_tls_domain_row)
    fake_tls_domain_layout.setContentsMargins(16, 8, 16, 6)
    fake_tls_domain_layout.setSpacing(12)
    fake_tls_domain_label = body_label_cls("Fake TLS:")
    fake_tls_domain_layout.addWidget(fake_tls_domain_label)
    fake_tls_domain_edit = line_edit_cls()
    fake_tls_domain_edit.setMinimumWidth(280)
    fake_tls_domain_edit.setPlaceholderText("front.example.com")
    fake_tls_domain_edit.setClearButtonEnabled(True)
    remove_line_edit_buttons_from_tab_order(fake_tls_domain_edit)
    set_tooltip(fake_tls_domain_edit, "Домен для MTProxy Fake TLS. Оставьте пустым, если Fake TLS не нужен.")
    set_control_accessibility(
        fake_tls_domain_edit,
        name="Домен MTProxy Fake TLS",
        description="Домен для MTProxy Fake TLS. Оставьте пустым, если Fake TLS не нужен.",
    )
    fake_tls_domain_layout.addWidget(fake_tls_domain_edit)
    fake_tls_nginx_btn = push_button_cls("Nginx", icon=FluentIcon.COPY)
    fake_tls_nginx_btn.setMinimumWidth(96)
    set_tooltip(fake_tls_nginx_btn, "Скопировать stream-конфиг Nginx для MTProxy Fake TLS.")
    set_control_accessibility(
        fake_tls_nginx_btn,
        name="Скопировать Nginx-конфиг MTProxy Fake TLS",
        description="Скопировать stream-конфиг Nginx для MTProxy Fake TLS.",
    )
    fake_tls_nginx_btn.clicked.connect(on_copy_fake_tls_nginx_config)
    fake_tls_domain_layout.addWidget(fake_tls_nginx_btn)
    fake_tls_domain_layout.addStretch()
    fake_tls_domain_row.setVisible(False)
    advanced_card.addSettingCard(fake_tls_domain_row)

    proxy_protocol_toggle = win11_toggle_row_cls(
        "mdi.lan-connect",
        text.proxy_protocol_title,
        text.proxy_protocol_description,
    )
    proxy_protocol_toggle.setChecked(False)
    proxy_protocol_toggle.setVisible(False)
    advanced_card.addSettingCard(proxy_protocol_toggle)

    upstream_card = advanced_card

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

    upstream_runtime_state_label = caption_label_cls("Сейчас используется: будет выбран после запуска")
    upstream_runtime_state_label.setWordWrap(True)
    upstream_runtime_state_label.setContentsMargins(16, 0, 16, 4)
    upstream_runtime_state_label.setVisible(False)
    preset_index = upstream_card.vBoxLayout.indexOf(upstream_preset_row)
    insert_widget_into_setting_card_group(
        upstream_card,
        preset_index + 1 if preset_index >= 0 else 2,
        upstream_runtime_state_label,
    )

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
    remove_line_edit_buttons_from_tab_order(upstream_host_edit)
    set_control_accessibility(
        upstream_host_edit,
        name="Хост upstream-прокси Telegram Proxy",
        description="Введите IP-адрес или домен upstream-прокси для Telegram Proxy.",
    )
    upstream_hp_row.addWidget(upstream_host_edit)
    upstream_hp_row.addSpacing(16)
    upstream_port_label = body_label_cls("Порт:")
    upstream_hp_row.addWidget(upstream_port_label)
    upstream_port_spin = spin_box_cls()
    upstream_port_spin.setRange(1, 65535)
    upstream_port_spin.setValue(1080)
    upstream_port_spin.setFixedWidth(140)
    _set_spinbox_value_accessibility(
        upstream_port_spin,
        name="Порт upstream-прокси Telegram Proxy",
        description="Введите порт upstream-прокси для Telegram Proxy.",
    )
    upstream_hp_row.addWidget(upstream_port_spin)
    upstream_hp_row.addStretch()
    manual_layout.addLayout(upstream_hp_row)

    upstream_auth_row = QHBoxLayout()
    upstream_user_label = body_label_cls("Логин:")
    upstream_auth_row.addWidget(upstream_user_label)
    upstream_user_edit = line_edit_cls()
    upstream_user_edit.setMinimumWidth(200)
    upstream_user_edit.setPlaceholderText("username")
    set_control_accessibility(
        upstream_user_edit,
        name="Логин upstream-прокси Telegram Proxy",
        description="Введите логин upstream-прокси, если он нужен.",
    )
    upstream_auth_row.addWidget(upstream_user_edit)
    upstream_auth_row.addSpacing(16)
    upstream_pass_label = body_label_cls("Пароль:")
    upstream_auth_row.addWidget(upstream_pass_label)
    upstream_pass_edit = password_line_edit_cls()
    upstream_pass_edit.setMinimumWidth(200)
    upstream_pass_edit.setPlaceholderText("password")
    set_control_accessibility(
        upstream_pass_edit,
        name="Пароль upstream-прокси Telegram Proxy",
        description="Введите пароль upstream-прокси, если он нужен.",
    )
    upstream_auth_row.addWidget(upstream_pass_edit)
    upstream_auth_row.addStretch()
    manual_layout.addLayout(upstream_auth_row)

    upstream_manual_widget.setVisible(True)
    upstream_card.addSettingCard(upstream_manual_widget)

    mtproxy_action_btn = push_button_cls("Открыть", icon=FluentIcon.SEND)
    mtproxy_action_btn.setMinimumWidth(132)
    set_tooltip(mtproxy_action_btn, "MTProxy настраивается в Telegram напрямую. Нажмите для добавления.")
    set_control_accessibility(
        mtproxy_action_btn,
        name="Открыть MTProxy в Telegram",
        description="Открывает ссылку для добавления MTProxy в Telegram.",
    )
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

    upstream_udp_toggle = win11_toggle_row_cls(
        "mdi.phone-in-talk",
        text.upstream_udp_title,
        text.upstream_udp_description,
    )
    upstream_udp_toggle.setChecked(False)
    upstream_card.addSettingCard(upstream_udp_toggle)

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
    remove_line_edit_buttons_from_tab_order(cloudflare_domains_edit)
    set_tooltip(cloudflare_domains_edit, "Cloudflare-домены для запасного WSS-пути. Оставьте пустым для авто-списка.")
    set_control_accessibility(
        cloudflare_domains_edit,
        name="Домены Cloudflare для Telegram Proxy",
        description="Cloudflare-домены для запасного WSS-пути. Оставьте пустым для авто-списка.",
    )
    cloudflare_domains_layout.addWidget(cloudflare_domains_edit)
    cloudflare_test_btn = push_button_cls("Проверить", icon=FluentIcon.SEARCH)
    cloudflare_test_btn.setMinimumWidth(116)
    set_tooltip(cloudflare_test_btn, "Проверить, отвечает ли ваш Cloudflare-домен для Telegram.")
    set_control_accessibility(
        cloudflare_test_btn,
        name="Проверить Cloudflare-домен Telegram Proxy",
        description="Проверить, отвечает ли ваш Cloudflare-домен для Telegram.",
    )
    cloudflare_test_btn.clicked.connect(on_test_cloudflare)
    cloudflare_domains_layout.addWidget(cloudflare_test_btn)
    cloudflare_dns_btn = push_button_cls("DNS", icon=FluentIcon.COPY)
    cloudflare_dns_btn.setMinimumWidth(84)
    set_tooltip(cloudflare_dns_btn, "Скопировать DNS-записи kws1, kws2, kws3, kws4, kws5 и kws203.")
    set_control_accessibility(
        cloudflare_dns_btn,
        name="Скопировать DNS-записи Cloudflare Telegram Proxy",
        description="Скопировать DNS-записи kws1, kws2, kws3, kws4, kws5 и kws203.",
    )
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
    remove_line_edit_buttons_from_tab_order(cloudflare_worker_domains_edit)
    set_tooltip(cloudflare_worker_domains_edit, "Домены Cloudflare Worker для отдельного запасного пути.")
    set_control_accessibility(
        cloudflare_worker_domains_edit,
        name="Домены Cloudflare Worker для Telegram Proxy",
        description="Домены Cloudflare Worker для отдельного запасного пути Telegram Proxy.",
    )
    cloudflare_worker_domains_layout.addWidget(cloudflare_worker_domains_edit)
    cloudflare_worker_test_btn = push_button_cls("Проверить", icon=FluentIcon.SEARCH)
    cloudflare_worker_test_btn.setMinimumWidth(116)
    set_tooltip(cloudflare_worker_test_btn, "Проверить, отвечает ли ваш Cloudflare Worker.")
    set_control_accessibility(
        cloudflare_worker_test_btn,
        name="Проверить Cloudflare Worker Telegram Proxy",
        description="Проверить, отвечает ли ваш Cloudflare Worker.",
    )
    cloudflare_worker_test_btn.clicked.connect(on_test_cloudflare_worker)
    cloudflare_worker_domains_layout.addWidget(cloudflare_worker_test_btn)
    cloudflare_worker_code_btn = push_button_cls("Код Worker", icon=FluentIcon.COPY)
    cloudflare_worker_code_btn.setMinimumWidth(120)
    set_tooltip(cloudflare_worker_code_btn, "Скопировать готовый код для Cloudflare Worker.")
    set_control_accessibility(
        cloudflare_worker_code_btn,
        name="Скопировать код Cloudflare Worker",
        description="Скопировать готовый код для Cloudflare Worker.",
    )
    cloudflare_worker_code_btn.clicked.connect(on_copy_cloudflare_worker_code)
    cloudflare_worker_domains_layout.addWidget(cloudflare_worker_code_btn)
    cloudflare_worker_domains_layout.addStretch()
    cloudflare_worker_domains_row.setVisible(False)
    upstream_card.addSettingCard(cloudflare_worker_domains_row)

    dc_ip_row = QWidget(upstream_card)
    dc_ip_layout = QHBoxLayout(dc_ip_row)
    dc_ip_layout.setContentsMargins(16, 8, 16, 6)
    dc_ip_layout.setSpacing(12)
    dc_ip_label = body_label_cls("DC -> IP:")
    dc_ip_layout.addWidget(dc_ip_label)
    dc_ip_edit = line_edit_cls()
    dc_ip_edit.setMinimumWidth(360)
    dc_ip_edit.setPlaceholderText("4:149.154.167.220, 5:91.108.56.100")
    dc_ip_edit.setClearButtonEnabled(True)
    remove_line_edit_buttons_from_tab_order(dc_ip_edit)
    set_tooltip(dc_ip_edit, "Ручные адреса дата-центров Telegram. Формат: номер:IP, через запятую.")
    set_control_accessibility(
        dc_ip_edit,
        name="Ручные адреса Telegram DC",
        description="Введите номер дата-центра и IP-адрес в формате номер:IP, через запятую.",
    )
    dc_ip_layout.addWidget(dc_ip_edit)
    dc_ip_layout.addStretch()
    upstream_card.addSettingCard(dc_ip_row)

    performance_label = caption_label_cls(text.performance_description)
    performance_label.setWordWrap(True)
    performance_label_index = upstream_card.vBoxLayout.count() if getattr(upstream_card, "vBoxLayout", None) else 1
    insert_widget_into_setting_card_group(upstream_card, performance_label_index, performance_label)

    performance_row = QWidget(upstream_card)
    performance_layout = QHBoxLayout(performance_row)
    performance_layout.setContentsMargins(16, 8, 16, 6)
    performance_layout.setSpacing(12)
    pool_size_label = body_label_cls("Пул WSS:")
    performance_layout.addWidget(pool_size_label)
    pool_size_spin = spin_box_cls()
    pool_size_spin.setRange(0, 32)
    pool_size_spin.setValue(4)
    pool_size_spin.setFixedWidth(120)
    set_tooltip(pool_size_spin, "Сколько запасных WSS-соединений держать в пуле. 4 — обычное значение.")
    _set_spinbox_value_accessibility(
        pool_size_spin,
        name="Пул WSS Telegram Proxy",
        description="Сколько запасных WSS-соединений держать в пуле. 4 — обычное значение.",
    )
    performance_layout.addWidget(pool_size_spin)
    performance_layout.addSpacing(16)
    buffer_kb_label = body_label_cls("Буфер, КБ:")
    performance_layout.addWidget(buffer_kb_label)
    buffer_kb_spin = spin_box_cls()
    buffer_kb_spin.setRange(4, 4096)
    buffer_kb_spin.setValue(256)
    buffer_kb_spin.setFixedWidth(120)
    set_tooltip(buffer_kb_spin, "Размер сетевого буфера. 256 КБ обычно достаточно.")
    _set_spinbox_value_accessibility(
        buffer_kb_spin,
        name="Размер буфера Telegram Proxy",
        description="Размер сетевого буфера. 256 КБ обычно достаточно.",
    )
    performance_layout.addWidget(buffer_kb_spin)
    performance_layout.addStretch()
    upstream_card.addSettingCard(performance_row)

    enable_setting_card_group_auto_height(upstream_card)

    _insert_before_trailing_stretch(layout, upstream_card)

    manual_section_label = strong_body_label_cls(text.manual_hidden_title)
    manual_section_label.setVisible(False)
    _insert_before_trailing_stretch(layout, manual_section_label)

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

    _insert_before_trailing_stretch(layout, instructions_card)
    instructions_card.setVisible(False)

    return TelegramProxyAdvancedSettingsWidgets(
        advanced_card=advanced_card,
        upstream_card=upstream_card,
        mtproxy_secret_row=mtproxy_secret_row,
        mtproxy_secret_label=mtproxy_secret_label,
        mtproxy_secret_edit=mtproxy_secret_edit,
        mtproxy_generate_btn=mtproxy_generate_btn,
        fake_tls_domain_row=fake_tls_domain_row,
        fake_tls_domain_label=fake_tls_domain_label,
        fake_tls_domain_edit=fake_tls_domain_edit,
        fake_tls_nginx_btn=fake_tls_nginx_btn,
        upstream_desc_label=upstream_desc_label,
        upstream_toggle=upstream_toggle,
        upstream_catalog=upstream_catalog,
        upstream_preset_row=upstream_preset_row,
        upstream_runtime_state_label=upstream_runtime_state_label,
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
        upstream_udp_toggle=upstream_udp_toggle,
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
        dc_ip_row=dc_ip_row,
        dc_ip_label=dc_ip_label,
        dc_ip_edit=dc_ip_edit,
        performance_label=performance_label,
        pool_size_label=pool_size_label,
        pool_size_spin=pool_size_spin,
        buffer_kb_label=buffer_kb_label,
        buffer_kb_spin=buffer_kb_spin,
        proxy_protocol_toggle=proxy_protocol_toggle,
        manual_section_label=manual_section_label,
        instructions_card=instructions_card,
        instr1_label=instr1_label,
        instr2_label=instr2_label,
        manual_host_port_label=manual_host_port_label,
    )
