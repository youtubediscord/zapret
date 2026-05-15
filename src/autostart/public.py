from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True, slots=True)
class GuiAutostartResult:
    success: bool
    removed_count: int = 0
    restart_requested: bool = False


def get_current_launch_method() -> str:
    from settings.dpi.public import get_launch_method

    return str(get_launch_method() or "").strip()


def save_gui_autostart_enabled(enabled: bool) -> bool:
    from settings.store import set_gui_autostart_enabled

    return bool(set_gui_autostart_enabled(bool(enabled)))


def disable_gui_autostart() -> GuiAutostartResult:
    from autostart.autostart_remove import clear_autostart_task

    removed_count = int(clear_autostart_task() or 0)
    return GuiAutostartResult(success=True, removed_count=removed_count)


def enable_gui_autostart(*, status_cb: Callable[[str], None] | None = None) -> GuiAutostartResult:
    from autostart.autostart_exe import request_admin_for_autostart, setup_autostart_for_exe
    from startup.admin_check import is_admin

    if not is_admin():
        restart_requested = bool(request_admin_for_autostart())
        return GuiAutostartResult(success=False, restart_requested=restart_requested)

    ok = bool(setup_autostart_for_exe(status_cb=status_cb))
    return GuiAutostartResult(success=ok)


__all__ = [
    "GuiAutostartResult",
    "disable_gui_autostart",
    "enable_gui_autostart",
    "get_current_launch_method",
    "save_gui_autostart_enabled",
]
