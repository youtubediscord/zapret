from __future__ import annotations

import webbrowser
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Protocol

from log.log import log



@dataclass(slots=True)
class UserPresetActionResult:
    ok: bool
    log_level: str
    log_message: str
    infobar_level: str | None
    infobar_title: str
    infobar_content: str
    structure_changed: bool
    switched_file_name: str | None = None
    error_code: str | None = None


@dataclass(slots=True)
class UserPresetImportResult:
    ok: bool
    actual_name: str
    actual_file_name: str
    requested_name: str
    log_level: str
    log_message: str
    infobar_level: str
    infobar_title: str
    infobar_content: str
    structure_changed: bool


@dataclass(slots=True)
class UserPresetResetAllResult:
    ok: bool
    success_count: int
    total_count: int
    failed_count: int
    log_level: str
    log_message: str
    structure_changed: bool
    switched_file_name: str | None


@dataclass(slots=True)
class UserPresetListPlan:
    rows: list[dict[str, object]]
    total_presets: int
    visible_presets: int
    query: str


@dataclass(slots=True)
class UserPresetActivationResult:
    ok: bool
    log_level: str
    log_message: str
    infobar_level: str | None
    infobar_title: str
    infobar_content: str
    activated_file_name: str | None


@dataclass(frozen=True, slots=True)
class UserPresetsPageControllerConfig:
    launch_method: str
    selection_key: str
    hierarchy_scope: str
    empty_not_found_key: str
    empty_none_key: str
    list_log_prefix: str
    activate_error_level: str
    activate_error_mode: str
    require_app_context: Callable[[], object]
    get_preset_store: Callable[[], object]


class UserPresetsListingApi(Protocol):
    def list_preset_entries_light(self) -> list[dict[str, object]]: ...
    def get_active_preset_name_light(self) -> str: ...
    def get_selected_source_preset_file_name_light(self) -> str: ...
    def get_presets_dir_light(self): ...
    def load_preset_list_metadata_light(self) -> dict[str, dict[str, object]]: ...
    def read_single_preset_list_metadata_light(self, file_name: str) -> tuple[str, dict[str, object]] | None: ...
    def resolve_display_name(self, reference: str) -> str: ...
    def build_preset_rows_plan(
        self,
        *,
        all_presets: dict[str, dict[str, object]],
        query: str,
        active_file_name: str,
        language: str,
    ) -> UserPresetListPlan: ...


class UserPresetsActionsApi(Protocol):
    def create_preset(self, *, name: str, from_current: bool) -> UserPresetActionResult: ...
    def rename_preset(self, *, current_name: str, new_name: str) -> UserPresetActionResult: ...
    def import_preset_from_file(self, *, file_path: str) -> UserPresetImportResult: ...
    def reset_all_presets(self) -> UserPresetResetAllResult: ...
    def activate_preset(self, *, file_name: str, display_name: str) -> UserPresetActivationResult: ...
    def duplicate_preset(self, *, file_name: str, display_name: str) -> UserPresetActionResult: ...
    def reset_preset_to_builtin(self, *, file_name: str, display_name: str) -> UserPresetActionResult: ...
    def delete_preset(self, *, file_name: str, display_name: str) -> UserPresetActionResult: ...
    def export_preset(self, *, file_name: str, file_path: str, display_name: str) -> UserPresetActionResult: ...
    def open_presets_info(self) -> UserPresetActionResult: ...
    def open_new_configs_post(self) -> UserPresetActionResult: ...


class UserPresetsStorageApi(Protocol):
    def get_preset_store(self): ...
    def get_hierarchy_store(self): ...
    def is_builtin_preset_file(self, name: str) -> bool: ...
    def is_builtin_preset_file_with_cache(self, name: str, cached_metadata: dict[str, dict[str, object]] | None) -> bool: ...
    def toggle_preset_pin(self, name: str) -> bool: ...
    def move_preset_by_step(self, name: str, direction: int, *, cached_metadata: dict[str, dict[str, object]] | None = None) -> bool: ...
    def move_preset_on_drop(
        self,
        *,
        source_kind: str,
        source_id: str,
        destination_kind: str,
        destination_id: str,
        cached_metadata: dict[str, dict[str, object]] | None = None,
    ) -> bool: ...


@dataclass(frozen=True, slots=True)
class UserPresetsPageApiBundle:
    listing: UserPresetsListingApi
    actions: UserPresetsActionsApi
    storage: UserPresetsStorageApi


