from __future__ import annotations

from pathlib import Path

from presets.public import get_preset_source_path_by_file_name
from presets.ui.common.preset_subpage_base import PresetSubpageBase
from settings.mode import ZAPRET1_MODE


class Zapret1PresetRawEditorPage(PresetSubpageBase):
    def _default_title(self) -> str:
        return "Пресет Zapret 1"

    def _get_preset_path(self, name: str) -> Path:
        return get_preset_source_path_by_file_name(
            ZAPRET1_MODE,
            str(name or "").strip(),
            app_context=self._require_app_context(),
        )

    def _preset_launch_method(self) -> str | None:
        return ZAPRET1_MODE
