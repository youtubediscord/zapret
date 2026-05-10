from __future__ import annotations

from donater.state import PremiumState
from log.log import log


def apply_subscription_starting_to_ui(app) -> None:
    """Показывает старт фоновой проверки Premium."""
    app.set_status("Инициализация подписок...")


def apply_subscription_progress_to_ui(app, message: str) -> None:
    """Показывает промежуточный статус Premium-проверки."""
    app.set_status(str(message or ""))


def apply_premium_state_to_ui(
    app,
    state: PremiumState,
) -> None:
    """Применяет Premium-статус к состоянию окна и верхней метке."""
    app.ui_state_store.set_subscription(state.is_premium, state.days_remaining)
    app.update_subscription_title_badge(
        state.is_premium,
        state.days_remaining,
        source=state.source,
    )
    log(f"Обновлена Premium-метка: premium={state.is_premium}", "DEBUG")


def apply_subscription_init_failed_to_ui(app) -> None:
    """Показывает состояние, когда PremiumService не удалось запустить."""
    app.update_subscription_title_badge(False, source="subscription_init_failed")
    app.set_status("Ошибка инициализации подписок")
    mark_startup_subscription_ready(app, "subscription_init_failed")


def apply_subscription_ready_to_ui(app) -> None:
    """Завершает UI-часть Premium-инициализации."""
    app._init_garland_from_registry()
    app.set_status("Подписка инициализирована")
    mark_startup_subscription_ready(app, "subscription_ready")


def mark_startup_subscription_ready(app, source: str) -> None:
    app._mark_startup_subscription_ready(source)
