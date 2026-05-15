from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import subprocess
import sys

from presets.file_service import PresetFileService
from presets.state import PresetSelectionState
from settings.mode import engine_for_launch_method, normalize_launch_method


def _create_preset_file_service(launch_method: str, *, preset_services) -> PresetFileService:
    return PresetFileService.from_launch_method(launch_method, preset_services=preset_services)


def list_preset_manifests(launch_method: str, *, preset_services):
    return _create_preset_file_service(launch_method, preset_services=preset_services).list_manifests()


def get_preset_manifest_by_file_name(launch_method: str, file_name: str, *, preset_services):
    return _create_preset_file_service(launch_method, preset_services=preset_services).get_manifest_by_file_name(file_name)


def get_preset_source_path_by_file_name(launch_method: str, file_name: str, *, preset_services):
    return _create_preset_file_service(launch_method, preset_services=preset_services).get_source_path_by_file_name(file_name)


def get_selected_source_preset_manifest(launch_method: str, *, preset_services):
    return _create_preset_file_service(launch_method, preset_services=preset_services).get_selected_manifest()


def get_selected_source_preset_file_name(launch_method: str, *, preset_services) -> str:
    return _create_preset_file_service(launch_method, preset_services=preset_services).get_selected_file_name()


def get_selected_source_preset_display(launch_method: str, *, preset_services) -> tuple[str, str]:
    manifest = get_selected_source_preset_manifest(launch_method, preset_services=preset_services)
    file_name = str(getattr(manifest, "file_name", "") or "").strip()
    display_name = str(getattr(manifest, "name", "") or "").strip()
    if not file_name:
        return "", ""
    if not display_name:
        display_name = Path(file_name).stem.strip() or file_name
    return display_name, display_name


def is_selected_preset_file_name(launch_method: str, file_name: str, *, preset_services) -> bool:
    return _create_preset_file_service(launch_method, preset_services=preset_services).is_selected_file_name(file_name)


def activate_preset_file(launch_method: str, file_name: str, *, preset_services):
    return _create_preset_file_service(launch_method, preset_services=preset_services).activate_preset_file(file_name)


def connect_preset_signals(
    launch_method: str,
    *,
    preset_services,
    on_changed=None,
    on_switched=None,
    on_identity_changed=None,
    on_content_changed=None,
) -> None:
    store = _create_preset_file_service(launch_method, preset_services=preset_services)._ui_store()
    if callable(on_changed):
        store.presets_changed.connect(on_changed)
    if callable(on_switched):
        store.preset_switched.connect(on_switched)
    if callable(on_identity_changed):
        store.preset_identity_changed.connect(on_identity_changed)
    if callable(on_content_changed):
        store.preset_content_changed.connect(on_content_changed)


