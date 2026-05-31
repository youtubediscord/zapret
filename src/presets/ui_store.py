from __future__ import annotations

import os
from typing import Dict, Optional

from PyQt6.QtCore import QObject, pyqtSignal

from .file_store import PresetFileStore
from .selection_service import PresetSelectionService

from .models import PresetManifest


class PresetUiStore(QObject):
    """Lightweight store for preset mode UI notifications and metadata.

    It keeps only manifest metadata and the selected source preset file name.
    Preset content is parsed by the profile layer.
    """

    presets_changed = pyqtSignal()
    preset_switched = pyqtSignal(str)
    preset_identity_changed = pyqtSignal(str)
    preset_content_changed = pyqtSignal(str)

    def __init__(
        self,
        engine: str,
        preset_file_store: PresetFileStore,
        selection_service: PresetSelectionService,
        parent: Optional[QObject] = None,
    ):
        super().__init__(parent)
        self._engine = str(engine or "").strip()
        self._preset_file_store = preset_file_store
        self._selection_service = selection_service
        self._manifests_by_file_name: Dict[str, PresetManifest] = {}
        self._selected_source_file_name: Optional[str] = None
        self._loaded = False
        self._last_content_change_key: tuple[object, ...] | None = None
        self._last_identity_change_key: tuple[object, ...] | None = None

    def list_manifests(self) -> list[PresetManifest]:
        self._ensure_loaded()
        return sorted(self._manifests_by_file_name.values(), key=lambda item: item.file_name.lower())

    def get_preset_file_names(self) -> list[str]:
        self._ensure_loaded()
        return sorted(self._manifests_by_file_name.keys(), key=lambda value: value.lower())

    def get_display_name(self, file_name: str) -> str:
        self._ensure_loaded()
        manifest = self._manifests_by_file_name.get(str(file_name or "").strip())
        if manifest is None:
            return str(file_name or "").strip()
        return str(manifest.name or manifest.file_name).strip()

    def get_selected_source_preset_file_name(self) -> Optional[str]:
        self._ensure_loaded()
        return self._selected_source_file_name

    def refresh(self) -> None:
        was_loaded = bool(self._loaded)
        previous_key = self._metadata_cache_key()
        self._last_content_change_key = None
        self._last_identity_change_key = None
        self._reload_metadata()
        if was_loaded and previous_key == self._metadata_cache_key():
            return
        self.presets_changed.emit()

    def notify_preset_content_changed(self, file_name: str) -> None:
        change_key = self._content_change_key(file_name)
        if change_key is not None and change_key == self._last_content_change_key:
            return
        self._last_content_change_key = change_key
        self._invalidate_metadata_cache()
        self.preset_content_changed.emit(str(file_name or "").strip())

    def notify_presets_changed(self) -> None:
        was_loaded = bool(self._loaded)
        previous_key = self._metadata_cache_key()
        self._last_content_change_key = None
        self._last_identity_change_key = None
        if was_loaded:
            self._reload_metadata()
            if previous_key == self._metadata_cache_key():
                return
        else:
            self._invalidate_metadata_cache()
        self.presets_changed.emit()

    def notify_preset_switched(self, file_name: str) -> None:
        selected = str(file_name or "").strip() or None
        current = str(self._selected_source_file_name or "").strip() or None
        if current and selected and current.casefold() == selected.casefold():
            return
        self._selected_source_file_name = selected
        self.preset_switched.emit(self._selected_source_file_name or "")

    def notify_preset_identity_changed(self, file_name: str) -> None:
        selected = str(file_name or "").strip() or None
        change_key = self._content_change_key(selected or "")
        if change_key is not None and change_key == self._last_identity_change_key:
            return
        self._last_identity_change_key = change_key
        self._last_content_change_key = None
        self._invalidate_metadata_cache()
        self._selected_source_file_name = selected
        self.preset_identity_changed.emit(self._selected_source_file_name or "")

    def _content_change_key(self, file_name: str) -> tuple[object, ...] | None:
        candidate = str(file_name or "").strip()
        if not candidate:
            return None
        normalized_name = candidate.lower()
        try:
            path = self._preset_file_store.get_source_path(self._engine, candidate)
            stat = path.stat()
            return (
                normalized_name,
                os.path.abspath(str(path)).replace("\\", "/").lower(),
                int(getattr(stat, "st_size", 0) or 0),
                int(getattr(stat, "st_mtime_ns", 0) or 0),
            )
        except Exception:
            return ("missing", normalized_name)

    def _ensure_loaded(self) -> None:
        if not self._loaded:
            self._reload_metadata()

    def _invalidate_metadata_cache(self) -> None:
        self._manifests_by_file_name = {}
        self._selected_source_file_name = None
        self._loaded = False

    def _metadata_cache_key(self) -> tuple[object, ...]:
        manifests_key = tuple(
            sorted(
                (
                    str(getattr(manifest, "file_name", "") or "").casefold(),
                    str(getattr(manifest, "name", "") or ""),
                    str(getattr(manifest, "updated_at", "") or ""),
                    str(getattr(manifest, "kind", "") or ""),
                    str(getattr(manifest, "storage_scope", "") or ""),
                )
                for manifest in self._manifests_by_file_name.values()
            )
        )
        return (manifests_key, str(self._selected_source_file_name or "").casefold())

    def _reload_metadata(self) -> None:
        manifests_by_file_name: Dict[str, PresetManifest] = {}
        for manifest in self._preset_file_store.list_manifests(self._engine):
            file_name = str(getattr(manifest, "file_name", "") or "").strip()
            if file_name:
                manifests_by_file_name[file_name] = manifest

        self._manifests_by_file_name = manifests_by_file_name
        try:
            self._selected_source_file_name = self._selection_service.get_selected_file_name(self._engine)
        except Exception:
            self._selected_source_file_name = None
        self._loaded = True
