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


def build_dpi_settings_feature() -> DpiSettingsFeature:
    from settings.dpi import public as dpi_public

    return DpiSettingsFeature(
        load_initial_state=dpi_public.load_initial_state,
        apply_launch_method=dpi_public.apply_launch_method,
        get_launch_method=dpi_public.get_launch_method,
        describe_visibility=dpi_public.describe_visibility,
        load_orchestra_settings=dpi_public.load_orchestra_settings,
    )
