from __future__ import annotations

from app.page_names import PageName
from profile.setup_controller import ProfileSetupActions
from settings.mode import ZAPRET1_MODE, ZAPRET2_MODE
from presets.ui.common.user_presets_page_runtime import UserPresetsRuntimeActions
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
        "get_selected_source_preset_display": presets_feature.get_selected_source_preset_display,
        "get_enabled_profile_count_snapshot": profile_feature.get_enabled_profile_count_snapshot,
        "create_additional_settings_load_worker": profile_feature.create_additional_settings_load_worker,
        "set_wssize_enabled": profile_feature.set_wssize_enabled,
        "set_debug_log_enabled": profile_feature.set_debug_log_enabled,
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
        "get_cached_profile_list": profile_feature.get_cached_profile_list,
        "list_profiles": profile_feature.list_profiles,
        "create_user_profile": profile_feature.create_user_profile,
        "update_user_profile": profile_feature.update_user_profile,
        "delete_user_profile": profile_feature.delete_user_profile,
        "create_profile_list_load_worker": profile_feature.create_profile_list_load_worker,
        "create_profile_context_action_worker": profile_feature.create_profile_context_action_worker,
        "create_profile_move_worker": profile_feature.create_profile_move_worker,
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
        "profile_setup_actions": ProfileSetupActions(
            get_profile_setup=profile_feature.get_profile_setup,
            get_profile_list_file_editor_state=profile_feature.get_profile_list_file_editor_state,
            update_winws2_profile_settings=profile_feature.update_winws2_profile_settings,
            update_profile_raw_text=profile_feature.update_profile_raw_text,
            validate_profile_list_file_text=profile_feature.validate_profile_list_file_text,
            save_profile_list_file_text=profile_feature.save_profile_list_file_text,
            set_profile_enabled=profile_feature.set_profile_enabled,
            update_user_profile=profile_feature.update_user_profile,
            list_profiles=profile_feature.list_profiles,
            delete_user_profile=profile_feature.delete_user_profile,
            apply_strategy_to_profile=profile_feature.apply_strategy_to_profile,
            set_current_strategy_state=profile_feature.set_current_strategy_state,
        ),
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
        "preset_runtime_actions": UserPresetsRuntimeActions(
            create_preset=presets_feature.create_preset,
            rename_preset_by_file_name=presets_feature.rename_preset_by_file_name,
            is_selected_preset_file_name=presets_feature.is_selected_preset_file_name,
            import_preset_from_file=presets_feature.import_preset_from_file,
            reset_all_presets_to_builtin=presets_feature.reset_all_presets_to_builtin,
            get_selected_source_preset_file_name=presets_feature.get_selected_source_preset_file_name,
            duplicate_preset_by_file_name=presets_feature.duplicate_preset_by_file_name,
            reset_preset_to_builtin_by_file_name=presets_feature.reset_preset_to_builtin_by_file_name,
            delete_preset_by_file_name=presets_feature.delete_preset_by_file_name,
            export_preset_plain_text=presets_feature.export_preset_plain_text,
            get_preset_manifest_by_file_name=presets_feature.get_preset_manifest_by_file_name,
            list_preset_manifests=presets_feature.list_preset_manifests,
            get_selected_source_preset_manifest=presets_feature.get_selected_source_preset_manifest,
            get_user_presets_dir=presets_feature.get_user_presets_dir,
            get_cached_preset_list_metadata=presets_feature.get_cached_preset_list_metadata,
            warm_preset_list_metadata_cache=presets_feature.warm_preset_list_metadata_cache,
            get_preset_source_path_by_file_name=presets_feature.get_preset_source_path_by_file_name,
            activate_preset_file=presets_feature.activate_preset_file,
        ),
        "connect_preset_signals": presets_feature.connect_preset_signals,
        "create_user_presets_open_folder_worker": presets_feature.create_user_presets_open_folder_worker,
        "open_preset_raw_editor": lambda preset_name, m=method: open_preset_raw_editor(
            m,
            preset_name,
            allow_internal=True,
        ),
        "open_url": external_actions_feature.open_url,
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
        "save_preset_source_by_file_name": presets_feature.save_preset_source_by_file_name,
        "get_preset_source_path_by_file_name": presets_feature.get_preset_source_path_by_file_name,
        "get_preset_manifest_by_file_name": presets_feature.get_preset_manifest_by_file_name,
        "open_preset_source_file": presets_feature.open_preset_source_file,
        "rename_preset_by_file_name": presets_feature.rename_preset_by_file_name,
        "duplicate_preset_by_file_name": presets_feature.duplicate_preset_by_file_name,
        "export_preset_plain_text": presets_feature.export_preset_plain_text,
        "reset_preset_to_builtin_by_file_name": presets_feature.reset_preset_to_builtin_by_file_name,
        "delete_preset_by_file_name": presets_feature.delete_preset_by_file_name,
        "get_selected_source_preset_manifest": presets_feature.get_selected_source_preset_manifest,
        "get_selected_source_preset_file_name": presets_feature.get_selected_source_preset_file_name,
        "activate_preset_file": presets_feature.activate_preset_file,
        "publish_preset_content_changed": presets_feature.publish_preset_content_changed,
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
