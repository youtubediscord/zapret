# admin_check_debug.py
import os, ctypes
from ctypes import wintypes
from log.log import log

from utils.subproc import get_system32_path

def debug_admin_status():
    """Детальная диагностика прав администратора"""
    log("=== ДИАГНОСТИКА ПРАВ АДМИНИСТРАТОРА ===", level="🔍 DIAG")
    
    # 1. Старый метод
    try:
        is_admin_old = ctypes.windll.shell32.IsUserAnAdmin()
        log(f"IsUserAnAdmin(): {bool(is_admin_old)}", level="🔍 DIAG")
    except Exception as e:
        log(f"IsUserAnAdmin() failed: {e}", level="⚠ WARNING")
    
    # 2. Проверка SID (исправлено)
    try:
        import win32security
        # Получаем SID группы администраторов
        admin_sid = win32security.ConvertStringSidToSid("S-1-5-32-544")
        is_admin_sid = win32security.CheckTokenMembership(None, admin_sid)
        log(f"CheckTokenMembership(Administrators): {is_admin_sid}", level="🔍 DIAG")
    except ImportError:
        log("win32security не установлен, пропускаем SID проверку", level="⚠ WARNING")
    except Exception as e:
        log(f"SID check failed: {e}", level="⚠ WARNING")
    
    # 3. Токены (исправлено)
    advapi32 = ctypes.windll.advapi32
    kernel32 = ctypes.windll.kernel32
    
    TOKEN_QUERY = 0x0008
    TokenElevationType = 18
    TokenElevation = 20
    
    # GetCurrentProcess возвращает псевдо-хэндл -1
    current_process = wintypes.HANDLE(kernel32.GetCurrentProcess())
    
    hToken = wintypes.HANDLE()
    # Исправлен вызов OpenProcessToken
    if advapi32.OpenProcessToken(
        current_process,
        TOKEN_QUERY,
        ctypes.byref(hToken)
    ):
        try:
            # Elevation Type
            elevation_type = wintypes.DWORD()
            size_needed = wintypes.DWORD()
            
            if advapi32.GetTokenInformation(
                hToken,
                TokenElevationType,
                ctypes.byref(elevation_type),
                ctypes.sizeof(elevation_type),
                ctypes.byref(size_needed)
            ):
                types = {
                    1: "TokenElevationTypeDefault",
                    2: "TokenElevationTypeFull", 
                    3: "TokenElevationTypeLimited"
                }
                log(f"TokenElevationType: {elevation_type.value} ({types.get(elevation_type.value, 'Unknown')})", level="🔍 DIAG")
            else:
                error = kernel32.GetLastError()
                log(f"Не удалось получить TokenElevationType, код ошибки: {error}", level="⚠ WARNING")
            
            # Elevation Status
            is_elevated = wintypes.DWORD()
            size_needed = wintypes.DWORD()
            
            if advapi32.GetTokenInformation(
                hToken,
                TokenElevation,
                ctypes.byref(is_elevated),
                ctypes.sizeof(is_elevated),
                ctypes.byref(size_needed)
            ):
                log(f"TokenElevation: {bool(is_elevated.value)}", level="🔍 DIAG")
            else:
                error = kernel32.GetLastError()
                log(f"Не удалось получить TokenElevation, код ошибки: {error}", level="⚠ WARNING")
                
        finally:
            kernel32.CloseHandle(hToken)
    else:
        error = kernel32.GetLastError()
        log(f"Не удалось открыть токен процесса, код ошибки: {error}", level="❌ ERROR")
    
    # 4. Реальный тест
    log("=== РЕАЛЬНЫЙ ТЕСТ ПРАВ ===", level="🔍 DIAG")
    test_file = os.path.join(get_system32_path(), "admin_test.tmp")
    try:
        with open(test_file, 'w') as f:
            f.write("test")
        os.remove(test_file)
        log("✅ Могу писать в System32 - ЕСТЬ права админа", level="✅ SUCCESS")
    except Exception as e:
        log(f"❌ НЕ могу писать в System32 - НЕТ прав админа ({e})", level="❌ ERROR")
    
    # 5. Проверка UAC
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, 
                           r"SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System")
        uac_enabled, _ = winreg.QueryValueEx(key, "EnableLUA")
        consent_prompt, _ = winreg.QueryValueEx(key, "ConsentPromptBehaviorAdmin")
        log(f"UAC включен: {bool(uac_enabled)}", level="🔍 DIAG")
        log(f"ConsentPromptBehaviorAdmin: {consent_prompt}", level="🔍 DIAG")
        winreg.CloseKey(key)
    except Exception as e:
        log(f"Не могу проверить UAC: {e}", level="⚠ WARNING")
    
    # 6. Дополнительные проверки
    log("=== ДОПОЛНИТЕЛЬНАЯ ИНФОРМАЦИЯ ===", level="🔍 DIAG")
    
    # Проверка пользователя
    try:
        import getpass
        log(f"Текущий пользователь: {getpass.getuser()}", level="🔍 DIAG")
    except Exception as e:
        log(f"Не могу получить имя пользователя: {e}", level="⚠ WARNING")
    
    # Проверка переменных окружения
    log(f"USERNAME: {os.environ.get('USERNAME', 'не определено')}", level="🔍 DIAG")
    log(f"USERDOMAIN: {os.environ.get('USERDOMAIN', 'не определено')}", level="🔍 DIAG")
    
    # Итоговый вывод
    log("=== КОНЕЦ ДИАГНОСТИКИ ===", level="🔍 DIAG")
