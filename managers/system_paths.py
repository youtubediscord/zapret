# utils/system_paths.py
from pathlib import Path
import os
import ctypes
from ctypes import wintypes

def get_hosts_path() -> Path:
    """
    Возвращает абсолютный путь к файлу hosts на той букве диска,
    где реально установлена Windows.
    """
    # 1. Пробуем переменную среды — самый простой и быстрый способ
    sys_root = os.getenv("SystemRoot")
    if sys_root and Path(sys_root).exists():
        return Path(sys_root, "System32", "drivers", "etc", "hosts")

    # 2. Если почему-то переменной нет — берём через WinAPI
    GetSystemWindowsDirectoryW = ctypes.windll.kernel32.GetSystemWindowsDirectoryW
    GetSystemWindowsDirectoryW.argtypes = [wintypes.LPWSTR, wintypes.UINT]
    GetSystemWindowsDirectoryW.restype  = wintypes.UINT

    buf = ctypes.create_unicode_buffer(260)
    if GetSystemWindowsDirectoryW(buf, len(buf)):
        return Path(buf.value, "System32", "drivers", "etc", "hosts")

    # 3. Фолбэк на C:\Windows (маловероятно, но пусть будет)
    return Path(r"C:\Windows\System32\drivers\etc\hosts")