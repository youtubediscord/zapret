from __future__ import annotations

from .models import PresetManifest
from .preset_file_store import PresetFileStore


class PresetSelectionService:
    def __init__(self, preset_file_store: PresetFileStore):
        self._preset_file_store = preset_file_store

    def get_selected_file_name(self, engine: str) -> str | None:
        from settings.store import get_selected_source_preset_file_name, set_selected_source_preset_file_name

        raw_value = str(get_selected_source_preset_file_name(engine) or "").strip()
        if not raw_value:
            return None

        resolved = str(self._preset_file_store.resolve_file_name(engine, raw_value) or "").strip()
        if resolved and resolved != raw_value:
            try:
                set_selected_source_preset_file_name(engine, resolved)
            except Exception:
                pass
        return resolved or raw_value or None

    def get_selected_manifest(self, engine: str) -> PresetManifest | None:
        file_name = self.get_selected_file_name(engine)
        if not file_name:
            return None
        return self._preset_file_store.get_manifest(engine, file_name)

    def select_preset(self, engine: str, file_name: str) -> PresetManifest:
        from settings.store import set_selected_source_preset_file_name

        preset = self._preset_file_store.get_manifest(engine, file_name)
        if preset is None:
            raise ValueError(f"Preset not found: {file_name}")
        set_selected_source_preset_file_name(engine, preset.file_name)
        return preset

    def select_preset_file_name_fast(self, engine: str, file_name: str) -> str:
        """Direct selection path that does not depend on preset index.json."""
        from settings.store import set_selected_source_preset_file_name

        candidate = str(self._preset_file_store.resolve_file_name(engine, file_name) or "").strip()
        if not candidate:
            raise ValueError("Preset file name is required")

        try:
            preset_path = self._preset_file_store.get_source_path(engine, candidate)
        except Exception:
            preset_path = None
        if preset_path is None or not preset_path.exists():
            raise ValueError(f"Preset not found: {file_name}")

        set_selected_source_preset_file_name(engine, candidate)
        return candidate

    def clear_selection(self, engine: str) -> None:
        from settings.store import clear_selected_source_preset_file_name

        clear_selected_source_preset_file_name(engine)

    def ensure_can_delete(self, engine: str, file_name: str) -> None:
        selected_file_name = self.get_selected_file_name(engine)
        candidate = str(self._preset_file_store.resolve_file_name(engine, file_name) or file_name or "").strip()
        if selected_file_name and selected_file_name.strip().lower() == candidate.lower():
            raise ValueError("Cannot delete the selected source preset")

    def ensure_selected_manifest(self, engine: str, preferred_file_name: str | None = None) -> PresetManifest | None:
        current = self.get_selected_manifest(engine)
        if current is not None:
            return current

        preferred_key = str(preferred_file_name or "").strip()
        if preferred_key:
            preferred = self._preset_file_store.get_manifest(engine, preferred_key)
            if preferred is not None:
                return self.select_preset(engine, preferred.file_name)

        manifests = self._preset_file_store.list_manifests(engine)
        if not manifests:
            return None
        return self.select_preset(engine, manifests[0].file_name)
