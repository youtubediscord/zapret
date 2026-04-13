"""Build-helper settings and Telegram sections for Servers page."""

from __future__ import annotations

from dataclasses import dataclass

from ui.theme import get_themed_qta_icon


@dataclass(slots=True)
class ServersSettingsWidgets:
    card: object
    auto_check_card: object | None
    auto_check_toggle: object
    toggle_label: object | None
    version_info_label: object


@dataclass(slots=True)
class ServersTelegramWidgets:
    card: object
    info_label: object | None
    button: object


def build_servers_settings_section(
    *,
    content_parent,
    tr_fn,
    accent_hex: str,
    auto_check_enabled: bool,
    app_version: str,
    channel: str,
    has_fluent: bool,
    setting_card_group_cls,
    settings_card_cls,
    win11_toggle_row_cls,
    switch_button_cls,
    body_label_cls,
    caption_label_cls,
    qhbox_layout_cls,
    qvbox_layout_cls,
    on_auto_check_toggled,
) -> ServersSettingsWidgets:
    if setting_card_group_cls is not None and has_fluent:
        settings_card = setting_card_group_cls(tr_fn("page.servers.settings.title", "Настройки"), content_parent)

        auto_check_card = win11_toggle_row_cls(
            "fa5s.sync-alt",
            tr_fn("page.servers.settings.auto_check", "Проверять обновления при запуске"),
            tr_fn(
                "page.servers.settings.auto_check.description",
                "Автоматически проверять наличие обновлений при старте приложения.",
            ),
            accent_hex,
        )
        auto_check_card.setChecked(auto_check_enabled, block_signals=True)
        auto_check_card.toggled.connect(on_auto_check_toggled)
        auto_check_toggle = auto_check_card.toggle
        settings_card.addSettingCard(auto_check_card)

        version_card = settings_card_cls()
        version_layout = qhbox_layout_cls()
        version_layout.setContentsMargins(10, 6, 12, 6)
        version_layout.setSpacing(8)
        version_info_label = caption_label_cls(
            tr_fn("page.servers.settings.version_channel_template", "v{version} · {channel}").format(
                version=app_version,
                channel=channel,
            )
        )
        version_layout.addWidget(version_info_label)
        version_layout.addStretch()
        version_card.add_layout(version_layout)
        settings_card.addSettingCard(version_card)
        toggle_label = None
    else:
        settings_card = settings_card_cls(tr_fn("page.servers.settings.title", "Настройки"))
        settings_layout = qvbox_layout_cls()
        settings_layout.setSpacing(12)

        toggle_row = qhbox_layout_cls()
        toggle_row.setSpacing(12)

        auto_check_toggle = switch_button_cls()
        auto_check_toggle.setChecked(auto_check_enabled)
        if has_fluent:
            auto_check_toggle.checkedChanged.connect(on_auto_check_toggled)
        else:
            auto_check_toggle.toggled.connect(on_auto_check_toggled)
        toggle_row.addWidget(auto_check_toggle)

        toggle_label = body_label_cls(
            tr_fn("page.servers.settings.auto_check", "Проверять обновления при запуске")
        )
        toggle_row.addWidget(toggle_label)
        toggle_row.addStretch()

        version_info_label = caption_label_cls(
            tr_fn("page.servers.settings.version_channel_template", "v{version} · {channel}").format(
                version=app_version,
                channel=channel,
            )
        )
        toggle_row.addWidget(version_info_label)

        settings_layout.addLayout(toggle_row)
        settings_card.add_layout(settings_layout)
        auto_check_card = None

    return ServersSettingsWidgets(
        card=settings_card,
        auto_check_card=auto_check_card,
        auto_check_toggle=auto_check_toggle,
        toggle_label=toggle_label,
        version_info_label=version_info_label,
    )


def build_servers_telegram_section(
    *,
    tr_fn,
    accent_hex: str,
    has_fluent: bool,
    push_setting_card_cls,
    settings_card_cls,
    body_label_cls,
    action_button_cls,
    qta_module,
    qhbox_layout_cls,
    qvbox_layout_cls,
    on_open_channel,
) -> ServersTelegramWidgets:
    if push_setting_card_cls is not None and has_fluent:
        tg_info_label = None
        tg_card = push_setting_card_cls(
            tr_fn("page.servers.telegram.button.open_channel", "Открыть Telegram канал"),
            get_themed_qta_icon("fa5b.telegram-plane", color=accent_hex),
            tr_fn("page.servers.telegram.title", "Проблемы с обновлением?"),
            tr_fn(
                "page.servers.telegram.info",
                "Если возникают трудности с автоматическим обновлением, все версии программы выкладываются в Telegram канале.",
            ),
        )
        tg_card.clicked.connect(on_open_channel)
        tg_btn = tg_card.button
    else:
        tg_card = settings_card_cls(tr_fn("page.servers.telegram.title", "Проблемы с обновлением?"))
        tg_layout = qvbox_layout_cls()
        tg_layout.setSpacing(12)

        tg_info_label = body_label_cls(
            tr_fn(
                "page.servers.telegram.info",
                "Если возникают трудности с автоматическим обновлением, все версии программы выкладываются в Telegram канале.",
            )
        )
        tg_info_label.setWordWrap(True)
        tg_layout.addWidget(tg_info_label)

        tg_btn_row = qhbox_layout_cls()
        tg_btn = action_button_cls(
            tr_fn("page.servers.telegram.button.open_channel", "Открыть Telegram канал"),
            "fa5b.telegram-plane",
        )
        tg_btn.clicked.connect(on_open_channel)
        tg_btn_row.addWidget(tg_btn)
        tg_btn_row.addStretch()

        tg_layout.addLayout(tg_btn_row)
        tg_card.add_layout(tg_layout)

    return ServersTelegramWidgets(
        card=tg_card,
        info_label=tg_info_label,
        button=tg_btn,
    )
