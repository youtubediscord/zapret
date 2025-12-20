"""
Прямое управление службами Windows через Win32 API.
Поддерживает длинные командные строки (до 32767 символов).
"""

import ctypes
from ctypes import wintypes
from typing import Optional, Tuple
from log import log
from utils import get_system_exe

# ============================================================================
# Константы Windows API
# ============================================================================

# Service Control Manager access rights
SC_MANAGER_ALL_ACCESS = 0xF003F
SC_MANAGER_CREATE_SERVICE = 0x0002
SC_MANAGER_CONNECT = 0x0001

# Service access rights
SERVICE_ALL_ACCESS = 0xF01FF
SERVICE_START = 0x0010
SERVICE_STOP = 0x0020
SERVICE_QUERY_STATUS = 0x0004
DELETE = 0x00010000

# Service types
SERVICE_WIN32_OWN_PROCESS = 0x00000010

# Service start types
SERVICE_AUTO_START = 0x00000002
SERVICE_DEMAND_START = 0x00000003
SERVICE_DISABLED = 0x00000004

# Error control
SERVICE_ERROR_NORMAL = 0x00000001

# Service control codes
SERVICE_CONTROL_STOP = 0x00000001

# Service states
SERVICE_STOPPED = 0x00000001
SERVICE_START_PENDING = 0x00000002
SERVICE_STOP_PENDING = 0x00000003
SERVICE_RUNNING = 0x00000004

# Service config info levels
SERVICE_CONFIG_DESCRIPTION = 1

# ============================================================================
# Структуры Windows API
# ============================================================================

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


class SERVICE_DESCRIPTION(ctypes.Structure):
    _fields_ = [
        ("lpDescription", wintypes.LPWSTR),
    ]


# ============================================================================
# Загрузка DLL
# ============================================================================

advapi32 = ctypes.windll.advapi32
kernel32 = ctypes.windll.kernel32

# OpenSCManagerW
advapi32.OpenSCManagerW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD]
advapi32.OpenSCManagerW.restype = wintypes.HANDLE

# CloseServiceHandle
advapi32.CloseServiceHandle.argtypes = [wintypes.HANDLE]
advapi32.CloseServiceHandle.restype = wintypes.BOOL

# CreateServiceW
advapi32.CreateServiceW.argtypes = [
    wintypes.HANDLE,      # hSCManager
    wintypes.LPCWSTR,     # lpServiceName
    wintypes.LPCWSTR,     # lpDisplayName
    wintypes.DWORD,       # dwDesiredAccess
    wintypes.DWORD,       # dwServiceType
    wintypes.DWORD,       # dwStartType
    wintypes.DWORD,       # dwErrorControl
    wintypes.LPCWSTR,     # lpBinaryPathName (до 32767 символов!)
    wintypes.LPCWSTR,     # lpLoadOrderGroup
    wintypes.LPDWORD,     # lpdwTagId
    wintypes.LPCWSTR,     # lpDependencies
    wintypes.LPCWSTR,     # lpServiceStartName
    wintypes.LPCWSTR,     # lpPassword
]
advapi32.CreateServiceW.restype = wintypes.HANDLE

# OpenServiceW
advapi32.OpenServiceW.argtypes = [wintypes.HANDLE, wintypes.LPCWSTR, wintypes.DWORD]
advapi32.OpenServiceW.restype = wintypes.HANDLE

# DeleteService
advapi32.DeleteService.argtypes = [wintypes.HANDLE]
advapi32.DeleteService.restype = wintypes.BOOL

# StartServiceW
advapi32.StartServiceW.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.LPCWSTR)]
advapi32.StartServiceW.restype = wintypes.BOOL

# ControlService
advapi32.ControlService.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(SERVICE_STATUS)]
advapi32.ControlService.restype = wintypes.BOOL

# QueryServiceStatus
advapi32.QueryServiceStatus.argtypes = [wintypes.HANDLE, ctypes.POINTER(SERVICE_STATUS)]
advapi32.QueryServiceStatus.restype = wintypes.BOOL

