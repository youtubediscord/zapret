from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import re
import time as _time
from typing import Callable, Optional

from core.direct_preset_core.common.source_preset_models import OutRangeSettings, SendSettings, SyndataSettings
from core.direct_preset_core.service import BasicUiPayload, DirectPresetService, TargetDetailPayload
from core.presets.template_support import resolve_reset_template as _template_support_resolve_reset_template
from core.presets.template_support import reset_all_templates as _template_support_reset_all_templates
from core.presets.template_support import restore_deleted_templates as _template_support_restore_deleted_templates
from core.services import get_app_paths, get_direct_flow_coordinator, get_preset_repository, get_selection_service

from .models import PresetManifest
from log import log


_BASIC_UI_PAYLOAD_CACHE: dict[tuple[str, str, str, str, int, int], BasicUiPayload] = {}


def _log_startup_payload_metric(scope: str | None, section: str, elapsed_ms: float, *, extra: str | None = None) -> None:
    resolved_scope = str(scope or "").strip()
    if not resolved_scope:
        return
    try:
        rounded = int(round(float(elapsed_ms)))
    except Exception:
        rounded = 0
    suffix = f" ({extra})" if extra else ""
    log(f"⏱ Startup UI Section: {resolved_scope} {section} {rounded}ms{suffix}", "⏱ STARTUP")


def _rewrite_preset_header_name(source_text: str, target_name: str) -> str:
    text = (source_text or "").replace("\r\n", "\n").replace("\r", "\n")
    lines = text.splitlines()
    replaced = False

    for idx, raw in enumerate(lines):
        stripped = raw.strip()
        if stripped.lower().startswith("# preset:"):
            lines[idx] = f"# Preset: {target_name}"
            replaced = True
            break
        if stripped and not stripped.startswith("#"):
            break

    if not replaced:
        lines.insert(0, f"# Preset: {target_name}")

    rewritten = "\n".join(lines).rstrip("\n")
    return rewritten + "\n"


def _rewrite_preset_headers(
    source_text: str,
    target_name: str,
    *,
    template_origin: str | None = None,
    created: str | None = None,
) -> str:
    text = (source_text or "").replace("\r\n", "\n").replace("\r", "\n")
    lines = text.splitlines()

    header_end = 0
    for idx, raw in enumerate(lines):
        stripped = raw.strip()
        if stripped and not stripped.startswith("#"):
            header_end = idx
            break
    else:
        header_end = len(lines)

    header = lines[:header_end]
    body = lines[header_end:]
    out_header: list[str] = []
    saw_preset = False
    saw_template_origin = False
    saw_created = False

    for raw in header:
        stripped = raw.strip()
        lowered = stripped.lower()
        if lowered.startswith("# preset:"):
            out_header.append(f"# Preset: {target_name}")
            saw_preset = True
            continue
        if lowered.startswith("# templateorigin:"):
            if template_origin is not None:
                out_header.append(f"# TemplateOrigin: {template_origin}")
                saw_template_origin = True
            else:
                out_header.append(raw.rstrip("\n"))
                saw_template_origin = True
            continue
        if lowered.startswith("# created:"):
            if created is not None:
                out_header.append(f"# Created: {created}")
                saw_created = True
            else:
                out_header.append(raw.rstrip("\n"))
                saw_created = True
            continue
        if lowered.startswith("# modified:"):
            continue
        if lowered.startswith("# activepreset:"):
            continue
        out_header.append(raw.rstrip("\n"))

    if not saw_preset:
        out_header.insert(0, f"# Preset: {target_name}")

    insert_idx = 1 if out_header and out_header[0].startswith("# Preset:") else 0
    if template_origin is not None and not saw_template_origin:
        out_header.insert(insert_idx, f"# TemplateOrigin: {template_origin}")
        insert_idx += 1

    if created is not None and not saw_created:
        out_header.insert(insert_idx, f"# Created: {created}")

    rewritten = "\n".join(out_header + body).rstrip("\n")
    return rewritten + "\n"


