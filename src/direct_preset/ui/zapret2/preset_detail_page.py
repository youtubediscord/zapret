from __future__ import annotations

from pathlib import Path

from direct_preset.ui.common.preset_subpage_base import PresetSubpageBase


class Zapret2PresetDetailPage(PresetSubpageBase):
    def _default_title(self) -> str:
        return "Пресет Zapret 2"

    def _get_preset_path(self, name: str) -> Path:
        return self._require_app_context().preset_file_store.get_source_path("winws2", str(name or "").strip())

    def _direct_launch_method(self) -> str | None:
        return "direct_zapret2"