# ChangeServiceConfig2W
advapi32.ChangeServiceConfig2W.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.c_void_p]
advapi32.ChangeServiceConfig2W.restype = wintypes.BOOL

# GetLastError
kernel32.GetLastError.argtypes = []
kernel32.GetLastError.restype = wintypes.DWORD


# ============================================================================
# Основные функции
# ============================================================================

def get_last_error() -> Tuple[int, str]:
    """Получает код и описание последней ошибки Windows"""
    error_code = kernel32.GetLastError()
    
    # Получаем описание ошибки
    buf = ctypes.create_unicode_buffer(256)
    kernel32.FormatMessageW(
        0x00001000 | 0x00000200,  # FORMAT_MESSAGE_FROM_SYSTEM | FORMAT_MESSAGE_IGNORE_INSERTS
        None,
        error_code,
        0,
        buf,
        256,
        None
    )
    return error_code, buf.value.strip()


def open_sc_manager(access: int = SC_MANAGER_ALL_ACCESS) -> Optional[int]:
    """Открывает Service Control Manager"""
    handle = advapi32.OpenSCManagerW(None, None, access)
    if handle == 0:
        code, msg = get_last_error()
        log(f"OpenSCManager failed: {code} - {msg}", "ERROR")
        return None
    return handle


def close_handle(handle: int) -> None:
    """Закрывает handle службы или SCM"""
    if handle:
        advapi32.CloseServiceHandle(handle)


def service_exists(service_name: str) -> bool:
    """Проверяет существование службы"""
    scm = open_sc_manager(SC_MANAGER_CONNECT)
    if not scm:
        return False
    
    try:
        service = advapi32.OpenServiceW(scm, service_name, SERVICE_QUERY_STATUS)
        if service:
            close_handle(service)
            return True
        return False
    finally:
        close_handle(scm)


def get_service_state(service_name: str) -> Optional[int]:
    """Получает текущее состояние службы"""
    scm = open_sc_manager(SC_MANAGER_CONNECT)
    if not scm:
        return None
    
    try:
        service = advapi32.OpenServiceW(scm, service_name, SERVICE_QUERY_STATUS)
        if not service:
            return None
        
        try:
            status = SERVICE_STATUS()
            if advapi32.QueryServiceStatus(service, ctypes.byref(status)):
                return status.dwCurrentState
            return None
        finally:
            close_handle(service)
    finally:
        close_handle(scm)


def stop_service(service_name: str, wait_timeout_ms: int = 10000) -> bool:
    """
    Останавливает службу.
    
    Args:
        service_name: Имя службы
        wait_timeout_ms: Таймаут ожидания остановки в мс
    
    Returns:
        True если служба остановлена
    """
    scm = open_sc_manager(SC_MANAGER_CONNECT)
    if not scm:
        return False
    
    try:
        service = advapi32.OpenServiceW(scm, service_name, SERVICE_STOP | SERVICE_QUERY_STATUS)
        if not service:
            code, msg = get_last_error()
            # 1060 = ERROR_SERVICE_DOES_NOT_EXIST
            if code == 1060:
                return True  # Службы нет - считаем что остановлена
            log(f"OpenService failed: {code} - {msg}", "WARNING")
            return False
        
        try:
            status = SERVICE_STATUS()
            
            # Проверяем текущий статус
            if advapi32.QueryServiceStatus(service, ctypes.byref(status)):
                if status.dwCurrentState == SERVICE_STOPPED:
                    log(f"Служба {service_name} уже остановлена", "DEBUG")
                    return True
            
            # Отправляем команду остановки
            if not advapi32.ControlService(service, SERVICE_CONTROL_STOP, ctypes.byref(status)):
                code, msg = get_last_error()
                # 1062 = ERROR_SERVICE_NOT_ACTIVE
                if code == 1062:
                    return True
                log(f"ControlService STOP failed: {code} - {msg}", "WARNING")
                return False
            
            # Ждём остановки
            import time
            start_time = time.time()
            while (time.time() - start_time) * 1000 < wait_timeout_ms:
                if advapi32.QueryServiceStatus(service, ctypes.byref(status)):
                    if status.dwCurrentState == SERVICE_STOPPED:
                        log(f"Служба {service_name} остановлена", "INFO")
                        return True
                time.sleep(0.1)
            
            log(f"Таймаут ожидания остановки службы {service_name}", "WARNING")
            return False
            
        finally:
            close_handle(service)
    finally:
        close_handle(scm)


