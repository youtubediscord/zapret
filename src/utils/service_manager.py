"""
Управление службами Windows через Win API
Быстрее и надёжнее чем sc.exe
"""

import ctypes
import subprocess
from ctypes import wintypes
from typing import Optional, List
import time
from .winapi_service_types import SERVICE_STATUS

# Безопасный импорт log
try:
    from log.log import log

except ImportError:
    def log(msg, level="INFO"):
        print(f"[{level}] {msg}")


# Windows API константы
SC_MANAGER_CONNECT = 0x0001
SC_MANAGER_ALL_ACCESS = 0xF003F
SERVICE_ALL_ACCESS = 0xF01FF
SERVICE_QUERY_STATUS = 0x0004
SERVICE_STOP = 0x0020
SERVICE_DELETE = 0x00010000
SERVICE_CHANGE_CONFIG = 0x0002

SERVICE_STOPPED = 0x00000001
SERVICE_STOP_PENDING = 0x00000003
SERVICE_RUNNING = 0x00000004
SERVICE_NO_CHANGE = 0xFFFFFFFF
SERVICE_DEMAND_START = 0x00000003

ERROR_SERVICE_DOES_NOT_EXIST = 1060
ERROR_SERVICE_NOT_ACTIVE = 1062
ERROR_SERVICE_MARKED_FOR_DELETE = 1072


def _get_winapi_last_error() -> int:
    try:
        error_code = int(ctypes.get_last_error() or 0)
    except Exception:
        error_code = 0
    if error_code:
        return error_code
    try:
        if hasattr(ctypes, "windll"):
            return int(ctypes.windll.kernel32.GetLastError() or 0)
    except Exception:
        return 0
    return 0


if hasattr(ctypes, "windll"):
    advapi32 = ctypes.windll.advapi32

    OpenSCManager = advapi32.OpenSCManagerW
    OpenSCManager.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD]
    OpenSCManager.restype = wintypes.HANDLE

    OpenService = advapi32.OpenServiceW
    OpenService.argtypes = [wintypes.HANDLE, wintypes.LPCWSTR, wintypes.DWORD]
    OpenService.restype = wintypes.HANDLE

    CloseServiceHandle = advapi32.CloseServiceHandle

    # ВАЖНО: `ControlService`/`QueryServiceStatus` — это функции из одного общего `advapi32` на процесс.
    # Если в разных местах объявлять разные `SERVICE_STATUS` и выставлять `argtypes` через POINTER(...),
    # ctypes начнёт падать из-за несовместимых типов. Используем единый `SERVICE_STATUS` из
    # `utils.winapi_service_types`.
    ControlService = advapi32.ControlService
    ControlService.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(SERVICE_STATUS)]
    ControlService.restype = wintypes.BOOL

    QueryServiceStatus = advapi32.QueryServiceStatus
    QueryServiceStatus.argtypes = [wintypes.HANDLE, ctypes.POINTER(SERVICE_STATUS)]
    QueryServiceStatus.restype = wintypes.BOOL

    DeleteService = advapi32.DeleteService
    DeleteService.argtypes = [wintypes.HANDLE]
    DeleteService.restype = wintypes.BOOL

    ChangeServiceConfig = advapi32.ChangeServiceConfigW
    ChangeServiceConfig.argtypes = [
        wintypes.HANDLE,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.LPCWSTR,
        wintypes.LPCWSTR,
        ctypes.POINTER(wintypes.DWORD),
        wintypes.LPCWSTR,
        wintypes.LPCWSTR,
        wintypes.LPCWSTR,
        wintypes.LPCWSTR,
    ]
    ChangeServiceConfig.restype = wintypes.BOOL
else:  # pragma: no cover - import safety for non-Windows environments
    advapi32 = None
    OpenSCManager = None
    OpenService = None
    CloseServiceHandle = None
    ControlService = None
    QueryServiceStatus = None
    DeleteService = None
    ChangeServiceConfig = None


