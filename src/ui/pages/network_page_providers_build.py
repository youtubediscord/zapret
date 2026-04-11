"""Сборка списка DNS-провайдеров для страницы Network."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class ProviderCardsBuildResult:
    dns_cards: dict[str, object]
    category_labels: list[object]


def build_provider_cards(
    *,
    providers_by_category: dict,
    has_fluent_labels: bool,
    caption_label_cls,
    qlabel_cls,
    dns_provider_card_cls,
    dns_cards_layout,
    show_ipv6: bool,
    on_selected,
) -> ProviderCardsBuildResult:
    dns_cards: dict[str, object] = {}
    category_labels: list[object] = []

    for category, providers in providers_by_category.items():
        if has_fluent_labels:
            category_label = caption_label_cls(category)
        else:
            category_label = qlabel_cls(category)
            category_labels.append(category_label)
        dns_cards_layout.addWidget(category_label)

        for name, data in providers.items():
            card = dns_provider_card_cls(name, data, False, show_ipv6=show_ipv6)
            card.selected.connect(on_selected)
            dns_cards[name] = card
            dns_cards_layout.addWidget(card)

    return ProviderCardsBuildResult(
        dns_cards=dns_cards,
        category_labels=category_labels,
    )
