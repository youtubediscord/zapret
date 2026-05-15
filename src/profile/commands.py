from __future__ import annotations

from .service import ProfilePresetService


def _profile_preset_service(profile_services, launch_method: str) -> ProfilePresetService:
    return ProfilePresetService(profile_services, launch_method)


def list_profiles(profile_services, launch_method: str):
    return _profile_preset_service(profile_services, launch_method).list_profiles()


def get_profile_setup(profile_services, launch_method: str, profile_key: str):
    return _profile_preset_service(profile_services, launch_method).get_profile_setup(profile_key)


def apply_strategy_to_profile(profile_services, launch_method: str, profile_key: str, strategy_id: str) -> str | None:
    return _profile_preset_service(profile_services, launch_method).apply_strategy(profile_key, strategy_id)


def set_profile_enabled(profile_services, launch_method: str, profile_key: str, enabled: bool) -> str | None:
    return _profile_preset_service(profile_services, launch_method).set_profile_enabled(profile_key, enabled)


def update_winws2_profile_settings(
    profile_services,
    launch_method: str,
    profile_key: str,
    *,
    filter_kind: str,
    filter_value: str,
    in_range: str,
    out_range: str,
) -> str | None:
    return _profile_preset_service(profile_services, launch_method).update_winws2_editable_settings(
        profile_key,
        filter_kind=filter_kind,
        filter_value=filter_value,
        in_range=in_range,
        out_range=out_range,
    )


def set_current_strategy_state(
    profile_services,
    launch_method: str,
    profile_key: str,
    *,
    rating: str | None = None,
    favorite: bool | None = None,
    clear: bool = False,
):
    return _profile_preset_service(profile_services, launch_method).set_current_strategy_state(
        profile_key,
        rating=rating,
        favorite=favorite,
        clear=clear,
    )


def set_strategy_state(
    profile_services,
    launch_method: str,
    profile_key: str,
    strategy_id: str,
    *,
    rating: str | None = None,
    favorite: bool | None = None,
    clear: bool = False,
):
    return _profile_preset_service(profile_services, launch_method).set_strategy_state(
        profile_key,
        strategy_id,
        rating=rating,
        favorite=favorite,
        clear=clear,
    )


def delete_profile(profile_services, launch_method: str, profile_key: str) -> bool:
    return _profile_preset_service(profile_services, launch_method).delete_profile(profile_key)


def duplicate_profile(profile_services, launch_method: str, profile_key: str) -> str | None:
    return _profile_preset_service(profile_services, launch_method).duplicate_profile(profile_key)


def move_profile_before(
    profile_services,
    launch_method: str,
    source_profile_key: str,
    destination_profile_key: str,
) -> str | None:
    return _profile_preset_service(profile_services, launch_method).move_profile_before(
        source_profile_key,
        destination_profile_key,
    )


def move_profile_to_end(profile_services, launch_method: str, profile_key: str) -> str | None:
    return _profile_preset_service(profile_services, launch_method).move_profile_to_end(profile_key)
