from __future__ import annotations

import json
from pathlib import Path

from core.paths import AppPaths

from .models import PresetDocument
from .repository import PresetRepository


class PresetSelectionService:
    def __init__(self, paths: AppPaths, repository: PresetRepository):
        self._paths = paths
        self._repository = repository

    def get_selected_preset_id(self, engine: str) -> str | None:
        path = self._selection_path(engine)
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None
        value = str(payload.get("selected_preset_id") or "").strip()
        return value or None

    def get_selected_preset(self, engine: str) -> PresetDocument | None:
        preset_id = self.get_selected_preset_id(engine)
        if not preset_id:
            return None
        return self._repository.get_preset(engine, preset_id)

    def select_preset(self, engine: str, preset_id: str) -> PresetDocument:
        preset = self._repository.get_preset(engine, preset_id)
        if preset is None:
            raise ValueError(f"Preset not found: {preset_id}")
        path = self._selection_path(engine)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({"selected_preset_id": preset.manifest.id}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return preset

    def clear_selection(self, engine: str) -> None:
        try:
            self._selection_path(engine).unlink()
        except FileNotFoundError:
            pass

    def ensure_can_delete(self, engine: str, preset_id: str) -> None:
        selected_id = self.get_selected_preset_id(engine)
        if selected_id and selected_id == preset_id:
            raise ValueError("Cannot delete the selected preset")

    def ensure_selected_preset(self, engine: str, preferred_name: str = "Default") -> PresetDocument | None:
        current = self.get_selected_preset(engine)
        if current is not None:
            return current

        preferred = self._repository.find_preset_by_name(engine, preferred_name)
        if preferred is not None:
            return self.select_preset(engine, preferred.manifest.id)

        presets = self._repository.list_presets(engine)
        if not presets:
            return None
        return self.select_preset(engine, presets[0].manifest.id)

    def select_preset_by_name(self, engine: str, name: str) -> PresetDocument:
        preset = self._repository.find_preset_by_name(engine, name)
        if preset is None:
            raise ValueError(f"Preset not found: {name}")
        return self.select_preset(engine, preset.manifest.id)

    def _selection_path(self, engine: str) -> Path:
        return self._paths.engine_paths(engine).ensure_directories().selected_state_path
