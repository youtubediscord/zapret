from __future__ import annotations

from pathlib import Path

from presets.public import get_preset_source_path_by_file_name
from presets.ui.common.preset_subpage_base import PresetSubpageBase
from settings.mode import ZAPRET2_MODE


class Zapret2PresetRawEditorPage(PresetSubpageBase):
    def _default_title(self) -> str:
        return "Пресет Zapret 2"

    def _get_preset_path(self, name: str) -> Path:
        return get_preset_source_path_by_file_name(
            ZAPRET2_MODE,
            str(name or "").strip(),
            app_context=self._require_app_context(),
        )

    def _preset_launch_method(self) -> str | None:
        return ZAPRET2_MODE
