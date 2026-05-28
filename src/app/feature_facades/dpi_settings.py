from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True, slots=True)
class DpiSettingsFeature:
    load_initial_state: Callable
    apply_launch_method: Callable
    get_launch_method: Callable
    describe_visibility: Callable
    load_orchestra_settings: Callable
    create_dpi_settings_worker: Callable


def build_dpi_settings_feature() -> DpiSettingsFeature:
    def _public():
        from settings.dpi import public as dpi_public

        return dpi_public

    return DpiSettingsFeature(
        load_initial_state=lambda *args, **kwargs: _public().load_initial_state(*args, **kwargs),
        apply_launch_method=lambda *args, **kwargs: _public().apply_launch_method(*args, **kwargs),
        get_launch_method=lambda *args, **kwargs: _public().get_launch_method(*args, **kwargs),
        describe_visibility=lambda *args, **kwargs: _public().describe_visibility(*args, **kwargs),
        load_orchestra_settings=lambda *args, **kwargs: _public().load_orchestra_settings(*args, **kwargs),
        create_dpi_settings_worker=lambda *args, **kwargs: _create_dpi_settings_worker(*args, **kwargs),
    )


def _create_dpi_settings_worker(request_id: int, *, action: str, method: str = "", parent=None):
    from settings.dpi.workers import DpiSettingsWorker

    return DpiSettingsWorker(
        request_id,
        action=action,
        method=method,
        parent=parent,
    )
