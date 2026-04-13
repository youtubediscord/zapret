"""Helper-слой обновления текстов Servers page при смене языка."""

from __future__ import annotations

from config.build_info import APP_VERSION, CHANNEL


from updater.ui.table_workflow import apply_server_table_headers


def apply_servers_page_language(
    *,
    tr_fn,
    ui_language: str,
    update_card,
    changelog_card,
    back_button,
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

    back_button.setText(tr_fn("page.servers.back.about", "О программе"))
    page_title_label.setText(tr_fn("page.servers.title", "Серверы"))
    servers_title_label.setText(tr_fn("page.servers.section.update_servers", "Серверы обновлений"))
    legend_active_label.setText(tr_fn("page.servers.legend.active", "⭐ активный"))
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
        auto_check_card.set_texts(
            tr_fn("page.servers.settings.auto_check", "Проверять обновления при запуске"),
            tr_fn(
                "page.servers.settings.auto_check.description",
                "Автоматически проверять наличие обновлений при старте приложения.",
            ),
        )

    version_info_label.setText(
        tr_fn("page.servers.settings.version_channel_template", "v{version} · {channel}").format(
            version=APP_VERSION,
            channel=CHANNEL,
        )
    )

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

    refresh_server_rows()
