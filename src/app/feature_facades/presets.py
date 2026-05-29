from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class PresetsFeature:
    _services: Any = None
    _app_paths: Any = None
    _profile_feature: Any = None
    _preset_list_metadata_cache: Any = None
    _preset_list_metadata_lock: Any = None

    @staticmethod
    def _commands():
        import presets.commands as preset_commands

        return preset_commands

    @staticmethod
    def _display_state():
        import presets.display_state as preset_display

        return preset_display

    @classmethod
    def create(cls, app_paths):
        return cls(_app_paths=app_paths)

    def _preset_services(self):
        if self._services is None:
            self._services = self._commands().create_preset_services(self._app_paths)
        return self._services

    def _metadata_cache(self) -> dict:
        if self._preset_list_metadata_cache is None:
            self._preset_list_metadata_cache = {}
        return self._preset_list_metadata_cache

    def _metadata_lock(self):
        if self._preset_list_metadata_lock is None:
            import threading

            self._preset_list_metadata_lock = threading.RLock()
        return self._preset_list_metadata_lock

    def attach_profile_feature(self, profile_feature) -> None:
        self._profile_feature = profile_feature

    def list_preset_manifests(self, launch_method: str):
        return self._commands().list_preset_manifests(launch_method, preset_services=self._preset_services())

    def warm_preset_list_metadata_cache(self, launch_method: str):
        signature, metadata = self._build_preset_list_metadata_snapshot(launch_method)
        with self._metadata_lock():
            self._metadata_cache()[str(launch_method or "").strip()] = (signature, dict(metadata))
        return dict(metadata)

    def get_cached_preset_list_metadata(self, launch_method: str):
        method = str(launch_method or "").strip()
        with self._metadata_lock():
            cached = self._metadata_cache().get(method)
        if cached is None:
            return None
        cached_signature, cached_metadata = cached
        try:
            signature = self._build_preset_list_metadata_signature(launch_method)
        except Exception:
            return None
        if signature != cached_signature:
            return None
        return dict(cached_metadata)

    def peek_cached_preset_list_metadata(self, launch_method: str):
        method = str(launch_method or "").strip()
        with self._metadata_lock():
            cached = self._metadata_cache().get(method)
        if cached is None:
            return None
        _cached_signature, cached_metadata = cached
        return dict(cached_metadata)

    def _build_preset_list_metadata_snapshot(self, launch_method: str):
        from presets.lightweight_metadata import build_lightweight_preset_metadata

        entries = self._preset_list_metadata_entries(launch_method)
        metadata = {
            file_name: build_lightweight_preset_metadata(
                path,
                display_name=display_name,
                kind=kind,
                is_builtin=is_builtin,
            )
            for file_name, display_name, kind, is_builtin, path, _stat_key in entries
        }
        signature = tuple((file_name, str(path), stat_key) for file_name, _display, _kind, _builtin, path, stat_key in entries)
        return signature, metadata

    def _build_preset_list_metadata_signature(self, launch_method: str):
        return tuple(
            (file_name, str(path), stat_key)
            for file_name, _display, _kind, _builtin, path, stat_key in self._preset_list_metadata_entries(launch_method)
        )

    def _preset_list_metadata_entries(self, launch_method: str):
        from settings.mode import engine_for_launch_method_or_none

        method = str(launch_method or "").strip()
        engine = engine_for_launch_method_or_none(method)
        if engine is None:
            return ()

        services = self._preset_services()
        engine_paths = services.app_paths.engine_paths(engine).ensure_directories()
        entries = []
        for manifest in self.list_preset_manifests(method):
            file_name = str(getattr(manifest, "file_name", "") or "").strip()
            if not file_name:
                continue
            display_name = str(getattr(manifest, "name", "") or file_name).strip()
            kind = str(getattr(manifest, "kind", "") or "user").strip() or "user"
            storage_scope = str(getattr(manifest, "storage_scope", "") or "").strip().lower()
            is_builtin = kind.lower() == "builtin" or storage_scope == "builtin"
            path = (engine_paths.builtin_presets_dir if storage_scope == "builtin" else engine_paths.user_presets_dir) / file_name
            entries.append((file_name, display_name, kind, is_builtin, path, self._preset_file_stat_key(path)))
        return tuple(entries)

    @staticmethod
    def _preset_file_stat_key(path) -> tuple[int, int]:
        try:
            stat_result = path.stat()
            return (
                int(getattr(stat_result, "st_mtime_ns", 0) or 0),
                int(getattr(stat_result, "st_size", 0) or 0),
            )
        except Exception:
            return (0, 0)

    def get_preset_manifest_by_file_name(self, launch_method: str, file_name: str):
        return self._commands().get_preset_manifest_by_file_name(launch_method, file_name, preset_services=self._preset_services())

    def get_preset_source_path_by_file_name(self, launch_method: str, file_name: str):
        return self._commands().get_preset_source_path_by_file_name(launch_method, file_name, preset_services=self._preset_services())

    def get_selected_source_preset_manifest(self, launch_method: str):
        return self._commands().get_selected_source_preset_manifest(launch_method, preset_services=self._preset_services())

    def get_selected_source_preset_file_name(self, launch_method: str) -> str:
        return self._commands().get_selected_source_preset_file_name(launch_method, preset_services=self._preset_services())

    def is_selected_source_preset_file(self, launch_method: str, file_name: str) -> bool:
        selected = str(self.get_selected_source_preset_file_name(launch_method) or "").strip()
        candidate = str(file_name or "").strip()
        return bool(selected and candidate and selected.lower() == candidate.lower())

    def get_selected_source_preset_display(self, launch_method: str) -> tuple[str, str]:
        return self._commands().get_selected_source_preset_display(launch_method, preset_services=self._preset_services())

    def activate_preset_file(self, launch_method: str, file_name: str):
        return self._commands().activate_preset_file(launch_method, file_name, preset_services=self._preset_services())

    def connect_preset_signals(self, launch_method: str, **callbacks) -> None:
        return self._commands().connect_preset_signals(launch_method, preset_services=self._preset_services(), **callbacks)

    def get_selected_source_path(self, launch_method: str):
        return self._commands().get_selected_source_path(launch_method, preset_services=self._preset_services())

    def get_selection_state(self, launch_method: str, *, profile_key: str = ""):
        return self._commands().get_selection_state(
            launch_method,
            preset_services=self._preset_services(),
            profile_feature=self._profile_feature,
            profile_key=profile_key,
        )

    def select_preset(self, launch_method: str, file_name: str):
        return self._commands().select_preset(
            launch_method,
            file_name,
            preset_services=self._preset_services(),
            profile_feature=self._profile_feature,
        )

    def select_profile(self, launch_method: str, profile_key: str):
        return self._commands().select_profile(
            launch_method,
            profile_key,
            preset_services=self._preset_services(),
            profile_feature=self._profile_feature,
        )

    def refresh_preset_summary(self, launch_method: str, *, profile_key: str = ""):
        return self._commands().refresh_preset_summary(
            launch_method,
            preset_services=self._preset_services(),
            profile_feature=self._profile_feature,
            profile_key=profile_key,
        )

    def get_user_presets_dir(self, launch_method: str):
        return self._commands().get_user_presets_dir(launch_method, preset_services=self._preset_services())

    def open_user_presets_folder(self, launch_method: str) -> None:
        return self._commands().open_user_presets_folder(launch_method, preset_services=self._preset_services())

    def create_user_presets_open_folder_worker(self, request_id: int, *, launch_method: str, parent=None):
        from presets.user_presets_action_workers import UserPresetOpenFolderWorker

        def _open_folder() -> None:
            self.open_user_presets_folder(launch_method)

        return UserPresetOpenFolderWorker(
            request_id,
            _open_folder,
            parent=parent,
        )

    def open_preset_source_file(self, path) -> None:
        return self._commands().open_preset_source_file(path)

    def save_preset_source_by_file_name(
        self,
        launch_method: str,
        file_name: str,
        source_text: str,
        *,
        publish_content_changed: bool = True,
    ):
        return self._commands().save_preset_source_by_file_name(
            launch_method,
            file_name,
            source_text,
            preset_services=self._preset_services(),
            publish_content_changed=publish_content_changed,
        )

    def publish_preset_content_changed(self, launch_method: str, file_name: str):
        return self._commands().publish_preset_content_changed(
            launch_method,
            file_name,
            preset_services=self._preset_services(),
        )

    def read_preset_source_by_file_name(self, launch_method: str, file_name: str) -> str:
        return self._commands().read_preset_source_by_file_name(launch_method, file_name, preset_services=self._preset_services())

    def read_selected_preset_source(self, launch_method: str):
        return self._commands().read_selected_preset_source(launch_method, preset_services=self._preset_services())

    def save_selected_preset_source(self, launch_method: str, source_text: str):
        return self._commands().save_selected_preset_source(launch_method, source_text, preset_services=self._preset_services())

    def get_launch_snapshot(self, launch_method: str, **kwargs):
        return self._commands().get_launch_snapshot(launch_method, preset_services=self._preset_services(), **kwargs)

    def create_preset(self, launch_method: str, name: str, *, from_current: bool = True):
        return self._commands().create_preset(
            launch_method,
            name,
            from_current=from_current,
            preset_services=self._preset_services(),
        )

    def rename_preset_by_file_name(self, launch_method: str, file_name: str, new_name: str):
        return self._commands().rename_preset_by_file_name(
            launch_method,
            file_name,
            new_name,
            preset_services=self._preset_services(),
        )

    def duplicate_preset_by_file_name(self, launch_method: str, file_name: str, new_name: str):
        return self._commands().duplicate_preset_by_file_name(
            launch_method,
            file_name,
            new_name,
            preset_services=self._preset_services(),
        )

    def import_preset_from_file(self, launch_method: str, src_path, name: str | None = None):
        return self._commands().import_preset_from_file(
            launch_method,
            src_path,
            name,
            preset_services=self._preset_services(),
        )

    def export_preset_plain_text(self, launch_method: str, file_name: str, dest_path):
        return self._commands().export_preset_plain_text(
            launch_method,
            file_name,
            dest_path,
            preset_services=self._preset_services(),
        )

    def reset_preset_to_builtin_by_file_name(self, launch_method: str, file_name: str):
        return self._commands().reset_preset_to_builtin_by_file_name(
            launch_method,
            file_name,
            preset_services=self._preset_services(),
        )

    def reset_all_presets_to_builtin(self, launch_method: str):
        return self._commands().reset_all_presets_to_builtin(launch_method, preset_services=self._preset_services())

    def delete_preset_by_file_name(self, launch_method: str, file_name: str) -> None:
        return self._commands().delete_preset_by_file_name(launch_method, file_name, preset_services=self._preset_services())

    def refresh_profile_strategy_summary_in_store(self, *, method: str, profile_feature, ui_state_store) -> None:
        return self._display_state().refresh_profile_strategy_summary_in_store(
            method=method,
            profile_feature=profile_feature,
            ui_state_store=ui_state_store,
        )

    def refresh_launch_summary_in_store(self, *, method: str, profile_feature, ui_state_store) -> None:
        return self._display_state().refresh_launch_summary_in_store(
            method=method,
            profile_feature=profile_feature,
            ui_state_store=ui_state_store,
        )
