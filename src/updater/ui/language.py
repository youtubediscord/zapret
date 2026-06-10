"""Helper-слой обновления текстов Servers page при смене языка."""

from __future__ import annotations

from config.build_info import APP_VERSION, CHANNEL


from updater.ui.main_build import set_active_server_legend_accessibility
from updater.ui.settings_build import set_auto_check_accessibility
from updater.ui.table_view import apply_server_table_headers
from ui.accessibility import set_control_accessibility, set_state_text


def _label_text(label) -> str:
    try:
        value = label.text()
    except Exception:
        value = getattr(label, "text", "")
    return " ".join(str(value or "").strip().split())


def apply_servers_page_language(
    *,
    tr_fn,
    ui_language: str,
    update_card,
    changelog_card,
    breadcrumb,
    page_title_label,
    servers_title_label,
    legend_active_label,
    servers_table,
    settings_card,
    toggle_label,
    auto_check_card,
    version_info_label,
    telegram_card,
    telegram_info_label,
    telegram_button,
    refresh_server_rows,
) -> None:
    update_card.set_ui_language(ui_language)
    changelog_card.set_ui_language(ui_language)

    breadcrumb.blockSignals(True)
    try:
        breadcrumb.clear()
        breadcrumb.addItem("about", tr_fn("page.servers.breadcrumb.about", "О программе"))
        breadcrumb.addItem("servers", tr_fn("page.servers.title", "Серверы"))
    finally:
        breadcrumb.blockSignals(False)
    page_title_label.setText(tr_fn("page.servers.title", "Серверы"))
    servers_title_label.setText(tr_fn("page.servers.section.update_servers", "Серверы обновлений"))
    legend_active_label.setText(tr_fn("page.servers.legend.active", "⭐ активный"))
    set_active_server_legend_accessibility(legend_active_label)
    apply_server_table_headers(servers_table, tr_fn=tr_fn)

    settings_title = tr_fn("page.servers.settings.title", "Настройки")
    settings_card.set_title(settings_title)
    title_label = getattr(settings_card, "titleLabel", None)
    if title_label is not None:
        title_label.setText(settings_title)

    if toggle_label is not None:
        toggle_label.setText(
            tr_fn("page.servers.settings.auto_check", "Проверять обновления при запуске")
        )

    if auto_check_card is not None:
        auto_check_title = tr_fn("page.servers.settings.auto_check", "Проверять обновления при запуске")
        auto_check_description = tr_fn(
            "page.servers.settings.auto_check.description",
            "Автоматически проверять наличие обновлений при старте приложения.",
        )
        auto_check_card.set_texts(
            auto_check_title,
            auto_check_description,
        )
        set_auto_check_accessibility(
            auto_check_card,
            title=auto_check_title,
            description=auto_check_description,
        )

    version_info_label.setText(
        tr_fn("page.servers.settings.version_channel_template", "v{version} · {channel}").format(
            version=APP_VERSION,
            channel=CHANNEL,
        )
    )
    set_state_text(version_info_label, f"Версия ZapretGUI: {_label_text(version_info_label)}")

    telegram_title = tr_fn("page.servers.telegram.title", "Проблемы с обновлением?")
    telegram_info = tr_fn(
        "page.servers.telegram.info",
        "Если возникают трудности с автоматическим обновлением, все версии программы выкладываются в Telegram канале.",
    )
    telegram_card.set_title(telegram_title)
    if telegram_info_label is not None:
        telegram_info_label.setText(telegram_info)
    else:
        try:
            telegram_card.setContent(telegram_info)
        except Exception:
            pass
    telegram_button.setText(
        tr_fn("page.servers.telegram.button.open_channel", "Открыть Telegram канал")
    )
    telegram_action_name = tr_fn(
        "page.servers.telegram.accessible_name",
        "Открыть Telegram канал обновлений",
    )
    telegram_action_description = tr_fn(
        "page.servers.telegram.accessible_description",
        "Открывает Telegram канал, где публикуются версии программы и новости обновлений.",
    )
    set_control_accessibility(
        telegram_card,
        name=telegram_action_name,
        description=telegram_action_description,
    )
    set_control_accessibility(
        telegram_button,
        name=telegram_action_name,
        description=telegram_action_description,
    )

    refresh_server_rows()