def stop_service(service_name: str) -> bool:
    """
    Останавливает службу через Win API
    
    Args:
        service_name: Имя службы
        
    Returns:
        True если служба остановлена
    """
    if advapi32 is None or OpenSCManager is None or OpenService is None or ControlService is None:
        return False
    try:
        # Для остановки конкретной службы достаточно подключиться к SCM.
        # Лишний ALL_ACCESS может дать отказ, хотя сама служба доступна.
        sc_manager = OpenSCManager(None, None, SC_MANAGER_CONNECT)
        if not sc_manager:
            log(f"Не удалось открыть SCManager для {service_name}", "DEBUG")
            return False
        
        try:
            # Открываем службу
            service = OpenService(sc_manager, service_name, SERVICE_STOP | SERVICE_QUERY_STATUS)
            if not service:
                log(f"Служба {service_name} не найдена (уже удалена?)", "DEBUG")
                return True  # Считаем что она не работает
            
            try:
                service_status = SERVICE_STATUS()

                # Сначала проверяем текущее состояние.
                if QueryServiceStatus(service, ctypes.byref(service_status)):
                    if service_status.dwCurrentState == SERVICE_STOPPED:
                        log(f"Служба {service_name} уже остановлена", "DEBUG")
                        return True
                    if service_status.dwCurrentState != SERVICE_STOP_PENDING:
                        result = ControlService(service, 1, ctypes.byref(service_status))  # 1 = SERVICE_CONTROL_STOP
                        if not result:
                            error_code = _get_winapi_last_error()
                            if error_code == ERROR_SERVICE_NOT_ACTIVE:
                                log(f"Служба {service_name} уже остановлена", "DEBUG")
                                return True
                            log(f"Не удалось остановить {service_name}, код: {error_code}", "DEBUG")
                            return False

                # Ждём реального перехода в STOPPED, а не только факта отправки stop-команды.
                deadline = time.time() + 5.0
                while time.time() < deadline:
                    if not QueryServiceStatus(service, ctypes.byref(service_status)):
                        error_code = _get_winapi_last_error()
                        log(f"QueryServiceStatus не удался для {service_name}, код: {error_code}", "DEBUG")
                        return False
                    if service_status.dwCurrentState == SERVICE_STOPPED:
                        log(f"✅ Служба {service_name} остановлена через Win API", "DEBUG")
                        return True
                    time.sleep(0.1)

                log(f"Таймаут ожидания остановки службы {service_name}", "DEBUG")
                return False
                        
            finally:
                CloseServiceHandle(service)
                
        finally:
            CloseServiceHandle(sc_manager)
            
    except Exception as e:
        log(f"Ошибка остановки службы {service_name}: {e}", "DEBUG")
        return False


def delete_service(service_name: str) -> bool:
    """
    Удаляет службу через Win API
    
    Args:
        service_name: Имя службы
        
    Returns:
        True если служба удалена
    """
    if advapi32 is None or OpenSCManager is None or OpenService is None or DeleteService is None:
        return False
    try:
        # Для удаления конкретной службы достаточно подключиться к SCM.
        # Нужные права запрашиваются уже у самой службы через OpenService.
        sc_manager = OpenSCManager(None, None, SC_MANAGER_CONNECT)
        if not sc_manager:
            log(f"Не удалось открыть SCManager для удаления {service_name}", "DEBUG")
            return False
        
        try:
            # Открываем службу и для удаления, и для контроля состояния.
            service = OpenService(sc_manager, service_name, SERVICE_DELETE | SERVICE_QUERY_STATUS)
            if not service:
                log(f"Служба {service_name} не найдена (уже удалена?)", "DEBUG")
                return True  # Считаем успехом
            
            try:
                service_status = SERVICE_STATUS()

                # Если сервис ещё живой, дожидаемся состояния STOPPED.
                deadline = time.time() + 5.0
                while time.time() < deadline:
                    if not QueryServiceStatus(service, ctypes.byref(service_status)):
                        error_code = _get_winapi_last_error()
                        if error_code == ERROR_SERVICE_DOES_NOT_EXIST:
                            return True
                        break
                    if service_status.dwCurrentState == SERVICE_STOPPED:
                        break
                    time.sleep(0.1)

                # Удаляем службу
                result = DeleteService(service)
                
                if result:
                    log(f"✅ Служба {service_name} удалена через Win API", "DEBUG")
                    return True
                else:
                    error_code = _get_winapi_last_error()
                    if error_code == ERROR_SERVICE_DOES_NOT_EXIST:
                        log(f"Служба {service_name} не существует", "DEBUG")
                        return True
                    elif error_code == ERROR_SERVICE_MARKED_FOR_DELETE:
                        log(f"Служба {service_name} уже помечена для удаления", "DEBUG")
                        return True
                    else:
                        log(f"Не удалось удалить {service_name}, код: {error_code}", "DEBUG")
                        return False
                        
            finally:
                CloseServiceHandle(service)
                
        finally:
            CloseServiceHandle(sc_manager)
            
    except Exception as e:
        log(f"Ошибка удаления службы {service_name}: {e}", "DEBUG")
        return False


