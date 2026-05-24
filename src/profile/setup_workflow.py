"""Workflow редактирования profile."""

from __future__ import annotations


def load_profile_setup(*, profile_feature, launch_method: str, profile_key: str):
    """Загружает данные экрана настройки profile."""
    return profile_feature.get_profile_setup(launch_method, profile_key)


def load_profile_list_file_editor_state(
    *,
    profile_feature,
    launch_method: str,
    profile_key: str,
    filter_kind: str = "",
    filter_value: str = "",
):
    """Загружает файл списка для вкладки «Редактор»."""
    return profile_feature.get_profile_list_file_editor_state(
        launch_method,
        profile_key,
        filter_kind=filter_kind,
        filter_value=filter_value,
    )


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


def save_profile_raw_text(*, profile_feature, launch_method: str, profile_key: str, raw_text: str) -> str | None:
    """Сохраняет полный текст profile в текущий preset."""
    return profile_feature.update_profile_raw_text(
        launch_method,
        profile_key,
        raw_text,
    )


def validate_profile_list_file_text(*, profile_feature, launch_method: str, kind: str, text: str):
    """Проверяет строки файла списка для вкладки «Редактор»."""
    return profile_feature.validate_profile_list_file_text(launch_method, kind, text)


def save_profile_list_file_text(*, profile_feature, launch_method: str, profile_key: str, text: str):
    """Сохраняет файл списка текущего profile."""
    return profile_feature.save_profile_list_file_text(launch_method, profile_key, text)


def set_profile_enabled(
    *,
    profile_feature,
    launch_method: str,
    profile_key: str,
    enabled: bool,
    filter_kind: str = "",
    filter_value: str = "",
) -> str | None:
    """Включает или выключает profile."""
    return profile_feature.set_profile_enabled(
        launch_method,
        profile_key,
        enabled,
        filter_kind=filter_kind,
        filter_value=filter_value,
    )


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
