from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True, slots=True)
class AutostartFeature:
    get_current_launch_method: Callable
    save_gui_autostart_enabled: Callable
    disable_gui_autostart: Callable
    enable_gui_autostart: Callable
    set_autostart_enabled: Callable


def build_autostart_feature(*, runtime_state=None) -> AutostartFeature:
    from autostart import public as autostart_public

    def _set_autostart_enabled(enabled: bool) -> bool:
        saved = bool(autostart_public.save_gui_autostart_enabled(bool(enabled)))
        if runtime_state is not None:
            runtime_state.set_autostart(bool(enabled))
        return saved

    return AutostartFeature(
        get_current_launch_method=autostart_public.get_current_launch_method,
        save_gui_autostart_enabled=autostart_public.save_gui_autostart_enabled,
        disable_gui_autostart=autostart_public.disable_gui_autostart,
        enable_gui_autostart=autostart_public.enable_gui_autostart,
        set_autostart_enabled=_set_autostart_enabled,
    )
