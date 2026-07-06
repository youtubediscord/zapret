from __future__ import annotations

from app.page_names import PageName
from settings.mode import ZAPRET1_MODE, ZAPRET2_MODE

# Импорты preset-страниц здесь намеренно ленивые (внутри функций-билдеров):
# preset_subpage_base тянет ui.fluent_widgets/qtawesome (~200 мс), а этот
# модуль импортируется до первого показа окна через ui.page_factory.
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
    from presets.ui.control.additional_settings_runtime import (
        create_additional_settings_save_worker,
        create_top_summary_worker,
    )
    from presets.ui.control.control_page_shared import ControlRuntimeActions

    if page_name == PageName.ZAPRET2_MODE_CONTROL:
        user_presets_page = PageName.ZAPRET2_USER_PRESETS
        preset_setup_page = PageName.ZAPRET2_PRESET_SETUP
        method = ZAPRET2_MODE
    else:
        user_presets_page = PageName.ZAPRET1_USER_PRESETS
        preset_setup_page = PageName.ZAPRET1_PRESET_SETUP
        method = ZAPRET1_MODE

    def _create_top_summary_worker(request_id: int, *, parent=None):
        return create_top_summary_worker(
            request_id,
            presets_feature.get_selected_source_preset_display,
            profile_feature.get_enabled_profile_count_snapshot,
            presets_feature.read_selected_preset_source,
            launch_method=method,
            get_enabled_profile_count_fallback=profile_feature.count_enabled_profiles,
            parent=parent,
        )

    def _create_additional_settings_save_worker(request_id: int, *, setting: str, enabled: bool, parent=None):
        from discord.discord_restart import set_discord_restart_setting

        return create_additional_settings_save_worker(
            request_id,
            set_discord_restart_setting,
            profile_feature.set_wssize_enabled,
            profile_feature.set_debug_log_enabled,
            launch_method=method,
            setting=setting,
            enabled=enabled,
            parent=parent,
        )

    return {
        "create_top_summary_worker": _create_top_summary_worker,
        "create_additional_settings_load_worker": profile_feature.create_additional_settings_load_worker,
        "create_additional_settings_save_worker": _create_additional_settings_save_worker,
        "runtime_actions": ControlRuntimeActions(
            start=runtime_feature.start,
            stop=runtime_feature.stop,
            stop_and_exit=runtime_feature.stop_and_exit,
            is_available=runtime_feature.is_available,
        ),
        "create_program_settings_save_worker": program_settings_feature.create_program_settings_save_worker,
        "create_program_settings_load_worker": program_settings_feature.create_program_settings_load_worker,
        "create_program_settings_admin_check_worker": program_settings_feature.create_program_settings_admin_check_worker,
        "attach_program_settings_runtime": program_settings_feature.attach_program_settings_runtime,
        "publish_program_settings_snapshot": program_settings_feature.publish_program_settings_snapshot,
        "remember_tray_close_mode": program_settings_feature.remember_tray_close_mode,
        "set_status": set_status,
        "request_exit": request_exit,
        "open_connection_test": open_connection_test,
        "open_folder": open_folder,
        "open_presets": lambda page=user_presets_page: show_page(page, allow_internal=True),
        "open_preset_setup": lambda page=preset_setup_page: show_page(page, allow_internal=True),
        "open_premium": lambda: show_page(PageName.PREMIUM, allow_internal=True),
        "create_external_open_url_worker": external_actions_feature.create_open_url_worker,
        "ui_state_store": ui_state_store,
    }


