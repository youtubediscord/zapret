"""Build-helper настроечной панели Telegram Proxy page."""

from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout

from ui.fluent_widgets import (
    SettingsCard,
    QuickActionsBar,
    enable_setting_card_group_auto_height,
    insert_widget_into_setting_card_group,
)
from telegram_proxy.upstream_catalog import UpstreamCatalog
from ui.theme import get_themed_qta_icon


@dataclass(slots=True)
class TelegramProxySettingsPanelWidgets:
    status_card: object
    status_dot: object
    status_label: object
    btn_toggle: object
    stats_label: object
    setup_section_label: object
    setup_desc_label: object
    setup_card: object
    setup_open_btn: object
    setup_copy_btn: object
    settings_card: object
    settings_host_row: object
    host_label: object
    host_edit: object
    port_label: object
    port_spin: object
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
) -> TelegramProxySettingsPanelWidgets:
    status_card = SettingsCard()

    status_header = QHBoxLayout()
    status_dot = status_dot_cls()
    status_label = strong_body_label_cls("Остановлен")
    status_header.addWidget(status_dot)
    status_header.addWidget(status_label)
    status_header.addStretch()

    btn_toggle = push_button_cls()
    btn_toggle.setText("Запустить")
    btn_toggle.setFixedWidth(140)
    btn_toggle.clicked.connect(on_toggle_proxy)
    status_header.addWidget(btn_toggle)
    status_card.add_layout(status_header)

    stats_label = caption_label_cls("")
    status_card.add_widget(stats_label)
    layout.addWidget(status_card)

    setup_section_label = strong_body_label_cls("Быстрая настройка Telegram")
    layout.addWidget(setup_section_label)

    setup_desc_label = caption_label_cls(
        "Нажмите кнопку ниже - Telegram автоматически добавит прокси. "
        "Настройка требуется один раз.\nЕсли Telegram не открывается попробуйте скопировать ссылку и отправить в любой чат Telegram или кому-то в ЛС — после чего нажмите на отправленную ссылку и подтвердите добавление прокси в Telegram клиент.\nРекомендуем полностью ПЕРЕЗАПУСТИТЬ клиент для более корректного работа прокси после включения Zapret 2 GUI!"
    )
    setup_desc_label.setWordWrap(True)
    layout.addWidget(setup_desc_label)

    setup_card = QuickActionsBar(content_parent)

    setup_open_btn = primary_push_button_cls()
    setup_open_btn.setText("Открыть")
    setup_open_btn.setIcon(get_themed_qta_icon("mdi.telegram", color="#229ED9"))
    setup_open_btn.setToolTip("Открыть ссылку для автоматической настройки прокси внутри Telegram.")
    setup_open_btn.clicked.connect(on_open_in_telegram)
    setup_card.add_button(setup_open_btn)

    setup_copy_btn = push_button_cls()
    setup_copy_btn.setText("Копировать")
    setup_copy_btn.setIcon(get_themed_qta_icon("mdi.content-copy", color="#60cdff"))
    setup_copy_btn.setToolTip("Сохранить ссылку в буфер обмена, если Telegram не открылся автоматически.")
    setup_copy_btn.clicked.connect(on_copy_link)
    setup_card.add_button(setup_copy_btn)

    layout.addWidget(setup_card)

    settings_card = setting_card_group_cls("Настройки", content_parent)
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
    host_edit.setToolTip(
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

    auto_deeplink_toggle = win11_toggle_row_cls(
        "mdi.telegram",
        "Авто-настройка Telegram",
        "При первом запуске прокси автоматически открыть ссылку настройки в Telegram",
    )
    auto_deeplink_toggle.setChecked(True)
    settings_card.addSettingCard(auto_deeplink_toggle)
    enable_setting_card_group_auto_height(settings_card)

    layout.addWidget(settings_card)

    upstream_card = setting_card_group_cls("Внешний прокси (upstream)", content_parent)

    upstream_desc_label = caption_label_cls(
        "SOCKS5 прокси-сервер для DC заблокированных вашим провайдером.\n"
        "Используется как резервный канал когда WSS relay и прямое подключение не работают."
    )
    upstream_desc_label.setWordWrap(True)
    insert_widget_into_setting_card_group(upstream_card, 1, upstream_desc_label)

    upstream_toggle = win11_toggle_row_cls(
        "mdi.server-network",
        "Использовать внешний прокси",
        "Маршрутизировать заблокированные DC через внешний SOCKS5 прокси",
    )
    upstream_toggle.setChecked(False)
    upstream_card.addSettingCard(upstream_toggle)

    upstream_catalog = UpstreamCatalog.load_from_runtime()
    upstream_preset_row = win11_combo_row_cls(
        icon_name="mdi.server-network",
        title="Сервер",
        description="Выберите сервер из списка или переключитесь на ручной ввод",
        items=upstream_catalog.items(),
    )
    upstream_preset_row.combo.setFixedWidth(250)
    upstream_card.addSettingCard(upstream_preset_row)

    upstream_catalog_hint = caption_label_cls(
        "В этой сборке список предустановленных прокси не загружен. "
        "Доступен только ручной ввод."
    )
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

    mtproxy_action_btn = push_button_cls()
    mtproxy_action_btn.setText("Открыть")
    mtproxy_action_btn.setIcon(get_themed_qta_icon("mdi.telegram", color="#229ED9"))
    mtproxy_action_btn.setToolTip("MTProxy настраивается в Telegram напрямую. Нажмите для добавления.")
    mtproxy_action_btn.clicked.connect(on_open_mtproxy)
    mtproxy_action_widget = mtproxy_action_btn
    mtproxy_action_widget.setVisible(False)
    upstream_card.addSettingCard(mtproxy_action_widget)

    upstream_mode_toggle = win11_toggle_row_cls(
        "mdi.swap-horizontal",
        "Весь трафик через прокси",
        "Если выключено — только заблокированные DC. Если включено — весь трафик Telegram.",
    )
    upstream_mode_toggle.setChecked(True)
    upstream_card.addSettingCard(upstream_mode_toggle)
    enable_setting_card_group_auto_height(upstream_card)

    layout.addWidget(upstream_card)

    manual_section_label = strong_body_label_cls("Ручная настройка")
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
    layout.addStretch()

    return TelegramProxySettingsPanelWidgets(
        status_card=status_card,
        status_dot=status_dot,
        status_label=status_label,
        btn_toggle=btn_toggle,
        stats_label=stats_label,
        setup_section_label=setup_section_label,
        setup_desc_label=setup_desc_label,
        setup_card=setup_card,
        setup_open_btn=setup_open_btn,
        setup_copy_btn=setup_copy_btn,
        settings_card=settings_card,
        settings_host_row=settings_host_row,
        host_label=host_label,
        host_edit=host_edit,
        port_label=port_label,
        port_spin=port_spin,
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
        manual_section_label=manual_section_label,
        instructions_card=instructions_card,
        instr1_label=instr1_label,
        instr2_label=instr2_label,
        manual_host_port_label=manual_host_port_label,
    )