def stop_and_delete_service(service_name: str, retry_count: int = 3) -> bool:
    """
    Останавливает и удаляет службу с повторными попытками
    
    Args:
        service_name: Имя службы
        retry_count: Количество попыток
        
    Returns:
        True если служба остановлена и удалена
    """
    try:
        # Сначала останавливаем и дожидаемся реального STOPPED.
        stop_service(service_name)

        # Пытаемся удалить несколько раз и проверяем, что служба реально исчезла.
        # DeleteService сначала только помечает запись на удаление; пока запись
        # видна SCM, WinDivert может продолжать получать 1058 при новом старте.
        for attempt in range(retry_count):
            delete_requested = delete_service(service_name)
            if delete_requested and not service_exists(service_name) and not service_registry_exists(service_name):
                return True
            if delete_requested and not service_exists(service_name) and service_registry_exists(service_name):
                log(f"Служба {service_name} исчезла из SCM, но registry-ключ ещё остался", "WARNING")

            if attempt < retry_count - 1:
                log(f"Попытка {attempt + 1}/{retry_count} удаления {service_name}", "DEBUG")
                time.sleep(0.35)

        if service_exists(service_name) or service_registry_exists(service_name):
            log(f"Служба {service_name} всё ещё видна после удаления через Win API или registry", "WARNING")
            if stop_and_delete_service_sc_fallback(service_name):
                return True
        return False
        
    except Exception as e:
        log(f"Ошибка при остановке и удалении {service_name}: {e}", "DEBUG")
        return False


def stop_and_delete_service_sc_fallback(service_name: str) -> bool:
    """Резервно удаляет службу через sc.exe, если WinAPI оставил запись видимой."""
    try:
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        for action in ("stop", "delete"):
            try:
                result = subprocess.run(
                    ["sc.exe", action, service_name],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    creationflags=creationflags,
                )
                output = ((result.stdout or "") + (result.stderr or "")).strip()
                log(
                    f"sc.exe {action} {service_name}: code={result.returncode}"
                    + (f", output={output[:200]}" if output else ""),
                    "WARNING",
                )
            except Exception as e:
                log(f"Ошибка sc.exe {action} {service_name}: {e}", "WARNING")

            deadline = time.time() + 2.0
            while time.time() < deadline:
                if not service_exists(service_name) and not service_registry_exists(service_name):
                    return True
                if not service_exists(service_name) and service_registry_exists(service_name):
                    log(f"sc.exe {action}: {service_name} исчезла из SCM, но registry-ключ ещё остался", "WARNING")
                    break
                time.sleep(0.2)

        if not service_exists(service_name) and not service_registry_exists(service_name):
            return True

        if stop_and_delete_service_pywin32_fallback(service_name):
            return True

        if delete_stopped_service_registry_tree(service_name):
            deadline = time.time() + 2.0
            while time.time() < deadline:
                if not service_exists(service_name) and not service_registry_exists(service_name):
                    return True
                time.sleep(0.2)

        return not service_exists(service_name) and not service_registry_exists(service_name)
    except Exception as e:
        log(f"Ошибка fallback-удаления службы {service_name}: {e}", "WARNING")
        return False


