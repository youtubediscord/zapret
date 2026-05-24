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
    def _public():
        from autostart import public as autostart_public

        return autostart_public

    def _set_autostart_enabled(enabled: bool) -> bool:
        saved = bool(_public().save_gui_autostart_enabled(bool(enabled)))
        if runtime_state is not None:
            runtime_state.set_autostart(bool(enabled))
        return saved

    return AutostartFeature(
        get_current_launch_method=lambda *args, **kwargs: _public().get_current_launch_method(*args, **kwargs),
        save_gui_autostart_enabled=lambda *args, **kwargs: _public().save_gui_autostart_enabled(*args, **kwargs),
        disable_gui_autostart=lambda *args, **kwargs: _public().disable_gui_autostart(*args, **kwargs),
        enable_gui_autostart=lambda *args, **kwargs: _public().enable_gui_autostart(*args, **kwargs),
        set_autostart_enabled=_set_autostart_enabled,
    )