def delete_service(service_name: str) -> bool:
    """
    Удаляет службу.
    
    Args:
        service_name: Имя службы
    
    Returns:
        True если служба удалена или не существовала
    """
    # Сначала останавливаем
    stop_service(service_name)
    
    scm = open_sc_manager(SC_MANAGER_ALL_ACCESS)
    if not scm:
        return False
    
    try:
        service = advapi32.OpenServiceW(scm, service_name, DELETE)
        if not service:
            code, msg = get_last_error()
            if code == 1060:  # ERROR_SERVICE_DOES_NOT_EXIST
                return True
            log(f"OpenService for delete failed: {code} - {msg}", "WARNING")
            return False
        
        try:
            if advapi32.DeleteService(service):
                log(f"Служба {service_name} удалена", "INFO")
                return True
            else:
                code, msg = get_last_error()
                # 1072 = ERROR_SERVICE_MARKED_FOR_DELETE (уже помечена на удаление)
                if code == 1072:
                    log(f"Служба {service_name} помечена на удаление", "DEBUG")
                    return True
                log(f"DeleteService failed: {code} - {msg}", "ERROR")
                return False
        finally:
            close_handle(service)
    finally:
        close_handle(scm)


def create_service(
    service_name: str,
    display_name: str,
    binary_path: str,
    description: Optional[str] = None,
    start_type: int = SERVICE_AUTO_START,
    dependencies: Optional[str] = None
) -> bool:
    """
    Создаёт службу Windows через API.
    
    ВАЖНО: binary_path может быть до 32767 символов!
    Это главное преимущество перед sc.exe (ограничение ~8000 символов).
    
    Args:
        service_name: Внутреннее имя службы
        display_name: Отображаемое имя
        binary_path: Путь к исполняемому файлу с аргументами
        description: Описание службы
        start_type: Тип запуска (SERVICE_AUTO_START, SERVICE_DEMAND_START и т.д.)
        dependencies: Зависимости (разделённые нулевыми символами)
    
    Returns:
        True если служба создана успешно
    """
    # Сначала удаляем старую службу если есть
    delete_service(service_name)
    
    scm = open_sc_manager(SC_MANAGER_CREATE_SERVICE)
    if not scm:
        return False
    
    try:
        log(f"Создание службы {service_name}...", "INFO")
        log(f"Binary path length: {len(binary_path)} chars", "DEBUG")
        
        service = advapi32.CreateServiceW(
            scm,                        # hSCManager
            service_name,               # lpServiceName
            display_name,               # lpDisplayName
            SERVICE_ALL_ACCESS,         # dwDesiredAccess
            SERVICE_WIN32_OWN_PROCESS,  # dwServiceType
            start_type,                 # dwStartType
            SERVICE_ERROR_NORMAL,       # dwErrorControl
            binary_path,                # lpBinaryPathName
            None,                       # lpLoadOrderGroup
            None,                       # lpdwTagId
            dependencies,               # lpDependencies
            None,                       # lpServiceStartName (LocalSystem)
            None                        # lpPassword
        )
        
        if not service:
            code, msg = get_last_error()
            log(f"CreateService failed: {code} - {msg}", "ERROR")
            return False
        
        try:
            log(f"Служба {service_name} создана", "✅ SUCCESS")
            
            # Устанавливаем описание
            if description:
                desc = SERVICE_DESCRIPTION()
                desc.lpDescription = description
                if not advapi32.ChangeServiceConfig2W(
                    service,
                    SERVICE_CONFIG_DESCRIPTION,
                    ctypes.byref(desc)
                ):
                    code, msg = get_last_error()
                    log(f"Не удалось установить описание: {code} - {msg}", "WARNING")
            
            return True
            
        finally:
            close_handle(service)
    finally:
        close_handle(scm)


