"""
Утилита для остановки процессов через Windows API.
Канонический путь для завершения процессов в runtime-слое.
"""

import ctypes
from ctypes import wintypes
from log.log import log

from typing import List
from utils.windows_process_probe import iter_process_records_winapi

# Windows API константы
PROCESS_TERMINATE = 0x0001
PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
SYNCHRONIZE = 0x00100000

# WaitForSingleObject константы
WAIT_OBJECT_0 = 0x00000000
WAIT_TIMEOUT = 0x00000102

if hasattr(ctypes, "windll"):
    kernel32 = ctypes.windll.kernel32

    OpenProcess = kernel32.OpenProcess
    OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    OpenProcess.restype = wintypes.HANDLE

    TerminateProcess = kernel32.TerminateProcess
    TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
    TerminateProcess.restype = wintypes.BOOL

    WaitForSingleObject = kernel32.WaitForSingleObject
    WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    WaitForSingleObject.restype = wintypes.DWORD

    CloseHandle = kernel32.CloseHandle
    CloseHandle.argtypes = [wintypes.HANDLE]
    CloseHandle.restype = wintypes.BOOL
else:  # pragma: no cover - import safety for non-Windows environments
    kernel32 = None
    OpenProcess = None
    TerminateProcess = None
    WaitForSingleObject = None
    CloseHandle = None


def kill_process_by_pid_winapi(pid: int, wait_timeout_ms: int = 3000) -> bool:
    """Завершает процесс по PID только через WinAPI без fallback-веток."""
    try:
        if OpenProcess is None or TerminateProcess is None or WaitForSingleObject is None or CloseHandle is None:
            raise RuntimeError("WinAPI unavailable")
        h_process = OpenProcess(
            PROCESS_TERMINATE | PROCESS_QUERY_INFORMATION | SYNCHRONIZE,
            False,
            pid
        )

        if h_process:
            try:
                result = TerminateProcess(h_process, 1)

                if result:
                    wait_result = WaitForSingleObject(h_process, wait_timeout_ms)

                    if wait_result == WAIT_OBJECT_0:
                        log(f"✅ Процесс PID={pid} завершён через Win API (подтверждено)", "DEBUG")
                        return True
                    elif wait_result == WAIT_TIMEOUT:
                        log(f"⚠ Процесс PID={pid}: TerminateProcess успешен, но процесс не завершился за {wait_timeout_ms}мс", "WARNING")
                    else:
                        log(f"⚠ Процесс PID={pid}: WaitForSingleObject вернул {wait_result}", "WARNING")

            finally:
                CloseHandle(h_process)
        else:
            log(f"Не удалось открыть процесс PID={pid} через WinAPI", "DEBUG")

    except Exception as e:
        log(f"Win API не сработал для PID={pid}: {e}", "DEBUG")

    return False


def kill_process_by_pid(pid: int, force: bool = True, wait_timeout_ms: int = 3000) -> bool:
    """
    Завершает процесс по PID через Windows API.
    Ждёт реального завершения процесса.

    Args:
        pid: ID процесса
        force: Сохранён для совместимости вызовов; WinAPI-завершение здесь всегда принудительное
        wait_timeout_ms: Таймаут ожидания завершения в миллисекундах

    Returns:
        True если процесс успешно завершён
    """
    _ = force
    return kill_process_by_pid_winapi(pid, wait_timeout_ms=wait_timeout_ms)


def kill_process_by_name(process_name: str, kill_all: bool = True) -> int:
    """
    Завершает все процессы с указанным именем через Windows API.
    
    Args:
        process_name: Имя процесса (например "winws.exe")
        kill_all: True для завершения всех найденных процессов
        
    Returns:
        Количество завершённых процессов
    """
    killed_count = 0
    process_name_lower = str(process_name or "").strip().lower()
    
    try:
        for pid, proc_name in iter_process_records_winapi():
            normalized = str(proc_name or "").strip().lower()
            if normalized != process_name_lower:
                continue

            if kill_process_by_pid(pid):
                killed_count += 1
                if not kill_all:
                    break
    except Exception as e:
        log(f"Ошибка поиска процесса {process_name}: {e}", "WARNING")
    
    if killed_count > 0:
        log(f"Завершено {killed_count} процессов {process_name}", "INFO")
    else:
        log(f"Процессы {process_name} не найдены или уже завершены", "DEBUG")
    
    return killed_count