def stop_and_delete_service_pywin32_fallback(service_name: str) -> bool:
    """Резерв через pywin32 RemoveService, если он доступен в сборке."""
    try:
        import win32service
        import win32serviceutil

        try:
            win32serviceutil.StopService(service_name)
        except win32service.error as exc:
            if getattr(exc, "winerror", None) not in (ERROR_SERVICE_DOES_NOT_EXIST, ERROR_SERVICE_NOT_ACTIVE):
                log(f"pywin32 stop {service_name}: {exc}", "WARNING")

        try:
            win32serviceutil.RemoveService(service_name)
        except win32service.error as exc:
            if getattr(exc, "winerror", None) == ERROR_SERVICE_DOES_NOT_EXIST:
                return True
            log(f"pywin32 delete {service_name}: {exc}", "WARNING")
            return False

        deadline = time.time() + 2.0
        while time.time() < deadline:
            if not service_exists(service_name):
                return True
            time.sleep(0.2)
        return not service_exists(service_name)
    except Exception as e:
        log(f"pywin32 fallback недоступен для {service_name}: {e}", "WARNING")
        return False


def delete_stopped_service_registry_tree(service_name: str) -> bool:
    """Последний fallback: удалить registry-ключ уже остановленной driver-службы."""
    try:
        state = get_service_state(service_name)
        if state not in (SERVICE_STOPPED, None):
            log(f"Registry fallback пропущен для {service_name}: служба не остановлена (state={state})", "WARNING")
            return False

        import winreg

        path = f"SYSTEM\\CurrentControlSet\\Services\\{service_name}"
        _delete_registry_tree(winreg.HKEY_LOCAL_MACHINE, path)
        log(f"Registry-ключ службы {service_name} удалён напрямую", "WARNING")
        return True
    except FileNotFoundError:
        return True
    except Exception as e:
        log(f"Ошибка прямого удаления registry-ключа службы {service_name}: {e}", "WARNING")
        return False


def _delete_registry_tree(root, sub_key: str) -> None:
    import winreg

    with winreg.OpenKey(root, sub_key, 0, winreg.KEY_READ | winreg.KEY_WRITE) as key:
        while True:
            try:
                child = winreg.EnumKey(key, 0)
            except OSError:
                break
            _delete_registry_tree(root, f"{sub_key}\\{child}")
    winreg.DeleteKey(root, sub_key)


def set_service_start_type(service_name: str, start_type: int) -> bool:
    """Меняет тип запуска существующей службы.

    Для WinDivert это нужно после неудачной аварийной очистки: если старая
    запись `Monkey` осталась в состоянии Disabled, новый WinDivertOpen
    получает 1058 и не может сам поднять драйвер.
    """
    if advapi32 is None or OpenSCManager is None or OpenService is None or ChangeServiceConfig is None:
        return set_service_registry_start_type(service_name, start_type)
    try:
        sc_manager = OpenSCManager(None, None, SC_MANAGER_CONNECT)
        if not sc_manager:
            log(f"Не удалось открыть SCManager для настройки {service_name}", "DEBUG")
            return set_service_registry_start_type(service_name, start_type)

        try:
            service = OpenService(
                sc_manager,
                service_name,
                SERVICE_CHANGE_CONFIG | SERVICE_QUERY_STATUS,
            )
            if not service:
                log(f"Служба {service_name} не найдена для настройки запуска", "DEBUG")
                return True

            try:
                result = ChangeServiceConfig(
                    service,
                    SERVICE_NO_CHANGE,
                    int(start_type),
                    SERVICE_NO_CHANGE,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                )
                if result:
                    log(f"Служба {service_name} переведена в ручной запуск", "DEBUG")
                    return True

                error_code = _get_winapi_last_error()
                log(f"Не удалось изменить тип запуска {service_name}, код: {error_code}", "DEBUG")
                return set_service_registry_start_type(service_name, start_type)
            finally:
                CloseServiceHandle(service)
        finally:
            CloseServiceHandle(sc_manager)
    except Exception as e:
        log(f"Ошибка настройки типа запуска {service_name}: {e}", "DEBUG")
        return set_service_registry_start_type(service_name, start_type)


