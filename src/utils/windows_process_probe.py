from __future__ import annotations

import ctypes
from ctypes import wintypes


TH32CS_SNAPPROCESS = 0x00000002
TH32CS_SNAPMODULE = 0x00000008
TH32CS_SNAPMODULE32 = 0x00000010
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

_ERROR_BAD_LENGTH = 24
_MAX_MODULE_NAME32 = 255


class PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("cntUsage", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("th32DefaultHeapID", ctypes.c_size_t),
        ("th32ModuleID", wintypes.DWORD),
        ("cntThreads", wintypes.DWORD),
        ("th32ParentProcessID", wintypes.DWORD),
        ("pcPriClassBase", ctypes.c_long),
        ("dwFlags", wintypes.DWORD),
        ("szExeFile", wintypes.WCHAR * wintypes.MAX_PATH),
    ]


class MODULEENTRY32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("th32ModuleID", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("GlblcntUsage", wintypes.DWORD),
        ("ProccntUsage", wintypes.DWORD),
        ("modBaseAddr", ctypes.POINTER(ctypes.c_byte)),
        ("modBaseSize", wintypes.DWORD),
        ("hModule", ctypes.c_void_p),
        ("szModule", wintypes.WCHAR * (_MAX_MODULE_NAME32 + 1)),
        ("szExePath", wintypes.WCHAR * wintypes.MAX_PATH),
    ]


if hasattr(ctypes, "WinDLL"):
    # Приватный экземпляр WinDLL, а не глобальный ctypes.windll.kernel32:
    # windll кэширует функции процессно-глобально, и argtypes на них может
    # перезаписать любой другой модуль со СВОИМ классом PROCESSENTRY32W —
    # тогда byref(наша структура) падает с TypeError
    # ("expected LP_PROCESSENTRY32W instance instead of pointer to PROCESSENTRY32W").
    _kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    _CreateToolhelp32Snapshot = _kernel32.CreateToolhelp32Snapshot
    _CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    _CreateToolhelp32Snapshot.restype = wintypes.HANDLE

    _Process32FirstW = _kernel32.Process32FirstW
    _Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
    _Process32FirstW.restype = wintypes.BOOL

    _Process32NextW = _kernel32.Process32NextW
    _Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
    _Process32NextW.restype = wintypes.BOOL

    _Module32FirstW = _kernel32.Module32FirstW
    _Module32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(MODULEENTRY32W)]
    _Module32FirstW.restype = wintypes.BOOL

    _Module32NextW = _kernel32.Module32NextW
    _Module32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(MODULEENTRY32W)]
    _Module32NextW.restype = wintypes.BOOL

    _CloseHandle = _kernel32.CloseHandle
    _CloseHandle.argtypes = [wintypes.HANDLE]
    _CloseHandle.restype = wintypes.BOOL
else:  # pragma: no cover - import safety for non-Windows environments
    _CreateToolhelp32Snapshot = None
    _Process32FirstW = None
    _Process32NextW = None
    _Module32FirstW = None
    _Module32NextW = None
    _CloseHandle = None


_UNINSTALL_KEY_PATHS = (
    r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
    r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall",
)


def iter_process_names_winapi() -> list[str]:
    """Перечисляет имена процессов напрямую через Toolhelp Snapshot."""
    return [name for _, name in iter_process_records_winapi()]


def iter_process_records_winapi() -> list[tuple[int, str]]:
    """Перечисляет пары (pid, имя процесса) напрямую через Toolhelp Snapshot."""
    if (
        _CreateToolhelp32Snapshot is None
        or _Process32FirstW is None
        or _Process32NextW is None
        or _CloseHandle is None
    ):
        return []

    snapshot = _CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if not snapshot or snapshot == INVALID_HANDLE_VALUE:
        return []

    records: list[tuple[int, str]] = []
    try:
        entry = PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(PROCESSENTRY32W)
        if not _Process32FirstW(snapshot, ctypes.byref(entry)):
            return records

        while True:
            name = str(entry.szExeFile or "").strip()
            if name:
                records.append((int(entry.th32ProcessID), name))
            if not _Process32NextW(snapshot, ctypes.byref(entry)):
                break
    finally:
        _CloseHandle(snapshot)

    return records


def iter_process_module_paths_winapi(pid: int, *, max_snapshot_attempts: int = 3) -> list[str]:
    """Перечисляет полные пути модулей процесса через Toolhelp Snapshot.

    Возвращает пустой список, если снимок недоступен (нет прав, процесс
    завершился, WOW64-несовпадение разрядности). ERROR_BAD_LENGTH — штатная
    гонка Toolhelp по MSDN, поэтому делаем несколько попыток снимка.
    """
    if (
        _CreateToolhelp32Snapshot is None
        or _Module32FirstW is None
        or _Module32NextW is None
        or _CloseHandle is None
        or int(pid) <= 0
    ):
        return []

    snapshot = None
    for _ in range(max(1, int(max_snapshot_attempts))):
        candidate = _CreateToolhelp32Snapshot(TH32CS_SNAPMODULE | TH32CS_SNAPMODULE32, int(pid))
        if candidate and candidate != INVALID_HANDLE_VALUE:
            snapshot = candidate
            break
        if ctypes.get_last_error() != _ERROR_BAD_LENGTH:
            return []
    if snapshot is None:
        return []

    paths: list[str] = []
    try:
        entry = MODULEENTRY32W()
        entry.dwSize = ctypes.sizeof(MODULEENTRY32W)
        if not _Module32FirstW(snapshot, ctypes.byref(entry)):
            return paths

        while True:
            path = str(entry.szExePath or "").strip()
            if path:
                paths.append(path)
            if not _Module32NextW(snapshot, ctypes.byref(entry)):
                break
    finally:
        _CloseHandle(snapshot)

    return paths


def iter_uninstall_display_names() -> list[str]:
    """Читает DisplayName из uninstall-разделов реестра Windows."""
    try:
        import winreg
    except Exception:
        return []

    roots = (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER)
    names: list[str] = []
    seen: set[str] = set()

    for root in roots:
        for key_path in _UNINSTALL_KEY_PATHS:
            try:
                with winreg.OpenKey(root, key_path, 0, winreg.KEY_READ) as uninstall_key:
                    subkeys_count, _, _ = winreg.QueryInfoKey(uninstall_key)
                    for index in range(subkeys_count):
                        try:
                            subkey_name = winreg.EnumKey(uninstall_key, index)
                            with winreg.OpenKey(uninstall_key, subkey_name, 0, winreg.KEY_READ) as app_key:
                                display_name, _ = winreg.QueryValueEx(app_key, "DisplayName")
                        except Exception:
                            continue

                        text = str(display_name or "").strip()
                        if not text:
                            continue
                        normalized = text.casefold()
                        if normalized in seen:
                            continue
                        seen.add(normalized)
                        names.append(text)
            except Exception:
                continue

    return names
