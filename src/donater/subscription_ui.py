from __future__ import annotations

from typing import Any, Dict

from log.log import log


def apply_subscription_info_to_ui(
    app,
    sub_info: Dict[str, Any],
) -> None:
    """Применяет Premium-статус к состоянию окна и заголовку."""
    is_premium = bool(sub_info.get("is_premium"))
    days_remaining = sub_info.get("days_remaining")

    app.ui_state_store.set_subscription(is_premium, days_remaining)
    app.update_title_with_subscription_status(
        is_premium,
        app.theme_manager.current_theme,
        days_remaining,
    )
    log(f"Обновлён заголовок подписки: premium={is_premium}", "DEBUG")


def apply_subscription_init_failed_to_ui(app) -> None:
    """Показывает состояние, когда PremiumService не удалось запустить."""
    app.update_title_with_subscription_status(False, None, 0)
    app.set_status("Ошибка инициализации подписок")
    mark_startup_subscription_ready(app, "subscription_init_failed")


def apply_subscription_ready_to_ui(app) -> None:
    """Завершает UI-часть Premium-инициализации."""
    app._init_garland_from_registry()
    app.set_status("Подписка инициализирована")
    mark_startup_subscription_ready(app, "subscription_ready")


def mark_startup_subscription_ready(app, source: str) -> None:
    app._mark_startup_subscription_ready(source)