def set_service_demand_start(service_name: str) -> bool:
    """Переводит службу в ручной запуск, если она существует."""
    return set_service_start_type(service_name, SERVICE_DEMAND_START)


def set_service_registry_start_type(service_name: str, start_type: int) -> bool:
    """Резервно меняет Start в реестре, если SCM не даёт ChangeServiceConfig."""
    try:
        import winreg

        path = f"SYSTEM\\CurrentControlSet\\Services\\{service_name}"
        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            path,
            0,
            winreg.KEY_SET_VALUE,
        ) as key:
            winreg.SetValueEx(key, "Start", 0, winreg.REG_DWORD, int(start_type))
        log(f"Start={int(start_type)} записан в реестр службы {service_name}", "DEBUG")
        return True
    except FileNotFoundError:
        return True
    except Exception as e:
        log(f"Ошибка записи Start службы {service_name}: {e}", "DEBUG")
        return False


def cleanup_windivert_services() -> bool:
    """
    Быстро очищает все службы WinDivert
    
    Returns:
        True если хотя бы одна служба была остановлена
    """
    service_names = ["WinDivert", "WinDivert14", "WinDivert64", "windivert", "Monkey"]
    
    cleaned = False
    for service_name in service_names:
        if stop_and_delete_service(service_name, retry_count=3):
            cleaned = True
    
    return cleaned


def unload_driver(driver_name: str) -> bool:
    """
    Выгружает драйвер через Win API / Service Control Manager.

    Для текущего проекта WinDivert/Monkey представлены как driver-service
    записи SCM. Для обычного runtime-cleanup здесь нельзя удалять service entry:
    это делает следующий запуск зависимым от повторной авто-установки драйвера.
    Поэтому "выгрузка" в стандартном пути означает:
    - остановить driver service;
    - дождаться состояния STOPPED.

    Полное удаление service entry оставляем только для явно агрессивной cleanup-ветки.
    
    Args:
        driver_name: Имя драйвера
        
    Returns:
        True если драйвер выгружен
    """
    try:
        if not service_exists(driver_name):
            log(f"Драйвер {driver_name} уже отсутствует в SCM", "DEBUG")
            return True

        if not stop_service(driver_name):
            return False

        deadline = time.time() + 5.0
        last_state = None
        while time.time() < deadline:
            exists = service_exists(driver_name)
            state = get_service_state(driver_name)
            last_state = state

            if exists and state == SERVICE_STOPPED:
                log(f"✅ Драйвер {driver_name} остановлен через Win API", "DEBUG")
                return True

            if (not exists) or state is None:
                log(f"✅ Драйвер {driver_name} выгружен через Win API", "DEBUG")
                return True

            time.sleep(0.15)

        log(
            f"Драйвер {driver_name} не выгружен через Win API "
            f"(state={last_state}, exists={service_exists(driver_name)})",
            "DEBUG",
        )
        return False
    except Exception as e:
        log(f"Ошибка выгрузки драйвера {driver_name}: {e}", "DEBUG")
        return False