class _UserPresetsListingApiImpl:
    def __init__(self, controller: "UserPresetsPageController") -> None:
        self._controller = controller

    def list_preset_entries_light(self) -> list[dict[str, object]]:
        return self._controller.list_preset_entries_light()

    def get_active_preset_name_light(self) -> str:
        return self._controller.get_active_preset_name_light()

    def get_selected_source_preset_file_name_light(self) -> str:
        return self._controller.get_selected_source_preset_file_name_light()

    def get_presets_dir_light(self):
        return self._controller.get_presets_dir_light()

    def load_preset_list_metadata_light(self) -> dict[str, dict[str, object]]:
        return self._controller.load_preset_list_metadata_light()

    def read_single_preset_list_metadata_light(self, file_name: str) -> tuple[str, dict[str, object]] | None:
        return self._controller.read_single_preset_list_metadata_light(file_name)

    def resolve_display_name(self, reference: str) -> str:
        return self._controller.resolve_display_name(reference)

    def build_preset_rows_plan(
        self,
        *,
        all_presets: dict[str, dict[str, object]],
        query: str,
        active_file_name: str,
        language: str,
    ) -> UserPresetListPlan:
        return self._controller.build_preset_rows_plan(
            all_presets=all_presets,
            query=query,
            active_file_name=active_file_name,
            language=language,
        )


class _UserPresetsActionsApiImpl:
    def __init__(self, controller: "UserPresetsPageController") -> None:
        self._controller = controller

    def create_preset(self, *, name: str, from_current: bool) -> UserPresetActionResult:
        return self._controller.create_preset(name=name, from_current=from_current)

    def rename_preset(self, *, current_name: str, new_name: str) -> UserPresetActionResult:
        return self._controller.rename_preset(current_name=current_name, new_name=new_name)

    def import_preset_from_file(self, *, file_path: str) -> UserPresetImportResult:
        return self._controller.import_preset_from_file(file_path=file_path)

    def reset_all_presets(self) -> UserPresetResetAllResult:
        return self._controller.reset_all_presets()

    def activate_preset(self, *, file_name: str, display_name: str) -> UserPresetActivationResult:
        return self._controller.activate_preset(file_name=file_name, display_name=display_name)

    def duplicate_preset(self, *, file_name: str, display_name: str) -> UserPresetActionResult:
        return self._controller.duplicate_preset(file_name=file_name, display_name=display_name)

    def reset_preset_to_builtin(self, *, file_name: str, display_name: str) -> UserPresetActionResult:
        return self._controller.reset_preset_to_builtin(file_name=file_name, display_name=display_name)

    def delete_preset(self, *, file_name: str, display_name: str) -> UserPresetActionResult:
        return self._controller.delete_preset(file_name=file_name, display_name=display_name)

    def export_preset(self, *, file_name: str, file_path: str, display_name: str) -> UserPresetActionResult:
        return self._controller.export_preset(file_name=file_name, file_path=file_path, display_name=display_name)

    def open_presets_info(self) -> UserPresetActionResult:
        return self._controller.open_presets_info()

    def open_new_configs_post(self) -> UserPresetActionResult:
        return self._controller.open_new_configs_post()


class _UserPresetsStorageApiImpl:
    def __init__(self, controller: "UserPresetsPageController") -> None:
        self._controller = controller

    def get_preset_store(self):
        return self._controller.get_preset_store()

    def get_hierarchy_store(self):
        return self._controller.get_hierarchy_store()

    def is_builtin_preset_file(self, name: str) -> bool:
        return self._controller.is_builtin_preset_file(name)

    def is_builtin_preset_file_with_cache(self, name: str, cached_metadata: dict[str, dict[str, object]] | None) -> bool:
        return self._controller.is_builtin_preset_file_with_cache(name, cached_metadata)

    def toggle_preset_pin(self, name: str) -> bool:
        return self._controller.toggle_preset_pin(name)

    def move_preset_by_step(self, name: str, direction: int, *, cached_metadata: dict[str, dict[str, object]] | None = None) -> bool:
        return self._controller.move_preset_by_step(name, direction, cached_metadata=cached_metadata)

    def move_preset_on_drop(
        self,
        *,
        source_kind: str,
        source_id: str,
        destination_kind: str,
        destination_id: str,
        cached_metadata: dict[str, dict[str, object]] | None = None,
    ) -> bool:
        return self._controller.move_preset_on_drop(
            source_kind=source_kind,
            source_id=source_id,
            destination_kind=destination_kind,
            destination_id=destination_id,
            cached_metadata=cached_metadata,
        )


