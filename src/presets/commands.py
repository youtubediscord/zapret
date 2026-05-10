from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from presets.file_service import PresetFileService
from presets.state import PresetSelectionState
from settings.mode import engine_for_launch_method, normalize_launch_method


def create_preset_file_service(launch_method: str, *, app_context) -> PresetFileService:
    return PresetFileService.from_launch_method(launch_method, app_context=app_context)


def list_preset_manifests(launch_method: str, *, app_context):
    return create_preset_file_service(launch_method, app_context=app_context).list_manifests()


def get_preset_manifest_by_file_name(launch_method: str, file_name: str, *, app_context):
    return create_preset_file_service(launch_method, app_context=app_context).get_manifest_by_file_name(file_name)


def get_preset_source_path_by_file_name(launch_method: str, file_name: str, *, app_context):
    return create_preset_file_service(launch_method, app_context=app_context).get_source_path_by_file_name(file_name)


def get_selected_source_preset_manifest(launch_method: str, *, app_context):
    return create_preset_file_service(launch_method, app_context=app_context).get_selected_manifest()


def get_selected_source_preset_file_name(launch_method: str, *, app_context) -> str:
    return create_preset_file_service(launch_method, app_context=app_context).get_selected_file_name()


def get_selected_source_preset_display(launch_method: str, *, app_context) -> tuple[str, str]:
    manifest = get_selected_source_preset_manifest(launch_method, app_context=app_context)
    file_name = str(getattr(manifest, "file_name", "") or "").strip()
    display_name = str(getattr(manifest, "name", "") or "").strip()
    if not file_name:
        return "", ""
    if not display_name:
        display_name = Path(file_name).stem.strip() or file_name
    return display_name, display_name


def is_selected_preset_file_name(launch_method: str, file_name: str, *, app_context) -> bool:
    return create_preset_file_service(launch_method, app_context=app_context).is_selected_file_name(file_name)


def activate_preset_file(launch_method: str, file_name: str, *, app_context):
    return create_preset_file_service(launch_method, app_context=app_context).activate_preset_file(file_name)


def get_selection_state(
    launch_method: str,
    *,
    app_context,
    profile_key: str = "",
) -> PresetSelectionState:
    method = normalize_launch_method(launch_method, default="")
    engine = engine_for_launch_method(method)
    manifest = get_selected_source_preset_manifest(method, app_context=app_context)
    file_name = str(getattr(manifest, "file_name", "") or "").strip()
    preset_name = str(getattr(manifest, "name", "") or "").strip() or Path(file_name).stem.strip() or file_name
    display_name = preset_name
    source_path = str(get_preset_source_path_by_file_name(method, file_name, app_context=app_context) or "")
    normalized_profile_key = str(profile_key or "").strip()
    profile_info = _profile_selection_details(
        app_context,
        method,
        selected_profile_key=normalized_profile_key,
    )
    return PresetSelectionState(
        method=method,
        engine=engine,
        selected_preset_file_name=file_name,
        selected_preset_name=preset_name,
        selected_source_path=source_path,
        display_name=display_name,
        summary=profile_info.summary,
        selected_profile_key=normalized_profile_key,
        selected_profile_name=profile_info.selected_profile_name,
        profile_count=profile_info.profile_count,
        enabled_profile_count=profile_info.enabled_profile_count,
        active_strategy_count=profile_info.active_strategy_count,
    )


def select_preset(launch_method: str, file_name: str, *, app_context) -> PresetSelectionState:
    activate_preset_file(launch_method, file_name, app_context=app_context)
    return get_selection_state(launch_method, app_context=app_context)


def refresh_preset_summary(launch_method: str, *, app_context, profile_key: str = "") -> PresetSelectionState:
    return get_selection_state(launch_method, app_context=app_context, profile_key=profile_key)


def select_profile(launch_method: str, profile_key: str, *, app_context) -> PresetSelectionState:
    return get_selection_state(launch_method, app_context=app_context, profile_key=profile_key)


def get_launch_snapshot(
    launch_method: str,
    *,
    app_context,
    require_filters: bool = False,
    timing_callback=None,
    timing_label: str | None = None,
):
    return app_context.preset_mode_coordinator.get_startup_snapshot(
        launch_method,
        require_filters=bool(require_filters),
        timing_callback=timing_callback,
        timing_label=timing_label,
    )


