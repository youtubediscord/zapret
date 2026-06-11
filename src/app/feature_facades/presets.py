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
            from presets.services_bundle import create_preset_services

            self._services = create_preset_services(self._app_paths)
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

    def get_selected_raw_preset_name(self, launch_method: str) -> str:
        selected = self.get_selected_source_preset_manifest(launch_method)
        return (selected.name if selected is not None else "").strip()

    def get_selected_raw_preset_file_name(self, launch_method: str) -> str:
        return (self.get_selected_source_preset_file_name(launch_method) or "").strip()

    def create_raw_preset_load_worker(self, request_id: int, *, launch_method: str, file_name: str, parent=None):
        from presets.raw_preset_editor_workflow import load_raw_preset_for_file
        from presets.raw_preset_loader import RawPresetLoadWorker

        clean_launch_method = str(launch_method or "").strip()

        def _load_preset(file_name: str):
            return load_raw_preset_for_file(
                presets_feature=self,
                launch_method=clean_launch_method,
                file_name=file_name,
            )

        return RawPresetLoadWorker(request_id, _load_preset, file_name, parent)

    def create_raw_preset_save_worker(
        self,
        request_id: int,
        *,
        launch_method: str,
        file_name: str,
        source_text: str,
        publish_content_changed: bool,
        parent=None,
    ):
        from presets.raw_preset_editor_workflow import save_raw_preset_text
        from presets.raw_preset_loader import RawPresetSaveWorker

        clean_launch_method = str(launch_method or "").strip()

        def _save_text(
            *,
            file_name: str,
            source_text: str,
            publish_content_changed: bool = True,
        ):
            return save_raw_preset_text(
                presets_feature=self,
                launch_method=clean_launch_method,
                file_name=file_name,
                source_text=source_text,
                publish_content_changed=publish_content_changed,
            )

        return RawPresetSaveWorker(
            request_id,
            _save_text,
            file_name=file_name,
            source_text=source_text,
            publish_content_changed=publish_content_changed,
            parent=parent,
        )

    def create_raw_preset_activate_worker(self, request_id: int, *, launch_method: str, file_name: str, parent=None):
        from presets.raw_preset_editor_workflow import activate_raw_preset
        from presets.raw_preset_loader import RawPresetActivateWorker

        clean_launch_method = str(launch_method or "").strip()

        def _activate(*, file_name: str) -> bool:
            return activate_raw_preset(
                presets_feature=self,
                launch_method=clean_launch_method,
                file_name=file_name,
            )

        return RawPresetActivateWorker(request_id, _activate, file_name, parent)

    def create_raw_preset_action_worker(
        self,
        request_id: int,
        *,
        launch_method: str,
        action: str,
        payload: dict | None = None,
        parent=None,
    ):
        from presets.raw_preset_editor_workflow import (
            delete_raw_preset,
            duplicate_raw_preset,
            export_raw_preset,
            get_raw_preset_source_path,
            open_raw_preset_source_file,
            rename_raw_preset,
            reset_raw_preset_to_builtin,
        )
        from presets.raw_preset_loader import RawPresetActionWorker

        clean_launch_method = str(launch_method or "").strip()

        def _open_source_file(path) -> None:
            open_raw_preset_source_file(presets_feature=self, path=path)

        def _rename_preset(*, file_name: str, new_name: str):
            return rename_raw_preset(
                presets_feature=self,
                launch_method=clean_launch_method,
                file_name=file_name,
                new_name=new_name,
            )

        def _duplicate_preset(*, file_name: str, new_name: str):
            return duplicate_raw_preset(
                presets_feature=self,
                launch_method=clean_launch_method,
                file_name=file_name,
                new_name=new_name,
            )

        def _export_preset(*, file_name: str, target_path: str) -> None:
            export_raw_preset(
                presets_feature=self,
                launch_method=clean_launch_method,
                file_name=file_name,
                target_path=target_path,
            )

        def _reset_to_builtin(*, file_name: str):
            return reset_raw_preset_to_builtin(
                presets_feature=self,
                launch_method=clean_launch_method,
                file_name=file_name,
            )

        def _delete_preset(*, file_name: str) -> None:
            delete_raw_preset(
                presets_feature=self,
                launch_method=clean_launch_method,
                file_name=file_name,
            )

        def _source_path(file_name: str):
            return get_raw_preset_source_path(
                presets_feature=self,
                launch_method=clean_launch_method,
                file_name=file_name,
            )

        return RawPresetActionWorker(
            request_id,
            _open_source_file,
            _rename_preset,
            _duplicate_preset,
            _export_preset,
            _reset_to_builtin,
            _delete_preset,
            _source_path,
            action=action,
            payload=payload,
            parent=parent,
        )

    def create_user_presets_open_folder_worker(self, request_id: int, *, launch_method: str, parent=None):
        from presets.user_presets_action_workers import UserPresetOpenFolderWorker

        def _open_folder() -> None:
            self.open_user_presets_folder(launch_method)

        return UserPresetOpenFolderWorker(
            request_id,
            _open_folder,
            parent=parent,
        )

    def create_preset_edit_action_worker(
        self,
        request_id: int,
        *,
        launch_method: str,
        action: str,
        name: str = "",
        current_name: str = "",
        new_name: str = "",
        from_current: bool = False,
        parent=None,
    ):
        from presets.user_presets_action_results import UserPresetActionResult
        from presets.user_presets_action_workers import UserPresetEditActionWorker

        def _create_preset(*, name: str, from_current: bool) -> UserPresetActionResult:
            created = self.create_preset(launch_method, name, from_current=from_current)
            return UserPresetActionResult(
                ok=True,
                log_level="INFO",
                log_message=f"Создан пресет '{name}'",
                infobar_level=None,
                infobar_title="",
                infobar_content="",
                structure_changed=True,
                preset_file_name=created.file_name,
                preset_display_name=created.name,
            )

        def _rename_preset(*, current_name: str, new_name: str) -> UserPresetActionResult:
            updated = self.rename_preset_by_file_name(launch_method, current_name, new_name)
            switched_file_name = (
                updated.file_name
                if self.is_selected_source_preset_file(launch_method, updated.file_name)
                else None
            )
            return UserPresetActionResult(
                ok=True,
                log_level="INFO",
                log_message=f"Пресет '{current_name}' переименован в '{new_name}'",
                infobar_level=None,
                infobar_title="",
                infobar_content="",
                structure_changed=True,
                switched_file_name=switched_file_name,
                preset_file_name=updated.file_name,
                preset_display_name=updated.name,
            )

        return UserPresetEditActionWorker(
            request_id,
            _create_preset,
            _rename_preset,
            action=action,
            name=name,
            current_name=current_name,
            new_name=new_name,
            from_current=from_current,
            parent=parent,
        )

    def create_preset_bulk_action_worker(
        self,
        request_id: int,
        *,
        launch_method: str,
        action: str,
        file_path: str = "",
        parent=None,
    ):
        from pathlib import Path

        from presets.user_presets_action_results import UserPresetImportResult, UserPresetResetAllResult
        from presets.user_presets_action_workers import UserPresetBulkActionWorker

        def _import_preset_from_file(*, file_path: str) -> UserPresetImportResult:
            requested_name = str(Path(file_path).stem or "").strip() or "Imported"
            imported = self.import_preset_from_file(launch_method, file_path, requested_name)
            actual_name = imported.name
            actual_file_name = imported.file_name
            expected_file_name = f"{requested_name}.txt" if requested_name else ""
            file_name_changed = bool(
                actual_file_name and expected_file_name and actual_file_name.casefold() != expected_file_name.casefold()
            )
            content = (
                "Пресет импортирован.\n"
                f"Отображаемое имя: {actual_name}\n"
                f"Имя файла: {actual_file_name}"
            )
            return UserPresetImportResult(
                ok=True,
                actual_name=actual_name,
                actual_file_name=actual_file_name,
                requested_name=requested_name,
                log_level="INFO",
                log_message=f"Импортирован пресет '{actual_name}'",
                infobar_level="warning" if file_name_changed else "success",
                infobar_title="Импортирован с новым именем файла" if file_name_changed else "Пресет импортирован",
                infobar_content=content,
                structure_changed=True,
            )

        def _reset_all_presets() -> UserPresetResetAllResult:
            success_count, total, failed = self.reset_all_presets_to_builtin(launch_method)
            selected_file_name = self.get_selected_source_preset_file_name(launch_method)
            failed_count = len(failed or [])
            if failed_count:
                log_message = (
                    "Сброс встроенных пресетов завершён с ошибками: "
                    f"сброшено={success_count}, ошибки={failed_count}, всего встроенных={total}"
                )
                level = "WARNING"
            elif int(success_count or 0) > 0:
                log_message = f"Сброшено встроенных пресетов: {success_count}"
                level = "INFO"
            else:
                log_message = "Сброс встроенных пресетов: нечего менять"
                level = "INFO"
            return UserPresetResetAllResult(
                ok=True,
                success_count=int(success_count or 0),
                total_count=int(total or 0),
                failed_count=failed_count,
                log_level=level,
                log_message=log_message,
                structure_changed=True,
                switched_file_name=selected_file_name,
            )

        return UserPresetBulkActionWorker(
            request_id,
            _import_preset_from_file,
            _reset_all_presets,
            action=action,
            file_path=file_path,
            parent=parent,
        )

    def create_preset_activate_worker(
        self,
        request_id: int,
        *,
        launch_method: str,
        file_name: str,
        display_name: str,
        activate_error_level: str,
        activate_error_mode: str,
        parent=None,
    ):
        from presets.user_presets_action_results import UserPresetActivationResult
        from presets.user_presets_action_workers import UserPresetActivateWorker

        def _activate_preset(*, file_name: str, display_name: str) -> UserPresetActivationResult:
            preset_file_name = str(file_name or "").strip()
            preset_display_name = str(display_name or preset_file_name).strip() or preset_file_name
            try:
                try:
                    selected_file_name = str(self.get_selected_source_preset_file_name(launch_method) or "").strip()
                except Exception:
                    selected_file_name = ""
                if selected_file_name and selected_file_name.casefold() == preset_file_name.casefold():
                    return UserPresetActivationResult(
                        ok=True,
                        log_level="DEBUG",
                        log_message=f"Пресет '{preset_display_name}' уже выбран",
                        infobar_level=None,
                        infobar_title="",
                        infobar_content="",
                        activated_file_name=selected_file_name,
                    )
                self.activate_preset_file(launch_method, preset_file_name)
                return UserPresetActivationResult(
                    ok=True,
                    log_level="INFO",
                    log_message=f"Активирован пресет '{preset_display_name}'",
                    infobar_level=None,
                    infobar_title="",
                    infobar_content="",
                    activated_file_name=preset_file_name,
                )
            except Exception as exc:
                content = (
                    f"Не удалось активировать пресет '{preset_display_name}'"
                    if str(activate_error_mode or "") == "friendly"
                    else f"Ошибка: {exc}"
                )
                return UserPresetActivationResult(
                    ok=False,
                    log_level="ERROR",
                    log_message=f"Ошибка активации пресета: {exc}",
                    infobar_level=activate_error_level,
                    infobar_title="Ошибка",
                    infobar_content=content,
                    activated_file_name=None,
                )

        return UserPresetActivateWorker(
            request_id,
            _activate_preset,
            file_name=file_name,
            display_name=display_name,
            parent=parent,
        )

    def create_preset_item_action_worker(
        self,
        request_id: int,
        *,
        launch_method: str,
        action: str,
        file_name: str,
        display_name: str,
        file_path: str = "",
        parent=None,
    ):
        from presets.user_presets_action_results import UserPresetActionResult
        from presets.user_presets_action_workers import UserPresetItemActionWorker

        def _duplicate_preset(*, file_name: str, display_name: str) -> UserPresetActionResult:
            new_name = f"{display_name} (копия)"
            duplicated = self.duplicate_preset_by_file_name(launch_method, file_name, new_name)
            return UserPresetActionResult(
                ok=True,
                log_level="INFO",
                log_message=f"Пресет '{display_name}' дублирован как '{new_name}'",
                infobar_level=None,
                infobar_title="",
                infobar_content="",
                structure_changed=True,
                preset_file_name=duplicated.file_name,
                preset_display_name=duplicated.name,
            )

        def _reset_preset_to_builtin(*, file_name: str, display_name: str) -> UserPresetActionResult:
            self.reset_preset_to_builtin_by_file_name(launch_method, file_name)
            return UserPresetActionResult(
                ok=True,
                log_level="INFO",
                log_message=f"Восстановлен встроенный пресет для '{display_name}'",
                infobar_level=None,
                infobar_title="",
                infobar_content="",
                structure_changed=False,
            )

        def _delete_preset(*, file_name: str, display_name: str) -> UserPresetActionResult:
            if self._is_builtin_preset_file(launch_method, file_name):
                return UserPresetActionResult(
                    ok=False,
                    log_level="WARNING",
                    log_message="Встроенные пресеты удалять нельзя",
                    infobar_level="warning",
                    infobar_title="Ошибка",
                    infobar_content="Встроенные пресеты удалять нельзя. Можно удалить только пользовательские пресеты.",
                    structure_changed=False,
                )
            try:
                self.delete_preset_by_file_name(launch_method, file_name)
            except Exception as exc:
                if "Preset not found" in str(exc):
                    return UserPresetActionResult(
                        ok=False,
                        log_level="ERROR",
                        log_message=f"Ошибка удаления пресета: {exc}",
                        infobar_level=None,
                        infobar_title="",
                        infobar_content="",
                        structure_changed=False,
                        error_code="not_found",
                    )
                raise
            return UserPresetActionResult(
                ok=True,
                log_level="INFO",
                log_message=f"Удалён пресет '{display_name}'",
                infobar_level=None,
                infobar_title="",
                infobar_content="",
                structure_changed=True,
            )

        def _export_preset(*, file_name: str, file_path: str, display_name: str) -> UserPresetActionResult:
            self.export_preset_plain_text(launch_method, file_name, file_path)
            return UserPresetActionResult(
                ok=True,
                log_level="INFO",
                log_message=f"Экспортирован пресет '{display_name}' в {file_path}",
                infobar_level="success",
                infobar_title="Успех",
                infobar_content=f"Пресет экспортирован: {file_path}",
                structure_changed=False,
            )

        return UserPresetItemActionWorker(
            request_id,
            _duplicate_preset,
            _reset_preset_to_builtin,
            _delete_preset,
            _export_preset,
            action=action,
            file_name=file_name,
            display_name=display_name,
            file_path=file_path,
            parent=parent,
        )

    def create_preset_link_action_worker(self, request_id: int, *, open_url, action: str, parent=None):
        from config.urls import PRESET_INFO_URL, SUPPORT_DISCUSSIONS_URL
        from presets.user_presets_action_results import UserPresetActionResult
        from presets.user_presets_action_workers import UserPresetLinkActionWorker

        def _open_url_action(url: str, *, success_message: str, error_message: str) -> UserPresetActionResult:
            try:
                result = open_url(url)
                if not getattr(result, "ok", False):
                    raise RuntimeError(getattr(result, "error", "Не удалось открыть ссылку"))
                return UserPresetActionResult(
                    ok=True,
                    log_level="INFO",
                    log_message=success_message,
                    infobar_level=None,
                    infobar_title="",
                    infobar_content="",
                    structure_changed=False,
                )
            except Exception as exc:
                return UserPresetActionResult(
                    ok=False,
                    log_level="ERROR",
                    log_message=f"{error_message}: {exc}",
                    infobar_level="warning",
                    infobar_title="Ошибка",
                    infobar_content=f"{error_message}: {exc}",
                    structure_changed=False,
                )

        return UserPresetLinkActionWorker(
            request_id,
            lambda: _open_url_action(
                PRESET_INFO_URL,
                success_message=f"Открыта страница о пресетах: {PRESET_INFO_URL}",
                error_message="Не удалось открыть страницу о пресетах",
            ),
            lambda: _open_url_action(
                SUPPORT_DISCUSSIONS_URL,
                success_message=f"Открыта страница пресетов: {SUPPORT_DISCUSSIONS_URL}",
                error_message="Не удалось открыть страницу пресетов",
            ),
            action=action,
            parent=parent,
        )

    def _is_builtin_preset_file(self, launch_method: str, file_name: str) -> bool:
        candidate = str(file_name or "").strip()
        if not candidate or not candidate.lower().endswith(".txt"):
            return False
        try:
            manifest = self.get_preset_manifest_by_file_name(launch_method, candidate)
            if manifest is not None:
                return str(getattr(manifest, "kind", "") or "").strip().lower() == "builtin"
        except Exception:
            pass
        return False

    def load_preset_folder_state(self, scope_key: str):
        from presets.folders import load_preset_folder_state

        return load_preset_folder_state(scope_key)

    def create_preset_folder_action_worker(
        self,
        request_id: int,
        *,
        scope_key: str,
        action: str,
        folder_key: str = "",
        name: str = "",
        direction: int = 0,
        collapsed: bool = False,
        context_extra: dict | None = None,
        parent=None,
    ):
        from presets.folders import (
            create_preset_folder,
            delete_preset_folder,
            load_preset_folder_state,
            move_preset_folder_by_step,
            rename_preset_folder,
            reset_preset_folders,
            set_preset_folder_collapsed,
        )
        from presets.user_presets_action_workers import UserPresetFolderActionWorker

        return UserPresetFolderActionWorker(
            request_id,
            load_preset_folder_state,
            create_preset_folder,
            rename_preset_folder,
            delete_preset_folder,
            move_preset_folder_by_step,
            set_preset_folder_collapsed,
            reset_preset_folders,
            scope_key=scope_key,
            action=action,
            folder_key=folder_key,
            name=name,
            direction=direction,
            collapsed=collapsed,
            context_extra=context_extra,
            parent=parent,
        )

    def create_preset_storage_action_worker(
        self,
        request_id: int,
        *,
        scope_key: str,
        list_preset_entries,
        action: str,
        name: str = "",
        display_name: str = "",
        rating: int = 0,
        direction: int = 0,
        cached_metadata=None,
        source_kind: str = "",
        source_id: str = "",
        destination_kind: str = "",
        destination_id: str = "",
        destination_folder_key: str = "",
        parent=None,
    ):
        from folders.defaults import classify_preset_folder
        from folders.ordering import build_folder_rows
        from presets.folders import (
            load_preset_folder_state,
            move_preset_after,
            move_preset_before,
            move_preset_by_step,
            move_preset_to_end,
            move_preset_to_folder,
            set_preset_rating,
            toggle_preset_pin,
        )
        from presets.user_presets_action_workers import UserPresetStorageActionWorker

        clean_scope = str(scope_key or "")

        def _build_move_live_items(cached_metadata=None) -> list[dict[str, object]]:
            live_items = []
            metadata = cached_metadata if isinstance(cached_metadata, dict) else {}
            for entry in tuple(list_preset_entries() or ()):
                item_file_name = str(entry.get("file_name") or entry.get("key") or "").strip()
                if not item_file_name:
                    continue
                cached = metadata.get(item_file_name) if isinstance(metadata.get(item_file_name), dict) else {}
                item_display_name = str(
                    (cached or {}).get("display_name")
                    or entry.get("display_name")
                    or entry.get("name")
                    or item_file_name
                ).strip()
                live_items.append(
                    {
                        "key": item_file_name,
                        "name": item_display_name or item_file_name,
                        "folder_key": classify_preset_folder(item_display_name or item_file_name, clean_scope),
                    }
                )
            return live_items

        def _move_step_destination_context(
            file_name: str,
            step: int,
            *,
            live_items: list[dict[str, object]],
        ) -> dict[str, str]:
            source = str(file_name or "").strip()
            if not source:
                return {}
            try:
                rows = build_folder_rows(
                    load_preset_folder_state(clean_scope),
                    live_items=live_items,
                    include_pinned_folder=True,
                )
            except Exception:
                return {}
            ordered = [
                (
                    str(row.get("key") or "").strip(),
                    str(row.get("folder_key") or "").strip(),
                )
                for row in rows
                if row.get("kind") == "item" and str(row.get("key") or "").strip()
            ]
            keys = [key for key, _folder_key in ordered]
            if source not in keys:
                return {}
            index = keys.index(source)
            direction = 1 if int(step or 0) > 0 else -1
            target_index = index + direction
            if target_index < 0 or target_index >= len(ordered):
                return {}
            target_key, target_folder_key = ordered[target_index]
            return {
                "destination_kind": "preset_after" if direction > 0 else "preset",
                "destination_id": target_key,
                "destination_folder_key": target_folder_key,
            }

        def _move_by_step(file_name: str, step: int, *, cached_metadata=None):
            live_items = _build_move_live_items(cached_metadata)
            destination_context = _move_step_destination_context(
                file_name,
                step,
                live_items=live_items,
            )
            moved = bool(move_preset_by_step(clean_scope, file_name, step, live_items=live_items))
            if not moved:
                return False
            if destination_context:
                return {"ok": True, **destination_context}
            return True

        def _move_on_drop(
            *,
            source_kind: str,
            source_id: str,
            destination_kind: str,
            destination_id: str,
            destination_folder_key: str = "",
        ) -> bool:
            if source_kind != "preset":
                return False
            if destination_kind == "folder" and destination_id:
                return bool(move_preset_to_folder(clean_scope, source_id, destination_id))
            if destination_kind == "preset" and destination_id:
                return bool(
                    move_preset_before(
                        clean_scope,
                        source_id,
                        destination_id,
                        destination_folder_key=destination_folder_key,
                    )
                )
            if destination_kind == "preset_after" and destination_id:
                return bool(
                    move_preset_after(
                        clean_scope,
                        source_id,
                        destination_id,
                        destination_folder_key=destination_folder_key,
                    )
                )
            return bool(move_preset_to_end(clean_scope, source_id))

        return UserPresetStorageActionWorker(
            request_id,
            lambda file_name, *, display_name="": toggle_preset_pin(
                clean_scope,
                file_name,
                display_name=display_name,
            ),
            lambda file_name, value, *, display_name="": set_preset_rating(
                clean_scope,
                file_name,
                value,
                display_name=display_name,
            ),
            _move_by_step,
            _move_on_drop,
            lambda: load_preset_folder_state(clean_scope),
            action=action,
            name=name,
            display_name=display_name,
            rating=rating,
            direction=direction,
            cached_metadata=cached_metadata,
            source_kind=source_kind,
            source_id=source_id,
            destination_kind=destination_kind,
            destination_id=destination_id,
            destination_folder_key=destination_folder_key,
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
