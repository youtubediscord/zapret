"""
Утилита для остановки процессов через Windows API.
Быстрее и надёжнее чем taskkill.exe
"""

import ctypes
from ctypes import wintypes
import psutil
from log import log
from typing import List, Optional

# Windows API константы
PROCESS_TERMINATE = 0x0001
PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
SYNCHRONIZE = 0x00100000

# WaitForSingleObject константы
WAIT_OBJECT_0 = 0x00000000
WAIT_TIMEOUT = 0x00000102
WAIT_FAILED = 0xFFFFFFFF
INFINITE = 0xFFFFFFFF

# Загрузка Windows API функций
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


def kill_process_by_pid(pid: int, force: bool = True, wait_timeout_ms: int = 3000) -> bool:
    """
    Завершает процесс по PID через Windows API с fallback на psutil.
    Ждёт реального завершения процесса.

    Args:
        pid: ID процесса
        force: True для принудительного завершения
        wait_timeout_ms: Таймаут ожидания завершения в миллисекундах

    Returns:
        True если процесс успешно завершён
    """
    # Сначала пробуем через Win API с расширенными правами
    try:
        # Открываем процесс с максимальными правами
        h_process = OpenProcess(
            PROCESS_TERMINATE | PROCESS_QUERY_INFORMATION | SYNCHRONIZE,
            False,
            pid
        )

        if h_process:
            try:
                # Завершаем процесс (код выхода = 1)
                exit_code = 1
                result = TerminateProcess(h_process, exit_code)

                if result:
                    # Ждём реального завершения процесса
                    wait_result = WaitForSingleObject(h_process, wait_timeout_ms)

                    if wait_result == WAIT_OBJECT_0:
                        log(f"✅ Процесс PID={pid} завершён через Win API (подтверждено)", "DEBUG")
                        return True
                    elif wait_result == WAIT_TIMEOUT:
                        log(f"⚠ Процесс PID={pid}: TerminateProcess успешен, но процесс не завершился за {wait_timeout_ms}мс", "WARNING")
                        # Не возвращаем True - попробуем через psutil
                    else:
                        log(f"⚠ Процесс PID={pid}: WaitForSingleObject вернул {wait_result}", "WARNING")

            finally:
                # Всегда закрываем handle
                CloseHandle(h_process)

    except Exception as e:
        log(f"Win API не сработал для PID={pid}: {e}", "DEBUG")

    # Fallback на psutil (работает с любыми привилегиями)
    try:
        proc = psutil.Process(pid)
        proc_name = proc.name()

        if force:
            proc.kill()  # SIGKILL
        else:
            proc.terminate()  # SIGTERM

        # Ждём завершения через psutil
        try:
            proc.wait(timeout=wait_timeout_ms / 1000)
            log(f"✅ Процесс {proc_name} (PID={pid}) завершён через psutil (подтверждено)", "DEBUG")
            return True
        except psutil.TimeoutExpired:
            log(f"⚠ Процесс {proc_name} (PID={pid}) не завершился за {wait_timeout_ms}мс", "WARNING")
            return False

    except psutil.NoSuchProcess:
        log(f"Процесс PID={pid} уже завершён", "DEBUG")
        return True
    except psutil.AccessDenied:
        log(f"❌ Нет прав для завершения процесса PID={pid} (требуются права администратора)", "WARNING")
        return False
    except Exception as e:
        log(f"❌ Ошибка завершения процесса PID={pid}: {e}", "WARNING")
        return False


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
    process_name_lower = process_name.lower()
    
    try:
        # Ищем все процессы с указанным именем через psutil
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                proc_name = proc.info['name']
                if proc_name and proc_name.lower() == process_name_lower:
                    pid = proc.info['pid']
                    
                    if kill_process_by_pid(pid):
                        killed_count += 1
                        
                        if not kill_all:
                            break
                            
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
                
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
    process_name_lower = process_name.lower()
    
    try:
        for proc in psutil.process_iter(['name']):
            try:
                proc_name = proc.info['name']
                if proc_name and proc_name.lower() == process_name_lower:
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
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
    process_name_lower = process_name.lower()
    
    try:
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                proc_name = proc.info['name']
                if proc_name and proc_name.lower() == process_name_lower:
                    pids.append(proc.info['pid'])
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
    except Exception as e:
        log(f"Ошибка получения PID {process_name}: {e}", "DEBUG")
    
    return pids


def kill_process_tree(pid: int) -> bool:
    """
    Завершает процесс и все его дочерние процессы.

    Args:
        pid: ID родительского процесса

    Returns:
        True если процесс завершён
    """
    try:
        parent = psutil.Process(pid)

        # Сначала завершаем дочерние процессы
        children = parent.children(recursive=True)
        for child in children:
            try:
                kill_process_by_pid(child.pid)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        # Затем завершаем родительский процесс
        return kill_process_by_pid(pid)

    except psutil.NoSuchProcess:
        log(f"Процесс PID={pid} уже завершён", "DEBUG")
        return False
    except Exception as e:
        log(f"Ошибка завершения дерева процессов PID={pid}: {e}", "WARNING")
        return False


