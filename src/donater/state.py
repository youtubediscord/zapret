from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True, slots=True)
class PremiumState:
    is_premium: bool = False
    days_remaining: int | None = None
    subscription_level: str = "-"
    status_msg: str = "Не активировано"
    source: str = "api"
    error: str = ""


def premium_state_from_activation_info(activation_info: Mapping[str, Any] | None) -> PremiumState:
    info = activation_info if isinstance(activation_info, Mapping) else {}
    is_premium = bool(info.get("activated") or info.get("is_premium"))
    raw_days = info.get("days_remaining") if is_premium else None
    days_remaining = _normalize_days(raw_days)
    status_msg = str(info.get("status") or info.get("status_msg") or info.get("status_message") or "").strip()
    if not status_msg:
        status_msg = "Premium активен" if is_premium else "Не активировано"
    source = "offline" if "offline" in status_msg.lower() else str(info.get("source") or "api").strip() or "api"
    subscription_level = str(
        info.get("subscription_level")
        or info.get("level")
        or ("zapretik" if is_premium else "-")
    ).strip() or "-"

    return PremiumState(
        is_premium=is_premium,
        days_remaining=days_remaining,
        subscription_level=subscription_level if is_premium else "-",
        status_msg=status_msg,
        source=source,
    )


def premium_state_from_subscription_info(subscription_info: Mapping[str, Any] | None) -> PremiumState:
    info = subscription_info if isinstance(subscription_info, Mapping) else {}
    is_premium = bool(info.get("is_premium") or info.get("activated"))
    raw_days = info.get("days_remaining") if is_premium else None
    status_msg = str(info.get("status_msg") or info.get("status") or "").strip()
    if not status_msg:
        status_msg = "Premium активен" if is_premium else "Не активировано"
    source = str(info.get("source") or ("offline" if "offline" in status_msg.lower() else "api")).strip() or "api"
    subscription_level = str(info.get("subscription_level") or ("zapretik" if is_premium else "-")).strip() or "-"
    return PremiumState(
        is_premium=is_premium,
        days_remaining=_normalize_days(raw_days),
        subscription_level=subscription_level if is_premium else "-",
        status_msg=status_msg,
        source=source,
    )


def premium_state_error(message: str) -> PremiumState:
    text = str(message or "").strip() or "Ошибка Premium"
    return PremiumState(status_msg=text, source="error", error=text)


def _normalize_days(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except Exception:
        return None

