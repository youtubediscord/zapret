"""Runtime helper'ы для канонической DNS страницы."""

from __future__ import annotations


def build_dynamic_network_ui(
    *,
    cleanup_in_progress: bool,
    ui_built: bool,
    tr_fn,
    has_fluent_labels: bool,
    settings_card_cls,
    qhbox_layout_cls,
    qframe_cls,
    strong_body_label_cls,
    caption_label_cls,
    qlabel_cls,
    dns_provider_card_cls,
    adapter_card_cls,
    qta_module,
    get_theme_tokens_fn,
    build_auto_dns_ui_fn,
    build_provider_cards_fn,
    build_adapter_cards_fn,
    providers,
    adapters,
    dns_info,
    dns_cards_layout,
    adapters_layout,
    on_auto_selected,
    on_provider_selected,
    on_adapter_state_changed,
    normalize_alias_fn,
    ipv6_available: bool,
    dns_cards_container,
    custom_card,
    adapters_container,
    sync_selected_dns_card_fn,
    check_and_show_isp_dns_warning_fn,
    apply_inline_theme_styles_fn,
) -> object | None:
    if cleanup_in_progress or ui_built:
        return None

    tokens = get_theme_tokens_fn()

    dns_cards_container.show()
    custom_card.show()
    adapters_container.show()

    auto_widgets = build_auto_dns_ui_fn(
        tr_fn=tr_fn,
        has_fluent_labels=has_fluent_labels,
        settings_card_cls=settings_card_cls,
        qhbox_layout_cls=qhbox_layout_cls,
        qframe_cls=qframe_cls,
        strong_body_label_cls=strong_body_label_cls if has_fluent_labels else qlabel_cls,
        qlabel_cls=qlabel_cls,
        qta_module=qta_module,
        icon_color=tokens.fg_faint,
        indicator_off_qss=dns_provider_card_cls.indicator_off(),
        on_select=lambda _event: on_auto_selected(),
    )
    dns_cards_layout.addWidget(auto_widgets.card)

    provider_cards = build_provider_cards_fn(
        providers_by_category=providers,
        has_fluent_labels=has_fluent_labels,
        caption_label_cls=caption_label_cls if has_fluent_labels else qlabel_cls,
        qlabel_cls=qlabel_cls,
        dns_provider_card_cls=dns_provider_card_cls,
        dns_cards_layout=dns_cards_layout,
        show_ipv6=ipv6_available,
        on_selected=on_provider_selected,
    )

    adapter_cards = build_adapter_cards_fn(
        adapters=adapters,
        dns_info=dns_info,
        adapter_card_cls=adapter_card_cls,
        adapters_layout=adapters_layout,
        normalize_alias_fn=normalize_alias_fn,
        on_state_changed=on_adapter_state_changed,
    )

    sync_selected_dns_card_fn()
    check_and_show_isp_dns_warning_fn()
    apply_inline_theme_styles_fn(tokens)

    return {
        "auto_widgets": auto_widgets,
        "provider_cards": provider_cards,
        "adapter_cards": adapter_cards,
    }


def sync_selected_dns_card_ui(
    *,
    adapter_cards: list,
    dns_info: dict,
    providers,
    build_dns_selection_plan_fn,
    get_selected_adapters_fn,
    apply_dns_selection_plan_ui_fn,
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
    if not adapter_cards:
        return None

    selection_plan = build_dns_selection_plan_fn(
        selected_adapters=get_selected_adapters_fn(),
        dns_info=dns_info,
        providers=providers,
    )
    return apply_dns_selection_plan_ui_fn(
        selection_plan=selection_plan,
        dns_cards=dns_cards,
        auto_indicator=auto_indicator,
        auto_card=auto_card,
        custom_indicator=custom_indicator,
        custom_card=custom_card,
        custom_primary=custom_primary,
        custom_secondary=custom_secondary,
        indicator_on_qss=indicator_on_qss,
        indicator_off_qss=indicator_off_qss,
        set_card_selected_fn=set_card_selected_fn,
    )


def clear_dns_selection_ui(
    *,
    dns_cards: dict,
    auto_indicator,
    auto_card,
    custom_indicator,
    custom_card,
    indicator_off_qss: str,
    clear_dns_selection_fn,
    set_card_selected_fn,
) -> None:
    clear_dns_selection_fn(
        dns_cards=dns_cards,
        auto_indicator=auto_indicator,
        auto_card=auto_card,
        custom_indicator=custom_indicator,
        custom_card=custom_card,
        indicator_off_qss=indicator_off_qss,
        set_card_selected_fn=set_card_selected_fn,
    )
