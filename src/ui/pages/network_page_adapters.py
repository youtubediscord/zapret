"""Build/update helper'ы адаптеров для страницы Network."""

from __future__ import annotations


def build_adapter_cards(
    *,
    adapters: list[tuple[str, str]],
    dns_info: dict,
    adapter_card_cls,
    adapters_layout,
    normalize_alias_fn,
    on_state_changed,
) -> list:
    cards: list = []
    for name, _desc in adapters:
        clean_name = normalize_alias_fn(name)
        adapter_dns = dns_info.get(clean_name, {"ipv4": [], "ipv6": []})

        card = adapter_card_cls(name, adapter_dns)
        card.checkbox.stateChanged.connect(on_state_changed)
        cards.append(card)
        adapters_layout.addWidget(card)
    return cards


def refresh_adapter_cards(
    *,
    adapter_cards: list,
    dns_info: dict,
    build_refresh_plan_fn,
) -> object | None:
    if not adapter_cards:
        return None

    adapter_names = [card.adapter_name for card in adapter_cards]
    refresh_plan = build_refresh_plan_fn(adapter_names, dns_info)
    entries_by_name = {entry.adapter_name: entry for entry in refresh_plan.entries}

    for card in adapter_cards:
        entry = entries_by_name.get(card.adapter_name)
        if entry is None:
            continue
        card.dns_info = entry.adapter_data
        card.update_dns_display(entry.ipv4, entry.ipv6)

    return refresh_plan
