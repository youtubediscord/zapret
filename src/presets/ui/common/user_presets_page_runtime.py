from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable, Protocol

from log.log import log
from presets.user_presets_page_plans import UserPresetListPlan, build_preset_rows_plan


@dataclass(frozen=True, slots=True)
class UserPresetsRuntimeActions:
    get_selected_source_preset_file_name: Callable[..., object]
    get_preset_manifest_by_file_name: Callable[..., object]
    list_preset_manifests: Callable[..., object]
    get_selected_source_preset_manifest: Callable[..., object]
    get_user_presets_dir: Callable[..., object]
    get_cached_preset_list_metadata: Callable[..., object]
    warm_preset_list_metadata_cache: Callable[..., object]
    get_preset_source_path_by_file_name: Callable[..., object]


@dataclass(frozen=True, slots=True)
class UserPresetsPageRuntimeConfig:
    launch_method: str
    folder_scope: str
    empty_not_found_key: str
    empty_none_key: str
    list_log_prefix: str
    activate_error_level: str
    activate_error_mode: str
    preset_runtime_actions: UserPresetsRuntimeActions


class UserPresetsListingApi(Protocol):
    def list_preset_entries_light(self) -> list[dict[str, object]]: ...
    def get_active_preset_name_light(self) -> str: ...
    def get_selected_source_preset_file_name_light(self) -> str: ...
    def get_presets_dir_light(self): ...
    def get_cached_preset_list_metadata_light(self) -> dict[str, dict[str, object]] | None: ...
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
        folder_state: dict[str, Any] | None = None,
    ) -> UserPresetListPlan: ...


def schedule_preset_search(*, preset_search_timer, refresh_presets_view_from_cache_fn) -> None:
    try:
        preset_search_timer.start(180)
    except Exception:
        refresh_presets_view_from_cache_fn()


def apply_preset_search(
    *,
    is_visible: bool,
    runtime_service,
    refresh_presets_view_from_cache_fn,
) -> None:
    if not is_visible:
        runtime_service.set_ui_dirty(True)
        return
    refresh_presets_view_from_cache_fn()


def update_presets_view_height(
    *,
    presets_model,
    presets_list,
    viewport,
    layout,
) -> None:
    if not presets_model or presets_list is None:
        return

    viewport_height = viewport.height()
    if viewport_height <= 0:
        return

    top = max(0, presets_list.geometry().top())
    bottom_margin = layout.contentsMargins().bottom()
    reserved_bottom_height = _layout_height_after_widget(layout, presets_list)
    desired_height = max(220, viewport_height - top - bottom_margin - reserved_bottom_height)

    if presets_list.minimumHeight() != desired_height:
        presets_list.setMinimumHeight(desired_height)
    if presets_list.maximumHeight() != desired_height:
        presets_list.setMaximumHeight(desired_height)


def _layout_height_after_widget(layout, widget) -> int:
    if layout is None or widget is None:
        return 0

    try:
        widget_index = layout.indexOf(widget)
        if widget_index < 0:
            return 0
        spacing = max(0, int(layout.spacing()))
        reserved = 0
        visible_items = 0
        for index in range(widget_index + 1, layout.count()):
            item = layout.itemAt(index)
            if item is None:
                continue

            item_height = 0
            child_widget = item.widget()
            if child_widget is not None:
                minimum = int(child_widget.minimumHeight())
                maximum = int(child_widget.maximumHeight())
                if minimum > 0 and minimum == maximum:
                    item_height = minimum
                else:
                    item_height = max(0, int(child_widget.sizeHint().height()))
            else:
                item_height = max(0, int(item.sizeHint().height()))

            if item_height <= 0:
                continue
            visible_items += 1
            reserved += item_height
        if visible_items > 0:
            reserved += spacing * visible_items
        return reserved
    except Exception:
        return 0


def rebuild_presets_rows(
    *,
    runtime_service,
    listing_api,
    presets_delegate,
    presets_model,
    presets_list,
    get_selected_source_preset_file_name_light_fn,
    ui_language: str,
    schedule_layout_resync_fn,
    update_presets_view_height_fn,
    log_fn,
    all_presets: dict[str, dict[str, object]],
    folder_state: dict[str, object] | None = None,
    started_at: float | None = None,
    log_source: str = "UserPresetsPage",
) -> None:
    try:
        view_state = runtime_service.capture_presets_view_state() if presets_list is not None else {}
        active_file_name = get_selected_source_preset_file_name_light_fn()
        plan = listing_api.build_preset_rows_plan(
            all_presets=all_presets,
            query=runtime_service.current_search_query(),
            active_file_name=active_file_name,
            language=ui_language,
            folder_state=folder_state,
        )

        previous_row_count = presets_model.rowCount() if presets_model else None
        rows_changed = True
        if presets_model:
            rows_changed = bool(presets_model.set_rows(plan.rows))
        if not rows_changed:
            if started_at is not None:
                elapsed_ms = int((time.perf_counter() - started_at) * 1000)
                log_fn(
                    f"{log_source}: lightweight list reload skipped {elapsed_ms}ms ({plan.total_presets} presets)",
                    "DEBUG",
                )
            return
        if presets_delegate:
            presets_delegate.reset_interaction_state()
        runtime_service.ensure_preset_list_current_index()
        if view_state:
            runtime_service.restore_presets_view_state(view_state)
        next_row_count = presets_model.rowCount() if presets_model else None
        if previous_row_count is None or next_row_count != previous_row_count:
            update_presets_view_height_fn()
            schedule_layout_resync_fn()
        if started_at is not None:
            elapsed_ms = int((time.perf_counter() - started_at) * 1000)
            log_fn(
                f"{log_source}: lightweight list reload {elapsed_ms}ms ({plan.total_presets} presets)",
                "DEBUG",
            )

    except Exception as exc:
        log_fn(f"Ошибка загрузки пресетов: {exc}", "ERROR")