def get_selection_state(
    launch_method: str,
    *,
    preset_services,
    profile_feature=None,
    profile_key: str = "",
) -> PresetSelectionState:
    method = normalize_launch_method(launch_method, default="")
    engine = engine_for_launch_method(method)
    manifest = get_selected_source_preset_manifest(method, preset_services=preset_services)
    file_name = str(getattr(manifest, "file_name", "") or "").strip()
    preset_name = str(getattr(manifest, "name", "") or "").strip() or Path(file_name).stem.strip() or file_name
    display_name = preset_name
    source_path = str(get_preset_source_path_by_file_name(method, file_name, preset_services=preset_services) or "")
    normalized_profile_key = str(profile_key or "").strip()
    profile_info = _profile_selection_details(
        profile_feature,
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


def select_preset(
    launch_method: str,
    file_name: str,
    *,
    preset_services,
    profile_feature=None,
) -> PresetSelectionState:
    activate_preset_file(launch_method, file_name, preset_services=preset_services)
    return get_selection_state(
        launch_method,
        preset_services=preset_services,
        profile_feature=profile_feature,
    )


def refresh_preset_summary(
    launch_method: str,
    *,
    preset_services,
    profile_feature=None,
    profile_key: str = "",
) -> PresetSelectionState:
    return get_selection_state(
        launch_method,
        preset_services=preset_services,
        profile_feature=profile_feature,
        profile_key=profile_key,
    )


def select_profile(launch_method: str, profile_key: str, *, preset_services, profile_feature=None) -> PresetSelectionState:
    return get_selection_state(
        launch_method,
        preset_services=preset_services,
        profile_feature=profile_feature,
        profile_key=profile_key,
    )


def get_launch_snapshot(
    launch_method: str,
    *,
    preset_services,
    require_filters: bool = False,
    timing_callback=None,
    timing_label: str | None = None,
):
    return preset_services.preset_mode_coordinator.get_startup_snapshot(
        launch_method,
        require_filters=bool(require_filters),
        timing_callback=timing_callback,
        timing_label=timing_label,
    )


def get_selected_source_path(launch_method: str, *, preset_services) -> Path:
    snapshot = get_launch_snapshot(launch_method, preset_services=preset_services, require_filters=False)
    return Path(snapshot.preset_path)


def get_user_presets_dir(launch_method: str, *, preset_services) -> Path:
    method = normalize_launch_method(launch_method, default="")
    engine = engine_for_launch_method(method)
    return preset_services.app_paths.engine_paths(engine).ensure_directories().user_presets_dir


def _open_path_in_system(path: str | Path) -> None:
    target = str(path)
    if sys.platform == "win32":
        os.startfile(target)  # type: ignore[attr-defined]
    else:
        subprocess.Popen(["xdg-open", target])  # noqa: S603 - user-triggered opener


def open_user_presets_folder(launch_method: str, *, preset_services) -> None:
    presets_dir = get_user_presets_dir(launch_method, preset_services=preset_services)
    presets_dir.mkdir(parents=True, exist_ok=True)
    _open_path_in_system(presets_dir)


def open_preset_source_file(path: str | Path) -> None:
    _open_path_in_system(path)


def save_preset_source_by_file_name(
    launch_method: str,
    file_name: str,
    source_text: str,
    *,
    preset_services,
):
    return _create_preset_file_service(launch_method, preset_services=preset_services).save_source_text_by_file_name(
        file_name,
        source_text,
    )


def read_preset_source_by_file_name(launch_method: str, file_name: str, *, preset_services) -> str:
    return _create_preset_file_service(launch_method, preset_services=preset_services).read_source_text_by_file_name(file_name)


def read_selected_preset_source(launch_method: str, *, preset_services) -> tuple[str, object]:
    service = _create_preset_file_service(launch_method, preset_services=preset_services)
    manifest = service.get_selected_manifest()
    source_text = service.read_source_text_by_file_name(str(getattr(manifest, "file_name", "") or ""))
    return source_text, manifest


def save_selected_preset_source(launch_method: str, source_text: str, *, preset_services):
    return _create_preset_file_service(launch_method, preset_services=preset_services).save_selected_source_text(source_text)


def create_preset(launch_method: str, name: str, *, from_current: bool = True, preset_services):
    return _create_preset_file_service(launch_method, preset_services=preset_services).create(
        name,
        from_current=from_current,
    )


def rename_preset_by_file_name(launch_method: str, file_name: str, new_name: str, *, preset_services):
    return _create_preset_file_service(launch_method, preset_services=preset_services).rename_by_file_name(
        file_name,
        new_name,
    )


def duplicate_preset_by_file_name(launch_method: str, file_name: str, new_name: str, *, preset_services):
    return _create_preset_file_service(launch_method, preset_services=preset_services).duplicate_by_file_name(
        file_name,
        new_name,
    )


def import_preset_from_file(launch_method: str, src_path: str | Path, name: str | None = None, *, preset_services):
    return _create_preset_file_service(launch_method, preset_services=preset_services).import_from_file(
        Path(src_path),
        name,
    )


def export_preset_plain_text(launch_method: str, file_name: str, dest_path: str | Path, *, preset_services):
    return _create_preset_file_service(launch_method, preset_services=preset_services).export_plain_text_by_file_name(
        file_name,
        Path(dest_path),
    )


def reset_preset_to_builtin_by_file_name(launch_method: str, file_name: str, *, preset_services):
    return _create_preset_file_service(launch_method, preset_services=preset_services).reset_to_builtin_by_file_name(file_name)


def reset_all_presets_to_builtin(launch_method: str, *, preset_services):
    return _create_preset_file_service(launch_method, preset_services=preset_services).reset_all_to_builtin()


def delete_preset_by_file_name(launch_method: str, file_name: str, *, preset_services) -> None:
    _create_preset_file_service(launch_method, preset_services=preset_services).delete_by_file_name(file_name)


@dataclass(frozen=True, slots=True)
class PresetServicesBundle:
    app_paths: object
    preset_mode_coordinator: object
    preset_file_store: object
    preset_selection_service: object
    preset_store_winws2: object
    preset_store_winws1: object


def create_preset_services(app_paths) -> PresetServicesBundle:
    from presets.file_store import PresetFileStore
    from presets.mode_coordinator import PresetModeCoordinator
    from presets.selection_service import PresetSelectionService
    from presets.ui_store import PresetUiStore
    from settings.mode import ENGINE_WINWS1, ENGINE_WINWS2

    preset_file_store = PresetFileStore(app_paths)
    preset_selection_service = PresetSelectionService(preset_file_store)
    return PresetServicesBundle(
        app_paths=app_paths,
        preset_mode_coordinator=PresetModeCoordinator(app_paths, preset_selection_service, preset_file_store),
        preset_file_store=preset_file_store,
        preset_selection_service=preset_selection_service,
        preset_store_winws2=PresetUiStore(ENGINE_WINWS2, preset_file_store, preset_selection_service),
        preset_store_winws1=PresetUiStore(ENGINE_WINWS1, preset_file_store, preset_selection_service),
    )


@dataclass(frozen=True, slots=True)
class _ProfileSelectionDetails:
    summary: str = ""
    selected_profile_name: str = ""
    profile_count: int = 0
    enabled_profile_count: int = 0
    active_strategy_count: int = 0


def _profile_selection_details(
    profile_feature,
    launch_method: str,
    *,
    selected_profile_key: str = "",
) -> _ProfileSelectionDetails:
    try:
        if profile_feature is None:
            return _ProfileSelectionDetails()
        selected_profile_name = ""
        if selected_profile_key:
            setup = profile_feature.get_profile_setup(launch_method, selected_profile_key)
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

        payload = profile_feature.list_profiles(launch_method)
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
