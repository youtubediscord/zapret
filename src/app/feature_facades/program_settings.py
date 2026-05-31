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

    def load_program_settings_snapshot(self):
        return self._commands().load_program_settings_snapshot(self.runtime_service)

    def publish_program_settings_snapshot(self, snapshot) -> bool:
        return bool(self._commands().publish_program_settings_snapshot(self.runtime_service, snapshot))

    def hide_to_tray_on_minimize_close_enabled(self) -> bool:
        return bool(
            self._commands().peek_hide_to_tray_on_minimize_close(
                self.runtime_service,
                default=False,
            )
        )

    def remember_hide_to_tray_on_minimize_close(self, enabled: bool) -> bool:
        return bool(
            self._commands().remember_hide_to_tray_on_minimize_close(
                self.runtime_service,
                bool(enabled),
            )
        )

    def attach_program_settings_runtime(self, owner, *, apply_snapshot_fn) -> None:
        return self._commands().attach_program_settings_runtime(
            owner,
            runtime_service=self.runtime_service,
            apply_snapshot_fn=apply_snapshot_fn,
        )

    def save_ui_state_settings(self, values: dict) -> dict:
        return self._commands().save_ui_state_settings(dict(values or {}))

    def create_sidebar_expanded_save_worker(self, *, expanded: bool, state_key: str, parent=None):
        from program_settings.workers import SidebarExpandedStateSaveWorker

        return SidebarExpandedStateSaveWorker(
            expanded=bool(expanded),
            state_key=state_key,
            save_ui_state_settings=self.save_ui_state_settings,
            parent=parent,
        )

    def _program_settings_save_action(self, action: str):
        normalized_action = str(action or "").strip()
        commands = self._commands()

        def save_hide_to_tray(enabled: bool, *, status_callback=None):
            return bool(commands.set_hide_to_tray_on_minimize_close(enabled))

        actions = {
            "auto_dpi": commands.set_auto_dpi_enabled,
            "hide_to_tray": save_hide_to_tray,
            "defender_disabled": commands.set_defender_disabled,
            "max_block": commands.set_max_block_enabled,
        }
        save_action = actions.get(normalized_action)
        if save_action is not None:
            return save_action

        def unknown_action(enabled: bool, *, status_callback=None):
            raise ValueError(f"Неизвестная настройка программы: {normalized_action}")

        return unknown_action

    def create_program_settings_save_worker(self, request_id: int, *, action: str, enabled: bool, parent=None):
        from program_settings.workers import ProgramSettingsSaveWorker

        return ProgramSettingsSaveWorker(
            request_id,
            action=action,
            enabled=bool(enabled),
            save_action=self._program_settings_save_action(action),
            parent=parent,
        )

    def create_program_settings_load_worker(self, request_id: int, *, parent=None):
        from program_settings.workers import ProgramSettingsLoadWorker

        return ProgramSettingsLoadWorker(
            request_id,
            load_program_settings_snapshot=self.load_program_settings_snapshot,
            parent=parent,
        )

    def create_program_settings_admin_check_worker(self, request_id: int, *, parent=None):
        from program_settings.workers import ProgramSettingsAdminCheckWorker

        return ProgramSettingsAdminCheckWorker(
            request_id,
            is_user_admin=self.is_user_admin,
            parent=parent,
        )


def build_program_settings_feature() -> ProgramSettingsFeature:
    return ProgramSettingsFeature()