def start_service(service_name: str) -> bool:
    """
    Запускает службу.
    
    Args:
        service_name: Имя службы
    
    Returns:
        True если служба запущена или уже работает
    """
    scm = open_sc_manager(SC_MANAGER_CONNECT)
    if not scm:
        return False
    
    try:
        service = advapi32.OpenServiceW(scm, service_name, SERVICE_START | SERVICE_QUERY_STATUS)
        if not service:
            code, msg = get_last_error()
            log(f"OpenService for start failed: {code} - {msg}", "ERROR")
            return False
        
        try:
            # Проверяем статус
            status = SERVICE_STATUS()
            if advapi32.QueryServiceStatus(service, ctypes.byref(status)):
                if status.dwCurrentState == SERVICE_RUNNING:
                    log(f"Служба {service_name} уже запущена", "DEBUG")
                    return True
            
            # Запускаем
            if advapi32.StartServiceW(service, 0, None):
                log(f"Служба {service_name} запущена", "✅ SUCCESS")
                return True
            else:
                code, msg = get_last_error()
                # 1056 = ERROR_SERVICE_ALREADY_RUNNING
                if code == 1056:
                    return True
                log(f"StartService failed: {code} - {msg}", "ERROR")
                return False
                
        finally:
            close_handle(service)
    finally:
        close_handle(scm)


# ============================================================================
# Высокоуровневые функции для Zapret
# ============================================================================

def create_zapret_service(
    service_name: str,
    display_name: str,
    exe_path: str,
    args: list[str],
    description: Optional[str] = None,
    auto_start: bool = True
) -> bool:
    """
    Создаёт службу Zapret с полным путём и аргументами.
    
    Args:
        service_name: Имя службы
        display_name: Отображаемое имя
        exe_path: Путь к исполняемому файлу
        args: Список аргументов командной строки
        description: Описание службы
        auto_start: Запускать автоматически при загрузке
    
    Returns:
        True если служба создана
    """
    # Формируем полную командную строку
    # Путь к exe в кавычках + аргументы
    if ' ' in exe_path and not exe_path.startswith('"'):
        binary_path = f'"{exe_path}"'
    else:
        binary_path = exe_path
    
    if args:
        # Экранируем аргументы с пробелами
        escaped_args = []
        for arg in args:
            if ' ' in arg and not arg.startswith('"'):
                escaped_args.append(f'"{arg}"')
            else:
                escaped_args.append(arg)
        binary_path += ' ' + ' '.join(escaped_args)
    
    log(f"Service binary path: {binary_path[:200]}...", "DEBUG")
    
    start_type = SERVICE_AUTO_START if auto_start else SERVICE_DEMAND_START
    
    return create_service(
        service_name=service_name,
        display_name=display_name,
        binary_path=binary_path,
        description=description,
        start_type=start_type
    )


def create_bat_service(
    service_name: str,
    display_name: str,
    bat_path: str,
    description: Optional[str] = None,
    auto_start: bool = True
) -> bool:
    """
    Создаёт службу, запускающую .bat файл.
    
    Args:
        service_name: Имя службы
        display_name: Отображаемое имя
        bat_path: Путь к .bat файлу
        description: Описание службы
        auto_start: Запускать автоматически при загрузке
    
    Returns:
        True если служба создана
    """
    # cmd.exe /c "путь к bat"
    binary_path = f'{get_system_exe("cmd.exe")} /c "{bat_path}"'
    
    start_type = SERVICE_AUTO_START if auto_start else SERVICE_DEMAND_START
    
    return create_service(
        service_name=service_name,
        display_name=display_name,
        binary_path=binary_path,
        description=description,
        start_type=start_type
    )

