"""Accessibility helpers for About page controls."""

from __future__ import annotations

from ui.accessibility import set_control_accessibility, set_state_text


def apply_about_buttons_accessibility(*, tr_fn, update_btn=None, premium_btn=None, kvn_btn=None) -> None:
    """Задаёт понятные имена кнопок вкладки «О программе» для экранного диктора."""

    if update_btn is not None:
        update_name = tr_fn(
            "page.about.action.update_settings.accessible_name",
            "Открыть настройки обновлений",
        )
        set_state_text(update_btn, update_name)
        set_control_accessibility(
            update_btn,
            name=update_name,
            description=tr_fn(
                "page.about.action.update_settings.description",
                "Открывает страницу настройки автоматической проверки обновлений.",
            ),
        )
    if premium_btn is not None:
        premium_name = tr_fn(
            "page.about.action.premium_vpn.accessible_name",
            "Открыть Premium и VPN",
        )
        set_state_text(premium_btn, premium_name)
        set_control_accessibility(
            premium_btn,
            name=premium_name,
            description=tr_fn(
                "page.about.action.premium_vpn.description",
                "Открывает страницу Premium, VPN и управления подпиской.",
            ),
        )
    if kvn_btn is not None:
        kvn_name = tr_fn(
            "page.about.action.zapret_kvn.accessible_name",
            "Открыть Zapret KVN на GitHub",
        )
        set_state_text(kvn_btn, kvn_name)
        set_control_accessibility(
            kvn_btn,
            name=kvn_name,
            description=tr_fn(
                "page.about.action.zapret_kvn.description",
                "Открывает репозиторий проекта Zapret KVN на GitHub.",
            ),
        )


__all__ = ["apply_about_buttons_accessibility"]
