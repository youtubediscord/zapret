"""UI-helper'ы выбора DNS-карточек для страницы Network."""

from __future__ import annotations


def set_dns_card_selected(card, selected: bool) -> None:
    if card is None:
        return
    try:
        card.setProperty("selected", bool(selected))
        style = card.style()
        if style is not None:
            style.unpolish(card)
            style.polish(card)
        card.update()
    except Exception:
        pass


def clear_dns_selection(
    *,
    dns_cards: dict,
    auto_indicator,
    auto_card,
    custom_indicator,
    custom_card,
    indicator_off_qss: str,
    set_card_selected_fn,
) -> None:
    for card in dns_cards.values():
        try:
            card.set_selected(False)
        except Exception:
            pass

    try:
        if auto_indicator is not None:
            auto_indicator.setStyleSheet(indicator_off_qss)
    except Exception:
        pass
    set_card_selected_fn(auto_card, False)

    try:
        if custom_indicator is not None:
            custom_indicator.setStyleSheet(indicator_off_qss)
    except Exception:
        pass
    set_card_selected_fn(custom_card, False)


def apply_dns_selection_plan_ui(
    *,
    selection_plan,
    dns_cards: dict,
    auto_indicator,
    auto_card,
    custom_indicator,
    custom_card,
    custom_primary,
    custom_secondary,
    indicator_on_qss: str,
    indicator_off_qss: str,
    set_card_selected_fn,
) -> str | None:
    if selection_plan.kind == "none":
        return None

    clear_dns_selection(
        dns_cards=dns_cards,
        auto_indicator=auto_indicator,
        auto_card=auto_card,
        custom_indicator=custom_indicator,
        custom_card=custom_card,
        indicator_off_qss=indicator_off_qss,
        set_card_selected_fn=set_card_selected_fn,
    )

    if selection_plan.kind == "auto":
        try:
            if auto_indicator is not None:
                auto_indicator.setStyleSheet(indicator_on_qss)
        except Exception:
            pass
        set_card_selected_fn(auto_card, True)
        return None

    if selection_plan.kind == "provider" and selection_plan.selected_provider in dns_cards:
        dns_cards[selection_plan.selected_provider].set_selected(True)
        return selection_plan.selected_provider

    try:
        if custom_indicator is not None:
            custom_indicator.setStyleSheet(indicator_on_qss)
    except Exception:
        pass
    set_card_selected_fn(custom_card, True)
    try:
        if custom_primary is not None:
            custom_primary.setText(selection_plan.custom_primary)
    except Exception:
        pass
    try:
        if custom_secondary is not None:
            custom_secondary.setText(selection_plan.custom_secondary)
    except Exception:
        pass
    return None


def select_provider_dns_ui(
    *,
    name: str,
    dns_cards: dict,
    auto_indicator,
    auto_card,
    custom_indicator,
    custom_card,
    indicator_off_qss: str,
    set_card_selected_fn,
) -> str | None:
    clear_dns_selection(
        dns_cards=dns_cards,
        auto_indicator=auto_indicator,
        auto_card=auto_card,
        custom_indicator=custom_indicator,
        custom_card=custom_card,
        indicator_off_qss=indicator_off_qss,
        set_card_selected_fn=set_card_selected_fn,
    )
    card = dns_cards.get(name)
    if card is not None:
        try:
            card.set_selected(True)
        except Exception:
            pass
        return name
    return None


def select_auto_dns_ui(
    *,
    dns_cards: dict,
    auto_indicator,
    auto_card,
    custom_indicator,
    custom_card,
    indicator_on_qss: str,
    indicator_off_qss: str,
    set_card_selected_fn,
) -> None:
    clear_dns_selection(
        dns_cards=dns_cards,
        auto_indicator=auto_indicator,
        auto_card=auto_card,
        custom_indicator=custom_indicator,
        custom_card=custom_card,
        indicator_off_qss=indicator_off_qss,
        set_card_selected_fn=set_card_selected_fn,
    )
    try:
        if auto_indicator is not None:
            auto_indicator.setStyleSheet(indicator_on_qss)
    except Exception:
        pass
    set_card_selected_fn(auto_card, True)


def select_custom_dns_ui(
    *,
    dns_cards: dict,
    auto_indicator,
    auto_card,
    custom_indicator,
    custom_card,
    indicator_on_qss: str,
    indicator_off_qss: str,
    set_card_selected_fn,
) -> None:
    clear_dns_selection(
        dns_cards=dns_cards,
        auto_indicator=auto_indicator,
        auto_card=auto_card,
        custom_indicator=custom_indicator,
        custom_card=custom_card,
        indicator_off_qss=indicator_off_qss,
        set_card_selected_fn=set_card_selected_fn,
    )
    try:
        if custom_indicator is not None:
            custom_indicator.setStyleSheet(indicator_on_qss)
    except Exception:
        pass
    set_card_selected_fn(custom_card, True)