@dataclass(frozen=True, slots=True)
class UserPresetsPageApiBundle:
    listing: UserPresetsListingApi


class _UserPresetsListingApiImpl:
    def __init__(self, runtime: "UserPresetsPageRuntime") -> None:
        self._runtime = runtime

    def list_preset_entries_light(self) -> list[dict[str, object]]:
        return self._runtime.list_preset_entries_light()

    def get_active_preset_name_light(self) -> str:
        return self._runtime.get_active_preset_name_light()

    def get_selected_source_preset_file_name_light(self) -> str:
        return self._runtime.get_selected_source_preset_file_name_light()

    def get_presets_dir_light(self):
        return self._runtime.get_presets_dir_light()

    def get_cached_preset_list_metadata_light(self) -> dict[str, dict[str, object]] | None:
        return self._runtime.get_cached_preset_list_metadata_light()

    def load_preset_list_metadata_light(self) -> dict[str, dict[str, object]]:
        return self._runtime.load_preset_list_metadata_light()

    def read_single_preset_list_metadata_light(self, file_name: str) -> tuple[str, dict[str, object]] | None:
        return self._runtime.read_single_preset_list_metadata_light(file_name)

    def resolve_display_name(self, reference: str) -> str:
        return self._runtime.resolve_display_name(reference)

    def build_preset_rows_plan(
        self,
        *,
        all_presets: dict[str, dict[str, object]],
        query: str,
        active_file_name: str,
        language: str,
        folder_state: dict[str, Any] | None = None,
    ) -> UserPresetListPlan:
        return self._runtime.build_preset_rows_plan(
            all_presets=all_presets,
            query=query,
            active_file_name=active_file_name,
            language=language,
            folder_state=folder_state,
        )


class UserPresetsPageRuntime:
    def __init__(self, config: UserPresetsPageRuntimeConfig) -> None:
        self._config = config
        self._page_api = UserPresetsPageApiBundle(
            listing=_UserPresetsListingApiImpl(self),
        )

    def build_page_api(self) -> UserPresetsPageApiBundle:
        return self._page_api

    def _preset_actions(self) -> UserPresetsRuntimeActions:
        return self._config.preset_runtime_actions

    def is_builtin_preset_file(self, name: str) -> bool:
        candidate = str(name or "").strip()
        if not candidate or not candidate.lower().endswith(".txt"):
            return False
        try:
            manifest = self._preset_actions().get_preset_manifest_by_file_name(
                self._config.launch_method,
                candidate,
            )
            if manifest is not None:
                return str(manifest.kind or "").strip().lower() == "builtin"
        except Exception:
            pass
        return False

    def list_preset_entries_light(self) -> list[dict[str, object]]:
        try:
            return [
                {
                    "file_name": item.file_name,
                    "display_name": item.name,
                    "kind": item.kind,
                    "storage_scope": item.storage_scope,
                    "is_builtin": str(item.kind or "").strip().lower() == "builtin",
                }
                for item in self._preset_actions().list_preset_manifests(
                    self._config.launch_method,
                )
            ]
        except Exception as e:
            log(f"{self._config.list_log_prefix}: не удалось загрузить lightweight список пресетов: {e}", "ERROR")
            return []

    def get_active_preset_name_light(self) -> str:
        try:
            preset = self._preset_actions().get_selected_source_preset_manifest(
                self._config.launch_method,
            )
            return str(preset.name if preset is not None else "").strip()
        except Exception:
            return ""

    def get_selected_source_preset_file_name_light(self) -> str:
        try:
            return str(
                self._preset_actions().get_selected_source_preset_file_name(
                    self._config.launch_method,
                )
                or ""
            ).strip()
        except Exception:
            return ""

    def get_presets_dir_light(self):
        return self._preset_actions().get_user_presets_dir(
            self._config.launch_method,
        )

    def get_cached_preset_list_metadata_light(self) -> dict[str, dict[str, object]] | None:
        cached = self._preset_actions().get_cached_preset_list_metadata(self._config.launch_method)
        return dict(cached) if cached else None

    def load_preset_list_metadata_light(self) -> dict[str, dict[str, object]]:
        return dict(self._preset_actions().warm_preset_list_metadata_cache(self._config.launch_method) or {})

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

        path = self._preset_actions().get_preset_source_path_by_file_name(
            self._config.launch_method,
            candidate_file_name,
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
                manifest = self._preset_actions().get_preset_manifest_by_file_name(
                    self._config.launch_method,
                    candidate,
                )
                if manifest is not None:
                    return manifest.name
            except Exception:
                pass
        return candidate

    def is_builtin_preset_file_with_cache(self, name: str, cached_metadata: dict[str, dict[str, object]] | None) -> bool:
        candidate = str(name or "").strip()
        if not candidate or not candidate.lower().endswith(".txt"):
            return False

        if isinstance(cached_metadata, dict):
            cached_meta = cached_metadata.get(candidate)
            if isinstance(cached_meta, dict):
                return bool(cached_meta.get("is_builtin", False))

        return self.is_builtin_preset_file(candidate)

    def build_preset_rows_plan(
        self,
        *,
        all_presets: dict[str, dict[str, object]],
        query: str,
        active_file_name: str,
        language: str,
        folder_state: dict[str, Any] | None = None,
    ) -> UserPresetListPlan:
        return build_preset_rows_plan(
            all_presets=all_presets,
            query=query,
            active_file_name=active_file_name,
            language=language,
            folder_state=folder_state,
            folder_scope=self._config.folder_scope,
            empty_not_found_key=self._config.empty_not_found_key,
            empty_none_key=self._config.empty_none_key,
        )
