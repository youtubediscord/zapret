"""Helper-слой статусов и runtime-действий Premium страницы."""

from __future__ import annotations

from collections.abc import Callable

import donater.ui.page_plans as premium_page_plans


def render_server_status_label(
    label,
    *,
    tr: Callable[[str, str], str],
    mode: str,
    message: str,
    success: bool | None,
) -> None:
    if mode == "checking":
        label.setText(
            tr("page.premium.connection.progress.testing", "🔄 Проверка соединения...")
        )
        return
    if mode == "idle":
        label.setText(
            tr("page.premium.label.server.idle", "Сервер: нажмите «Проверить соединение»")
        )
        return
    if mode == "init_error":
        label.setText(
            tr("page.premium.activation.error.init", "❌ Ошибка инициализации")
        )
        return
    if mode == "result":
        icon = "✅" if success else "❌"
        label.setText(
            tr(
                "page.premium.connection.result.template",
                "{icon} {message}",
                icon=icon,
                message=message,
            )
        )
        return
    if mode == "error":
        label.setText(
            tr(
                "page.premium.activation.error.generic",
                "❌ Ошибка: {error}",
                error=message,
            )
        )
        return

    label.setText(tr("page.premium.label.server.checking", "Сервер: проверка..."))


def build_status_check_hints(*, tr: Callable[[str, str], str]) -> tuple[str, str]:
    linked_hint = tr(
        "page.premium.status.inactive.linked_hint",
        "Продлите подписку в боте и нажмите «Обновить статус».",
    )
    unlinked_hint = tr(
        "page.premium.status.inactive.unlinked_hint",
        "Создайте код и привяжите устройство.",
    )
    return linked_hint, unlinked_hint


def apply_status_check_start_ui(
    *,
    refresh_btn,
    set_status_badge: Callable[..., None],
) -> None:
    refresh_btn.set_loading(True)
    set_status_badge(
        status="neutral",
        text_key="page.premium.status.checking.title",
        text_default="Проверка...",
        details_key="page.premium.status.checking.details",
        details_default="Подключение к серверу",
    )


def apply_status_check_success(
    result,
    *,
    tr: Callable[[str, str], str],
    refresh_btn,
    update_device_info: Callable[[], None],
    set_status_badge: Callable[..., None],
    set_activation_section_visible: Callable[[bool], None],
    stop_autopoll: Callable[[], None],
    sync_autopoll: Callable[[], None],
    apply_subscription_state: Callable[[bool, int], None],
) -> tuple[bool, int]:
    refresh_btn.set_loading(False)
    update_device_info()
    linked_hint, unlinked_hint = build_status_check_hints(tr=tr)
    plan = premium_page_plans.build_status_check_plan(
        result,
        linked_hint=linked_hint,
        unlinked_hint=unlinked_hint,
    )

    set_status_badge(
        status=plan.badge_plan.status,
        text_key=plan.badge_plan.text_key,
        text_default=plan.badge_plan.text_default,
        text_kwargs=plan.badge_plan.text_kwargs,
        details_key=plan.badge_plan.details_key,
        details_default=plan.badge_plan.details_default,
        details_kwargs=plan.badge_plan.details_kwargs,
    )
    set_activation_section_visible(not plan.hide_activation_section)

    if plan.stop_autopoll:
        stop_autopoll()
    elif plan.sync_autopoll:
        sync_autopoll()

    apply_subscription_state(plan.emitted_is_premium, plan.emitted_days)
    return plan.days_plan.kind, plan.days_plan.value


def apply_status_check_exception(
    error,
    *,
    tr: Callable[[str, str], str],
    sync_autopoll: Callable[[], None],
    refresh_btn,
    set_status_badge: Callable[..., None],
) -> None:
    sync_autopoll()
    refresh_btn.set_loading(False)
    linked_hint, unlinked_hint = build_status_check_hints(tr=tr)
    plan = premium_page_plans.build_status_check_plan(
        {"activated": False, "status": str(error or ""), "found": False},
        linked_hint=linked_hint,
        unlinked_hint=unlinked_hint,
    )
    set_status_badge(
        status="expired",
        text_key="page.premium.status.error.check_failed",
        text_default="Ошибка проверки",
        details=plan.badge_plan.details_default or str(error or ""),
    )


def apply_connection_test_plan(
    plan,
    *,
    tr: Callable[[str, str], str],
    test_btn,
    render_server_status: Callable[[], None],
    set_server_status_state: Callable[[str, str, bool | None], None],
) -> bool:
    test_btn.setEnabled(plan.test_enabled)
    test_btn.setText(tr(plan.test_text_key, plan.test_text_default))
    set_server_status_state(
        plan.server_status_plan.mode,
        plan.server_status_plan.message,
        plan.server_status_plan.success,
    )
    render_server_status()
    return plan.connection_in_progress


def apply_reset_plan_ui(
    *,
    premium_feature,
    key_input,
    set_activation_status: Callable[..., None],
    update_device_info: Callable[[], None],
    set_status_badge: Callable[..., None],
    render_days_label: Callable[[], None],
    set_activation_section_visible: Callable[[bool], None],
    stop_autopoll: Callable[[], None],
    apply_subscription_state: Callable[[bool, int], None],
) -> tuple[str, int]:
    premium_feature.reset_premium_storage()
    plan = premium_page_plans.build_reset_plan()

    if plan.clear_pair_input:
        key_input.clear()
    set_activation_status(
        text=plan.activation_status_plan.text,
        text_key=plan.activation_status_plan.text_key,
        text_default=plan.activation_status_plan.text_default,
        text_kwargs=plan.activation_status_plan.text_kwargs,
    )
    update_device_info()
    set_status_badge(
        status=plan.badge_plan.status,
        text_key=plan.badge_plan.text_key,
        text_default=plan.badge_plan.text_default,
        text_kwargs=plan.badge_plan.text_kwargs,
        details_key=plan.badge_plan.details_key,
        details_default=plan.badge_plan.details_default,
        details_kwargs=plan.badge_plan.details_kwargs,
    )
    render_days_label()
    set_activation_section_visible(plan.show_activation_section)
    if plan.stop_autopoll:
        stop_autopoll()
    apply_subscription_state(plan.emitted_is_premium, plan.emitted_days)
    return plan.days_plan.kind, plan.days_plan.value
