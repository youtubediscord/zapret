from __future__ import annotations

from pathlib import Path

from ui.page_names import PageName
from ui.pages.preset_subpage_base import PresetSubpageBase


class Zapret1PresetDetailPage(PresetSubpageBase):
    def _default_title(self) -> str:
        return "Пресет Zapret 1"

    def _create_manager(self):
        from preset_zapret1 import PresetManagerV1

        return PresetManagerV1()

    def _get_preset_path(self, name: str) -> Path:
        from preset_zapret1 import get_preset_path_v1

        return get_preset_path_v1(name)

    def _direct_launch_method(self) -> str | None:
        return "direct_zapret1"
