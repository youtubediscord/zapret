from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True, slots=True)
class AutostartFeature:
    get_current_launch_method: Callable
    save_gui_autostart_enabled: Callable
    disable_gui_autostart: Callable
    enable_gui_autostart: Callable
    set_autostart_runtime_state: Callable
    create_autostart_action_worker: Callable
    create_autostart_mode_load_worker: Callable


def build_autostart_feature(*, runtime_state=None) -> AutostartFeature:
    def _public():
        from autostart import public as autostart_public

        return autostart_public

    def _set_autostart_runtime_state(enabled: bool) -> bool:
        if runtime_state is not None:
            runtime_state.set_autostart(bool(enabled))
        return bool(enabled)

    def _create_autostart_action_worker(request_id: int, *, action: str, enabled=None, strategy_name=None, parent=None):
        from autostart.workers import AutostartActionWorker

        return AutostartActionWorker(
            request_id,
            action=action,
            enable_gui_autostart=feature.enable_gui_autostart,
            disable_gui_autostart=feature.disable_gui_autostart,
            save_gui_autostart_enabled=feature.save_gui_autostart_enabled,
            enabled=enabled,
            strategy_name=strategy_name,
            parent=parent,
        )

    def _create_autostart_mode_load_worker(request_id: int, *, parent=None):
        from autostart.workers import AutostartModeLoadWorker

        return AutostartModeLoadWorker(
            request_id,
            get_current_launch_method=feature.get_current_launch_method,
            parent=parent,
        )

    feature = AutostartFeature(
        get_current_launch_method=lambda *args, **kwargs: _public().get_current_launch_method(*args, **kwargs),
        save_gui_autostart_enabled=lambda *args, **kwargs: _public().save_gui_autostart_enabled(*args, **kwargs),
        disable_gui_autostart=lambda *args, **kwargs: _public().disable_gui_autostart(*args, **kwargs),
        enable_gui_autostart=lambda *args, **kwargs: _public().enable_gui_autostart(*args, **kwargs),
        set_autostart_runtime_state=_set_autostart_runtime_state,
        create_autostart_action_worker=_create_autostart_action_worker,
        create_autostart_mode_load_worker=_create_autostart_mode_load_worker,
    )
    return feature
