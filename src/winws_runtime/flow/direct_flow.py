from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import time
from typing import Callable

from core.paths import AppPaths
from settings.schema import SETTINGS_DIR_NAME, SETTINGS_FILE_NAME

from core.presets.cache_signatures import path_cache_signature
from core.presets.models import PresetManifest
from core.presets.preset_file_store import PresetFileStore
from core.presets.selection_service import PresetSelectionService


class DirectFlowError(RuntimeError):
    """Raised when the direct-launch selected source preset flow cannot be prepared."""


@dataclass(frozen=True)
class DirectLaunchProfile:
    launch_method: str
    engine: str
    preset_file_name: str
    preset_name: str
    preset_path: Path
    display_name: str

    def to_selected_mode(self) -> dict[str, object]:
        return {
            "is_preset_file": True,
            "name": self.display_name,
            "preset_path": str(self.preset_path),
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
            preset_path=self.preset_path,
            display_name=self.display_name,
        )


class DirectFlowCoordinator:
    _METHOD_TO_ENGINE = {
        "direct_zapret1": "winws1",
        "direct_zapret2": "winws2",
    }
    _DEFAULT_PRESET_BY_ENGINE = {
        "winws1": "Default v1.txt",
        "winws2": "Default v1 (game filter).txt",
    }

    def __init__(
        self,
        app_paths: AppPaths,
        preset_selection_service: PresetSelectionService,
        preset_file_store: PresetFileStore,
    ) -> None:
        self._app_paths = app_paths
        self._preset_selection_service = preset_selection_service
        self._preset_file_store = preset_file_store
        self._selected_manifest_cache: dict[str, tuple[tuple[object, ...], PresetManifest]] = {}

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
        preset_path = self._get_source_preset_path(
            self._METHOD_TO_ENGINE[method],
            selected.file_name,
        )
        self._emit_timing(timing_callback, f"{label}.selected_source_path", t_path)
        if not preset_path.exists():
            raise DirectFlowError(f"Selected source preset not found: {preset_path}")

        has_required_filters: bool | None = None
        if require_filters:
            text = ""
            t_read = time.perf_counter()
            try:
                text = preset_path.read_text(encoding="utf-8").strip()
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
            preset_path=preset_path,
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
        engine = self._METHOD_TO_ENGINE[self._normalize_method(launch_method)]
        return self._preset_file_store.get_source_path(engine, selected.file_name)

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
        selected_file_name = self._preset_selection_service.select_preset_file_name_fast(engine, file_name)
        selected_manifest = self._preset_file_store.get_manifest(engine, selected_file_name)
        if selected_manifest is None:
            raise DirectFlowError(f"Выбранный пресет не найден: {selected_file_name}")
        selected_path = self._get_source_preset_path(engine, selected_file_name)
        display_name = str(getattr(selected_manifest, "name", "") or "").strip() or Path(selected_file_name).stem
        return DirectLaunchProfile(
            launch_method=method,
            engine=engine,
            preset_file_name=selected_file_name,
            preset_name=display_name,
            preset_path=selected_path,
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

        t_selection_service = time.perf_counter()
        selection = self._preset_selection_service
        self._emit_timing(timing_callback, f"{label}.selection_service", t_selection_service)

        preferred_file_name = self._DEFAULT_PRESET_BY_ENGINE.get(engine, "")
        t_manifest = time.perf_counter()
        manifest = selection.ensure_selected_manifest(engine, preferred_file_name=preferred_file_name)
        self._emit_timing(timing_callback, f"{label}.selected_manifest", t_manifest)
        if manifest is None:
            raise DirectFlowError(
                "Пресеты не найдены. Проверьте папку presets рядом с программой "
                "и переустановите приложение, если системные пресеты отсутствуют."
            )

        t_cache_key = time.perf_counter()
        cache_key = self._selected_manifest_cache_key(method, engine, manifest.file_name)
        self._emit_timing(timing_callback, f"{label}.cache_key", t_cache_key)
        t_cache_lookup = time.perf_counter()
        cached_manifest = self._selected_manifest_from_cache(method, cache_key)
        self._emit_timing(timing_callback, f"{label}.cache_lookup", t_cache_lookup)
        if cached_manifest is not None:
            self._emit_timing(timing_callback, f"{label}.total", started_at)
            return cached_manifest

        if cache_key is not None:
            self._selected_manifest_cache[method] = (cache_key, manifest)
        self._emit_timing(timing_callback, f"{label}.total", started_at)
        return manifest

    @staticmethod
    def _has_required_filters(launch_method: str, text: str) -> bool:
        content = str(text or "")
        if launch_method == "direct_zapret1":
            return any(flag in content for flag in ("--wf-tcp=", "--wf-udp="))
        return any(flag in content for flag in ("--wf-tcp-out", "--wf-udp-out", "--wf-raw-part"))

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

        try:
            preset_path = self._preset_file_store.get_source_path(engine, candidate)
        except Exception:
            return None

        settings_path = self._app_paths.user_root / SETTINGS_DIR_NAME / SETTINGS_FILE_NAME

        return (
            self._normalize_method(launch_method),
            engine,
            candidate.lower(),
            *path_cache_signature(settings_path),
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

    def _get_source_preset_path(self, engine: str, file_name: str) -> Path:
        return self._preset_file_store.get_source_path(engine, file_name)