def get_selected_source_path(launch_method: str, *, app_context) -> Path:
    snapshot = get_launch_snapshot(launch_method, app_context=app_context, require_filters=False)
    return Path(snapshot.preset_path)


def save_preset_source_by_file_name(
    launch_method: str,
    file_name: str,
    source_text: str,
    *,
    app_context,
):
    return create_preset_file_service(launch_method, app_context=app_context).save_source_text_by_file_name(
        file_name,
        source_text,
    )


def save_selected_preset_source(launch_method: str, source_text: str, *, app_context):
    return create_preset_file_service(launch_method, app_context=app_context).save_selected_source_text(source_text)


def create_preset(launch_method: str, name: str, *, from_current: bool = True, app_context):
    return create_preset_file_service(launch_method, app_context=app_context).create(
        name,
        from_current=from_current,
    )


def rename_preset_by_file_name(launch_method: str, file_name: str, new_name: str, *, app_context):
    return create_preset_file_service(launch_method, app_context=app_context).rename_by_file_name(
        file_name,
        new_name,
    )


def duplicate_preset_by_file_name(launch_method: str, file_name: str, new_name: str, *, app_context):
    return create_preset_file_service(launch_method, app_context=app_context).duplicate_by_file_name(
        file_name,
        new_name,
    )


def import_preset_from_file(launch_method: str, src_path: str | Path, name: str | None = None, *, app_context):
    return create_preset_file_service(launch_method, app_context=app_context).import_from_file(
        Path(src_path),
        name,
    )


def export_preset_plain_text(launch_method: str, file_name: str, dest_path: str | Path, *, app_context):
    return create_preset_file_service(launch_method, app_context=app_context).export_plain_text_by_file_name(
        file_name,
        Path(dest_path),
    )


def reset_preset_to_builtin_by_file_name(launch_method: str, file_name: str, *, app_context):
    return create_preset_file_service(launch_method, app_context=app_context).reset_to_builtin_by_file_name(file_name)


def reset_all_presets_to_builtin(launch_method: str, *, app_context):
    return create_preset_file_service(launch_method, app_context=app_context).reset_all_to_builtin()


def delete_preset_by_file_name(launch_method: str, file_name: str, *, app_context) -> None:
    create_preset_file_service(launch_method, app_context=app_context).delete_by_file_name(file_name)


@dataclass(frozen=True, slots=True)
class _ProfileSelectionDetails:
    summary: str = ""
    selected_profile_name: str = ""
    profile_count: int = 0
    enabled_profile_count: int = 0
    active_strategy_count: int = 0


def _profile_selection_details(
    app_context,
    launch_method: str,
    *,
    selected_profile_key: str = "",
) -> _ProfileSelectionDetails:
    try:
        from profile.public import get_profile_setup, list_profiles

        selected_profile_name = ""
        if selected_profile_key:
            setup = get_profile_setup(app_context, launch_method, selected_profile_key)
            if setup is not None:
                item = setup.item
                selected_profile_name = str(item.display_name or "").strip()
                return _ProfileSelectionDetails(
                    summary=str(item.strategy_name or item.display_name or "").strip(),
                    selected_profile_name=selected_profile_name,
                    profile_count=1 if item.in_preset else 0,
                    enabled_profile_count=1 if item.in_preset and item.enabled else 0,
                    active_strategy_count=1 if item.in_preset and item.enabled and item.strategy_id != "none" else 0,
                )

        payload = list_profiles(app_context, launch_method)
        profile_items = [item for item in payload.items if item.in_preset]
        enabled_items = [item for item in profile_items if item.enabled]
        active_items = [item for item in enabled_items if item.strategy_id != "none"]
        active_names = [str(item.strategy_name or item.display_name or "").strip() for item in active_items]
        active_names = [name for name in active_names if name]
        if not active_names:
            summary = ""
        else:
            max_items = 2
            if len(active_names) <= max_items:
                summary = " • ".join(active_names)
            else:
                summary = " • ".join(active_names[:max_items]) + f" +{len(active_names) - max_items} ещё"
        return _ProfileSelectionDetails(
            summary=summary,
            profile_count=len(profile_items),
            enabled_profile_count=len(enabled_items),
            active_strategy_count=len(active_items),
        )
    except Exception:
        return _ProfileSelectionDetails()