def build_preset_setup_page_kwargs(
    *,
    page_name: PageName,
    profile_feature,
    external_actions_feature,
    open_profile_setup,
    show_page,
    ui_state_store,
) -> dict:
    method = ZAPRET2_MODE if page_name == PageName.ZAPRET2_PRESET_SETUP else ZAPRET1_MODE
    return {
        "create_profile_list_load_worker": profile_feature.create_profile_list_load_worker,
        "create_profile_item_refresh_worker": profile_feature.create_profile_item_refresh_worker,
        "create_profile_context_action_worker": profile_feature.create_profile_context_action_worker,
        "create_profile_move_worker": profile_feature.create_profile_move_worker,
        "create_user_profile_create_worker": profile_feature.create_user_profile_create_worker,
        "create_user_profile_update_worker": profile_feature.create_user_profile_update_worker,
        "create_user_profile_delete_worker": profile_feature.create_user_profile_delete_worker,
        "create_profile_folder_action_worker": profile_feature.create_profile_folder_action_worker,
        "create_profile_request_form_open_worker": external_actions_feature.create_open_url_worker,
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
        "create_profile_setup_load_worker": profile_feature.create_profile_setup_load_worker,
        "create_profile_list_file_load_worker": profile_feature.create_profile_list_file_load_worker,
        "create_profile_list_file_save_worker": profile_feature.create_profile_list_file_save_worker,
        "create_profile_list_file_validation_worker": profile_feature.create_profile_list_file_validation_worker,
        "create_profile_settings_save_worker": profile_feature.create_profile_settings_save_worker,
        "create_profile_raw_text_save_worker": profile_feature.create_profile_raw_text_save_worker,
        "create_profile_enabled_save_worker": profile_feature.create_profile_enabled_save_worker,
        "create_profile_user_update_worker": profile_feature.create_profile_user_update_worker,
        "create_profile_user_delete_worker": profile_feature.create_profile_user_delete_worker,
        "create_profile_strategy_apply_worker": profile_feature.create_profile_strategy_apply_worker,
        "create_profile_strategy_feedback_save_worker": profile_feature.create_profile_strategy_feedback_save_worker,
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
    ui_state_store=None,
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
        "ui_state_store": ui_state_store,
    }


def build_user_presets_page_kwargs(
    *,
    page_name: PageName,
    presets_feature,
    external_actions_feature,
    open_preset_raw_editor,
    notify=None,
    ui_state_store,
) -> dict:
    from presets.ui.common.user_presets_page_runtime import UserPresetsRuntimeActions

    method = ZAPRET2_MODE if page_name == PageName.ZAPRET2_USER_PRESETS else ZAPRET1_MODE

    def _create_preset_link_action_worker(request_id: int, *, action: str, parent=None):
        return presets_feature.create_preset_link_action_worker(
            request_id,
            open_url=external_actions_feature.open_url,
            action=action,
            parent=parent,
        )

    return {
        "preset_runtime_actions": UserPresetsRuntimeActions(
            get_selected_source_preset_file_name=presets_feature.get_selected_source_preset_file_name,
            list_preset_manifests=presets_feature.list_preset_manifests,
            get_user_presets_dir=presets_feature.get_user_presets_dir,
            get_cached_preset_list_metadata=presets_feature.get_cached_preset_list_metadata,
            warm_preset_list_metadata_cache=presets_feature.warm_preset_list_metadata_cache,
            get_preset_source_path_by_file_name=presets_feature.get_preset_source_path_by_file_name,
            preset_differs_from_builtin_by_file_name=presets_feature.preset_differs_from_builtin_by_file_name,
            read_single_preset_list_metadata=presets_feature.read_single_preset_list_metadata,
        ),
        "connect_preset_signals": presets_feature.connect_preset_signals,
        "create_user_presets_open_folder_worker": presets_feature.create_user_presets_open_folder_worker,
        "create_preset_edit_action_worker": presets_feature.create_preset_edit_action_worker,
        "create_preset_bulk_action_worker": presets_feature.create_preset_bulk_action_worker,
        "create_preset_activate_worker": presets_feature.create_preset_activate_worker,
        "create_preset_item_action_worker": presets_feature.create_preset_item_action_worker,
        "create_preset_link_action_worker": _create_preset_link_action_worker,
        "create_preset_folder_action_worker": presets_feature.create_preset_folder_action_worker,
        "create_preset_storage_action_worker": presets_feature.create_preset_storage_action_worker,
        "load_preset_folder_state": presets_feature.load_preset_folder_state,
        "open_preset_raw_editor": lambda preset_name, m=method: open_preset_raw_editor(
            m,
            preset_name,
            allow_internal=True,
        ),
        "notify": notify,
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
    from presets.ui.common.preset_subpage_base import RawPresetRuntimeActions

    method = ZAPRET2_MODE if page_name == PageName.ZAPRET2_PRESET_RAW_EDITOR else ZAPRET1_MODE
    return {
        "create_raw_preset_load_worker": presets_feature.create_raw_preset_load_worker,
        "create_raw_preset_save_worker": presets_feature.create_raw_preset_save_worker,
        "create_raw_preset_activate_worker": presets_feature.create_raw_preset_activate_worker,
        "create_raw_preset_action_worker": presets_feature.create_raw_preset_action_worker,
        "launch_method": method,
        "title": "Пресет Zapret 2" if method == ZAPRET2_MODE else "Пресет Zapret 1",
        "runtime_actions": RawPresetRuntimeActions(
            start=runtime_feature.start,
            stop=runtime_feature.stop,
            is_available=runtime_feature.is_available,
        ),
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
