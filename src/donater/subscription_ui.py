from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from donater.state import PremiumState
from log.log import log


@dataclass(frozen=True, slots=True)
class SubscriptionUiActions:
    set_status: Callable[[str], None]
    ui_state_store: object
    update_title_badge: Callable
    init_holiday_effects: Callable[[bool], None]
    mark_startup_ready: Callable[[str], None]


def apply_subscription_starting_to_ui(*, set_status) -> None:
    """Показывает старт фоновой проверки Premium."""
    set_status("Инициализация подписок...")


def apply_subscription_progress_to_ui(*, set_status, message: str) -> None:
    """Показывает промежуточный статус Premium-проверки."""
    set_status(str(message or ""))


def apply_premium_state_to_ui(
    *,
    ui_state_store,
    update_title_badge,
    state: PremiumState,
) -> None:
    """Применяет Premium-статус к состоянию окна и верхней метке."""
    ui_state_store.set_subscription(state.is_premium, state.days_remaining)
    update_title_badge(
        state.is_premium,
        state.days_remaining,
        source=state.source,
    )
    log(f"Обновлена Premium-метка: premium={state.is_premium}", "DEBUG")


def apply_premium_state_to_store(*, ui_state_store, state: PremiumState) -> None:
    """Записывает Premium-статус в общий UI-store.

    Страница Premium не должна напрямую решать, какие поля store менять.
    Она передаёт готовое Premium-состояние сюда, а этот слой остаётся
    единым местом применения Premium-состояния к AppUiState.
    """
    ui_state_store.set_subscription(state.is_premium, state.days_remaining)


def apply_subscription_init_failed_to_ui(
    *,
    update_title_badge,
    set_status,
    mark_startup_ready,
) -> None:
    """Показывает состояние, когда PremiumService не удалось запустить."""
    update_title_badge(False, source="subscription_init_failed")
    set_status("Ошибка инициализации подписок")
    mark_startup_ready("subscription_init_failed")


def apply_subscription_ready_to_ui(
    *,
    init_holiday_effects,
    effects_allowed: bool,
    set_status,
    mark_startup_ready,
) -> None:
    """Завершает UI-часть Premium-инициализации."""
    init_holiday_effects(bool(effects_allowed))
    set_status("Подписка инициализирована")
    mark_startup_ready("subscription_ready")
