from __future__ import annotations

from app.text_catalog import tr as tr_catalog


def build_profiles_value(enabled_count: int | None, *, language: str) -> str:
    if enabled_count is None:
        return tr_catalog(
            "page.control.summary.profiles.unavailable",
            language=language,
            default="Не удалось проверить",
        )
    return tr_catalog(
        "page.control.summary.profiles.enabled_template",
        language=language,
        default="{count} включено",
    ).format(count=max(0, int(enabled_count)))


def build_premium_summary(
    is_premium: bool,
    days_remaining: int | None,
    *,
    language: str,
) -> tuple[str, str]:
    if not is_premium:
        return (
            "Free",
            tr_catalog(
                "page.control.summary.premium.free_details",
                language=language,
                default="Базовые функции",
            ),
        )

    if days_remaining is not None:
        try:
            days = max(0, int(days_remaining))
        except Exception:
            days = 0
        return (
            "Premium",
            tr_catalog(
                "page.control.summary.premium.days_left",
                language=language,
                default="Осталось {days} дней",
            ).format(days=days),
        )

    return (
        "Premium",
        tr_catalog(
            "page.control.summary.premium.active_details",
            language=language,
            default="Активен",
        ),
    )