def _normalize_direct_preset_source_text(source_text: str) -> str:
    text = (source_text or "").replace("\r\n", "\n").replace("\r", "\n")
    lines = [
        line
        for line in text.splitlines()
        if not line.strip().lower().startswith("# activepreset:")
        and not line.strip().lower().startswith("# modified:")
    ]
    return "\n".join(lines).rstrip("\n") + "\n"


def _extract_debug_log_file(source_text: str) -> str:
    text = (source_text or "").replace("\r\n", "\n").replace("\r", "\n")
    for raw in text.splitlines():
        stripped = raw.strip()
        if not stripped.lower().startswith("--debug="):
            continue
        value = stripped.split("=", 1)[1].strip() if "=" in stripped else ""
        value = value.lstrip("@").replace("\\", "/").lstrip("/")
        return value
    return ""


def _build_stable_debug_log_file(preset_name: str) -> str:
    safe_name = re.sub(r"[^\w.-]+", "_", str(preset_name or "").strip(), flags=re.UNICODE).strip("._")
    if not safe_name:
        safe_name = "preset"
    return f"logs/{safe_name}_debug.log"


def _default_debug_insert_index(lines: list[str]) -> int:
    insert_at = 0
    for idx, raw in enumerate(lines):
        stripped = raw.strip()
        if stripped.startswith("--lua-init="):
            insert_at = idx + 1
    if insert_at:
        return insert_at

    header_end = 0
    for idx, raw in enumerate(lines):
        stripped = raw.strip()
        if stripped.startswith("#") or not stripped:
            header_end = idx + 1
            continue
        break
    return header_end


def _rewrite_debug_log_setting(source_text: str, preset_name: str, enabled: bool) -> str:
    text = (source_text or "").replace("\r\n", "\n").replace("\r", "\n")
    lines = text.splitlines()

    existing_value = ""
    existing_insert_at: int | None = None
    cleaned: list[str] = []
    for raw in lines:
        stripped = raw.strip()
        if stripped.lower().startswith("--debug="):
            if not existing_value:
                existing_value = stripped.split("=", 1)[1].strip() if "=" in stripped else ""
                existing_value = existing_value.lstrip("@").replace("\\", "/").lstrip("/")
                existing_insert_at = len(cleaned)
            continue
        cleaned.append(raw)

    if enabled:
        debug_file = existing_value or _build_stable_debug_log_file(preset_name)
        debug_line = f"--debug=@{debug_file}"
        insert_at = existing_insert_at if existing_insert_at is not None else _default_debug_insert_index(cleaned)
        if insert_at < 0:
            insert_at = 0
        if insert_at > len(cleaned):
            insert_at = len(cleaned)
        cleaned.insert(insert_at, debug_line)

    return "\n".join(cleaned).rstrip("\n") + "\n"


_V1_WSSIZE_FLAG = "--wssize"
_V1_WSSIZE_VALUE = "1:6"
_V1_WSSIZE_COMBINED = "--wssize=1:6"
_V1_WSSIZE_CUTOFF = "--wssize-forced-cutoff=0"
_V2_WSSIZE_LINE = "--lua-desync=wssize:wsize=1:scale=6"


def _ports_include_443(value: str) -> bool:
    for raw_part in str(value or "").split(","):
        part = raw_part.strip()
        if not part:
            continue
        if "-" in part:
            try:
                start_s, end_s = part.split("-", 1)
                start = int(start_s.strip())
                end = int(end_s.strip())
            except Exception:
                continue
            if start <= 443 <= end:
                return True
            continue
        try:
            if int(part) == 443:
                return True
        except Exception:
            continue
    return False


def _split_arg_lines(args_text: str) -> list[str]:
    return [str(raw or "").strip() for raw in str(args_text or "").splitlines() if str(raw or "").strip()]


def _join_arg_lines(lines: list[str]) -> str:
    return "\n".join(str(line or "").strip() for line in lines if str(line or "").strip()).strip()