def service_exists(service_name: str) -> bool:
    """
    Проверяет существует ли служба
    
    Args:
        service_name: Имя службы
        
    Returns:
        True если служба существует
    """
    try:
        sc_manager = OpenSCManager(None, None, SC_MANAGER_CONNECT)
        if not sc_manager:
            return False
        
        try:
            service = OpenService(sc_manager, service_name, SERVICE_QUERY_STATUS)
            if service:
                CloseServiceHandle(service)
                return True
            return False
            
        finally:
            CloseServiceHandle(sc_manager)
            
    except Exception as e:
        log(f"Ошибка проверки службы {service_name}: {e}", "DEBUG")
        return False


def service_registry_exists(service_name: str) -> bool:
    try:
        import winreg

        path = f"SYSTEM\\CurrentControlSet\\Services\\{service_name}"
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path, 0, winreg.KEY_READ):
            return True
    except FileNotFoundError:
        return False
    except Exception as e:
        log(f"Ошибка проверки registry-ключа службы {service_name}: {e}", "DEBUG")
        return False


def get_service_state(service_name: str) -> int | None:
    """
    Возвращает текущее состояние службы Windows или None, если службы нет
    или состояние не удалось прочитать.
    """
    if advapi32 is None or OpenSCManager is None or OpenService is None or QueryServiceStatus is None:
        return None
    try:
        sc_manager = OpenSCManager(None, None, SC_MANAGER_CONNECT)
        if not sc_manager:
            return None

        try:
            service = OpenService(sc_manager, service_name, SERVICE_QUERY_STATUS)
            if not service:
                return None

            try:
                service_status = SERVICE_STATUS()
                if QueryServiceStatus(service, ctypes.byref(service_status)):
                    return int(service_status.dwCurrentState)
                return None
            finally:
                CloseServiceHandle(service)
        finally:
            CloseServiceHandle(sc_manager)
    except Exception as e:
        log(f"Ошибка чтения состояния службы {service_name}: {e}", "DEBUG")
        return None


def get_service_registry_flags(service_name: str) -> dict[str, int | None]:
    """Читает Start и DeleteFlag из реестра службы Windows."""
    try:
        import winreg

        path = f"SYSTEM\\CurrentControlSet\\Services\\{service_name}"
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path, 0, winreg.KEY_READ) as key:
            values: dict[str, int | None] = {"start": None, "delete_flag": None}
            try:
                values["start"] = int(winreg.QueryValueEx(key, "Start")[0])
            except FileNotFoundError:
                values["start"] = None
            try:
                values["delete_flag"] = int(winreg.QueryValueEx(key, "DeleteFlag")[0])
            except FileNotFoundError:
                values["delete_flag"] = 0
            return values
    except FileNotFoundError:
        return {"start": None, "delete_flag": None}
    except Exception as e:
        log(f"Ошибка чтения реестра службы {service_name}: {e}", "DEBUG")
        return {"start": None, "delete_flag": None}


def clear_service_delete_flag(service_name: str) -> bool:
    """Удаляет зависший DeleteFlag у driver-service, если SCM не снял его сам."""
    try:
        import winreg

        path = f"SYSTEM\\CurrentControlSet\\Services\\{service_name}"
        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            path,
            0,
            winreg.KEY_SET_VALUE,
        ) as key:
            try:
                winreg.DeleteValue(key, "DeleteFlag")
                log(f"DeleteFlag очищен для службы {service_name}", "DEBUG")
            except FileNotFoundError:
                pass
        return True
    except FileNotFoundError:
        return True
    except Exception as e:
        log(f"Ошибка очистки DeleteFlag службы {service_name}: {e}", "DEBUG")
        return False


def fast_cleanup_all() -> None:
    """
    Быстрая очистка всех служб и драйверов (не ждёт результата)
    Для использования перед запуском когда нужна максимальная скорость
    """
    try:
        # Очищаем службы
        cleanup_windivert_services()
        
        # Выгружаем драйверы (не ждём)
        for driver in ["WinDivert", "WinDivert14", "WinDivert64", "Monkey"]:
            try:
                unload_driver(driver)
            except:
                pass
                
    except Exception as e:
        log(f"Ошибка быстрой очистки: {e}", "DEBUG")
