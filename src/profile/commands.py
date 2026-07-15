from __future__ import annotations

from settings.mode import normalize_launch_method

from .key_resolution import PresetProfileMoveResult
from .service import ProfilePresetService
from .state import StrategyApplyResult


def _profile_preset_service(profile_services, launch_method: str) -> ProfilePresetService:
    key = normalize_launch_method(launch_method)
    cache = getattr(profile_services, "_preset_service_cache", None)
    if isinstance(cache, dict):
        service = cache.get(key)
        if service is None:
            service = ProfilePresetService(profile_services, key)
            cache[key] = service
        return service
    return ProfilePresetService(profile_services, key)


def list_profiles(profile_services, launch_method: str):
    return _profile_preset_service(profile_services, launch_method).list_profiles()


def get_cached_profile_list(profile_services, launch_method: str):
    return _profile_preset_service(profile_services, launch_method).get_cached_profile_list()


def peek_cached_profile_list(profile_services, launch_method: str):
    return _profile_preset_service(profile_services, launch_method).peek_cached_profile_list()


def list_preset_order_profiles(profile_services, launch_method: str):
    return _profile_preset_service(profile_services, launch_method).list_preset_order_profiles()


def count_enabled_profiles(profile_services, launch_method: str) -> int:
    return _profile_preset_service(profile_services, launch_method).count_enabled_profiles()


def get_enabled_profile_count_snapshot(profile_services, launch_method: str) -> int | None:
    return _profile_preset_service(profile_services, launch_method).get_enabled_profile_count_snapshot()


def get_profile_strategy_display_state(profile_services, launch_method: str, max_items: int = 2):
    return _profile_preset_service(profile_services, launch_method).get_profile_strategy_display_state(max_items=max_items)


def get_profile_selection_details(
    profile_services,
    launch_method: str,
    *,
    selected_profile_key: str = "",
    max_items: int = 2,
):
    return _profile_preset_service(profile_services, launch_method).get_profile_selection_details(
        selected_profile_key=selected_profile_key,
        max_items=max_items,
    )


def get_profile_setup(profile_services, launch_method: str, profile_key: str):
    return _profile_preset_service(profile_services, launch_method).get_profile_setup(profile_key)


def get_profile_list_file_editor_state(
    profile_services,
    launch_method: str,
    profile_key: str,
    *,
    filter_kind: str = "",
    filter_value: str = "",
):
    return _profile_preset_service(profile_services, launch_method).get_profile_list_file_editor_state(
        profile_key,
        filter_kind=filter_kind,
        filter_value=filter_value,
    )


def apply_strategy_to_profile(
    profile_services,
    launch_method: str,
    profile_key: str,
    strategy_id: str,
    *,
    strategy_branch_id: str = "",
) -> StrategyApplyResult:
    return _profile_preset_service(profile_services, launch_method).apply_strategy(
        profile_key,
        strategy_id,
        strategy_branch_id=strategy_branch_id,
    )


def set_profile_enabled(
    profile_services,
    launch_method: str,
    profile_key: str,
    enabled: bool,
    *,
    filter_kind: str = "",
    filter_value: str = "",
) -> str | None:
    return _profile_preset_service(profile_services, launch_method).set_profile_enabled(
        profile_key,
        enabled,
        filter_kind=filter_kind,
        filter_value=filter_value,
    )


def update_winws2_profile_settings(
    profile_services,
    launch_method: str,
    profile_key: str,
    *,
    filter_kind: str,
    filter_value: str,
    in_range: str,
    out_range: str,
) -> tuple[str, str] | None:
    return _profile_preset_service(profile_services, launch_method).update_winws2_editable_settings(
        profile_key,
        filter_kind=filter_kind,
        filter_value=filter_value,
        in_range=in_range,
        out_range=out_range,
    )


def update_profile_raw_text(
    profile_services,
    launch_method: str,
    profile_key: str,
    raw_text: str,
) -> tuple[str, str] | None:
    return _profile_preset_service(profile_services, launch_method).update_profile_raw_text(profile_key, raw_text)


def validate_profile_list_file_text(
    profile_services,
    launch_method: str,
    kind: str,
    text: str,
) -> tuple[tuple[int, str], ...]:
    return _profile_preset_service(profile_services, launch_method).validate_list_file_text(kind, text)


def save_profile_list_file_text(
    profile_services,
    launch_method: str,
    profile_key: str,
    text: str,
    *,
    filter_kind: str = "",
    filter_value: str = "",
):
    return _profile_preset_service(profile_services, launch_method).save_profile_list_file_text(
        profile_key,
        text,
        filter_kind=filter_kind,
        filter_value=filter_value,
    )


def set_profile_filter_kind(
    profile_services,
    launch_method: str,
    profile_key: str,
    filter_kind: str,
) -> tuple[str, str] | None:
    return _profile_preset_service(profile_services, launch_method).set_profile_filter_kind(profile_key, filter_kind)


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
    *,
    destination_folder_key: str = "",
) -> str | None:
    return _profile_preset_service(profile_services, launch_method).move_profile_before(
        source_profile_key,
        destination_profile_key,
        destination_folder_key=destination_folder_key,
    )


def move_profile_after(
    profile_services,
    launch_method: str,
    source_profile_key: str,
    destination_profile_key: str,
    *,
    destination_folder_key: str = "",
) -> str | None:
    return _profile_preset_service(profile_services, launch_method).move_profile_after(
        source_profile_key,
        destination_profile_key,
        destination_folder_key=destination_folder_key,
    )


def move_profile_to_end(profile_services, launch_method: str, profile_key: str) -> str | None:
    return _profile_preset_service(profile_services, launch_method).move_profile_to_end(profile_key)


def move_profile_to_folder(profile_services, launch_method: str, profile_key: str, folder_key: str) -> str | None:
    return _profile_preset_service(profile_services, launch_method).move_profile_to_folder(profile_key, folder_key)


def move_preset_profile_before(
    profile_services,
    launch_method: str,
    source_profile_key: str,
    destination_profile_key: str,
) -> PresetProfileMoveResult | None:
    return _profile_preset_service(profile_services, launch_method).move_preset_profile_before(
        source_profile_key,
        destination_profile_key,
    )


def move_preset_profile_after(
    profile_services,
    launch_method: str,
    source_profile_key: str,
    destination_profile_key: str,
) -> PresetProfileMoveResult | None:
    return _profile_preset_service(profile_services, launch_method).move_preset_profile_after(
        source_profile_key,
        destination_profile_key,
    )


def move_preset_profile_to_end(profile_services, launch_method: str, profile_key: str) -> PresetProfileMoveResult | None:
    return _profile_preset_service(profile_services, launch_method).move_preset_profile_to_end(profile_key)


def create_user_profile(profile_services, *, name: str, protocol: str, ports: str) -> str:
    return _profile_preset_service(profile_services, "").create_user_profile(
        name=name,
        protocol=protocol,
        ports=ports,
    )


def update_user_profile(profile_services, profile_id: str, *, name: str, protocol: str, ports: str) -> int:
    return _profile_preset_service(profile_services, "").update_user_profile(
        profile_id,
        name=name,
        protocol=protocol,
        ports=ports,
    )


def delete_user_profile(profile_services, profile_id: str) -> int:
    return _profile_preset_service(profile_services, "").delete_user_profile(profile_id)