def _settings_payload_to_dict(value) -> dict[str, object]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return dict(value)
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        try:
            data = to_dict()
            if isinstance(data, dict):
                return dict(data)
        except Exception:
            pass

    payload: dict[str, object] = {}
    for field in (
        "enabled",
        "blob",
        "tls_mod",
        "autottl_delta",
        "autottl_min",
        "autottl_max",
        "tcp_flags_unset",
        "out_range",
        "out_range_mode",
        "send_enabled",
        "send_repeats",
        "send_ip_ttl",
        "send_ip6_ttl",
        "send_ip_id",
        "send_badsum",
    ):
        if hasattr(value, field):
            payload[field] = getattr(value, field)
    return payload


def _coerce_int(value, default: int) -> int:
    try:
        return int(value)
    except Exception:
        return int(default)


def _v1_wssize_enabled_from_args(args_text: str) -> bool:
    lines = _split_arg_lines(args_text)
    for idx, line in enumerate(lines):
        lowered = line.lower()
        if lowered == _V1_WSSIZE_COMBINED:
            return True
        if lowered == _V1_WSSIZE_FLAG and idx + 1 < len(lines) and lines[idx + 1].strip() == _V1_WSSIZE_VALUE:
            return True
    return False


def _rewrite_v1_wssize_args(args_text: str, enabled: bool) -> str:
    lines = _split_arg_lines(args_text)
    cleaned: list[str] = []
    idx = 0
    while idx < len(lines):
        lowered = lines[idx].strip().lower()
        if lowered == _V1_WSSIZE_COMBINED:
            idx += 1
            continue
        if lowered == _V1_WSSIZE_FLAG:
            if idx + 1 < len(lines) and lines[idx + 1].strip() == _V1_WSSIZE_VALUE:
                idx += 2
                if idx < len(lines) and lines[idx].strip().lower() == _V1_WSSIZE_CUTOFF:
                    idx += 1
                continue
        if lowered == _V1_WSSIZE_CUTOFF:
            idx += 1
            continue
        cleaned.append(lines[idx])
        idx += 1

    if enabled and not _v1_wssize_enabled_from_args(_join_arg_lines(cleaned)):
        cleaned.extend([_V1_WSSIZE_FLAG, _V1_WSSIZE_VALUE, _V1_WSSIZE_CUTOFF])

    return _join_arg_lines(cleaned)


def _v2_wssize_enabled_from_args(args_text: str) -> bool:
    return any(line.strip().lower() == _V2_WSSIZE_LINE for line in _split_arg_lines(args_text))


def _rewrite_v2_wssize_args(args_text: str, enabled: bool) -> str:
    lines = [line for line in _split_arg_lines(args_text) if line.strip().lower() != _V2_WSSIZE_LINE]
    if enabled and not any(line.strip().lower() == _V2_WSSIZE_LINE for line in lines):
        lines.insert(0, _V2_WSSIZE_LINE)
    return _join_arg_lines(lines)


def _resolve_reset_template(launch_method: str, preset_name: str) -> str:
    return _template_support_resolve_reset_template(launch_method, preset_name)


