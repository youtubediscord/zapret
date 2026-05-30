from __future__ import annotations

from app.page_names import PageName
from settings.mode import ZAPRET1_MODE, ZAPRET2_MODE
from ui.navigation_pages import (
    resolve_preset_raw_editor_back_page_for_method,
    resolve_preset_raw_editor_root_page_for_method,
    resolve_profile_order_page_for_method,
    resolve_profile_setup_root_page_for_method,
)


def build_control_page_kwargs(
    *,
    page_name: PageName,
    presets_feature,
    profile_feature,
    runtime_feature,
    program_settings_feature,
    external_actions_feature,
    set_status,
    request_exit,
    open_connection_test,
    open_folder,
    show_page,
    ui_state_store,
) -> dict:
    if page_name == PageName.ZAPRET2_MODE_CONTROL:
        user_presets_page = PageName.ZAPRET2_USER_PRESETS
        preset_setup_page = PageName.ZAPRET2_PRESET_SETUP
    else:
        user_presets_page = PageName.ZAPRET1_USER_PRESETS
        preset_setup_page = PageName.ZAPRET1_PRESET_SETUP
    return {
        "presets_feature": presets_feature,
        "profile_feature": profile_feature,
        "runtime_feature": runtime_feature,
        "create_program_settings_save_worker": program_settings_feature.create_program_settings_save_worker,
        "create_program_settings_load_worker": program_settings_feature.create_program_settings_load_worker,
        "create_program_settings_admin_check_worker": program_settings_feature.create_program_settings_admin_check_worker,
        "attach_program_settings_runtime": program_settings_feature.attach_program_settings_runtime,
        "publish_program_settings_snapshot": program_settings_feature.publish_program_settings_snapshot,
        "remember_hide_to_tray_on_minimize_close": program_settings_feature.remember_hide_to_tray_on_minimize_close,
        "set_status": set_status,
        "request_exit": request_exit,
        "open_connection_test": open_connection_test,
        "open_folder": open_folder,
        "open_presets": lambda page=user_presets_page: show_page(page, allow_internal=True),
        "open_preset_setup": lambda page=preset_setup_page: show_page(page, allow_internal=True),
        "open_blobs": lambda: show_page(PageName.BLOBS, allow_internal=True),
        "open_premium": lambda: show_page(PageName.PREMIUM, allow_internal=True),
        "create_external_open_url_worker": external_actions_feature.create_open_url_worker,
        "ui_state_store": ui_state_store,
    }


def build_preset_setup_page_kwargs(*, page_name: PageName, profile_feature, open_profile_setup, show_page, ui_state_store) -> dict:
    method = ZAPRET2_MODE if page_name == PageName.ZAPRET2_PRESET_SETUP else ZAPRET1_MODE
    return {
        "profile_feature": profile_feature,
        "open_profile_setup": lambda profile_key, m=method: open_profile_setup(m, profile_key),
        "open_profile_order": lambda m=method: show_page(resolve_profile_order_page_for_method(m), allow_internal=True),
        "ui_state_store": ui_state_store,
    }


def build_profile_setup_page_kwargs(
    *,
    page_name: PageName,
    profile_feature,
    show_page,
    on_profile_setup_changed,
) -> dict:
    method = ZAPRET2_MODE if page_name == PageName.ZAPRET2_PROFILE_SETUP else ZAPRET1_MODE
    profiles_page = (
        PageName.ZAPRET2_PRESET_SETUP
        if page_name == PageName.ZAPRET2_PROFILE_SETUP
        else PageName.ZAPRET1_PRESET_SETUP
    )
    return {
        "profile_feature": profile_feature,
        "open_profiles": lambda page=profiles_page: show_page(page, allow_internal=True),
        "open_root": lambda m=method: show_page(resolve_profile_setup_root_page_for_method(m), allow_internal=True),
        "on_profile_changed": lambda profile_key, change_kind, profile_item=None, m=method: on_profile_setup_changed(
            m,
            profile_key,
            change_kind,
            profile_item,
        ),
    }


def build_profile_order_page_kwargs(
    *,
    page_name: PageName,
    profile_feature,
    show_page,
) -> dict:
    method = ZAPRET2_MODE if page_name == PageName.ZAPRET2_PROFILE_ORDER else ZAPRET1_MODE
    profiles_page = (
        PageName.ZAPRET2_PRESET_SETUP
        if page_name == PageName.ZAPRET2_PROFILE_ORDER
        else PageName.ZAPRET1_PRESET_SETUP
    )
    control_page = (
        PageName.ZAPRET2_MODE_CONTROL
        if page_name == PageName.ZAPRET2_PROFILE_ORDER
        else PageName.ZAPRET1_MODE_CONTROL
    )
    return {
        "create_profile_order_load_worker": profile_feature.create_profile_order_load_worker,
        "create_preset_profile_order_move_worker": profile_feature.create_preset_profile_order_move_worker,
        "open_profiles": lambda page=profiles_page: show_page(page, allow_internal=True),
        "open_root": lambda page=control_page: show_page(page, allow_internal=True),
    }


def build_user_presets_page_kwargs(
    *,
    page_name: PageName,
    presets_feature,
    external_actions_feature,
    open_preset_raw_editor,
    ui_state_store,
) -> dict:
    method = ZAPRET2_MODE if page_name == PageName.ZAPRET2_USER_PRESETS else ZAPRET1_MODE
    return {
        "presets_feature": presets_feature,
        "open_preset_raw_editor": lambda preset_name, m=method: open_preset_raw_editor(
            m,
            preset_name,
            allow_internal=True,
        ),
        "external_actions_feature": external_actions_feature,
        "ui_state_store": ui_state_store,
    }


def build_preset_raw_editor_page_kwargs(
    *,
    page_name: PageName,
    presets_feature,
    runtime_feature,
    show_page,
    ui_state_store,
) -> dict:
    method = ZAPRET2_MODE if page_name == PageName.ZAPRET2_PRESET_RAW_EDITOR else ZAPRET1_MODE
    return {
        "presets_feature": presets_feature,
        "launch_method": method,
        "title": "Пресет Zapret 2" if method == ZAPRET2_MODE else "Пресет Zapret 1",
        "runtime_feature": runtime_feature,
        "open_back": lambda m=method: show_page(
            resolve_preset_raw_editor_back_page_for_method(m),
            allow_internal=True,
        ),
        "open_root": lambda m=method: show_page(
            resolve_preset_raw_editor_root_page_for_method(m),
            allow_internal=True,
        ),
        "ui_state_store": ui_state_store,
    }


__all__ = [
    "build_control_page_kwargs",
    "build_preset_raw_editor_page_kwargs",
    "build_preset_setup_page_kwargs",
    "build_profile_order_page_kwargs",
    "build_profile_setup_page_kwargs",
    "build_user_presets_page_kwargs",
]
