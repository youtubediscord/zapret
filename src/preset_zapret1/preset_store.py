# preset_zapret1/preset_store.py
"""Central in-memory preset store for Zapret 1 (singleton)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, List, Optional

from PyQt6.QtCore import QObject, pyqtSignal

from log import log


class PresetStoreV1(QObject):
    """Central in-memory preset store for Zapret 1 presets."""

    presets_changed = pyqtSignal()
    preset_switched = pyqtSignal(str)
    preset_updated = pyqtSignal(str)

    _instance: Optional[PresetStoreV1] = None

    @classmethod
    def instance(cls) -> PresetStoreV1:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._presets: Dict[str, "PresetV1"] = {}
        self._preset_mtimes: Dict[str, float] = {}
        self._loaded = False
        self._active_name: Optional[str] = None

    def get_all_presets(self) -> Dict[str, "PresetV1"]:
        self._ensure_loaded()
        return dict(self._presets)

    def get_preset(self, name: str) -> Optional["PresetV1"]:
        self._ensure_loaded()
        return self._presets.get(name)

    def get_preset_names(self) -> List[str]:
        self._ensure_loaded()
        return sorted(self._presets.keys(), key=lambda s: s.lower())

    def get_active_preset_name(self) -> Optional[str]:
        self._ensure_loaded()
        return self._active_name

    def preset_exists(self, name: str) -> bool:
        self._ensure_loaded()
        return name in self._presets

    def refresh(self) -> None:
        self._do_full_load()
        self.presets_changed.emit()

    def notify_preset_saved(self, name: str) -> None:
        self._ensure_loaded()
        self._reload_single_preset(name)
        self.preset_updated.emit(name)

    def notify_presets_changed(self) -> None:
        self._do_full_load()
        self.presets_changed.emit()

    def notify_preset_switched(self, name: str) -> None:
        self._active_name = name
        self.preset_switched.emit(name)

    def notify_active_name_changed(self) -> None:
        try:
            from core.services import get_direct_flow_coordinator

            self._active_name = get_direct_flow_coordinator().get_selected_preset_name("direct_zapret1")
        except Exception:
            self._active_name = None

    def _ensure_loaded(self) -> None:
        if not self._loaded:
            self._do_full_load()

    def _do_full_load(self) -> None:
        from .preset_storage import list_presets_v1, load_preset_v1, get_preset_path_v1
        self._presets.clear()
        self._preset_mtimes.clear()
        names = list_presets_v1()
        for name in names:
            try:
                preset = load_preset_v1(name)
                if preset is not None:
                    self._presets[name] = preset
                    try:
                        path = get_preset_path_v1(name)
                        if path.exists():
                            self._preset_mtimes[name] = os.path.getmtime(str(path))
                    except Exception:
                        pass
            except Exception as e:
                log(f"PresetStoreV1: error loading preset '{name}': {e}", "DEBUG")
        try:
            from core.services import get_direct_flow_coordinator

            self._active_name = get_direct_flow_coordinator().get_selected_preset_name("direct_zapret1")
        except Exception:
            self._active_name = None
        self._loaded = True
        log(f"PresetStoreV1: loaded {len(self._presets)} presets", "DEBUG")

    def _reload_single_preset(self, name: str) -> None:
        from .preset_storage import load_preset_v1, get_preset_path_v1
        try:
            preset = load_preset_v1(name)
            if preset is not None:
                self._presets[name] = preset
                try:
                    path = get_preset_path_v1(name)
                    if path.exists():
                        self._preset_mtimes[name] = os.path.getmtime(str(path))
                except Exception:
                    pass
            else:
                self._presets.pop(name, None)
                self._preset_mtimes.pop(name, None)
        except Exception as e:
            log(f"PresetStoreV1: error reloading preset '{name}': {e}", "DEBUG")


def get_preset_store_v1() -> PresetStoreV1:
    """Returns the global PresetStoreV1 singleton."""
    return PresetStoreV1.instance()
