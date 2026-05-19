"""Workflow редактирования profile."""

from __future__ import annotations


def load_profile_setup(*, profile_feature, launch_method: str, profile_key: str):
    """Загружает данные экрана настройки profile."""
    return profile_feature.get_profile_setup(launch_method, profile_key)


def save_winws2_profile_settings(
    *,
    profile_feature,
    launch_method: str,
    profile_key: str,
    filter_kind: str,
    filter_value: str,
    in_range: str,
    out_range: str,
) -> str | None:
    """Сохраняет редактируемые поля winws2 profile."""
    return profile_feature.update_winws2_profile_settings(
        launch_method,
        profile_key,
        filter_kind=filter_kind,
        filter_value=filter_value,
        in_range=in_range,
        out_range=out_range,
    )


def set_profile_enabled(*, profile_feature, launch_method: str, profile_key: str, enabled: bool) -> str | None:
    """Включает или выключает profile."""
    return profile_feature.set_profile_enabled(launch_method, profile_key, enabled)


def apply_strategy_to_profile(*, profile_feature, launch_method: str, profile_key: str, strategy_id: str) -> str | None:
    """Применяет готовую стратегию к profile."""
    return profile_feature.apply_strategy_to_profile(launch_method, profile_key, strategy_id)


def set_current_strategy_feedback(
    *,
    profile_feature,
    launch_method: str,
    profile_key: str,
    rating: str | None = None,
    favorite: bool | None = None,
) -> None:
    """Сохраняет оценку или избранность текущей стратегии."""
    kwargs = {}
    if rating is not None:
        kwargs["rating"] = rating
    if favorite is not None:
        kwargs["favorite"] = favorite
    profile_feature.set_current_strategy_state(launch_method, profile_key, **kwargs)
