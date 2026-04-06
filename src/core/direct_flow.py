from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import time
from typing import Callable

from log import log
from core.presets.cache_signatures import path_cache_signature
from core.presets.models import PresetManifest
from core.presets.v1_builtin_templates import is_builtin_preset_file_name_v1
from core.presets.z2_builtin_templates import is_builtin_preset_file_name_v2


class DirectFlowError(RuntimeError):
    """Raised when the direct-launch selected source preset flow cannot be prepared."""


@dataclass(frozen=True)
class DirectLaunchProfile:
    launch_method: str
    engine: str
    preset_file_name: str
    preset_name: str
    launch_config_path: Path
    display_name: str

    def to_selected_mode(self) -> dict[str, object]:
        return {
            "is_preset_file": True,
            "name": self.display_name,
            "preset_path": str(self.launch_config_path),
        }


@dataclass(frozen=True)
class DirectStartupSnapshot:
    launch_method: str
    engine: str
    preset_file_name: str
    preset_name: str
    preset_path: Path
    display_name: str
    has_required_filters: bool | None = None

    def to_selected_mode(self) -> dict[str, object]:
        return {
            "is_preset_file": True,
            "name": self.display_name,
            "preset_path": str(self.preset_path),
        }

    def to_launch_profile(self) -> DirectLaunchProfile:
        return DirectLaunchProfile(
            launch_method=self.launch_method,
            engine=self.engine,
            preset_file_name=self.preset_file_name,
            preset_name=self.preset_name,
            launch_config_path=self.preset_path,
            display_name=self.display_name,
        )


