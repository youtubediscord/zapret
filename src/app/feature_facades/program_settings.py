from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True, init=False)
class ProgramSettingsFeature:
    _runtime_service: Any | None = field(default=None, repr=False, compare=False)

    def __init__(self, runtime_service: Any | None = None) -> None:
        object.__setattr__(self, "_runtime_service", runtime_service)

    @staticmethod
    def _commands():
        import program_settings.public as program_settings_commands

        return program_settings_commands

    @staticmethod
    def _create_runtime_service():
        from core.runtime.program_settings_runtime_service import ProgramSettingsRuntimeService

        return ProgramSettingsRuntimeService()

    @property
    def runtime_service(self):
        runtime_service = self._runtime_service
        if runtime_service is None:
            runtime_service = self._create_runtime_service()
            object.__setattr__(self, "_runtime_service", runtime_service)
        return runtime_service

    def is_user_admin(self) -> bool:
        return bool(self._commands().is_user_admin())

    def refresh_program_settings_snapshot(self):
        return self._commands().refresh_program_settings_snapshot(self.runtime_service)

    def attach_program_settings_runtime(self, owner, *, apply_snapshot_fn) -> None:
        return self._commands().attach_program_settings_runtime(
            owner,
            runtime_service=self.runtime_service,
            apply_snapshot_fn=apply_snapshot_fn,
        )

    def set_auto_dpi_enabled(self, enabled: bool):
        return self._commands().set_auto_dpi_enabled(enabled)

    def set_hide_to_tray_on_minimize_close(self, enabled: bool) -> bool:
        return bool(self._commands().set_hide_to_tray_on_minimize_close(enabled))

    def set_defender_disabled(self, disable: bool, *, status_callback=None):
        return self._commands().set_defender_disabled(disable, status_callback=status_callback)

    def set_max_block_enabled(self, enable: bool, *, status_callback=None):
        return self._commands().set_max_block_enabled(enable, status_callback=status_callback)


def build_program_settings_feature() -> ProgramSettingsFeature:
    return ProgramSettingsFeature()
