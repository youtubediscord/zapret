"""Автозапуск ZapretGUI через задачу `--tray` и служебные Windows helpers."""

from .autostart_exe import setup_autostart_for_exe
from .registry_check import is_autostart_enabled, verify_autostart_status

__all__ = [
    "setup_autostart_for_exe",
    "is_autostart_enabled",
    "verify_autostart_status",
]
