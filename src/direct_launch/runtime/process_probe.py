from __future__ import annotations

import ctypes
import os
from ctypes import wintypes
from dataclasses import dataclass


_WINWS_NAMES = ("winws.exe", "winws2.exe")
_WINWS_NAME_SET = frozenset(_WINWS_NAMES)

TH32CS_SNAPPROCESS = 0x00000002
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value
MAX_PROCESS_PATH = 32768


@dataclass(frozen=True, slots=True)
class WinwsProcessRecord:
    pid: int
    name: str
    exe_path: str


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


if hasattr(ctypes, "windll"):
    _kernel32 = ctypes.windll.kernel32

    _CreateToolhelp32Snapshot = _kernel32.CreateToolhelp32Snapshot
    _CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    _CreateToolhelp32Snapshot.restype = wintypes.HANDLE

    _Process32FirstW = _kernel32.Process32FirstW
    _Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
    _Process32FirstW.restype = wintypes.BOOL

    _Process32NextW = _kernel32.Process32NextW
    _Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
    _Process32NextW.restype = wintypes.BOOL

    _OpenProcess = _kernel32.OpenProcess
    _OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    _OpenProcess.restype = wintypes.HANDLE

    _QueryFullProcessImageNameW = _kernel32.QueryFullProcessImageNameW
    _QueryFullProcessImageNameW.argtypes = [
        wintypes.HANDLE,
        wintypes.DWORD,
        wintypes.LPWSTR,
        ctypes.POINTER(wintypes.DWORD),
    ]
    _QueryFullProcessImageNameW.restype = wintypes.BOOL

    _CloseHandle = _kernel32.CloseHandle
    _CloseHandle.argtypes = [wintypes.HANDLE]
    _CloseHandle.restype = wintypes.BOOL
else:  # pragma: no cover - import safety for non-Windows environments
    _CreateToolhelp32Snapshot = None
    _Process32FirstW = None
    _Process32NextW = None
    _OpenProcess = None
    _QueryFullProcessImageNameW = None
    _CloseHandle = None


def _normalize_path(path: str) -> str:
    text = str(path or "").strip()
    if not text:
        return ""
    try:
        text = os.path.abspath(text)
    except Exception:
        pass
    return os.path.normcase(text)


def get_expected_winws_paths() -> dict[str, str]:
    try:
        from config import WINWS_EXE, WINWS2_EXE
    except Exception:
        return {}

    paths = {
        "winws.exe": _normalize_path(WINWS_EXE),
        "winws2.exe": _normalize_path(WINWS2_EXE),
    }
    return {name: path for name, path in paths.items() if path}


def _iter_winws_process_entries() -> list[tuple[int, str]]:
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

    entries: list[tuple[int, str]] = []
    try:
        process_entry = PROCESSENTRY32W()
        process_entry.dwSize = ctypes.sizeof(PROCESSENTRY32W)

        if not _Process32FirstW(snapshot, ctypes.byref(process_entry)):
            return entries

        while True:
            name = str(process_entry.szExeFile or "").strip().lower()
            if name in _WINWS_NAME_SET:
                entries.append((int(process_entry.th32ProcessID), name))
            if not _Process32NextW(snapshot, ctypes.byref(process_entry)):
                break
    finally:
        _CloseHandle(snapshot)

    return entries


def _query_process_image_path(pid: int) -> str:
    if _OpenProcess is None or _QueryFullProcessImageNameW is None or _CloseHandle is None:
        return ""

    handle = _OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
    if not handle:
        return ""

    try:
        buffer = ctypes.create_unicode_buffer(MAX_PROCESS_PATH)
        size = wintypes.DWORD(len(buffer))
        if not _QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
            return ""
        return _normalize_path(buffer.value[: size.value] or buffer.value)
    finally:
        _CloseHandle(handle)


def find_expected_winws_processes(expected_exe_path: str) -> list[WinwsProcessRecord]:
    normalized_expected_path = _normalize_path(expected_exe_path)
    expected_name = os.path.basename(normalized_expected_path).strip().lower()

    if expected_name not in _WINWS_NAME_SET or not normalized_expected_path:
        return []
    if not os.path.exists(normalized_expected_path):
        return []

    matches: list[WinwsProcessRecord] = []
    for pid, process_name in _iter_winws_process_entries():
        if process_name != expected_name:
            continue
        process_path = _query_process_image_path(pid)
        if not process_path or process_path != normalized_expected_path:
            continue
        matches.append(
            WinwsProcessRecord(
                pid=int(pid),
                name=process_name,
                exe_path=process_path,
            )
        )

    matches.sort(key=lambda item: item.pid)
    return matches


def find_canonical_winws_processes() -> dict[str, list[WinwsProcessRecord]]:
    result: dict[str, list[WinwsProcessRecord]] = {}
    for process_name, expected_path in get_expected_winws_paths().items():
        matches = find_expected_winws_processes(expected_path)
        if matches:
            result[process_name] = matches
    return result


def get_canonical_winws_process_pids() -> dict[str, list[int]]:
    result: dict[str, list[int]] = {}
    for process_name, records in find_canonical_winws_processes().items():
        pids = [record.pid for record in records if isinstance(record.pid, int)]
        if pids:
            result[process_name] = pids
    return result


def is_expected_winws_running(expected_exe_path: str) -> bool:
    return bool(find_expected_winws_processes(expected_exe_path))


def is_any_canonical_winws_running() -> bool:
    return bool(get_canonical_winws_process_pids())
