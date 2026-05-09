from __future__ import annotations

from typing import Dict, Optional

from PyQt6.QtCore import QObject, pyqtSignal

from .preset_file_store import PresetFileStore
from .selection_service import PresetSelectionService

from .models import PresetManifest


class PresetUiStore(QObject):
    """Lightweight store for preset mode UI notifications and metadata.

    It deliberately avoids legacy preset parsing. It keeps only manifest
    metadata and the selected source preset file name.
    """

    presets_changed = pyqtSignal()
    preset_switched = pyqtSignal(str)
    preset_identity_changed = pyqtSignal(str)
    preset_updated = pyqtSignal(str)

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
        self._reload_metadata()
        self.presets_changed.emit()

    def notify_preset_saved(self, file_name: str) -> None:
        self._invalidate_metadata_cache()
        self.preset_updated.emit(str(file_name or "").strip())

    def notify_presets_changed(self) -> None:
        self._invalidate_metadata_cache()
        self.presets_changed.emit()

    def notify_preset_switched(self, file_name: str) -> None:
        self._selected_source_file_name = str(file_name or "").strip() or None
        self.preset_switched.emit(self._selected_source_file_name or "")

    def notify_preset_identity_changed(self, file_name: str) -> None:
        selected = str(file_name or "").strip() or None
        self._invalidate_metadata_cache()
        self._selected_source_file_name = selected
        self.preset_identity_changed.emit(self._selected_source_file_name or "")

    def _ensure_loaded(self) -> None:
        if not self._loaded:
            self._reload_metadata()

    def _invalidate_metadata_cache(self) -> None:
        self._manifests_by_file_name = {}
        self._selected_source_file_name = None
        self._loaded = False

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
