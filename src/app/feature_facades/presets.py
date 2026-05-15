from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import presets.commands as preset_commands
import presets.display_state as preset_display


@dataclass(slots=True)
class PresetsFeature:
    _services: Any
    _profile_feature: Any = None

    @classmethod
    def create(cls, app_paths):
        return cls(_services=preset_commands.create_preset_services(app_paths))

    def attach_profile_feature(self, profile_feature) -> None:
        self._profile_feature = profile_feature

    def list_preset_manifests(self, launch_method: str):
        return preset_commands.list_preset_manifests(launch_method, preset_services=self._services)

    def get_preset_manifest_by_file_name(self, launch_method: str, file_name: str):
        return preset_commands.get_preset_manifest_by_file_name(launch_method, file_name, preset_services=self._services)

    def get_preset_source_path_by_file_name(self, launch_method: str, file_name: str):
        return preset_commands.get_preset_source_path_by_file_name(launch_method, file_name, preset_services=self._services)

    def get_selected_source_preset_manifest(self, launch_method: str):
        return preset_commands.get_selected_source_preset_manifest(launch_method, preset_services=self._services)

    def get_selected_source_preset_file_name(self, launch_method: str) -> str:
        return preset_commands.get_selected_source_preset_file_name(launch_method, preset_services=self._services)

    def is_selected_source_preset_file(self, launch_method: str, file_name: str) -> bool:
        selected = str(self.get_selected_source_preset_file_name(launch_method) or "").strip()
        candidate = str(file_name or "").strip()
        return bool(selected and candidate and selected.lower() == candidate.lower())

    def get_selected_source_preset_display(self, launch_method: str) -> tuple[str, str]:
        return preset_commands.get_selected_source_preset_display(launch_method, preset_services=self._services)

    def activate_preset_file(self, launch_method: str, file_name: str):
        return preset_commands.activate_preset_file(launch_method, file_name, preset_services=self._services)

    def connect_preset_signals(self, launch_method: str, **callbacks) -> None:
        return preset_commands.connect_preset_signals(launch_method, preset_services=self._services, **callbacks)

    def get_selected_source_path(self, launch_method: str):
        return preset_commands.get_selected_source_path(launch_method, preset_services=self._services)

    def get_selection_state(self, launch_method: str, *, profile_key: str = ""):
        return preset_commands.get_selection_state(
            launch_method,
            preset_services=self._services,
            profile_feature=self._profile_feature,
            profile_key=profile_key,
        )

    def select_preset(self, launch_method: str, file_name: str):
        return preset_commands.select_preset(
            launch_method,
            file_name,
            preset_services=self._services,
            profile_feature=self._profile_feature,
        )

    def select_profile(self, launch_method: str, profile_key: str):
        return preset_commands.select_profile(
            launch_method,
            profile_key,
            preset_services=self._services,
            profile_feature=self._profile_feature,
        )

    def refresh_preset_summary(self, launch_method: str, *, profile_key: str = ""):
        return preset_commands.refresh_preset_summary(
            launch_method,
            preset_services=self._services,
            profile_feature=self._profile_feature,
            profile_key=profile_key,
        )

    def get_user_presets_dir(self, launch_method: str):
        return preset_commands.get_user_presets_dir(launch_method, preset_services=self._services)

    def open_user_presets_folder(self, launch_method: str) -> None:
        return preset_commands.open_user_presets_folder(launch_method, preset_services=self._services)

    def open_preset_source_file(self, path) -> None:
        return preset_commands.open_preset_source_file(path)

    def save_preset_source_by_file_name(self, launch_method: str, file_name: str, source_text: str):
        return preset_commands.save_preset_source_by_file_name(
            launch_method,
            file_name,
            source_text,
            preset_services=self._services,
        )

    def read_preset_source_by_file_name(self, launch_method: str, file_name: str) -> str:
        return preset_commands.read_preset_source_by_file_name(launch_method, file_name, preset_services=self._services)

    def read_selected_preset_source(self, launch_method: str):
        return preset_commands.read_selected_preset_source(launch_method, preset_services=self._services)

    def save_selected_preset_source(self, launch_method: str, source_text: str):
        return preset_commands.save_selected_preset_source(launch_method, source_text, preset_services=self._services)

    def get_launch_snapshot(self, launch_method: str, **kwargs):
        return preset_commands.get_launch_snapshot(launch_method, preset_services=self._services, **kwargs)

    def create_preset(self, launch_method: str, name: str, *, from_current: bool = True):
        return preset_commands.create_preset(
            launch_method,
            name,
            from_current=from_current,
            preset_services=self._services,
        )

    def rename_preset_by_file_name(self, launch_method: str, file_name: str, new_name: str):
        return preset_commands.rename_preset_by_file_name(
            launch_method,
            file_name,
            new_name,
            preset_services=self._services,
        )

    def duplicate_preset_by_file_name(self, launch_method: str, file_name: str, new_name: str):
        return preset_commands.duplicate_preset_by_file_name(
            launch_method,
            file_name,
            new_name,
            preset_services=self._services,
        )

    def import_preset_from_file(self, launch_method: str, src_path, name: str | None = None):
        return preset_commands.import_preset_from_file(
            launch_method,
            src_path,
            name,
            preset_services=self._services,
        )

    def export_preset_plain_text(self, launch_method: str, file_name: str, dest_path):
        return preset_commands.export_preset_plain_text(
            launch_method,
            file_name,
            dest_path,
            preset_services=self._services,
        )

    def reset_preset_to_builtin_by_file_name(self, launch_method: str, file_name: str):
        return preset_commands.reset_preset_to_builtin_by_file_name(
            launch_method,
            file_name,
            preset_services=self._services,
        )

    def reset_all_presets_to_builtin(self, launch_method: str):
        return preset_commands.reset_all_presets_to_builtin(launch_method, preset_services=self._services)

    def delete_preset_by_file_name(self, launch_method: str, file_name: str) -> None:
        return preset_commands.delete_preset_by_file_name(launch_method, file_name, preset_services=self._services)

    def refresh_profile_strategy_summary_in_store(self, *, method: str, profile_feature, ui_state_store) -> None:
        return preset_display.refresh_profile_strategy_summary_in_store(
            method=method,
            profile_feature=profile_feature,
            ui_state_store=ui_state_store,
        )

    def refresh_launch_summary_in_store(self, *, method: str, profile_feature, ui_state_store) -> None:
        return preset_display.refresh_launch_summary_in_store(
            method=method,
            profile_feature=profile_feature,
            ui_state_store=ui_state_store,
        )
