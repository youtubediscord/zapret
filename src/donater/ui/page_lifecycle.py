"""Lifecycle/state/language helper'ы Premium страницы."""

from __future__ import annotations

from donater.ui.accessibility import apply_premium_button_accessibility
from ui.fluent_widgets import set_tooltip


def apply_subscription_snapshot_ui(
    *,
    is_premium: bool,
    days_remaining: int | None,
    build_subscription_snapshot_plan_fn,
    set_status_badge_fn,
    set_days_state_kind_fn,
    set_days_state_value_fn,
    render_days_label_fn,
) -> None:
    badge_plan, days_plan, _emitted_days = build_subscription_snapshot_plan_fn(
        is_premium=is_premium,
        days_remaining=days_remaining,
    )
    set_status_badge_fn(
        status=badge_plan.status,
        text_key=badge_plan.text_key,
        text_default=badge_plan.text_default,
        text_kwargs=badge_plan.text_kwargs,
        details_key=badge_plan.details_key,
        details_default=badge_plan.details_default,
        details_kwargs=badge_plan.details_kwargs,
    )
    set_days_state_kind_fn(days_plan.kind)
    set_days_state_value_fn(days_plan.value)
    render_days_label_fn()


def render_activation_status_label(
    *,
    activation_status_state: dict,
    tr_fn,
    activation_status_label,
) -> None:
    text_key = activation_status_state.get("text_key")
    if text_key:
        activation_status_label.setText(
            tr_fn(
                text_key,
                activation_status_state.get("text_default") or "",
                **(activation_status_state.get("text_kwargs") or {}),
            )
        )
        return
    activation_status_label.setText(activation_status_state.get("text") or "")


def bind_premium_subscription_state_store(
    *,
    current_store,
    store,
    current_unsubscribe,
    set_store_fn,
    set_unsubscribe_fn,
    on_ui_state_changed_fn,
) -> None:
    if current_store is store:
        return

    if callable(current_unsubscribe):
        try:
            current_unsubscribe()
        except Exception:
            pass

    set_store_fn(store)
    set_unsubscribe_fn(
        store.subscribe(
            on_ui_state_changed_fn,
            fields={"subscription_is_premium", "subscription_days_remaining"},
            emit_initial=True,
        )
    )


def handle_premium_ui_state_changed(
    *,
    state,
    apply_subscription_snapshot_fn,
) -> None:
    apply_subscription_snapshot_fn(
        state.subscription_is_premium,
        state.subscription_days_remaining,
    )


def run_premium_runtime_init_once(
    *,
    runtime_initialized: bool,
    build_page_init_plan_fn,
    set_runtime_initialized_fn,
    start_init_worker_fn,
    set_server_status_mode_fn,
    set_server_status_message_fn,
    set_server_status_success_fn,
    render_server_status_fn,
) -> None:
    plan = build_page_init_plan_fn(
        runtime_initialized=runtime_initialized,
    )
    if not plan.ensure_checker_once:
        return

    set_runtime_initialized_fn(True)
    start_init_worker_fn()
    set_server_status_mode_fn(plan.init_server_status_plan.mode)
    set_server_status_message_fn(plan.init_server_status_plan.message)
    set_server_status_success_fn(plan.init_server_status_plan.success)
    render_server_status_fn()


def activate_premium_page(*, sync_pairing_status_autopoll_fn) -> None:
    sync_pairing_status_autopoll_fn()


def hide_premium_page(*, stop_pairing_status_autopoll_fn) -> None:
    stop_pairing_status_autopoll_fn()


def close_premium_page(
    *,
    set_cleanup_in_progress_fn,
    build_close_plan_fn,
    premium_action_runtime,
    stop_pairing_status_autopoll_fn,
    event,
) -> None:
    set_cleanup_in_progress_fn(True)
    plan = build_close_plan_fn(
        thread_running=premium_action_runtime.is_running(),
    )
    if plan.stop_autopoll:
        stop_pairing_status_autopoll_fn()
    if plan.should_quit_thread:
        premium_action_runtime.stop(
            blocking=False,
            wait_timeout_ms=plan.wait_timeout_ms,
            warning_prefix="Premium action worker",
        )
    event.accept()


def cleanup_premium_page(
    *,
    set_cleanup_in_progress_fn,
    stop_pairing_status_autopoll_fn,
    premium_action_runtime,
) -> None:
    set_cleanup_in_progress_fn(True)
    stop_pairing_status_autopoll_fn()
    premium_action_runtime.stop(
        blocking=False,
        wait_timeout_ms=1000,
        warning_prefix="Premium action worker",
    )


def apply_premium_language(
    *,
    tr_fn,
    activation_in_progress: bool,
    connection_test_in_progress: bool,
    instructions_label,
    key_input,
    activate_btn,
    open_bot_btn,
    refresh_btn,
    change_key_btn,
    extend_btn,
    test_btn,
    render_server_status_fn,
    render_days_label_fn,
    render_status_badge_fn,
    render_activation_status_fn,
) -> None:
    instructions_label.setText(
        tr_fn(
            "page.premium.instructions",
            "1. Нажмите «Создать код»\n2. Отправьте код боту @zapretvpns_bot в Telegram (сообщением)\n3. Вернитесь сюда и нажмите «Проверить статус»",
        )
    )
    key_input.setPlaceholderText(tr_fn("page.premium.placeholder.pair_code", "ABCD12EF"))

    if activation_in_progress:
        activate_btn.setText(tr_fn("page.premium.button.create_code.loading", "Создание..."))
    else:
        activate_btn.setText(tr_fn("page.premium.button.create_code", "Создать код"))

    open_bot_btn.setText(tr_fn("page.premium.button.open_bot", "Открыть бота"))
    refresh_btn.setText(tr_fn("page.premium.button.refresh_status", "Обновить статус"))
    change_key_btn.setText(tr_fn("page.premium.button.reset_activation", "Сбросить активацию"))
    extend_btn.setText(tr_fn("page.premium.button.extend", "Продлить подписку"))
    set_tooltip(
        refresh_btn,
        tr_fn(
            "page.premium.action.refresh_status.description",
            "Повторно запросить Premium-статус и обновить данные устройства.",
        )
    )
    set_tooltip(
        change_key_btn,
        tr_fn(
            "page.premium.action.reset_activation.description",
            "Удалить токен устройства, офлайн-кэш и код привязки на этом компьютере.",
        )
    )
    set_tooltip(
        extend_btn,
        tr_fn(
            "page.premium.action.extend.description",
            "Открыть Telegram-бота для продления подписки или покупки Premium.",
        )
    )

    if connection_test_in_progress:
        test_btn.setText(tr_fn("page.premium.button.test_connection.loading", "Проверка..."))
    else:
        test_btn.setText(tr_fn("page.premium.button.test_connection", "Проверить соединение"))
    set_tooltip(
        test_btn,
        tr_fn(
            "page.premium.action.test_connection.description",
            "Проверить доступность Premium backend и соединение с сервером.",
        )
    )
    apply_premium_button_accessibility(
        tr_fn=tr_fn,
        activate_btn=activate_btn,
        activate_loading=activation_in_progress,
        open_bot_btn=open_bot_btn,
        refresh_btn=refresh_btn,
        change_key_btn=change_key_btn,
        test_btn=test_btn,
        test_loading=connection_test_in_progress,
        extend_btn=extend_btn,
    )

    render_server_status_fn()
    render_days_label_fn()
    render_status_badge_fn()
    render_activation_status_fn()
