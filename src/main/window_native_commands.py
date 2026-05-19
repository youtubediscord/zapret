from __future__ import annotations

import sys
from ctypes import wintypes

from log.log import log


WM_SYSCOMMAND = 0x0112
SC_MINIMIZE = 0xF020
_SC_COMMAND_MASK = 0xFFF0


def handle_native_minimize_command(window, message) -> bool:
    """Перехватывает команду Windows «свернуть» до обычного сворачивания."""
    if sys.platform != "win32":
        return False

    msg = _read_msg(message)
    if msg is None:
        return False
    if int(msg.message) != WM_SYSCOMMAND:
        return False
    if (int(msg.wParam) & _SC_COMMAND_MASK) != SC_MINIMIZE:
        return False

    return handle_minimize_request(window)


def handle_minimize_request(window) -> bool:
    """Общий обработчик команды «свернуть окно»."""
    try:
        from settings.store import get_hide_to_tray_on_minimize_close

        if not get_hide_to_tray_on_minimize_close():
            return False
        return bool(window.close_to_tray())
    except Exception as exc:
        log(f"Не удалось обработать команду сворачивания в трей: {exc}", "DEBUG")
        return False


def _read_msg(message):
    try:
        address = int(message)
    except Exception:
        return None
    if address <= 0:
        return None

    try:
        return wintypes.MSG.from_address(address)
    except Exception:
        return None


__all__ = [
    "SC_MINIMIZE",
    "WM_SYSCOMMAND",
    "handle_minimize_request",
    "handle_native_minimize_command",
]
