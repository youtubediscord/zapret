from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from presets.models import PresetManifest
from presets.preset_file_ops import (
    create_preset as _create_preset,
    delete_by_file_name as _delete_by_file_name,
    duplicate_by_file_name as _duplicate_by_file_name,
    export_plain_text_by_file_name as _export_plain_text_by_file_name,
    import_from_file as _import_from_file,
    rename_by_file_name as _rename_by_file_name,
    reset_all_to_builtin as _reset_all_to_builtin,
    reset_to_builtin_by_file_name as _reset_to_builtin_by_file_name,
)
from presets.preset_text_ops import _normalize_presets_source_text
from settings.mode import (
    ENGINE_WINWS1,
    ENGINE_WINWS2,
    PRESETS_SCOPE_WINWS1,
    PRESETS_SCOPE_WINWS2,
    engine_for_launch_method_or_none,
    normalize_launch_method,
)

if TYPE_CHECKING:
    from core.paths import AppPaths
    from presets.file_store import PresetFileStore
    from presets.ui_store import PresetUiStore
    from presets.selection_service import PresetSelectionService


_ENGINE_TO_HIERARCHY_SCOPE = {
    ENGINE_WINWS2: PRESETS_SCOPE_WINWS2,
    ENGINE_WINWS1: PRESETS_SCOPE_WINWS1,
}


