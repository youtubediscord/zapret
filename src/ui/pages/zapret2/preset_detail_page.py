from __future__ import annotations

from pathlib import Path

from ui.page_names import PageName
from ui.pages.preset_subpage_base import PresetSubpageBase


class Zapret2PresetDetailPage(PresetSubpageBase):
    def _default_title(self) -> str:
        try:
            from strategy_menu import get_strategy_launch_method

            if (get_strategy_launch_method() or "").strip().lower() == "direct_zapret2_orchestra":
                return "Пресет Оркестра Zapret 2"
        except Exception:
            pass
        return "Пресет Zapret 2"

    def _create_manager(self):
        try:
            from strategy_menu import get_strategy_launch_method

            if (get_strategy_launch_method() or "").strip().lower() == "direct_zapret2_orchestra":
                from preset_orchestra_zapret2 import PresetManager
                return PresetManager()
        except Exception:
            pass

        from core.presets.direct_facade import DirectPresetFacade

        return DirectPresetFacade.from_launch_method("direct_zapret2")

    def _get_preset_path(self, name: str) -> Path:
        try:
            from strategy_menu import get_strategy_launch_method

            if (get_strategy_launch_method() or "").strip().lower() == "direct_zapret2_orchestra":
                from preset_orchestra_zapret2 import get_preset_path
                return get_preset_path(name)
        except Exception:
            pass

        from preset_zapret2 import get_preset_path
        return get_preset_path(name)

    def _direct_launch_method(self) -> str | None:
        try:
            from strategy_menu import get_strategy_launch_method

            if (get_strategy_launch_method() or "").strip().lower() == "direct_zapret2_orchestra":
                return None
        except Exception:
            pass
        return "direct_zapret2"

    def _preset_hierarchy_scope_key(self) -> str | None:
        try:
            from strategy_menu import get_strategy_launch_method

            if (get_strategy_launch_method() or "").strip().lower() == "direct_zapret2_orchestra":
                return "preset_orchestra_zapret2"
        except Exception:
            pass
        return "preset_zapret2"
