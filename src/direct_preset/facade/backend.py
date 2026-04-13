from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
import time as _time
from typing import TYPE_CHECKING, Callable, Optional

from direct_preset.common.source_preset_models import OutRangeSettings, SendSettings, SyndataSettings
from direct_preset.service import BasicUiPayload, DirectPresetService, TargetDetailPayload
from core.paths import AppPaths
from core.presets.preset_file_store import PresetFileStore
from core.presets.runtime_store import DirectRuntimePresetStore
from core.presets.selection_service import PresetSelectionService
from direct_preset.adapters import DirectPresetEngineAdapter, get_direct_preset_engine_adapter
from .preset_ops import (
    create_preset as _create_preset,
    delete_by_file_name as _delete_by_file_name,
    duplicate_by_file_name as _duplicate_by_file_name,
    export_plain_text_by_file_name as _export_plain_text_by_file_name,
    get_advanced_settings_state as _get_advanced_settings_state,
    get_wssize_enabled as _get_wssize_enabled,
    import_from_file as _import_from_file,
    rename_by_file_name as _rename_by_file_name,
    reset_all_to_templates as _reset_all_to_templates,
    reset_to_template_by_file_name as _reset_to_template_by_file_name,
    _resolve_reset_template,
    set_debug_log_enabled as _set_debug_log_enabled,
    set_wssize_enabled as _set_wssize_enabled,
)
from direct_preset.modes import DIRECT_UI_MODE_DEFAULT, load_current_direct_ui_mode
from .text_ops import (
    _collect_changed_strategy_selections,
    _coerce_int,
    _extract_debug_log_file,
    _join_arg_lines,
    _log_startup_payload_metric,
    _normalize_direct_preset_source_text,
    _normalize_strategy_selection_value,
    _ports_include_443,
    _settings_payload_to_dict,
)

from core.presets.models import PresetManifest

if TYPE_CHECKING:
    from winws_runtime.flow.direct_flow import DirectFlowCoordinator


