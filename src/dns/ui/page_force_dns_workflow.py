"""Force DNS workflow/helper'ы для канонической DNS страницы."""

from __future__ import annotations


def apply_force_dns_status_state(
    *,
    has_status_label: bool,
    enabled: bool,
    details_key: str | None,
    details_kwargs: dict | None,
    details_fallback: str,
    set_enabled_state_fn,
    set_details_key_fn,
    set_details_kwargs_fn,
    set_details_fallback_fn,
    update_force_dns_status_label_fn,
) -> None:
    if not has_status_label:
        return

    set_enabled_state_fn(bool(enabled))
    set_details_key_fn(details_key)
    set_details_kwargs_fn(dict(details_kwargs or {}))
    set_details_fallback_fn(details_fallback or "")
    update_force_dns_status_label_fn(
        enabled=enabled,
        details_key=details_key,
        details_kwargs=details_kwargs,
        details_fallback=details_fallback,
    )


def handle_force_dns_toggled_action(
    *,
    enabled: bool,
    get_force_dns_status_fn,
    enable_force_dns_fn,
    disable_force_dns_fn,
    build_toggle_plan_fn,
    build_toggle_error_plan_fn,
    set_force_dns_active_fn,
    set_force_dns_toggle_fn,
    update_force_dns_status_fn,
    update_dns_selection_state_fn,
    refresh_adapters_dns_fn,
    log_fn,
) -> None:
    try:
        current_state = get_force_dns_status_fn()
        if enabled == current_state:
            update_force_dns_status_fn(enabled)
            update_dns_selection_state_fn()
            return

        if enabled:
            success, ok_count, total, message = enable_force_dns_fn(include_disconnected=False)
            log_fn(message, "DNS")
            plan = build_toggle_plan_fn(
                requested_enabled=True,
                success=success,
                ok_count=ok_count,
                total=total,
            )
        else:
            success, message = disable_force_dns_fn(reset_to_auto=False)
            log_fn(message, "DNS")
            plan = build_toggle_plan_fn(
                requested_enabled=False,
                success=success,
            )

        set_force_dns_active_fn(plan.force_dns_active)
        set_force_dns_toggle_fn(plan.final_checked)
        update_force_dns_status_fn(
            plan.force_dns_active,
            plan.details_key,
            details_kwargs=plan.details_kwargs,
            details_fallback=plan.details_fallback,
        )
        update_dns_selection_state_fn()
        refresh_adapters_dns_fn()
    except Exception as exc:
        log_fn(f"Ошибка переключения Force DNS: {exc}", "ERROR")
        plan = build_toggle_error_plan_fn(requested_enabled=enabled)
        set_force_dns_active_fn(plan.force_dns_active)
        set_force_dns_toggle_fn(plan.final_checked)
        update_force_dns_status_fn(
            plan.force_dns_active,
            plan.details_key,
        )


def flush_dns_cache_action(
    *,
    flush_dns_cache_fn,
    build_result_plan_fn,
    language: str,
    info_bar_cls,
    parent_window,
) -> None:
    success, message = flush_dns_cache_fn()
    plan = build_result_plan_fn(
        success=success,
        message=message,
        language=language,
    )
    if plan.infobar_level == "warning" and info_bar_cls:
        info_bar_cls.warning(
            title=plan.title,
            content=plan.content,
            parent=parent_window,
        )


def reset_dns_to_dhcp_action(
    *,
    disable_force_dns_fn,
    get_force_dns_status_fn,
    build_result_plan_fn,
    language: str,
    set_force_dns_active_fn,
    set_force_dns_toggle_fn,
    select_auto_dns_ui_fn,
    dns_cards,
    auto_indicator,
    auto_card,
    custom_indicator,
    custom_card,
    indicator_on_qss: str,
    indicator_off_qss: str,
    set_card_selected_fn,
    set_selected_provider_fn,
    update_force_dns_status_fn,
    update_dns_selection_state_fn,
    refresh_adapters_dns_fn,
    info_bar_cls,
    parent_window,
    tr_fn,
    log_fn,
) -> None:
    try:
        success, message = disable_force_dns_fn(reset_to_auto=True)
        log_fn(message, "DNS")

        result_plan = build_result_plan_fn(
            success=success,
            message=message,
            force_dns_active=get_force_dns_status_fn(),
            language=language,
        )

        set_force_dns_active_fn(result_plan.force_dns_active)
        set_force_dns_toggle_fn(result_plan.force_dns_active)

        if result_plan.should_select_auto:
            select_auto_dns_ui_fn(
                dns_cards=dns_cards,
                auto_indicator=auto_indicator,
                auto_card=auto_card,
                custom_indicator=custom_indicator,
                custom_card=custom_card,
                indicator_on_qss=indicator_on_qss,
                indicator_off_qss=indicator_off_qss,
                set_card_selected_fn=set_card_selected_fn,
            )
            set_selected_provider_fn(None)

        update_force_dns_status_fn(
            result_plan.force_dns_active,
            result_plan.status_details_key,
        )
        update_dns_selection_state_fn()
        refresh_adapters_dns_fn()

        if info_bar_cls:
            if result_plan.infobar_level == "success":
                info_bar_cls.success(
                    title=result_plan.infobar_title,
                    content=result_plan.infobar_content,
                    parent=parent_window,
                )
            else:
                info_bar_cls.warning(
                    title=result_plan.infobar_title,
                    content=result_plan.infobar_content,
                    parent=parent_window,
                )
    except Exception as exc:
        log_fn(f"Ошибка сброса DNS на DHCP: {exc}", "ERROR")
        if info_bar_cls:
            info_bar_cls.warning(
                title=tr_fn("page.network.error.title", "Ошибка"),
                content=tr_fn(
                    "page.network.error.reset_dhcp_failed",
                    "Не удалось сбросить DNS: {error}",
                ).format(error=exc),
                parent=parent_window,
            )
