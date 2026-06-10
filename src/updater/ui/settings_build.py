"""Build-helper settings and Telegram sections for Servers page."""

from __future__ import annotations

from dataclasses import dataclass

from ui.accessibility import set_control_accessibility, set_state_text
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


def _label_text(label) -> str:
    try:
        value = label.text()
    except Exception:
        value = getattr(label, "text", "")
    return " ".join(str(value or "").strip().split())


def set_auto_check_accessibility(
    widget,
    *,
    title: str,
    description: str,
    checked: bool | None = None,
) -> None:
    title_value = str(title or "").strip()
    if checked is None:
        try:
            checked = bool(widget.isChecked())
        except Exception:
            checked = None
    if checked is None:
        name = title_value
    else:
        state = "включено" if bool(checked) else "выключено"
        name = f"{title_value}, {state}".strip(", ")
    set_control_accessibility(widget, name=name, description=description)
    set_state_text(widget, name)


def build_servers_settings_section(
    *,
    content_parent,
    tr_fn,
    accent_hex: str,
    auto_check_enabled: bool,
    app_version: str,
    channel: str,
    setting_card_group_cls,
    settings_card_cls,
    win11_toggle_row_cls,
    caption_label_cls,
    qhbox_layout_cls,
    on_auto_check_toggled,
) -> ServersSettingsWidgets:
    settings_card = setting_card_group_cls(tr_fn("page.servers.settings.title", "Настройки"), content_parent)

    auto_check_title = tr_fn("page.servers.settings.auto_check", "Проверять обновления при запуске")
    auto_check_description = tr_fn(
        "page.servers.settings.auto_check.description",
        "Автоматически проверять наличие обновлений при старте приложения.",
    )
    auto_check_card = win11_toggle_row_cls(
        "fa5s.sync-alt",
        auto_check_title,
        auto_check_description,
        accent_hex,
    )
    auto_check_card.setChecked(auto_check_enabled, block_signals=True)
    set_auto_check_accessibility(
        auto_check_card,
        title=auto_check_title,
        description=auto_check_description,
        checked=auto_check_enabled,
    )
    auto_check_card.toggled.connect(on_auto_check_toggled)
    auto_check_toggle = auto_check_card
    settings_card.addSettingCard(auto_check_card)

    _ = settings_card_cls, qhbox_layout_cls
    version_info_label = caption_label_cls(
        tr_fn("page.servers.settings.version_channel_template", "v{version} · {channel}").format(
            version=app_version,
            channel=channel,
        )
    )
    set_state_text(version_info_label, f"Версия ZapretGUI: {_label_text(version_info_label)}")
    toggle_label = None

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
    push_setting_card_cls,
    on_open_channel,
) -> ServersTelegramWidgets:
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
    telegram_action_name = tr_fn(
        "page.servers.telegram.accessible_name",
        "Открыть Telegram канал обновлений",
    )
    telegram_action_description = tr_fn(
        "page.servers.telegram.accessible_description",
        "Открывает Telegram канал, где публикуются версии программы и новости обновлений.",
    )
    set_control_accessibility(tg_card, name=telegram_action_name, description=telegram_action_description)
    set_control_accessibility(tg_btn, name=telegram_action_name, description=telegram_action_description)

    return ServersTelegramWidgets(
        card=tg_card,
        info_label=tg_info_label,
        button=tg_btn,
    )