def get_taskkill_path() -> str:
    """
    Получает полный путь к taskkill.exe.
    Ищет в System32 на диске где установлена Windows.

    Returns:
        Полный путь к taskkill.exe или 'taskkill' если не найден
    """
    import os

    # 1. Через переменную среды SystemRoot
    sys_root = os.getenv("SystemRoot")
    if sys_root:
        taskkill_path = os.path.join(sys_root, "System32", "taskkill.exe")
        if os.path.exists(taskkill_path):
            return taskkill_path

    # 2. Через Win API GetSystemWindowsDirectoryW
    try:
        GetSystemWindowsDirectoryW = ctypes.windll.kernel32.GetSystemWindowsDirectoryW
        GetSystemWindowsDirectoryW.argtypes = [wintypes.LPWSTR, wintypes.DWORD]
        GetSystemWindowsDirectoryW.restype = wintypes.DWORD

        buf = ctypes.create_unicode_buffer(260)
        if GetSystemWindowsDirectoryW(buf, len(buf)):
            taskkill_path = os.path.join(buf.value, "System32", "taskkill.exe")
            if os.path.exists(taskkill_path):
                return taskkill_path
    except Exception:
        pass

    # 3. Fallback - просто taskkill (надеемся что в PATH)
    return "taskkill"


def force_kill_via_taskkill(process_name: str) -> bool:
    """
    Принудительное завершение процесса через taskkill /F /T.
    Используется как последняя мера когда Win API и psutil не справились.

    Args:
        process_name: Имя процесса (например "winws2.exe")

    Returns:
        True если команда выполнена успешно
    """
    import subprocess

    taskkill_exe = get_taskkill_path()

    try:
        result = subprocess.run(
            [taskkill_exe, '/F', '/T', '/IM', process_name],
            capture_output=True,
            text=True,
            encoding='cp866',
            creationflags=0x08000000,  # CREATE_NO_WINDOW
            timeout=10
        )

        if result.returncode == 0:
            log(f"✅ Процесс {process_name} завершён через taskkill /F /T", "INFO")
            return True
        elif "не найден" in result.stderr.lower() or "not found" in result.stderr.lower():
            log(f"Процесс {process_name} не найден для taskkill", "DEBUG")
            return True  # Процесса нет - это успех
        else:
            log(f"taskkill для {process_name} вернул код {result.returncode}: {result.stderr}", "WARNING")
            return False

    except subprocess.TimeoutExpired:
        log(f"taskkill для {process_name} превысил таймаут", "WARNING")
        return False
    except Exception as e:
        log(f"Ошибка taskkill для {process_name}: {e}", "WARNING")
        return False


def kill_via_wmi(process_name: str) -> bool:
    """
    Завершение процесса через WMI (Windows Management Instrumentation).
    Работает когда другие методы не помогают.

    Args:
        process_name: Имя процесса (например "winws.exe")

    Returns:
        True если команда выполнена успешно
    """
    import subprocess

    try:
        # wmic process where name="winws.exe" delete
        result = subprocess.run(
            ['wmic', 'process', 'where', f'name="{process_name}"', 'delete'],
            capture_output=True,
            text=True,
            encoding='cp866',
            creationflags=0x08000000,  # CREATE_NO_WINDOW
            timeout=15
        )

        # wmic возвращает 0 даже если процесс не найден
        if "No Instance" in result.stdout or "нет экземпляров" in result.stdout.lower():
            log(f"WMI: процесс {process_name} не найден", "DEBUG")
            return True

        if result.returncode == 0:
            log(f"✅ Процесс {process_name} завершён через WMI", "INFO")
            return True
        else:
            log(f"WMI для {process_name} вернул код {result.returncode}: {result.stderr}", "DEBUG")
            return False

    except subprocess.TimeoutExpired:
        log(f"WMI для {process_name} превысил таймаут", "WARNING")
        return False
    except Exception as e:
        log(f"Ошибка WMI для {process_name}: {e}", "DEBUG")
        return False


def kill_winws_force() -> bool:
    """
    Агрессивное завершение всех процессов winws через все доступные методы.
    Используется когда обычные методы не работают.

    Returns:
        True если все процессы завершены
    """
    import time

    # Быстрая проверка - если процессов нет, сразу выходим
    if not get_process_pids("winws.exe") and not get_process_pids("winws2.exe"):
        log("Процессы winws не найдены", "DEBUG")
        return True

    # 1. Пробуем через Win API (быстро)
    kill_winws_all(max_retries=2, retry_delay=0.3)

    # 2. Проверяем остались ли процессы
    remaining = get_process_pids("winws.exe") + get_process_pids("winws2.exe")

    if not remaining:
        return True  # Win API справился

    # 3. Win API не справился - применяем taskkill /F /T
    log(f"⚠ Осталось {len(remaining)} процессов, применяем taskkill", "WARNING")
    force_kill_via_taskkill("winws.exe")
    force_kill_via_taskkill("winws2.exe")

    time.sleep(0.3)

    # 4. Проверяем после taskkill
    remaining = get_process_pids("winws.exe") + get_process_pids("winws2.exe")

    if not remaining:
        log("✅ Процессы winws завершены через taskkill", "INFO")
        return True

    # 5. Taskkill не справился - применяем WMI
    log(f"⚠ Taskkill не справился, осталось {len(remaining)} процессов. Применяем WMI", "WARNING")
    kill_via_wmi("winws.exe")
    kill_via_wmi("winws2.exe")

    time.sleep(0.3)

    # 6. Финальная проверка
    remaining = get_process_pids("winws.exe") + get_process_pids("winws2.exe")

    if remaining:
        log(f"❌ Не удалось завершить процессы winws: PIDs={remaining}", "ERROR")
        # Пытаемся собрать диагностику
        try:
            for pid in remaining:
                proc = psutil.Process(pid)
                log(f"  PID={pid}: name={proc.name()}, status={proc.status()}, username={proc.username()}", "DEBUG")
        except Exception:
            pass
        return False

    log("✅ Процессы winws завершены через WMI", "INFO")
    return True