class DirectFlowCoordinator:
    PRESETS_DOWNLOAD_URL = "https://github.com/youtubediscord/zapret/discussions/categories/presets"

    _METHOD_TO_ENGINE = {
        "direct_zapret1": "winws1",
        "direct_zapret2": "winws2",
    }
    _PRESET_HEADER_RE = re.compile(r"^\s*#\s*Preset:\s*(.+?)\s*$", re.IGNORECASE | re.MULTILINE)
    _TEMPLATE_ORIGIN_RE = re.compile(r"^\s*#\s*TemplateOrigin:\s*(.+?)\s*$", re.IGNORECASE | re.MULTILINE)

    def __init__(self) -> None:
        self._prepared_support_methods: set[str] = set()
        self._selected_manifest_cache: dict[str, tuple[tuple[object, ...], PresetManifest]] = {}
        self._index_kind_cache: dict[str, tuple[tuple[object, ...], dict[str, str]]] = {}
        self._support_prepare_errors: dict[str, str] = {}

    def ensure_support_files_ready(self, launch_method: str) -> None:
        """Prepares runtime support files for the given direct launch method."""
        self._ensure_support_files(launch_method)

    def ensure_launch_profile(
        self,
        launch_method: str,
        *,
        require_filters: bool = False,
        timing_callback: Callable[[str, float], None] | None = None,
        timing_label: str | None = None,
    ) -> DirectLaunchProfile:
        snapshot = self.get_startup_snapshot(
            launch_method,
            require_filters=require_filters,
            timing_callback=timing_callback,
            timing_label=timing_label,
        )
        return snapshot.to_launch_profile()

    def get_startup_snapshot(
        self,
        launch_method: str,
        *,
        require_filters: bool = False,
        timing_callback: Callable[[str, float], None] | None = None,
        timing_label: str | None = None,
    ) -> DirectStartupSnapshot:
        started_at = time.perf_counter()
        method = self._normalize_method(launch_method)
        label = str(timing_label or f"direct_flow.{method}.startup_snapshot")

        t_selected = time.perf_counter()
        selected = self._ensure_selected_source_manifest(
            method,
            timing_callback=timing_callback,
            timing_label=label,
        )
        self._emit_timing(timing_callback, f"{label}.selected_manifest", t_selected)

        t_path = time.perf_counter()
        launch_config_path = self._get_source_preset_path(
            self._METHOD_TO_ENGINE[method],
            selected.file_name,
        )
        self._emit_timing(timing_callback, f"{label}.selected_source_path", t_path)
        if not launch_config_path.exists():
            raise DirectFlowError(f"Selected source preset not found: {launch_config_path}")

        has_required_filters: bool | None = None
        if require_filters:
            text = ""
            t_read = time.perf_counter()
            try:
                text = launch_config_path.read_text(encoding="utf-8").strip()
            except Exception as exc:
                raise DirectFlowError(f"Failed to read selected source preset: {exc}") from exc
            self._emit_timing(timing_callback, f"{label}.read_preset_text", t_read)

            t_filters = time.perf_counter()
            has_required_filters = self._has_required_filters(method, text)
            if not has_required_filters:
                raise DirectFlowError("Выберите хотя бы одну категорию для запуска")
            self._emit_timing(timing_callback, f"{label}.filter_validation", t_filters)

        self._emit_timing(timing_callback, f"{label}.total", started_at)

        return DirectStartupSnapshot(
            launch_method=method,
            engine=self._METHOD_TO_ENGINE[method],
            preset_file_name=selected.file_name,
            preset_name=selected.name,
            preset_path=launch_config_path,
            display_name=f"Пресет: {selected.name}",
            has_required_filters=has_required_filters,
        )

    def build_selected_mode(
        self,
        launch_method: str,
        *,
        require_filters: bool = False,
    ) -> dict[str, object]:
        return self.get_startup_snapshot(
            launch_method,
            require_filters=require_filters,
        ).to_selected_mode()

    def get_selected_source_manifest(self, launch_method: str) -> PresetManifest:
        return self._ensure_selected_source_manifest(launch_method)

    def get_selected_source_file_name(self, launch_method: str) -> str:
        return self.get_selected_source_manifest(launch_method).file_name

    def get_selected_source_path(self, launch_method: str) -> Path:
        selected = self.get_selected_source_manifest(launch_method)
        from core.services import get_app_paths

        engine = self._METHOD_TO_ENGINE[self._normalize_method(launch_method)]
        return get_app_paths().engine_paths(engine).ensure_directories().presets_dir / selected.file_name

    def ensure_selected_source_path(self, launch_method: str) -> Path:
        return self.get_startup_snapshot(launch_method, require_filters=False).preset_path

    def is_selected_preset(self, launch_method: str, preset_name: str) -> bool:
        try:
            current = (self.get_selected_source_manifest(launch_method).name or "").strip().lower()
        except Exception:
            current = ""
        target = str(preset_name or "").strip().lower()
        return bool(current and target and current == target)

    def select_preset_file_name(self, launch_method: str, file_name: str) -> DirectLaunchProfile:
        method = self._normalize_method(launch_method)
        engine = self._METHOD_TO_ENGINE[method]
        self._ensure_support_files(method)

        from core.services import get_selection_service

        selected_file_name = get_selection_service().select_preset_file_name_fast(engine, file_name)
        selected_manifest = self._remember_manifest_from_file_name(method, engine, selected_file_name)
        selected_path = self._get_source_preset_path(engine, selected_file_name)
        display_name = str(getattr(selected_manifest, "name", "") or "").strip() or Path(selected_file_name).stem
        return DirectLaunchProfile(
            launch_method=method,
            engine=engine,
            preset_file_name=selected_file_name,
            preset_name=display_name,
            launch_config_path=selected_path,
            display_name=f"Пресет: {display_name}",
        )

    def refresh_selected_launch_profile(self, launch_method: str) -> DirectLaunchProfile:
        return self.ensure_launch_profile(launch_method, require_filters=False)

    def _normalize_method(self, launch_method: str) -> str:
        method = str(launch_method or "").strip().lower()
        if method not in self._METHOD_TO_ENGINE:
            raise DirectFlowError(f"Unsupported direct launch method: {launch_method}")
        return method

    def _ensure_selected_source_manifest(
        self,
        launch_method: str,
        *,
        timing_callback: Callable[[str, float], None] | None = None,
        timing_label: str | None = None,
    ) -> PresetManifest:
        started_at = time.perf_counter()
        method = self._normalize_method(launch_method)
        engine = self._METHOD_TO_ENGINE[method]
        label = str(timing_label or f"direct_flow.{method}.ensure_selected_source_manifest")

        t_support = time.perf_counter()
        self._ensure_support_files(
            method,
            timing_callback=timing_callback,
            timing_label=label,
        )
        self._emit_timing(timing_callback, f"{label}.support_files", t_support)

        from core.services import get_selection_service

        t_selection_service = time.perf_counter()
        selection = get_selection_service()
        self._emit_timing(timing_callback, f"{label}.selection_service", t_selection_service)

        t_selected_name = time.perf_counter()
        selected_file_name = str(selection.get_selected_file_name(engine) or "").strip()
        self._emit_timing(timing_callback, f"{label}.selected_file_name", t_selected_name)
        if selected_file_name:
            t_cache_key = time.perf_counter()
            cache_key = self._selected_manifest_cache_key(method, engine, selected_file_name)
            self._emit_timing(timing_callback, f"{label}.cache_key", t_cache_key)
            t_cache_lookup = time.perf_counter()
            cached_manifest = self._selected_manifest_from_cache(method, cache_key)
            self._emit_timing(timing_callback, f"{label}.cache_lookup", t_cache_lookup)
            if cached_manifest is not None:
                self._emit_timing(timing_callback, f"{label}.total", started_at)
                return cached_manifest

            t_selected_path = time.perf_counter()
            selected_path = self._get_source_preset_path(engine, selected_file_name)
            self._emit_timing(timing_callback, f"{label}.selected_path", t_selected_path)
            if selected_path.exists():
                t_manifest = time.perf_counter()
                manifest = self._remember_manifest_from_path(
                    method,
                    engine,
                    selected_path,
                    cache_key=cache_key,
                    timing_callback=timing_callback,
                    timing_label=label,
                )
                self._emit_timing(timing_callback, f"{label}.remember_selected_manifest", t_manifest)
                self._emit_timing(timing_callback, f"{label}.total", started_at)
                return manifest

        t_default = time.perf_counter()
        default_path = self._get_source_preset_path(engine, "Default.txt")
        if default_path.exists():
            selected_file_name = selection.select_preset_file_name_fast(engine, default_path.name)
            manifest = self._remember_manifest_from_file_name(method, engine, selected_file_name)
            self._emit_timing(timing_callback, f"{label}.default_manifest", t_default)
            self._emit_timing(timing_callback, f"{label}.total", started_at)
            return manifest

        t_list = time.perf_counter()
        preset_paths = self._list_source_preset_paths(engine)
        self._emit_timing(timing_callback, f"{label}.list_source_presets", t_list)
        if not preset_paths:
            support_error = str(self._support_prepare_errors.get(method) or "").strip()
            if support_error:
                raise DirectFlowError(
                    "Не удалось подготовить встроенные пресеты: "
                    f"{support_error}"
                )
            raise DirectFlowError(
                "Пресеты не найдены. Скачайте файлы пресетов вручную: "
                f"{self.PRESETS_DOWNLOAD_URL}"
            )

        t_first = time.perf_counter()
        first_path = preset_paths[0]
        selected_file_name = selection.select_preset_file_name_fast(engine, first_path.name)
        selected_path = self._get_source_preset_path(engine, selected_file_name)
        if selected_path.exists():
            manifest = self._remember_manifest_from_path(
                method,
                engine,
                selected_path,
                timing_callback=timing_callback,
                timing_label=label,
            )
            self._emit_timing(timing_callback, f"{label}.first_available_manifest", t_first)
            self._emit_timing(timing_callback, f"{label}.total", started_at)
            return manifest

        if not selected_file_name:
            raise DirectFlowError("Не удалось определить выбранный пресет")
        raise DirectFlowError(f"Выбранный пресет не найден: {selected_file_name}")

    @staticmethod
    def _has_required_filters(launch_method: str, text: str) -> bool:
        content = str(text or "")
        if launch_method == "direct_zapret1":
            return any(flag in content for flag in ("--wf-tcp=", "--wf-udp="))
        return any(flag in content for flag in ("--wf-tcp-out", "--wf-udp-out", "--wf-raw-part"))

    def _ensure_support_files(
        self,
        launch_method: str,
        *,
        timing_callback: Callable[[str, float], None] | None = None,
        timing_label: str | None = None,
    ) -> None:
        method = self._normalize_method(launch_method)
        if method in self._prepared_support_methods:
            return
        label = str(timing_label or f"direct_flow.{method}.support_files")
        started_at = time.perf_counter()
        try:
            from core.presets.support_files import prepare_direct_support_files

            prepare_direct_support_files(method)
            self._prepared_support_methods.add(method)
            self._support_prepare_errors.pop(method, None)
            self._emit_timing(timing_callback, f"{label}.prepare_direct_support_files", started_at)
        except Exception as exc:
            self._support_prepare_errors[method] = str(exc or "unknown support preparation error")
            log(f"Failed to prepare direct support files for {method}: {exc}", "DEBUG")

    @staticmethod
    def _emit_timing(
        timing_callback: Callable[[str, float], None] | None,
        section: str,
        started_at: float,
    ) -> None:
        if timing_callback is None:
            return
        try:
            timing_callback(str(section or ""), max(0.0, (time.perf_counter() - started_at) * 1000.0))
        except Exception:
            pass

    def _selected_manifest_cache_key(
        self,
        launch_method: str,
        engine: str,
        selected_file_name: str,
    ) -> tuple[object, ...] | None:
        candidate = str(selected_file_name or "").strip()
        if not candidate:
            return None

        from core.services import get_app_paths

        engine_paths = get_app_paths().engine_paths(engine).ensure_directories()
        preset_path = engine_paths.presets_dir / candidate
        if not preset_path.exists():
            return None

        return (
            self._normalize_method(launch_method),
            engine,
            candidate.lower(),
            *path_cache_signature(engine_paths.selected_state_path),
            *path_cache_signature(engine_paths.index_path),
            *path_cache_signature(preset_path),
        )

    def _selected_manifest_from_cache(
        self,
        launch_method: str,
        cache_key: tuple[object, ...] | None,
    ) -> PresetManifest | None:
        if cache_key is None:
            return None
        cached = self._selected_manifest_cache.get(self._normalize_method(launch_method))
        if cached is None:
            return None
        cached_key, manifest = cached
        if cached_key == cache_key:
            return manifest
        return None

    def _remember_manifest_from_path(
        self,
        launch_method: str,
        engine: str,
        path: Path,
        *,
        cache_key: tuple[object, ...] | None = None,
        timing_callback: Callable[[str, float], None] | None = None,
        timing_label: str | None = None,
    ) -> PresetManifest:
        manifest_started = time.perf_counter()
        manifest = self._manifest_from_source_path(
            engine,
            path,
            timing_callback=timing_callback,
            timing_label=timing_label,
        )
        label = str(timing_label or f"direct_flow.{self._normalize_method(launch_method)}.manifest")
        self._emit_timing(timing_callback, f"{label}.manifest_from_source_path", manifest_started)
        resolved_key = cache_key
        if resolved_key is None:
            resolved_key = self._selected_manifest_cache_key(launch_method, engine, path.name)
        if resolved_key is not None:
            self._selected_manifest_cache[self._normalize_method(launch_method)] = (resolved_key, manifest)
        return manifest

    def _remember_manifest_from_file_name(
        self,
        launch_method: str,
        engine: str,
        selected_file_name: str,
    ) -> PresetManifest:
        selected_path = self._get_source_preset_path(engine, selected_file_name)
        return self._remember_manifest_from_path(
            launch_method,
            engine,
            selected_path,
            cache_key=self._selected_manifest_cache_key(launch_method, engine, selected_file_name),
        )

    @classmethod
    def _read_header_metadata_from_source(
        cls,
        path: Path,
        *,
        fallback: str,
    ) -> tuple[str, str | None]:
        try:
            lines: list[str] = []
            with path.open("r", encoding="utf-8", errors="replace") as handle:
                for raw in handle:
                    stripped = raw.strip()
                    if stripped and not stripped.startswith("#"):
                        break
                    lines.append(raw.rstrip("\n"))
        except Exception:
            return str(fallback or "Preset").strip() or "Preset", None

        text = "\n".join(lines)
        display_name = str(fallback or "Preset").strip() or "Preset"
        match = cls._PRESET_HEADER_RE.search(text or "")
        if match:
            value = str(match.group(1) or "").strip()
            if value:
                display_name = value

        template_origin = None
        match = cls._TEMPLATE_ORIGIN_RE.search(text or "")
        if match:
            value = str(match.group(1) or "").strip()
            if value:
                template_origin = value

        return display_name, template_origin

    def _get_source_preset_path(self, engine: str, file_name: str) -> Path:
        from core.services import get_app_paths

        return get_app_paths().engine_paths(engine).ensure_directories().presets_dir / str(file_name or "").strip()

    def _list_source_preset_paths(self, engine: str) -> list[Path]:
        from core.services import get_app_paths

        presets_dir = get_app_paths().engine_paths(engine).ensure_directories().presets_dir
        return sorted(
            (path for path in presets_dir.glob("*.txt") if path.is_file()),
            key=lambda path: path.name.lower(),
        )

    @staticmethod
    def _file_time_to_iso(path: Path) -> str:
        try:
            value = float(path.stat().st_mtime)
        except Exception:
            value = 0.0
        if value <= 0:
            return ""
        return datetime.fromtimestamp(value, tz=timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    def _manifest_from_source_path(
        self,
        engine: str,
        path: Path,
        *,
        timing_callback: Callable[[str, float], None] | None = None,
        timing_label: str | None = None,
    ) -> PresetManifest:
        label = str(timing_label or f"direct_flow.{engine}.manifest")
        file_name = path.name
        t_header = time.perf_counter()
        display_name, template_origin = self._read_header_metadata_from_source(path, fallback=path.stem)
        self._emit_timing(timing_callback, f"{label}.manifest_header_metadata", t_header)
        t_timestamp = time.perf_counter()
        timestamp = self._file_time_to_iso(path)
        self._emit_timing(timing_callback, f"{label}.manifest_timestamp", t_timestamp)
        kind = "builtin" if self._is_builtin_preset(engine, path, template_origin) else "user"
        t_kind = time.perf_counter()
        imported_kind = self._get_index_kind_hint(engine, file_name)
        if imported_kind == "imported":
            kind = "imported"
        self._emit_timing(timing_callback, f"{label}.manifest_kind_hint", t_kind)
        return PresetManifest(
            file_name=file_name,
            name=display_name,
            template_origin=template_origin,
            created_at=timestamp,
            updated_at=timestamp,
            kind=kind,
        )

    def _get_index_kind_hint(self, engine: str, file_name: str) -> str | None:
        normalized_engine = str(engine or "").strip().lower()
        target = str(file_name or "").strip().lower()
        if not normalized_engine or not target:
            return None

        try:
            from core.services import get_app_paths

            index_path = get_app_paths().engine_paths(normalized_engine).ensure_directories().index_path
        except Exception:
            return None

        signature = path_cache_signature(index_path)
        cached = self._index_kind_cache.get(normalized_engine)
        if cached is not None and cached[0] == signature:
            return cached[1].get(target)

        kinds: dict[str, str] = {}
        if index_path.exists():
            try:
                payload = json.loads(index_path.read_text(encoding="utf-8", errors="replace") or "[]")
            except Exception:
                payload = []

            if isinstance(payload, list):
                for item in payload:
                    if not isinstance(item, dict):
                        continue
                    item_file_name = str(item.get("file_name") or "").strip().lower()
                    item_kind = str(item.get("kind") or "").strip().lower()
                    if item_file_name and item_kind:
                        kinds[item_file_name] = item_kind

        self._index_kind_cache[normalized_engine] = (signature, kinds)
        return kinds.get(target)

    @staticmethod
    def _is_builtin_preset(engine: str, path: Path, template_origin: str | None) -> bool:
        engine_key = str(engine or "").strip().lower()
        if engine_key == "winws2":
            return is_builtin_preset_file_name_v2(path.name)
        if engine_key == "winws1":
            return is_builtin_preset_file_name_v1(path.name)
        return False