@dataclass(frozen=True)
class DirectPresetFacadeBackend:
    engine: str
    launch_method: str
    on_dpi_reload_needed: Optional[Callable[[], None]] = None

    def _service(self) -> DirectPresetService:
        return DirectPresetService(get_app_paths(), self.engine)

    def _current_direct_strategy_set(self) -> str:
        if self.launch_method != "direct_zapret2":
            return ""
        try:
            from strategy_menu.ui_prefs_store import get_direct_zapret2_ui_mode

            value = str(get_direct_zapret2_ui_mode() or "").strip().lower()
            if value in ("basic", "advanced"):
                return value
        except Exception:
            pass
        return "basic"

    def _invalidate_basic_ui_payload_cache(self) -> None:
        global _BASIC_UI_PAYLOAD_CACHE
        prefix = (self.engine, self.launch_method)
        _BASIC_UI_PAYLOAD_CACHE = {
            key: value
            for key, value in _BASIC_UI_PAYLOAD_CACHE.items()
            if key[:2] != prefix
        }

    def _basic_ui_payload_cache_key(self) -> tuple[str, str, str, str, int, int] | None:
        selected_manifest = self.get_selected_manifest()
        if selected_manifest is None:
            return None
        selected_file_name = str(selected_manifest.file_name or "").strip()
        if not selected_file_name:
            return None
        try:
            path = self.get_source_path_by_file_name(selected_file_name)
            stat = path.stat()
        except Exception:
            return None
        return (
            self.engine,
            self.launch_method,
            self._current_direct_strategy_set(),
            selected_file_name,
            int(getattr(stat, "st_mtime_ns", 0) or 0),
            int(getattr(stat, "st_size", 0) or 0),
        )

    def _load_selected_preset_model(self):
        selected_manifest = self.get_selected_manifest()
        if selected_manifest is None:
            return None
        selected_file_name = str(selected_manifest.file_name or "").strip()
        if not selected_file_name:
            return None
        return self._service().read_source_preset(self.get_source_path_by_file_name(selected_file_name))

    def list_manifests(self) -> list[PresetManifest]:
        return get_preset_repository().list_manifests(self.engine)

    def get_basic_ui_payload(self, *, startup_scope: str | None = None) -> BasicUiPayload:
        _t_total = _time.perf_counter()
        _t_load = _time.perf_counter()
        cache_key = self._basic_ui_payload_cache_key()
        if cache_key is not None:
            cached_payload = _BASIC_UI_PAYLOAD_CACHE.get(cache_key)
            if cached_payload is not None:
                _log_startup_payload_metric(
                    startup_scope,
                    "_build_content.payload.backend.load_selected_preset",
                    (_time.perf_counter() - _t_load) * 1000,
                    extra=f"has_preset=yes, cache=hit",
                )
                _log_startup_payload_metric(
                    startup_scope,
                    "_build_content.payload.backend.total",
                    (_time.perf_counter() - _t_total) * 1000,
                    extra=f"targets={len(cached_payload.target_items or {})}, cache=hit",
                )
                return cached_payload
        preset = self.get_selected_source_preset_model()
        _log_startup_payload_metric(
            startup_scope,
            "_build_content.payload.backend.load_selected_preset",
            (_time.perf_counter() - _t_load) * 1000,
            extra=f"has_preset={'yes' if preset else 'no'}, cache=miss",
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
            )
        _t_service = _time.perf_counter()
        payload = self._service().build_basic_ui_payload(
            preset,
            startup_scope=startup_scope,
            strategy_set=self._current_direct_strategy_set(),
        )
        if cache_key is not None:
            _BASIC_UI_PAYLOAD_CACHE[cache_key] = payload
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
        presets_dir = get_app_paths().engine_paths(self.engine).ensure_directories().presets_dir
        preset_paths = sorted(path for path in presets_dir.glob("*.txt") if path.is_file())
        if not preset_paths:
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
            return get_direct_flow_coordinator().get_selected_source_manifest(self.launch_method)
        except Exception:
            return None

    def is_selected_file_name(self, file_name: str) -> bool:
        return (self.get_selected_file_name() or "").strip().lower() == str(file_name or "").strip().lower()

    def get_manifest_by_file_name(self, file_name: str) -> PresetManifest | None:
        return get_preset_repository().get_manifest(self.engine, file_name)

    def read_source_text_by_file_name(self, file_name: str) -> str:
        manifest = self.get_manifest_by_file_name(file_name)
        if manifest is None:
            raise ValueError(f"Preset not found: {file_name}")
        return get_preset_repository().read_source_text(self.engine, manifest.file_name)

    def read_selected_source_text(self) -> str:
        selected_file_name = self.get_selected_file_name()
        if not selected_file_name:
            return ""
        return self.read_source_text_by_file_name(selected_file_name)

    def _hierarchy_scope_key(self) -> str:
        if self.launch_method == "direct_zapret2":
            return "preset_zapret2"
        if self.launch_method == "direct_zapret1":
            return "preset_zapret1"
        raise ValueError(f"Unsupported launch method for preset hierarchy: {self.launch_method}")

    def _get_hierarchy_store(self):
        from .library_hierarchy import PresetHierarchyStore

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
        return get_app_paths().engine_paths(self.engine).ensure_directories().presets_dir / manifest.file_name

    def save_source_text_by_file_name(self, file_name: str, source_text: str) -> PresetManifest:
        manifest = self.get_manifest_by_file_name(file_name)
        if manifest is None:
            raise ValueError(f"Preset not found: {file_name}")
        normalized = _normalize_direct_preset_source_text(source_text)
        updated = get_preset_repository().update_preset(self.engine, manifest.file_name, normalized, None)
        if self.is_selected_file_name(updated.file_name):
            get_direct_flow_coordinator().refresh_selected_launch_profile(self.launch_method)
        return updated

    def get_debug_log_file(self) -> str:
        selected_file_name = self.get_selected_file_name()
        if not selected_file_name:
            return ""
        return _extract_debug_log_file(self.read_source_text_by_file_name(selected_file_name))

    def get_debug_log_enabled(self) -> bool:
        return bool(self.get_debug_log_file())

    def get_advanced_settings_state(self) -> dict[str, bool]:
        discord_restart = True
        try:
            from discord.discord_restart import get_discord_restart_setting

            discord_restart = bool(get_discord_restart_setting(default=True))
        except Exception:
            pass

        manifest = self.get_selected_manifest()
        if manifest is None:
            return {
                "discord_restart": discord_restart,
                "wssize_enabled": False,
                "debug_log_enabled": False,
            }

        debug_log_enabled = False
        try:
            debug_log_enabled = bool(_extract_debug_log_file(self.read_source_text_by_file_name(manifest.file_name)))
        except Exception:
            debug_log_enabled = False

        wssize_enabled = False
        try:
            preset = self.get_selected_source_preset_model()
            if preset:
                contexts = self._service().collect_target_contexts(preset)
                for target_key, ctx in contexts.items():
                    if ctx.protocol_kind != "tcp":
                        continue
                    profile = preset.profiles[ctx.profile_index]
                    if not any(
                        line.strip().startswith("--filter-tcp=") and _ports_include_443(line.split("=", 1)[1].strip())
                        for line in profile.match_lines
                    ):
                        continue
                    args_text = self._service()._get_raw_args(preset, target_key)
                    if self.launch_method == "direct_zapret2" and _v2_wssize_enabled_from_args(args_text):
                        wssize_enabled = True
                        break
                    if self.launch_method == "direct_zapret1" and _v1_wssize_enabled_from_args(args_text):
                        wssize_enabled = True
                        break
        except Exception:
            wssize_enabled = False

        return {
            "discord_restart": discord_restart,
            "wssize_enabled": bool(wssize_enabled),
            "debug_log_enabled": bool(debug_log_enabled),
        }

    def set_debug_log_enabled(self, enabled: bool) -> bool:
        manifest = self.get_selected_manifest()
        if manifest is None:
            return False
        display_name = str(manifest.name or "").strip() or Path(manifest.file_name).stem
        source_text = self.read_source_text_by_file_name(manifest.file_name)
        rewritten = _rewrite_debug_log_setting(source_text, display_name, bool(enabled))
        self.save_source_text_by_file_name(manifest.file_name, rewritten)
        return True

    def get_wssize_enabled(self) -> bool:
        preset = self.get_selected_source_preset_model()
        if not preset:
            return False

        contexts = self._service().collect_target_contexts(preset)
        for target_key, ctx in contexts.items():
            if ctx.protocol_kind != "tcp":
                continue
            profile = preset.profiles[ctx.profile_index]
            if not any(
                line.strip().startswith("--filter-tcp=") and _ports_include_443(line.split("=", 1)[1].strip())
                for line in profile.match_lines
            ):
                continue
            args_text = self._service()._get_raw_args(preset, target_key)
            if self.launch_method == "direct_zapret2" and _v2_wssize_enabled_from_args(args_text):
                return True
            if self.launch_method == "direct_zapret1" and _v1_wssize_enabled_from_args(args_text):
                return True
        return False

    def set_wssize_enabled(self, enabled: bool) -> bool:
        preset = self.get_selected_source_preset_model()
        if not preset:
            return False

        changed = False
        touched_any_tcp_443 = False
        target_keys = list(self._service().collect_target_contexts(preset).keys())

        for target_key in target_keys:
            normalized_key = str(target_key or "").strip().lower()
            current_ctx = self._service().collect_target_contexts(preset).get(normalized_key)
            if not normalized_key or current_ctx is None or current_ctx.protocol_kind != "tcp":
                continue
            profile = preset.profiles[current_ctx.profile_index]
            if not any(
                line.strip().startswith("--filter-tcp=") and _ports_include_443(line.split("=", 1)[1].strip())
                for line in profile.match_lines
            ):
                continue

            touched_any_tcp_443 = True
            current_args = self._service()._get_raw_args(preset, normalized_key) or ""
            if self.launch_method == "direct_zapret2":
                next_args = _rewrite_v2_wssize_args(current_args, bool(enabled))
            else:
                next_args = _rewrite_v1_wssize_args(current_args, bool(enabled))
            if next_args != _join_arg_lines(_split_arg_lines(current_args)):
                if self._service()._update_raw_args(preset, normalized_key, next_args):
                    changed = True

        if not touched_any_tcp_443:
            return False if enabled else True
        if not changed:
            return True

        try:
            preset.touch()
        except Exception:
            pass
        return bool(self.save_preset_model(preset))

    def _refresh_selected_launch_profile_from_source(self) -> None:
        selected_file_name = self.get_selected_file_name()
        if not selected_file_name or self.get_manifest_by_file_name(selected_file_name) is None:
            return
        get_direct_flow_coordinator().refresh_selected_launch_profile(self.launch_method)

    def select_file_name(self, file_name: str):
        return get_direct_flow_coordinator().select_preset_file_name(self.launch_method, file_name)

    def rename_by_file_name(self, file_name: str, new_name: str) -> PresetManifest:
        manifest = self.get_manifest_by_file_name(file_name)
        if manifest is None:
            raise ValueError(f"Preset not found: {file_name}")
        if str(manifest.kind or "").strip().lower() == "builtin":
            raise ValueError(f"Built-in preset cannot be renamed: {manifest.name}")
        was_selected = self.is_selected_file_name(manifest.file_name)
        source_text = self.read_source_text_by_file_name(manifest.file_name)
        renamed = get_preset_repository().rename_preset(self.engine, manifest.file_name, new_name)
        rewritten = _rewrite_preset_headers(
            source_text,
            new_name,
            template_origin=manifest.template_origin,
        )
        updated = get_preset_repository().update_preset(self.engine, renamed.file_name, rewritten, None)
        self._rename_library_meta(
            manifest.file_name,
            updated.file_name,
            old_display_name=manifest.name,
            new_display_name=updated.name,
        )
        if was_selected:
            get_selection_service().select_preset(self.engine, updated.file_name)
            self._refresh_selected_launch_profile_from_source()
        return updated

    def duplicate_by_file_name(self, file_name: str, new_name: str) -> PresetManifest:
        manifest = self.get_manifest_by_file_name(file_name)
        if manifest is None:
            raise ValueError(f"Preset not found: {file_name}")
        source_text = self.read_source_text_by_file_name(manifest.file_name)
        now = datetime.now().isoformat()
        rewritten = _rewrite_preset_headers(
            source_text,
            new_name,
            template_origin=manifest.template_origin,
            created=now,
        )
        duplicated = get_preset_repository().create_preset(self.engine, new_name, rewritten)
        self._copy_library_meta(
            manifest.file_name,
            duplicated.file_name,
            source_display_name=manifest.name,
            new_display_name=duplicated.name,
        )
        return duplicated

    def create(self, name: str, *, from_current: bool = True) -> PresetManifest:
        source_text = self.read_selected_source_text() if from_current else _resolve_reset_template(self.launch_method, "Default")
        now = datetime.now().isoformat()
        rewritten = _rewrite_preset_headers(source_text, name, created=now)
        return get_preset_repository().create_preset(self.engine, name, rewritten)

    def import_from_file(self, src_path: Path, name: str | None = None) -> PresetManifest:
        src = Path(src_path)
        if not src.exists():
            raise ValueError(f"Import source not found: {src}")
        target_name = str(name or src.stem or "Imported").strip() or "Imported"
        source_text = src.read_text(encoding="utf-8", errors="replace")
        rewritten = _rewrite_preset_headers(source_text, target_name)
        imported = get_preset_repository().create_preset(self.engine, target_name, rewritten, kind="imported")
        self._delete_library_meta(imported.file_name, display_name=imported.name)
        return imported

    def export_plain_text_by_file_name(self, file_name: str, dest_path: Path) -> Path:
        dest = Path(dest_path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        text = self.read_source_text_by_file_name(file_name)
        if not text.endswith("\n"):
            text += "\n"
        dest.write_text(text, encoding="utf-8")
        return dest

    def reset_to_template_by_file_name(self, file_name: str) -> PresetManifest:
        manifest = self.get_manifest_by_file_name(file_name)
        if manifest is None:
            raise ValueError(f"Preset not found: {file_name}")
        template_key = str(manifest.template_origin or manifest.name or "").strip()
        template_content = _resolve_reset_template(self.launch_method, template_key)
        if not template_content:
            raise ValueError("Template content not found")
        rewritten = _rewrite_preset_headers(
            template_content,
            manifest.name,
            template_origin=str(manifest.template_origin or "").strip() or None,
        )
        updated = get_preset_repository().update_preset(self.engine, manifest.file_name, rewritten, None)
        if self.is_selected_file_name(manifest.file_name):
            self._refresh_selected_launch_profile_from_source()
        return updated

    def reset_all_to_templates(self) -> tuple[int, int, list[str]]:
        result = _template_support_reset_all_templates(self.launch_method)
        selected_file_name = self.get_selected_file_name()
        if selected_file_name and self.get_manifest_by_file_name(selected_file_name) is not None:
            self._refresh_selected_launch_profile_from_source()
        return result

    def restore_deleted(self) -> None:
        _template_support_restore_deleted_templates(self.launch_method)
        selected_file_name = self.get_selected_file_name()
        if selected_file_name and self.get_manifest_by_file_name(selected_file_name) is not None:
            self._refresh_selected_launch_profile_from_source()

    def delete_by_file_name(self, file_name: str) -> None:
        manifest = self.get_manifest_by_file_name(file_name)
        if manifest is None:
            raise ValueError(f"Preset not found: {file_name}")
        if str(manifest.kind or "").strip().lower() == "builtin":
            raise ValueError(f"Built-in preset cannot be deleted: {manifest.name}")
        get_selection_service().ensure_can_delete(self.engine, manifest.file_name)
        get_preset_repository().delete_preset(self.engine, manifest.file_name)
        self._delete_library_meta(manifest.file_name, display_name=manifest.name)

    def get_strategy_selections(self) -> dict:
        preset = self.get_selected_source_preset_model()
        if not preset:
            return {}
        return self._service().get_strategy_selections(preset)

    def set_strategy_selections(self, selections: dict, *, save_and_sync: bool = True) -> bool:
        preset = self.get_selected_source_preset_model()
        if not preset:
            return False
        for target_key, strategy_id in (selections or {}).items():
            normalized_key = str(target_key or "").strip().lower()
            if not normalized_key:
                continue
            self._service().update_strategy_selection(preset, normalized_key, str(strategy_id or "").strip() or "none")
        return self.save_preset_model(preset) if save_and_sync else True

    def set_strategy_selection(self, target_key: str, strategy_id: str, *, save_and_sync: bool = True) -> bool:
        normalized_key = str(target_key or "").strip().lower()
        if not normalized_key:
            return False
        preset = self.get_selected_source_preset_model()
        if not preset:
            return False
        ok = self._service().update_strategy_selection(preset, normalized_key, strategy_id)
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
        if self.launch_method != "direct_zapret2":
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
        if self.launch_method != "direct_zapret2":
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
        return self.launch_method == "direct_zapret2"

    def save_preset_model(self, preset, *, changed_target: str | None = None) -> bool:
        _ = changed_target
        selected_manifest = self.get_selected_manifest()
        if selected_manifest is None:
            return False
        source_text = _normalize_direct_preset_source_text(self._service()._serializer().serialize(preset))
        get_preset_repository().update_preset(self.engine, selected_manifest.file_name, source_text, selected_manifest.name)
        self._invalidate_basic_ui_payload_cache()
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
