from __future__ import annotations

from program_settings.commands import (
    AutoDpiUpdateResult,
    ProgramSettingActionResult,
    ensure_gui_autostart_migrated,
    is_auto_dpi_enabled,
    is_user_admin,
    set_auto_dpi_enabled,
    set_defender_disabled,
    set_gui_autostart_enabled,
    set_tray_close_mode,
    set_max_block_enabled,
    set_state_media_block_enabled,
    save_ui_state_settings,
)
from program_settings.runtime import (
    attach_program_settings_runtime,
    load_program_settings_snapshot,
    peek_tray_close_mode,
    publish_program_settings_snapshot,
    remember_tray_close_mode,
    refresh_program_settings_snapshot,
)

__all__ = [
    "AutoDpiUpdateResult",
    "ProgramSettingActionResult",
    "attach_program_settings_runtime",
    "ensure_gui_autostart_migrated",
    "is_auto_dpi_enabled",
    "is_user_admin",
    "load_program_settings_snapshot",
    "peek_tray_close_mode",
    "publish_program_settings_snapshot",
    "remember_tray_close_mode",
    "refresh_program_settings_snapshot",
    "set_auto_dpi_enabled",
    "set_defender_disabled",
    "set_gui_autostart_enabled",
    "set_tray_close_mode",
    "set_max_block_enabled",
    "set_state_media_block_enabled",
    "save_ui_state_settings",
]
