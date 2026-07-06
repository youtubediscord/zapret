"""Замер разрыва между созданием процесса (двойной клик) и входом в Python.

Модуль должен импортироваться первой строкой main.py: момент импорта
фиксируется как «Python вошёл». Время создания процесса берётся у ОС через
kernel32.GetProcessTimes, поэтому в разрыв попадает всё, что происходит до
Python: PyInstaller bootloader, загрузка DLL, сканирование антивирусом.

Здесь нельзя импортировать ничего тяжелее ctypes/time — иначе замер
сдвинется и потеряет смысл.
"""

from __future__ import annotations

import sys
import time

_PYTHON_ENTERED_WALL = time.time()

# Секунды между эпохой FILETIME (1601-01-01) и Unix-эпохой (1970-01-01).
_FILETIME_EPOCH_OFFSET_SECONDS = 11_644_473_600
_FILETIME_TICKS_PER_SECOND = 10_000_000


def python_entered_wall() -> float:
    return _PYTHON_ENTERED_WALL


def filetime_to_unix_seconds(filetime_ticks: int) -> float:
    return filetime_ticks / _FILETIME_TICKS_PER_SECOND - _FILETIME_EPOCH_OFFSET_SECONDS


def process_creation_unix_seconds() -> float | None:
    if sys.platform != "win32":
        return None
    try:
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        # Без argtypes ctypes передал бы псевдо-хэндл -1 как 32-битный int,
        # и на x64 GetProcessTimes получил бы битый HANDLE.
        kernel32.GetCurrentProcess.restype = wintypes.HANDLE
        filetime_ptr = ctypes.POINTER(wintypes.FILETIME)
        kernel32.GetProcessTimes.argtypes = [
            wintypes.HANDLE,
            filetime_ptr,
            filetime_ptr,
            filetime_ptr,
            filetime_ptr,
        ]
        kernel32.GetProcessTimes.restype = wintypes.BOOL

        creation = wintypes.FILETIME()
        exit_time = wintypes.FILETIME()
        kernel_time = wintypes.FILETIME()
        user_time = wintypes.FILETIME()
        ok = kernel32.GetProcessTimes(
            kernel32.GetCurrentProcess(),
            ctypes.byref(creation),
            ctypes.byref(exit_time),
            ctypes.byref(kernel_time),
            ctypes.byref(user_time),
        )
        if not ok:
            return None
        ticks = (creation.dwHighDateTime << 32) | creation.dwLowDateTime
        return filetime_to_unix_seconds(ticks)
    except Exception:
        return None


def exe_to_python_ms() -> int | None:
    """Миллисекунды от создания процесса до входа в Python, либо None."""
    created = process_creation_unix_seconds()
    if created is None:
        return None
    gap_ms = (_PYTHON_ENTERED_WALL - created) * 1000.0
    if gap_ms < 0:
        return None
    return int(round(gap_ms))
