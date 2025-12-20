"""
Управление службами Windows через Win API
Быстрее и надёжнее чем sc.exe
"""

import ctypes
from ctypes import wintypes
from typing import Optional, List
import time

# Безопасный импорт log
try:
    from log import log
except ImportError:
    def log(msg, level="INFO"):
        print(f"[{level}] {msg}")


# Windows API константы
SC_MANAGER_ALL_ACCESS = 0xF003F
SERVICE_ALL_ACCESS = 0xF01FF
SERVICE_QUERY_STATUS = 0x0004
SERVICE_STOP = 0x0020
SERVICE_DELETE = 0x00010000

SERVICE_STOPPED = 0x00000001
SERVICE_STOP_PENDING = 0x00000003
SERVICE_RUNNING = 0x00000004

# Загрузка Win API
advapi32 = ctypes.windll.advapi32

OpenSCManager = advapi32.OpenSCManagerW
OpenSCManager.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD]
OpenSCManager.restype = wintypes.HANDLE

OpenService = advapi32.OpenServiceW
OpenService.argtypes = [wintypes.HANDLE, wintypes.LPCWSTR, wintypes.DWORD]
OpenService.restype = wintypes.HANDLE

CloseServiceHandle = advapi32.CloseServiceHandle


class SERVICE_STATUS(ctypes.Structure):
    _fields_ = [
        ("dwServiceType", wintypes.DWORD),
        ("dwCurrentState", wintypes.DWORD),
        ("dwControlsAccepted", wintypes.DWORD),
        ("dwWin32ExitCode", wintypes.DWORD),
        ("dwServiceSpecificExitCode", wintypes.DWORD),
        ("dwCheckPoint", wintypes.DWORD),
        ("dwWaitHint", wintypes.DWORD),
    ]


# Правильно определяем типы для ControlService
ControlService = advapi32.ControlService
ControlService.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(SERVICE_STATUS)]
ControlService.restype = wintypes.BOOL

DeleteService = advapi32.DeleteService
DeleteService.argtypes = [wintypes.HANDLE]
DeleteService.restype = wintypes.BOOL


def stop_service(service_name: str) -> bool:
    """
    Останавливает службу через Win API
    
    Args:
        service_name: Имя службы
        
    Returns:
        True если служба остановлена
    """
    try:
        # Открываем Service Control Manager
        sc_manager = OpenSCManager(None, None, SC_MANAGER_ALL_ACCESS)
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
                # Останавливаем службу
                service_status = SERVICE_STATUS()
                result = ControlService(service, 1, ctypes.byref(service_status))  # 1 = SERVICE_CONTROL_STOP
                
                if result:
                    log(f"✅ Служба {service_name} остановлена через Win API", "DEBUG")
                    return True
                else:
                    error_code = ctypes.get_last_error()
                    if error_code == 1062:  # ERROR_SERVICE_NOT_ACTIVE
                        log(f"Служба {service_name} уже остановлена", "DEBUG")
                        return True
                    else:
                        log(f"Не удалось остановить {service_name}, код: {error_code}", "DEBUG")
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
    try:
        # Открываем Service Control Manager
        sc_manager = OpenSCManager(None, None, SC_MANAGER_ALL_ACCESS)
        if not sc_manager:
            log(f"Не удалось открыть SCManager для удаления {service_name}", "DEBUG")
            return False
        
        try:
            # Открываем службу
            service = OpenService(sc_manager, service_name, SERVICE_DELETE)
            if not service:
                log(f"Служба {service_name} не найдена (уже удалена?)", "DEBUG")
                return True  # Считаем успехом
            
            try:
                # Удаляем службу
                result = DeleteService(service)
                
                if result:
                    log(f"✅ Служба {service_name} удалена через Win API", "DEBUG")
                    return True
                else:
                    error_code = ctypes.get_last_error()
                    if error_code == 1060:  # ERROR_SERVICE_DOES_NOT_EXIST
                        log(f"Служба {service_name} не существует", "DEBUG")
                        return True
                    elif error_code == 1072:  # ERROR_SERVICE_MARKED_FOR_DELETE
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
        # Сначала останавливаем
        stop_service(service_name)
        time.sleep(0.1)
        
        # Пытаемся удалить несколько раз
        for attempt in range(retry_count):
            if delete_service(service_name):
                return True
            
            if attempt < retry_count - 1:
                log(f"Попытка {attempt + 1}/{retry_count} удаления {service_name}", "DEBUG")
                time.sleep(0.2)
        
        return False
        
    except Exception as e:
        log(f"Ошибка при остановке и удалении {service_name}: {e}", "DEBUG")
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
        if stop_and_delete_service(service_name, retry_count=1):
            cleaned = True
    
    return cleaned


def unload_driver(driver_name: str) -> bool:
    """
    Выгружает драйвер через fltmc (через Win API пока не реализовано)
    
    Args:
        driver_name: Имя драйвера
        
    Returns:
        True если драйвер выгружен
    """
    try:
        import subprocess
        
        result = subprocess.run(
            ["fltmc", "unload", driver_name],
            capture_output=True,
            creationflags=0x08000000,  # CREATE_NO_WINDOW
            timeout=3
        )
        
        if result.returncode == 0:
            log(f"✅ Драйвер {driver_name} выгружен", "DEBUG")
            return True
        else:
            log(f"Драйвер {driver_name} не выгружен (возможно не загружен)", "DEBUG")
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
        sc_manager = OpenSCManager(None, None, SC_MANAGER_ALL_ACCESS)
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

