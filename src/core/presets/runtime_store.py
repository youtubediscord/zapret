from __future__ import annotations

import sys
from typing import Dict, Optional

from PyQt6.QtCore import QObject, pyqtSignal

from .models import PresetManifest


def _get_installed_app_context():
    try:
        core_services = sys.modules.get("core.services")
        if core_services is None:
            import core.services as core_services

        getter = getattr(core_services, "get_installed_app_context", None)
        if callable(getter):
            return getter()
    except Exception:
        pass
    return None


def _get_preset_repository():
    app_context = _get_installed_app_context()
    repository = getattr(app_context, "preset_repository", None)
    if repository is not None:
        return repository

    core_services = sys.modules.get("core.services")
    if core_services is None:
        import core.services as core_services

    return core_services.get_preset_repository()


def _get_selection_service():
    app_context = _get_installed_app_context()
    service = getattr(app_context, "preset_selection_service", None)
    if service is not None:
        return service

    core_services = sys.modules.get("core.services")
    if core_services is None:
        import core.services as core_services

    return core_services.get_selection_service()


class DirectRuntimePresetStore(QObject):
    """Lightweight store for direct preset runtime notifications and metadata.

    This store deliberately avoids legacy preset parsing. It keeps only
    manifest metadata and the selected source preset file name.
    """

    presets_changed = pyqtSignal()
    preset_switched = pyqtSignal(str)
    preset_updated = pyqtSignal(str)

    def __init__(self, engine: str, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._engine = str(engine or "").strip()
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

    def notify_preset_switched(self, file_name: str) -> None:
        self._selected_source_file_name = str(file_name or "").strip() or None
        self.preset_switched.emit(self._selected_source_file_name or "")

    def _ensure_loaded(self) -> None:
        if not self._loaded:
            self._reload_metadata()

    def _invalidate_metadata_cache(self) -> None:
        self._manifests_by_file_name = {}
        self._selected_source_file_name = None
        self._loaded = False

    def _reload_metadata(self) -> None:
        manifests_by_file_name: Dict[str, PresetManifest] = {}
        for manifest in _get_preset_repository().list_manifests(self._engine):
            file_name = str(getattr(manifest, "file_name", "") or "").strip()
            if file_name:
                manifests_by_file_name[file_name] = manifest

        self._manifests_by_file_name = manifests_by_file_name
        try:
            self._selected_source_file_name = _get_selection_service().get_selected_file_name(self._engine)
        except Exception:
            self._selected_source_file_name = None
        self._loaded = True
