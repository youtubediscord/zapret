from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import program_settings.public as program_settings_commands


@dataclass(frozen=True, slots=True)
class ProgramSettingsFeature:
    runtime_service: Any

    def is_user_admin(self) -> bool:
        return bool(program_settings_commands.is_user_admin())

    def refresh_program_settings_snapshot(self):
        return program_settings_commands.refresh_program_settings_snapshot(self.runtime_service)

    def attach_program_settings_runtime(self, owner, *, apply_snapshot_fn) -> None:
        return program_settings_commands.attach_program_settings_runtime(
            owner,
            runtime_service=self.runtime_service,
            apply_snapshot_fn=apply_snapshot_fn,
        )

    def set_auto_dpi_enabled(self, enabled: bool):
        return program_settings_commands.set_auto_dpi_enabled(enabled)

    def set_defender_disabled(self, disable: bool, *, status_callback=None):
        return program_settings_commands.set_defender_disabled(disable, status_callback=status_callback)

    def set_max_block_enabled(self, enable: bool, *, status_callback=None):
        return program_settings_commands.set_max_block_enabled(enable, status_callback=status_callback)


def build_program_settings_feature() -> ProgramSettingsFeature:
    from core.runtime.program_settings_runtime_service import ProgramSettingsRuntimeService

    return ProgramSettingsFeature(
        runtime_service=ProgramSettingsRuntimeService(),
    )