class UserPresetsPageController:
    def __init__(self, config: UserPresetsPageControllerConfig) -> None:
        self._config = config
        self._page_api = UserPresetsPageApiBundle(
            listing=_UserPresetsListingApiImpl(self),
            actions=_UserPresetsActionsApiImpl(self),
            storage=_UserPresetsStorageApiImpl(self),
        )

    def build_page_api(self) -> UserPresetsPageApiBundle:
        return self._page_api

    def _require_app_context(self):
        return self._config.require_app_context()

    def _get_app_paths(self):
        return self._require_app_context().app_paths

    def get_preset_store(self):
        return self._config.get_preset_store()

    def create_preset(self, *, name: str, from_current: bool) -> UserPresetActionResult:
        from presets.public import create_preset

        create_preset(
            self._config.launch_method,
            name,
            from_current=from_current,
            app_context=self._require_app_context(),
        )
        return UserPresetActionResult(
            ok=True,
            log_level="INFO",
            log_message=f"Создан пресет '{name}'",
            infobar_level=None,
            infobar_title="",
            infobar_content="",
            structure_changed=True,
        )

    def rename_preset(self, *, current_name: str, new_name: str) -> UserPresetActionResult:
        from presets.public import is_selected_preset_file_name, rename_preset_by_file_name

        updated = rename_preset_by_file_name(
            self._config.launch_method,
            current_name,
            new_name,
            app_context=self._require_app_context(),
        )
        switched_file_name = (
            updated.file_name
            if is_selected_preset_file_name(
                self._config.launch_method,
                updated.file_name,
                app_context=self._require_app_context(),
            )
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
        )

    def import_preset_from_file(self, *, file_path: str) -> UserPresetImportResult:
        from presets.public import import_preset_from_file

        requested_name = str(Path(file_path).stem or "").strip() or "Imported"
        imported = import_preset_from_file(
            self._config.launch_method,
            file_path,
            requested_name,
            app_context=self._require_app_context(),
        )
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

    def reset_all_presets(self) -> UserPresetResetAllResult:
        from presets.public import get_selected_source_preset_file_name, reset_all_presets_to_builtin

        success_count, total, failed = reset_all_presets_to_builtin(
            self._config.launch_method,
            app_context=self._require_app_context(),
        )
        selected_file_name = get_selected_source_preset_file_name(
            self._config.launch_method,
            app_context=self._require_app_context(),
        )

        failed_count = len(failed or [])
        if failed_count:
            log_message = (
                f"Восстановление встроенных пресетов завершено частично: "
                f"успешно={success_count}/{total}, ошибки={failed_count}"
            )
            level = "WARNING"
        else:
            log_message = f"Восстановлены встроенные пресеты: {success_count}/{total}"
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

    def duplicate_preset(self, *, file_name: str, display_name: str) -> UserPresetActionResult:
        from presets.public import duplicate_preset_by_file_name

        new_name = f"{display_name} (копия)"
        duplicate_preset_by_file_name(
            self._config.launch_method,
            file_name,
            new_name,
            app_context=self._require_app_context(),
        )
        return UserPresetActionResult(
            ok=True,
            log_level="INFO",
            log_message=f"Пресет '{display_name}' дублирован как '{new_name}'",
            infobar_level=None,
            infobar_title="",
            infobar_content="",
            structure_changed=True,
        )

    def reset_preset_to_builtin(self, *, file_name: str, display_name: str) -> UserPresetActionResult:
        from presets.public import reset_preset_to_builtin_by_file_name

        reset_preset_to_builtin_by_file_name(
            self._config.launch_method,
            file_name,
            app_context=self._require_app_context(),
        )

        return UserPresetActionResult(
            ok=True,
            log_level="INFO",
            log_message=f"Восстановлен встроенный пресет для '{display_name}'",
            infobar_level=None,
            infobar_title="",
            infobar_content="",
            structure_changed=False,
        )

    def delete_preset(self, *, file_name: str, display_name: str) -> UserPresetActionResult:
        if self.is_builtin_preset_file(file_name):
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
            from presets.public import delete_preset_by_file_name

            delete_preset_by_file_name(
                self._config.launch_method,
                file_name,
                app_context=self._require_app_context(),
            )
        except Exception as e:
            if "Preset not found" in str(e):
                return UserPresetActionResult(
                    ok=False,
                    log_level="ERROR",
                    log_message=f"Ошибка удаления пресета: {e}",
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

    def export_preset(self, *, file_name: str, file_path: str, display_name: str) -> UserPresetActionResult:
        from presets.public import export_preset_plain_text

        export_preset_plain_text(
            self._config.launch_method,
            file_name,
            file_path,
            app_context=self._require_app_context(),
        )
        return UserPresetActionResult(
            ok=True,
            log_level="INFO",
            log_message=f"Экспортирован пресет '{display_name}' в {file_path}",
            infobar_level="success",
            infobar_title="Успех",
            infobar_content=f"Пресет экспортирован: {file_path}",
            structure_changed=False,
        )

    @staticmethod
    def open_presets_info() -> UserPresetActionResult:
        try:
            from config.urls import PRESET_INFO_URL

            webbrowser.open(PRESET_INFO_URL)
            return UserPresetActionResult(
                ok=True,
                log_level="INFO",
                log_message=f"Открыта страница о пресетах: {PRESET_INFO_URL}",
                infobar_level=None,
                infobar_title="",
                infobar_content="",
                structure_changed=False,
            )
        except Exception as e:
            return UserPresetActionResult(
                ok=False,
                log_level="ERROR",
                log_message=f"Не удалось открыть страницу о пресетах: {e}",
                infobar_level="warning",
                infobar_title="Ошибка",
                infobar_content=f"Не удалось открыть страницу о пресетах: {e}",
                structure_changed=False,
            )

    @staticmethod
    def open_new_configs_post() -> UserPresetActionResult:
        try:
            from config.urls import SUPPORT_DISCUSSIONS_URL

            webbrowser.open(SUPPORT_DISCUSSIONS_URL)
            return UserPresetActionResult(
                ok=True,
                log_level="INFO",
                log_message=f"Открыта страница пресетов: {SUPPORT_DISCUSSIONS_URL}",
                infobar_level=None,
                infobar_title="",
                infobar_content="",
                structure_changed=False,
            )
        except Exception as e:
            return UserPresetActionResult(
                ok=False,
                log_level="ERROR",
                log_message=f"Ошибка открытия страницы пресетов: {e}",
                infobar_level="warning",
                infobar_title="Ошибка",
                infobar_content=f"Не удалось открыть страницу пресетов: {e}",
                structure_changed=False,
            )

    def is_builtin_preset_file(self, name: str) -> bool:
        candidate = str(name or "").strip()
        if not candidate or not candidate.lower().endswith(".txt"):
            return False
        try:
            from presets.public import get_preset_manifest_by_file_name

            manifest = get_preset_manifest_by_file_name(
                self._config.launch_method,
                candidate,
                app_context=self._require_app_context(),
            )
            if manifest is not None:
                return str(manifest.kind or "").strip().lower() == "builtin"
        except Exception:
            pass
        return False

    def list_preset_entries_light(self) -> list[dict[str, object]]:
        try:
            from presets.public import list_preset_manifests

            return [
                {
                    "file_name": item.file_name,
                    "display_name": item.name,
                    "kind": item.kind,
                    "storage_scope": item.storage_scope,
                    "is_builtin": str(item.kind or "").strip().lower() == "builtin",
                }
                for item in list_preset_manifests(
                    self._config.launch_method,
                    app_context=self._require_app_context(),
                )
            ]
        except Exception as e:
            log(f"{self._config.list_log_prefix}: не удалось загрузить lightweight список пресетов: {e}", "ERROR")
            return []

    def get_active_preset_name_light(self) -> str:
        try:
            from presets.public import get_selected_source_preset_manifest

            preset = get_selected_source_preset_manifest(
                self._config.launch_method,
                app_context=self._require_app_context(),
            )
            return str(preset.name if preset is not None else "").strip()
        except Exception:
            return ""

    def get_selected_source_preset_file_name_light(self) -> str:
        try:
            from presets.public import get_selected_source_preset_file_name

            return str(
                get_selected_source_preset_file_name(
                    self._config.launch_method,
                    app_context=self._require_app_context(),
                )
                or ""
            ).strip()
        except Exception:
            return ""

    def get_presets_dir_light(self):
        return self._get_app_paths().engine_paths(self._config.selection_key).ensure_directories().user_presets_dir

    def load_preset_list_metadata_light(self) -> dict[str, dict[str, object]]:
        from presets.lightweight_metadata import build_lightweight_preset_metadata
        from presets.public import get_preset_source_path_by_file_name

        metadata: dict[str, dict[str, object]] = {}

        for entry in self.list_preset_entries_light():
            file_name = str(entry.get("file_name") or "").strip()
            display_name = str(entry.get("display_name") or file_name).strip()
            kind = str(entry.get("kind") or "").strip() or "user"
            is_builtin = bool(entry.get("is_builtin", False))
            if not file_name:
                continue
            path = get_preset_source_path_by_file_name(
                self._config.launch_method,
                file_name,
                app_context=self._require_app_context(),
            )
            metadata[file_name] = build_lightweight_preset_metadata(
                path,
                display_name=display_name,
                kind=kind,
                is_builtin=is_builtin,
            )

        return metadata

    def read_single_preset_list_metadata_light(self, file_name: str) -> tuple[str, dict[str, object]] | None:
        from presets.lightweight_metadata import build_lightweight_preset_metadata

        candidate = str(file_name or "").strip()
        if not candidate:
            return None

        candidate_file_name = candidate if candidate.lower().endswith(".txt") else f"{candidate}.txt"
        matched_entry = None
        for entry in self.list_preset_entries_light():
            entry_file_name = str(entry.get("file_name") or "").strip()
            if entry_file_name == candidate_file_name:
                matched_entry = entry
                candidate_file_name = entry_file_name or candidate_file_name
                break

        if matched_entry is None:
            return None

        display_name = str(matched_entry.get("display_name") or candidate_file_name).strip()
        kind = str(matched_entry.get("kind") or "").strip() or "user"
        is_builtin = bool(matched_entry.get("is_builtin", False))
        from presets.public import get_preset_source_path_by_file_name

        path = get_preset_source_path_by_file_name(
            self._config.launch_method,
            candidate_file_name,
            app_context=self._require_app_context(),
        )

        metadata = build_lightweight_preset_metadata(
            path,
            display_name=display_name,
            kind=kind,
            is_builtin=is_builtin,
        )

        return candidate_file_name, metadata

    def resolve_display_name(self, reference: str) -> str:
        candidate = str(reference or "").strip()
        if not candidate:
            return ""
        if candidate.lower().endswith(".txt"):
            try:
                from presets.public import get_preset_manifest_by_file_name

                manifest = get_preset_manifest_by_file_name(
                    self._config.launch_method,
                    candidate,
                    app_context=self._require_app_context(),
                )
                if manifest is not None:
                    return manifest.name
            except Exception:
                pass
        return candidate

    def get_hierarchy_store(self):
        from presets.library_hierarchy import PresetHierarchyStore

        return PresetHierarchyStore(self._config.hierarchy_scope)

    def is_builtin_preset_file_with_cache(self, name: str, cached_metadata: dict[str, dict[str, object]] | None) -> bool:
        candidate = str(name or "").strip()
        if not candidate or not candidate.lower().endswith(".txt"):
            return False

        if isinstance(cached_metadata, dict):
            cached_meta = cached_metadata.get(candidate)
            if isinstance(cached_meta, dict):
                return bool(cached_meta.get("is_builtin", False))

        return self.is_builtin_preset_file(candidate)

    def toggle_preset_pin(self, name: str) -> bool:
        hierarchy = self.get_hierarchy_store()
        return bool(hierarchy.toggle_preset_pin(name))

    def move_preset_by_step(self, name: str, direction: int, *, cached_metadata: dict[str, dict[str, object]] | None = None) -> bool:
        hierarchy = self.get_hierarchy_store()
        return bool(
            hierarchy.move_preset_by_step_flat(
                self.list_preset_entries_light(),
                name,
                direction,
                is_builtin_resolver=lambda file_name: self.is_builtin_preset_file_with_cache(str(file_name or ""), cached_metadata),
            )
        )

    def move_preset_on_drop(
        self,
        *,
        source_kind: str,
        source_id: str,
        destination_kind: str,
        destination_id: str,
        cached_metadata: dict[str, dict[str, object]] | None = None,
    ) -> bool:
        if source_kind != "preset":
            return False

        hierarchy = self.get_hierarchy_store()
        all_names = self.list_preset_entries_light()

        if destination_kind == "preset" and destination_id:
            return bool(
                hierarchy.move_preset_before_flat(
                    all_names,
                    source_id,
                    destination_id,
                    is_builtin_resolver=lambda file_name: self.is_builtin_preset_file_with_cache(str(file_name or ""), cached_metadata),
                )
            )

        return bool(
            hierarchy.move_preset_to_end_flat(
                all_names,
                source_id,
                is_builtin_resolver=lambda file_name: self.is_builtin_preset_file_with_cache(str(file_name or ""), cached_metadata),
            )
        )

    def build_preset_rows_plan(
        self,
        *,
        all_presets: dict[str, dict[str, object]],
        query: str,
        active_file_name: str,
        language: str,
    ) -> UserPresetListPlan:
        from core.runtime.user_presets_runtime_service import normalize_preset_icon_color
        from ui.text_catalog import tr as tr_catalog

        normalized_query = str(query or "").strip().lower()
        hierarchy = self.get_hierarchy_store()
        builtin_by_file = {
            file_name: bool(meta.get("is_builtin", False))
            for file_name, meta in all_presets.items()
        }

        rows: list[dict[str, object]] = []
        visible_entries: list[dict[str, object]] = []

        for file_name, meta in all_presets.items():
            display_name = str(meta.get("display_name") or file_name).strip()
            if normalized_query and normalized_query not in display_name.lower():
                continue
            visible_entries.append(
                {
                    "file_name": file_name,
                    "display_name": display_name,
                    "is_builtin": builtin_by_file.get(file_name, False),
                }
            )

        ordered_names = hierarchy.list_presets_flat(
            visible_entries,
            is_builtin_resolver=lambda file_name: builtin_by_file.get(str(file_name or ""), False),
        )

        for file_name in ordered_names:
            preset = all_presets.get(file_name)
            if not preset:
                continue
            display_name = str(preset.get("display_name") or file_name).strip()
            is_builtin = builtin_by_file.get(file_name, False)
            meta = hierarchy.get_preset_meta(file_name)
            rows.append(
                {
                    "kind": "preset",
                    "name": display_name,
                    "file_name": file_name,
                    "description": str(preset.get("description") or ""),
                    "date": str(preset.get("modified_display") or ""),
                    "is_active": bool(file_name and file_name == str(active_file_name or "").strip()),
                    "is_builtin": is_builtin,
                    "icon_color": normalize_preset_icon_color(str(preset.get("icon_color") or "")),
                    "depth": 0,
                    "is_pinned": bool(meta.get("pinned", False)),
                    "rating": int(meta.get("rating", 0) or 0),
                }
            )

        if not rows:
            if normalized_query:
                rows.append(
                    {
                        "kind": "empty",
                        "text": tr_catalog(
                            self._config.empty_not_found_key,
                            language=language,
                            default="По этому поиску пресетов нет. Измените запрос или очистите строку поиска.",
                        ),
                    }
                )
            else:
                rows.append(
                    {
                        "kind": "empty",
                        "text": tr_catalog(
                            self._config.empty_none_key,
                            language=language,
                            default="Пресеты не найдены. Создайте новый пресет или импортируйте txt-файл.",
                        ),
                    }
                )

        return UserPresetListPlan(
            rows=rows,
            total_presets=len(all_presets),
            visible_presets=len(visible_entries),
            query=normalized_query,
        )

    def activate_preset(self, *, file_name: str, display_name: str) -> UserPresetActivationResult:
        preset_file_name = str(file_name or "").strip()
        preset_display_name = str(display_name or preset_file_name).strip() or preset_file_name

        try:
            from presets.public import activate_preset_file

            activate_preset_file(
                self._config.launch_method,
                preset_file_name,
                app_context=self._require_app_context(),
            )
            return UserPresetActivationResult(
                ok=True,
                log_level="INFO",
                log_message=f"Активирован пресет '{preset_display_name}'",
                infobar_level=None,
                infobar_title="",
                infobar_content="",
                activated_file_name=preset_file_name,
            )
        except Exception as e:
            content = (
                f"Не удалось активировать пресет '{preset_display_name}'"
                if self._config.activate_error_mode == "friendly"
                else f"Ошибка: {e}"
            )
            return UserPresetActivationResult(
                ok=False,
                log_level="ERROR",
                log_message=f"Ошибка активации пресета: {e}",
                infobar_level=self._config.activate_error_level,
                infobar_title="Ошибка",
                infobar_content=content,
                activated_file_name=None,
            )
