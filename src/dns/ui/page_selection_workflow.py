"""Workflow выбора и подсветки активного DNS на канонической DNS-странице."""

from __future__ import annotations


def build_dns_selection_sync_request_fn(
    *,
    get_cleanup_in_progress_fn,
    get_sync_queued_fn,
    set_sync_queued_fn,
    schedule_fn,
    get_adapter_cards_fn,
    get_dns_info_fn,
    providers,
    build_dns_selection_plan_fn,
    get_selected_adapters_fn,
    apply_dns_selection_plan_ui_fn,
    get_dns_cards_fn,
    get_auto_indicator_fn,
    get_auto_card_fn,
    get_custom_indicator_fn,
    get_custom_card_fn,
    get_custom_primary_fn,
    get_custom_secondary_fn,
    get_indicator_on_qss_fn,
    get_indicator_off_qss_fn,
    set_card_selected_fn,
    set_selected_provider_fn,
):
    def request(*_args) -> None:
        request_dns_selection_sync(
            get_cleanup_in_progress_fn=get_cleanup_in_progress_fn,
            get_sync_queued_fn=get_sync_queued_fn,
            set_sync_queued_fn=set_sync_queued_fn,
            schedule_fn=schedule_fn,
            get_adapter_cards_fn=get_adapter_cards_fn,
            get_dns_info_fn=get_dns_info_fn,
            providers=providers,
            build_dns_selection_plan_fn=build_dns_selection_plan_fn,
            get_selected_adapters_fn=get_selected_adapters_fn,
            apply_dns_selection_plan_ui_fn=apply_dns_selection_plan_ui_fn,
            get_dns_cards_fn=get_dns_cards_fn,
            get_auto_indicator_fn=get_auto_indicator_fn,
            get_auto_card_fn=get_auto_card_fn,
            get_custom_indicator_fn=get_custom_indicator_fn,
            get_custom_card_fn=get_custom_card_fn,
            get_custom_primary_fn=get_custom_primary_fn,
            get_custom_secondary_fn=get_custom_secondary_fn,
            get_indicator_on_qss_fn=get_indicator_on_qss_fn,
            get_indicator_off_qss_fn=get_indicator_off_qss_fn,
            set_card_selected_fn=set_card_selected_fn,
            set_selected_provider_fn=set_selected_provider_fn,
        )

    return request


def request_dns_selection_sync(
    *,
    get_cleanup_in_progress_fn,
    get_sync_queued_fn,
    set_sync_queued_fn,
    schedule_fn,
    get_adapter_cards_fn,
    get_dns_info_fn,
    providers,
    build_dns_selection_plan_fn,
    get_selected_adapters_fn,
    apply_dns_selection_plan_ui_fn,
    get_dns_cards_fn,
    get_auto_indicator_fn,
    get_auto_card_fn,
    get_custom_indicator_fn,
    get_custom_card_fn,
    get_custom_primary_fn,
    get_custom_secondary_fn,
    get_indicator_on_qss_fn,
    get_indicator_off_qss_fn,
    set_card_selected_fn,
    set_selected_provider_fn,
) -> None:
    if get_cleanup_in_progress_fn() or get_sync_queued_fn():
        return
    set_sync_queued_fn(True)
    schedule_fn(
        0,
        lambda: apply_dns_selection_sync(
            get_cleanup_in_progress_fn=get_cleanup_in_progress_fn,
            set_sync_queued_fn=set_sync_queued_fn,
            get_adapter_cards_fn=get_adapter_cards_fn,
            get_dns_info_fn=get_dns_info_fn,
            providers=providers,
            build_dns_selection_plan_fn=build_dns_selection_plan_fn,
            get_selected_adapters_fn=get_selected_adapters_fn,
            apply_dns_selection_plan_ui_fn=apply_dns_selection_plan_ui_fn,
            get_dns_cards_fn=get_dns_cards_fn,
            get_auto_indicator_fn=get_auto_indicator_fn,
            get_auto_card_fn=get_auto_card_fn,
            get_custom_indicator_fn=get_custom_indicator_fn,
            get_custom_card_fn=get_custom_card_fn,
            get_custom_primary_fn=get_custom_primary_fn,
            get_custom_secondary_fn=get_custom_secondary_fn,
            get_indicator_on_qss_fn=get_indicator_on_qss_fn,
            get_indicator_off_qss_fn=get_indicator_off_qss_fn,
            set_card_selected_fn=set_card_selected_fn,
            set_selected_provider_fn=set_selected_provider_fn,
        ),
    )


def apply_dns_selection_sync(
    *,
    get_cleanup_in_progress_fn,
    set_sync_queued_fn,
    get_adapter_cards_fn,
    get_dns_info_fn,
    providers,
    build_dns_selection_plan_fn,
    get_selected_adapters_fn,
    apply_dns_selection_plan_ui_fn,
    get_dns_cards_fn,
    get_auto_indicator_fn,
    get_auto_card_fn,
    get_custom_indicator_fn,
    get_custom_card_fn,
    get_custom_primary_fn,
    get_custom_secondary_fn,
    get_indicator_on_qss_fn,
    get_indicator_off_qss_fn,
    set_card_selected_fn,
    set_selected_provider_fn,
) -> None:
    set_sync_queued_fn(False)
    if get_cleanup_in_progress_fn():
        return

    adapter_cards = get_adapter_cards_fn()
    if not adapter_cards:
        return

    dns_info = get_dns_info_fn()
    dns_cards = get_dns_cards_fn()

    selection_plan = build_dns_selection_plan_fn(
        selected_adapters=get_selected_adapters_fn(),
        dns_info=dns_info,
        providers=providers,
    )
    selected_provider = apply_dns_selection_plan_ui_fn(
        selection_plan=selection_plan,
        dns_cards=dns_cards,
        auto_indicator=get_auto_indicator_fn(),
        auto_card=get_auto_card_fn(),
        custom_indicator=get_custom_indicator_fn(),
        custom_card=get_custom_card_fn(),
        custom_primary=get_custom_primary_fn(),
        custom_secondary=get_custom_secondary_fn(),
        indicator_on_qss=get_indicator_on_qss_fn(),
        indicator_off_qss=get_indicator_off_qss_fn(),
        set_card_selected_fn=set_card_selected_fn,
    )
    set_selected_provider_fn(selected_provider)