@dataclass(frozen=True)
class PresetFileService:
    """File-only service for preset mode management.

    Этот сервис работает только с физическими preset-файлами: создать,
    переименовать, импортировать, сбросить, сохранить текст. Он не строит
    список profile и не читает содержимое preset-а.
    """

    engine: str
    launch_method: str
    app_paths: "AppPaths"
    preset_mode_coordinator: object
    preset_file_store: "PresetFileStore"
    preset_selection_service: "PresetSelectionService"
    preset_store_winws2: "PresetUiStore"
    preset_store_winws1: "PresetUiStore"

    @classmethod
    def from_launch_method(cls, launch_method: str, *, preset_services) -> "PresetFileService":
        method = normalize_launch_method(launch_method, default="")
        engine = engine_for_launch_method_or_none(method)
        if engine is None:
            raise ValueError(f"Unsupported preset launch method: {launch_method}")
        return cls(
            engine=engine,
            launch_method=method,
            app_paths=preset_services.app_paths,
            preset_mode_coordinator=preset_services.preset_mode_coordinator,
            preset_file_store=preset_services.preset_file_store,
            preset_selection_service=preset_services.preset_selection_service,
            preset_store_winws2=preset_services.preset_store_winws2,
            preset_store_winws1=preset_services.preset_store_winws1,
        )

    def _ui_store(self):
        if self.engine == ENGINE_WINWS2:
            return self.preset_store_winws2
        if self.engine == ENGINE_WINWS1:
            return self.preset_store_winws1
        raise ValueError(f"Unsupported preset mode engine: {self.engine}")

    def _hierarchy_scope_key(self) -> str:
        scope_key = _ENGINE_TO_HIERARCHY_SCOPE.get(self.engine)
        if scope_key is None:
            raise ValueError(f"Unsupported preset mode engine: {self.engine}")
        return scope_key

    def _get_hierarchy_store(self):
        from presets.library_hierarchy import PresetHierarchyStore

        return PresetHierarchyStore(self._hierarchy_scope_key())

    def _rename_library_meta(
        self,
        old_file_name: str,
        new_file_name: str,
    ) -> None:
        try:
            self._get_hierarchy_store().rename_preset_meta(
                old_file_name,
                new_file_name,
            )
        except Exception:
            pass

    def _copy_library_meta(
        self,
        source_file_name: str,
        new_file_name: str,
    ) -> None:
        try:
            self._get_hierarchy_store().copy_preset_meta_to_new(
                source_file_name,
                new_file_name,
            )
        except Exception:
            pass

    def _delete_library_meta(self, preset_file_name: str) -> None:
        try:
            self._get_hierarchy_store().delete_preset_meta(preset_file_name)
        except Exception:
            pass

    def _refresh_selected_source_preset(self) -> None:
        selected_file_name = self.get_selected_file_name()
        if not selected_file_name or self.get_manifest_by_file_name(selected_file_name) is None:
            return
        self.preset_mode_coordinator.refresh_selected_launch_preset(self.launch_method)

    def list_manifests(self) -> list[PresetManifest]:
        return self.preset_file_store.list_manifests(self.engine)

    def notify_preset_content_changed(self, file_name: str) -> None:
        candidate = str(file_name or "").strip()
        if candidate:
            self._ui_store().notify_preset_content_changed(candidate)

    def notify_preset_switched(self, file_name: str) -> None:
        candidate = str(file_name or "").strip()
        if candidate:
            self._ui_store().notify_preset_switched(candidate)

    def notify_preset_identity_changed(self, file_name: str) -> None:
        candidate = str(file_name or "").strip()
        if candidate:
            self._ui_store().notify_preset_identity_changed(candidate)

    def notify_presets_changed(self) -> None:
        self._ui_store().notify_presets_changed()

    def activate_preset_file(self, file_name: str):
        return self.select_file_name(file_name)

    def select_file_name(self, file_name: str):
        profile = self.preset_mode_coordinator.select_preset_file_name(self.launch_method, file_name)
        self.notify_preset_switched(profile.preset_file_name)
        return profile

    def get_selected_manifest(self) -> PresetManifest | None:
        try:
            return self.preset_mode_coordinator.get_selected_source_manifest(self.launch_method)
        except Exception:
            return None

    def get_selected_file_name(self) -> str:
        preset = self.get_selected_manifest()
        return preset.file_name if preset is not None else ""

    def is_selected_file_name(self, file_name: str) -> bool:
        current = str(self.get_selected_file_name() or "").strip()
        candidate = str(self.preset_file_store.resolve_file_name(self.engine, file_name) or file_name or "").strip()
        return bool(current and candidate and current.lower() == candidate.lower())

    def get_manifest_by_file_name(self, file_name: str) -> PresetManifest | None:
        return self.preset_file_store.get_manifest(self.engine, file_name)

    def get_source_path_by_file_name(self, file_name: str) -> Path:
        return self.preset_file_store.get_source_path(self.engine, file_name)

    def read_source_text_by_file_name(self, file_name: str) -> str:
        manifest = self.get_manifest_by_file_name(file_name)
        if manifest is None:
            raise ValueError(f"Preset not found: {file_name}")
        return self.preset_file_store.read_source_text(self.engine, manifest.file_name)

    def read_selected_source_text(self) -> str:
        selected_file_name = self.get_selected_file_name()
        if not selected_file_name:
            return ""
        return self.read_source_text_by_file_name(selected_file_name)

    def save_source_text_by_file_name(self, file_name: str, source_text: str) -> PresetManifest:
        manifest = self.get_manifest_by_file_name(file_name)
        if manifest is None:
            raise ValueError(f"Preset not found: {file_name}")
        normalized = _normalize_presets_source_text(source_text)
        updated = self.preset_file_store.update_preset(self.engine, manifest.file_name, normalized, None)
        self.notify_preset_content_changed(updated.file_name)
        if self.is_selected_file_name(updated.file_name):
            self.preset_mode_coordinator.refresh_selected_launch_preset(self.launch_method)
        return updated

    def save_selected_source_text(self, source_text: str) -> PresetManifest:
        selected_file_name = self.get_selected_file_name()
        if not selected_file_name:
            raise ValueError("Selected preset is required")
        return self.save_source_text_by_file_name(selected_file_name, source_text)

    def rename_by_file_name(self, file_name: str, new_name: str) -> PresetManifest:
        return _rename_by_file_name(self, file_name, new_name)

    def duplicate_by_file_name(self, file_name: str, new_name: str) -> PresetManifest:
        return _duplicate_by_file_name(self, file_name, new_name)

    def create(self, name: str, *, from_current: bool = True) -> PresetManifest:
        return _create_preset(self, name, from_current=from_current)

    def import_from_file(self, src_path: Path, name: str | None = None) -> PresetManifest:
        return _import_from_file(self, src_path, name=name)

    def export_plain_text_by_file_name(self, file_name: str, dest_path: Path) -> Path:
        return _export_plain_text_by_file_name(self, file_name, dest_path)

    def reset_to_builtin_by_file_name(self, file_name: str) -> PresetManifest:
        return _reset_to_builtin_by_file_name(self, file_name)

    def reset_all_to_builtin(self) -> tuple[int, int, list[str]]:
        return _reset_all_to_builtin(self)

    def delete_by_file_name(self, file_name: str) -> None:
        _delete_by_file_name(self, file_name)