@dataclass(frozen=True)
class DirectPresetFacadeBackend:
    engine: str
    launch_method: str
    app_paths: AppPaths
    direct_flow_coordinator: DirectFlowCoordinator
    preset_file_store: PresetFileStore
    preset_selection_service: PresetSelectionService
    preset_store: DirectRuntimePresetStore
    preset_store_v1: DirectRuntimePresetStore
    on_dpi_reload_needed: Optional[Callable[[], None]] = None

    def _adapter(self) -> DirectPresetEngineAdapter:
        return get_direct_preset_engine_adapter(self.engine)

    def _runtime_store(self):
        return self._adapter().runtime_store(
            preset_store=self.preset_store,
            preset_store_v1=self.preset_store_v1,
        )

    def _service(self) -> DirectPresetService:
        return DirectPresetService(self.app_paths, self.engine)

    def _current_direct_strategy_set(self) -> str:
        if not self._adapter().supports_direct_ui_mode():
            return ""
        resolved = load_current_direct_ui_mode(self.engine)
        return resolved or DIRECT_UI_MODE_DEFAULT

    def _selected_source_path_from_manifest(self, selected_manifest: PresetManifest) -> Path:
        selected_file_name = str(getattr(selected_manifest, "file_name", "") or "").strip()
        if not selected_file_name:
            raise ValueError("Selected source preset file name is required")
        return self.app_paths.engine_paths(self.engine).ensure_directories().presets_dir / selected_file_name

    def _load_selected_preset_model(self, selected_manifest: PresetManifest | None = None):
        if selected_manifest is None:
            selected_manifest = self.get_selected_manifest()
        if selected_manifest is None:
            return None
        selected_file_name = str(selected_manifest.file_name or "").strip()
        if not selected_file_name:
            return None
        return self._service().read_source_preset(self._selected_source_path_from_manifest(selected_manifest))

    def list_manifests(self) -> list[PresetManifest]:
        return self.preset_file_store.list_manifests(self.engine)

    def notify_preset_saved(self, file_name: str) -> None:
        candidate = str(file_name or "").strip()
        if candidate:
            self._runtime_store().notify_preset_saved(candidate)

    def notify_preset_switched(self, file_name: str) -> None:
        candidate = str(file_name or "").strip()
        if candidate:
            self._runtime_store().notify_preset_switched(candidate)

    def notify_preset_identity_changed(self, file_name: str) -> None:
        candidate = str(file_name or "").strip()
        if candidate:
            self._runtime_store().notify_preset_identity_changed(candidate)

    def activate_preset_file(self, file_name: str):
        candidate = str(file_name or "").strip()
        if not candidate:
            raise ValueError("Preset file name is required")

        profile = self.direct_flow_coordinator.select_preset_file_name(self.launch_method, candidate)
        self.notify_preset_switched(profile.preset_file_name)
        return profile

    def get_basic_ui_payload(
        self,
        *,
        startup_scope: str | None = None,
    ) -> BasicUiPayload:
        _t_total = _time.perf_counter()
        _t_load = _time.perf_counter()
        selected_manifest = self.get_selected_manifest()
        preset = self._load_selected_preset_model(selected_manifest)
        _log_startup_payload_metric(
            startup_scope,
            "_build_content.payload.backend.load_selected_preset",
            (_time.perf_counter() - _t_load) * 1000,
            extra=f"has_preset={'yes' if preset else 'no'}",
        )
        if not preset:
            _log_startup_payload_metric(
                startup_scope,
                "_build_content.payload.backend.total",
                (_time.perf_counter() - _t_total) * 1000,
                extra="has_preset=no",
            )
            return BasicUiPayload(
                target_views=(),
                target_items={},
                strategy_selections={},
                strategy_names_by_target={},
                filter_modes={},
                selected_preset_file_name="",
                selected_preset_name="",
            )
        _t_service = _time.perf_counter()
        payload = self._service().build_basic_ui_payload(
            preset,
            startup_scope=startup_scope,
            strategy_set=self._current_direct_strategy_set(),
        )
        payload = replace(
            payload,
            selected_preset_file_name=str(getattr(selected_manifest, "file_name", "") or ""),
            selected_preset_name=str(getattr(selected_manifest, "name", "") or ""),
        )
        _log_startup_payload_metric(
            startup_scope,
            "_build_content.payload.backend.service",
            (_time.perf_counter() - _t_service) * 1000,
            extra=f"targets={len(payload.target_items or {})}",
        )
        _log_startup_payload_metric(
            startup_scope,
            "_build_content.payload.backend.total",
            (_time.perf_counter() - _t_total) * 1000,
            extra=f"targets={len(payload.target_items or {})}",
        )
        return payload

    def get_basic_ui_empty_state(self) -> dict[str, str] | None:
        """Explains why the direct categories page is empty, if it is empty."""
        try:
            presets_dir = self.app_paths.engine_paths(self.engine).ensure_directories().presets_dir
            has_any_preset = any(
                path.is_file() and path.suffix.lower() == ".txt" and not path.name.startswith("_")
                for path in presets_dir.glob("*.txt")
            )
        except Exception:
            try:
                has_any_preset = bool(self.list_manifests())
            except Exception:
                has_any_preset = False

        if not has_any_preset:
            return {
                "reason": "no_presets",
                "preset_name": "",
            }

        selected_manifest = self.get_selected_manifest()
        if selected_manifest is None:
            return {
                "reason": "no_selected_preset",
                "preset_name": "",
            }

        preset_name = str(selected_manifest.name or Path(selected_manifest.file_name).stem or "Preset").strip() or "Preset"

        try:
            preset = self.get_selected_source_preset_model()
        except Exception as exc:
            log(f"DirectPresetFacadeBackend[{self.launch_method}]: failed to read selected preset for empty-state: {exc}", "DEBUG")
            return {
                "reason": "preset_read_error",
                "preset_name": preset_name,
            }

        if not preset:
            return {
                "reason": "preset_read_error",
                "preset_name": preset_name,
            }

        try:
            contexts = self._service().collect_target_contexts(preset)
        except Exception as exc:
            log(f"DirectPresetFacadeBackend[{self.launch_method}]: failed to parse selected preset for empty-state: {exc}", "DEBUG")
            return {
                "reason": "preset_read_error",
                "preset_name": preset_name,
            }

        has_basic_targets = any(
            self._service()._target_metadata.should_include_in_basic_ui(target_key)
            for target_key in contexts.keys()
        )
        if has_basic_targets:
            return None

        return {
            "reason": "no_categories",
            "preset_name": preset_name,
        }

    def get_target_detail_payload(self, target_key: str) -> TargetDetailPayload | None:
        preset = self.get_selected_source_preset_model()
        if not preset:
            return None
        return self._service().build_target_detail_payload(
            preset,
            str(target_key or "").strip().lower(),
            strategy_set=self._current_direct_strategy_set(),
        )

    def list_file_names(self) -> list[str]:
        return [item.file_name for item in self.list_manifests()]

    def exists_file_name(self, file_name: str) -> bool:
        return self.get_manifest_by_file_name(file_name) is not None

    def get_selected_file_name(self) -> str:
        preset = self.get_selected_manifest()
        return preset.file_name if preset is not None else ""

    def get_selected_manifest(self) -> PresetManifest | None:
        try:
            return self.direct_flow_coordinator.get_selected_source_manifest(self.launch_method)
        except Exception:
            return None

    def is_selected_file_name(self, file_name: str) -> bool:
        current = str(self.get_selected_file_name() or "").strip()
        candidate = str(self.preset_file_store.resolve_file_name(self.engine, file_name) or file_name or "").strip()
        return bool(current and candidate and current.lower() == candidate.lower())

    def get_manifest_by_file_name(self, file_name: str) -> PresetManifest | None:
        return self.preset_file_store.get_manifest(self.engine, file_name)

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

    def _hierarchy_scope_key(self) -> str:
        return self._adapter().hierarchy_scope_key()

    def _get_hierarchy_store(self):
        from core.presets.library_hierarchy import PresetHierarchyStore

        return PresetHierarchyStore(self._hierarchy_scope_key())

    def _rename_library_meta(
        self,
        old_file_name: str,
        new_file_name: str,
        *,
        old_display_name: str,
        new_display_name: str,
    ) -> None:
        try:
            self._get_hierarchy_store().rename_preset_meta(
                old_file_name,
                new_file_name,
                old_display_name=old_display_name,
                new_display_name=new_display_name,
            )
        except Exception:
            pass

    def _copy_library_meta(
        self,
        source_file_name: str,
        new_file_name: str,
        *,
        source_display_name: str,
        new_display_name: str,
    ) -> None:
        try:
            self._get_hierarchy_store().copy_preset_meta_to_new(
                source_file_name,
                new_file_name,
                source_display_name=source_display_name,
                new_display_name=new_display_name,
            )
        except Exception:
            pass

    def _delete_library_meta(self, preset_file_name: str, *, display_name: str) -> None:
        try:
            self._get_hierarchy_store().delete_preset_meta(preset_file_name, display_name=display_name)
        except Exception:
            pass

    def get_source_path_by_file_name(self, file_name: str) -> Path:
        manifest = self.get_manifest_by_file_name(file_name)
        if manifest is None:
            raise ValueError(f"Preset not found: {file_name}")
        return self.app_paths.engine_paths(self.engine).ensure_directories().presets_dir / manifest.file_name

    def save_source_text_by_file_name(self, file_name: str, source_text: str) -> PresetManifest:
        manifest = self.get_manifest_by_file_name(file_name)
        if manifest is None:
            raise ValueError(f"Preset not found: {file_name}")
        normalized = _normalize_direct_preset_source_text(source_text)
        updated = self.preset_file_store.update_preset(self.engine, manifest.file_name, normalized, None)
        self.notify_preset_saved(updated.file_name)
        if self.is_selected_file_name(updated.file_name):
            self.direct_flow_coordinator.refresh_selected_launch_profile(self.launch_method)
        return updated

    def get_debug_log_file(self) -> str:
        selected_file_name = self.get_selected_file_name()
        if not selected_file_name:
            return ""
        return _extract_debug_log_file(self.read_source_text_by_file_name(selected_file_name))

    def get_debug_log_enabled(self) -> bool:
        return bool(self.get_debug_log_file())

    def get_advanced_settings_state(self) -> dict[str, bool]:
        return _get_advanced_settings_state(self)

    def set_debug_log_enabled(self, enabled: bool) -> bool:
        return _set_debug_log_enabled(self, enabled)

    def get_wssize_enabled(self) -> bool:
        return _get_wssize_enabled(self)

    def set_wssize_enabled(self, enabled: bool) -> bool:
        return _set_wssize_enabled(self, enabled)

    def _refresh_selected_launch_profile_from_source(self) -> None:
        selected_file_name = self.get_selected_file_name()
        if not selected_file_name or self.get_manifest_by_file_name(selected_file_name) is None:
            return
        self.direct_flow_coordinator.refresh_selected_launch_profile(self.launch_method)

    def select_file_name(self, file_name: str):
        profile = self.direct_flow_coordinator.select_preset_file_name(self.launch_method, file_name)
        self.notify_preset_switched(profile.preset_file_name)
        return profile

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

    def reset_to_template_by_file_name(self, file_name: str) -> PresetManifest:
        return _reset_to_template_by_file_name(self, file_name)

    def reset_all_to_templates(self) -> tuple[int, int, list[str]]:
        return _reset_all_to_templates(self)

    def delete_by_file_name(self, file_name: str) -> None:
        _delete_by_file_name(self, file_name)

    def get_strategy_selections(self) -> dict:
        preset = self.get_selected_source_preset_model()
        if not preset:
            return {}
        return self._service().get_strategy_selections(
            preset,
            strategy_set=self._current_direct_strategy_set(),
        )

    def set_strategy_selections(self, selections: dict, *, save_and_sync: bool = True) -> bool:
        preset = self.get_selected_source_preset_model()
        if not preset:
            return False
        strategy_set = self._current_direct_strategy_set()
        current = self._service().get_strategy_selections(preset, strategy_set=strategy_set)
        changed = _collect_changed_strategy_selections(current, selections)
        if not changed:
            return True
        for target_key, strategy_id in changed.items():
            self._service().update_strategy_selection(
                preset,
                target_key,
                strategy_id,
                strategy_set=strategy_set,
            )
        return self.save_preset_model(preset) if save_and_sync else True

    def set_strategy_selection(self, target_key: str, strategy_id: str, *, save_and_sync: bool = True) -> bool:
        normalized_key = str(target_key or "").strip().lower()
        if not normalized_key:
            return False
        preset = self.get_selected_source_preset_model()
        if not preset:
            return False
        strategy_set = self._current_direct_strategy_set()
        current = self._service().get_strategy_selections(preset, strategy_set=strategy_set)
        normalized_strategy_id = _normalize_strategy_selection_value(strategy_id)
        if (
            normalized_strategy_id != "none"
            and _normalize_strategy_selection_value(current.get(normalized_key, "none")) == normalized_strategy_id
        ):
            return True
        ok = self._service().update_strategy_selection(
            preset,
            normalized_key,
            normalized_strategy_id,
            strategy_set=strategy_set,
        )
        if not ok:
            return False
        return self.save_preset_model(preset, changed_target=normalized_key) if save_and_sync else True

    def get_selected_source_preset(self):
        return self._load_selected_preset_model()

    def get_selected_source_preset_model(self):
        return self.get_selected_source_preset()

    def get_target_filter_mode(self, target_key: str) -> str:
        preset = self.get_selected_source_preset_model()
        if not preset:
            return "hostlist"
        return self._service()._get_filter_mode(preset, target_key)

    def update_target_filter_mode(self, target_key: str, filter_mode: str, *, save_and_sync: bool = True) -> bool:
        mode = str(filter_mode or "").strip().lower()
        if mode not in ("hostlist", "ipset"):
            return False
        preset = self.get_selected_source_preset_model()
        if not preset:
            return False
        ok = self._service()._update_filter_mode(preset, target_key, mode)
        if not ok:
            return False
        return self.save_preset_model(preset, changed_target=str(target_key or "").strip().lower()) if save_and_sync else True

    def reset_target_settings(self, target_key: str) -> bool:
        if not self._adapter().supports_structured_target_settings():
            raise NotImplementedError(
                "direct_zapret1 does not expose a standalone reset_target_settings path in DirectPresetFacade."
            )
        preset = self.get_selected_source_preset_model()
        if not preset:
            return False
        selected_manifest = self.get_selected_manifest()
        template_key = str((selected_manifest.template_origin if selected_manifest else None) or "").strip()
        if not template_key and selected_manifest is not None:
            template_key = str(selected_manifest.name or "").strip()
        template_text = _resolve_reset_template(self.launch_method, template_key or "Default")
        template_source = self._service()._parser().parse(template_text)
        ok = self._service().reset_target_from_template(preset, template_source, target_key)
        if not ok:
            return False
        return self.save_preset_model(preset, changed_target=str(target_key or "").strip().lower())

    def update_target_details_settings(self, target_key: str, settings, *, save_and_sync: bool = True) -> bool:
        if not self._adapter().supports_structured_target_settings():
            raise NotImplementedError(
                "direct_zapret1 does not expose structured send/syndata/out_range settings."
            )
        preset = self.get_selected_source_preset_model()
        if not preset:
            return False
        details = self.get_target_details(target_key)
        if details is None:
            return False

        payload = _settings_payload_to_dict(settings)
        out_range_value = max(0, _coerce_int(payload.get("out_range", details.out_range_settings.value), details.out_range_settings.value))
        out_range_mode = str(payload.get("out_range_mode", details.out_range_settings.mode or "n") or "n").strip().lower()
        out_range = OutRangeSettings(enabled=out_range_value > 0, value=out_range_value, mode="d" if out_range_mode == "d" else "n")
        send = SendSettings(
            enabled=bool(payload.get("send_enabled", details.send_settings.enabled)),
            repeats=max(0, _coerce_int(payload.get("send_repeats", details.send_settings.repeats), details.send_settings.repeats)),
            ip_ttl=max(0, _coerce_int(payload.get("send_ip_ttl", details.send_settings.ip_ttl), details.send_settings.ip_ttl)),
            ip6_ttl=max(0, _coerce_int(payload.get("send_ip6_ttl", details.send_settings.ip6_ttl), details.send_settings.ip6_ttl)),
            ip_id=str(payload.get("send_ip_id", details.send_settings.ip_id or "none") or "none"),
            badsum=bool(payload.get("send_badsum", details.send_settings.badsum)),
        )
        syndata = SyndataSettings(
            enabled=bool(payload.get("enabled", details.syndata_settings.enabled)),
            blob=str(payload.get("blob", details.syndata_settings.blob or "tls_google") or "tls_google"),
            tls_mod=str(payload.get("tls_mod", details.syndata_settings.tls_mod or "none") or "none"),
            autottl_delta=_coerce_int(payload.get("autottl_delta", details.syndata_settings.autottl_delta), details.syndata_settings.autottl_delta),
            autottl_min=max(0, _coerce_int(payload.get("autottl_min", details.syndata_settings.autottl_min), details.syndata_settings.autottl_min)),
            autottl_max=max(0, _coerce_int(payload.get("autottl_max", details.syndata_settings.autottl_max), details.syndata_settings.autottl_max)),
            tcp_flags_unset=str(payload.get("tcp_flags_unset", details.syndata_settings.tcp_flags_unset or "none") or "none"),
        )
        ok = self._service().update_target_settings(
            preset,
            str(target_key or "").strip().lower(),
            out_range=out_range,
            send=send,
            syndata=syndata,
        )
        if not ok:
            return False
        return self.save_preset_model(preset, changed_target=str(target_key or "").strip().lower()) if save_and_sync else True

    def get_target_sort_order(self, target_key: str) -> str:
        _ = target_key
        return "default"

    def update_target_sort_order(self, target_key: str, sort_order: str, *, save_and_sync: bool = True) -> bool:
        _ = (target_key, sort_order, save_and_sync)
        return self._adapter().supports_target_sort_order()

    def save_preset_model(self, preset, *, changed_target: str | None = None) -> bool:
        _ = changed_target
        selected_manifest = self.get_selected_manifest()
        if selected_manifest is None:
            return False
        source_text = _normalize_direct_preset_source_text(self._service()._serializer().serialize(preset))
        self.preset_file_store.update_preset(self.engine, selected_manifest.file_name, source_text, selected_manifest.name)
        self.notify_preset_saved(selected_manifest.file_name)
        self._refresh_selected_launch_profile_from_source()
        if self.on_dpi_reload_needed:
            self.on_dpi_reload_needed()
        return True

    def list_target_views(self):
        preset = self.get_selected_source_preset_model()
        if not preset:
            return []
        return self._service().build_target_views(preset)

    def get_target_ui_items(self) -> dict:
        preset = self.get_selected_source_preset_model()
        if not preset:
            return {}
        return self._service().build_ui_items(preset)

    def get_target_ui_item(self, target_key: str):
        preset = self.get_selected_source_preset_model()
        if not preset:
            return None
        return self._service().target_info(preset, str(target_key or "").strip().lower())

    def get_target_details(self, target_key: str):
        preset = self.get_selected_source_preset_model()
        if not preset:
            return None
        return self._service().get_target_details(preset, str(target_key or "").strip().lower())

    def get_target_strategies(self, target_key: str) -> dict:
        preset = self.get_selected_source_preset_model()
        if not preset:
            return {}
        return self._service().get_strategy_entries(preset, str(target_key or "").strip().lower())

    def get_target_raw_args_text(self, target_key: str) -> str:
        preset = self.get_selected_source_preset_model()
        if not preset:
            return ""
        return self._service()._get_raw_args(preset, str(target_key or "").strip().lower())

    def update_target_raw_args_text(self, target_key: str, raw_args: str, *, save_and_sync: bool = True) -> bool:
        preset = self.get_selected_source_preset_model()
        if not preset:
            return False
        ok = self._service()._update_raw_args(preset, str(target_key or "").strip().lower(), raw_args)
        if not ok:
            return False
        return self.save_preset_model(preset, changed_target=str(target_key or "").strip().lower()) if save_and_sync else True