def kill_winws_all(max_retries: int = 3, retry_delay: float = 0.5) -> bool:
    """
    Завершает все процессы winws.exe и winws2.exe.
    Проверяет что процессы действительно завершены и делает повторные попытки.

    Args:
        max_retries: Максимальное количество попыток
        retry_delay: Задержка между попытками в секундах

    Returns:
        True если все процессы успешно завершены
    """
    import time

    for attempt in range(1, max_retries + 1):
        total_killed = 0

        # Завершаем winws.exe
        total_killed += kill_process_by_name("winws.exe", kill_all=True)

        # Завершаем winws2.exe
        total_killed += kill_process_by_name("winws2.exe", kill_all=True)

        if total_killed > 0:
            log(f"✅ Завершено {total_killed} процессов winws (попытка {attempt})", "INFO")

        # Проверяем, что процессы действительно завершены
        time.sleep(0.2)  # Небольшая пауза для обновления списка процессов

        remaining_winws = get_process_pids("winws.exe")
        remaining_winws2 = get_process_pids("winws2.exe")

        if not remaining_winws and not remaining_winws2:
            if total_killed > 0:
                log(f"✅ Всего завершено {total_killed} процессов winws (подтверждено)", "INFO")
            else:
                log("Процессы winws не найдены", "DEBUG")
            return True

        # Есть ещё живые процессы
        remaining_count = len(remaining_winws) + len(remaining_winws2)
        log(f"⚠ Осталось {remaining_count} процессов winws после попытки {attempt}", "WARNING")

        if attempt < max_retries:
            log(f"Повторная попытка через {retry_delay}с...", "DEBUG")
            time.sleep(retry_delay)

    # После всех попыток ещё раз проверяем
    remaining_winws = get_process_pids("winws.exe")
    remaining_winws2 = get_process_pids("winws2.exe")

    if remaining_winws or remaining_winws2:
        all_remaining = remaining_winws + remaining_winws2
        log(f"❌ Не удалось завершить процессы winws: PIDs={all_remaining}", "ERROR")
        return False

    return True


def is_process_running(process_name: str) -> bool:
    """
    Быстрая проверка запущен ли процесс.
    
    Args:
        process_name: Имя процесса (например "winws.exe")
        
    Returns:
        True если процесс найден
    """
    process_name_lower = str(process_name or "").strip().lower()
    
    try:
        for _pid, proc_name in iter_process_records_winapi():
            normalized = str(proc_name or "").strip().lower()
            if normalized == process_name_lower:
                return True
    except Exception as e:
        log(f"Ошибка проверки процесса {process_name}: {e}", "DEBUG")
    
    return False


def get_process_pids(process_name: str) -> List[int]:
    """
    Возвращает список PID всех процессов с указанным именем.
    
    Args:
        process_name: Имя процесса
        
    Returns:
        Список PID процессов
    """
    pids = []
    process_name_lower = str(process_name or "").strip().lower()
    
    try:
        for pid, proc_name in iter_process_records_winapi():
            normalized = str(proc_name or "").strip().lower()
            if normalized == process_name_lower:
                pids.append(int(pid))
    except Exception as e:
        log(f"Ошибка получения PID {process_name}: {e}", "DEBUG")
    
    return pids


def kill_winws_force() -> bool:
    """
    Агрессивное завершение всех процессов winws через один WinAPI-путь.
    Используется когда обычные методы не работают.

    Returns:
        True если все процессы завершены
    """
    import time

    # Быстрая проверка - если процессов нет, сразу выходим
    if not get_process_pids("winws.exe") and not get_process_pids("winws2.exe"):
        log("Процессы winws не найдены", "DEBUG")
        return True

    kill_winws_all(max_retries=3, retry_delay=0.3)

    # 2. Проверяем остались ли процессы
    remaining = get_process_pids("winws.exe") + get_process_pids("winws2.exe")

    if not remaining:
        return True

    if remaining:
        log(f"❌ Не удалось завершить процессы winws: PIDs={remaining}", "ERROR")
        return False

    log("✅ Процессы winws завершены через WinAPI", "INFO")
    return True
