from __future__ import annotations

from pathlib import Path

from presets.ui.common.preset_subpage_base import PresetSubpageBase
from settings.mode import ENGINE_WINWS1, ZAPRET1_MODE


class Zapret1PresetRawEditorPage(PresetSubpageBase):
    def _default_title(self) -> str:
        return "Пресет Zapret 1"

    def _get_preset_path(self, name: str) -> Path:
        return self._require_app_context().preset_file_store.get_source_path(ENGINE_WINWS1, str(name or "").strip())

    def _preset_launch_method(self) -> str | None:
        return ZAPRET1_MODE
