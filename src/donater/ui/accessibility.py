"""Accessibility helpers for Premium page controls."""

from __future__ import annotations

from ui.accessibility import set_control_accessibility


def apply_premium_button_accessibility(
    *,
    tr_fn,
    activate_btn=None,
    activate_loading: bool = False,
    open_bot_btn=None,
    refresh_btn=None,
    change_key_btn=None,
    test_btn=None,
    test_loading: bool = False,
    extend_btn=None,
) -> None:
    """Задаёт понятные имена Premium-кнопок для экранного диктора."""

    if activate_btn is not None:
        set_control_accessibility(
            activate_btn,
            name=tr_fn(
                "page.premium.action.create_code.accessible_name_loading"
                if activate_loading
                else "page.premium.action.create_code.accessible_name",
                "Создание кода привязки Premium" if activate_loading else "Создать код привязки Premium",
            ),
            description=tr_fn(
                "page.premium.action.create_code.description",
                "Создаёт код, который нужно отправить Premium-боту в Telegram.",
            ),
        )
    if open_bot_btn is not None:
        set_control_accessibility(
            open_bot_btn,
            name=tr_fn("page.premium.action.open_bot.accessible_name", "Открыть Premium-бота"),
            description=tr_fn(
                "page.premium.action.open_bot.description",
                "Открывает Telegram-бота для привязки или продления Premium.",
            ),
        )
    if refresh_btn is not None:
        set_control_accessibility(
            refresh_btn,
            name=tr_fn("page.premium.action.refresh_status.accessible_name", "Обновить Premium-статус"),
            description=tr_fn(
                "page.premium.action.refresh_status.description",
                "Повторно запросить Premium-статус и обновить данные устройства.",
            ),
        )
    if change_key_btn is not None:
        set_control_accessibility(
            change_key_btn,
            name=tr_fn("page.premium.action.reset_activation.accessible_name", "Сбросить Premium-активацию"),
            description=tr_fn(
                "page.premium.action.reset_activation.description",
                "Удаляет токен устройства, офлайн-кэш и код привязки на этом компьютере.",
            ),
        )
    if test_btn is not None:
        set_control_accessibility(
            test_btn,
            name=tr_fn(
                "page.premium.action.test_connection.accessible_name_loading"
                if test_loading
                else "page.premium.action.test_connection.accessible_name",
                "Проверка соединения Premium выполняется" if test_loading else "Проверить соединение Premium",
            ),
            description=tr_fn(
                "page.premium.action.test_connection.description",
                "Проверить доступность Premium backend и соединение с сервером.",
            ),
        )
    if extend_btn is not None:
        set_control_accessibility(
            extend_btn,
            name=tr_fn("page.premium.action.extend.accessible_name", "Продлить Premium-подписку"),
            description=tr_fn(
                "page.premium.action.extend.description",
                "Открыть Telegram-бота для продления подписки или покупки Premium.",
            ),
        )


__all__ = ["apply_premium_button_accessibility"]
