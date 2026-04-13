# admin_utils.py - ИСПРАВЛЕННАЯ ВЕРСИЯ
import ctypes
import sys
import os
from log.log import log


def is_admin():
    """Проверяет, запущено ли приложение с правами администратора"""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def ensure_admin_rights():
    """Убеждается, что приложение запущено с правами администратора"""
    # Если уже есть права админа - просто возвращаем True
    if is_admin():
        log("✅ Приложение запущено с правами администратора", level="INFO")
        return True
    
    # Проверяем, не был ли уже сделан запрос на повышение прав
    if "--elevated" in sys.argv:
        # Если мы уже пытались повысить права, но они все еще недостаточны
        ctypes.windll.user32.MessageBoxW(
            None,
            "Не удалось получить права администратора.\n"
            "Попробуйте запустить приложение от имени администратора вручную:\n\n"
            "1. Нажмите правой кнопкой на файле программы\n"
            "2. Выберите 'Запуск от имени администратора'",
            "Zapret - Ошибка получения прав",
            0x10  # MB_ICONERROR
        )
        return False
    
    log("⚠️ Приложение запущено БЕЗ прав администратора", level="⚠ WARNING")
    
    # Показываем диалог
    result = ctypes.windll.user32.MessageBoxW(
        None,
        "Zapret требует права администратора для корректной работы.\n\n"
        "Нажмите OK для перезапуска с правами администратора.",
        "Zapret - Требуются права администратора",
        0x41  # MB_OKCANCEL | MB_ICONINFORMATION
    )
    
    if result == 1:  # OK
        try:
            # Формируем параметры
            args = sys.argv[1:] + ["--elevated"]
            params = " ".join(f'"{arg}"' if " " in arg else arg for arg in args)
            
            # Получаем путь к исполняемому файлу
            if getattr(sys, 'frozen', False):
                # Если это скомпилированный exe
                exe_path = sys.executable
            else:
                # Если это Python скрипт
                exe_path = sys.executable
                script_path = os.path.abspath(sys.argv[0])
                params = f'"{script_path}" {params}'
            
            log(f"Запуск с правами администратора: {exe_path} {params}", level="INFO")
            
            # ShellExecuteW для запуска с правами администратора
            ret = ctypes.windll.shell32.ShellExecuteW(
                None,
                "runas",
                exe_path,
                params,
                None,
                1  # SW_SHOWNORMAL
            )
            
            if ret > 32:
                return False  # Сигнал для выхода из текущего процесса
            else:
                ctypes.windll.user32.MessageBoxW(
                    None,
                    "Не удалось запустить приложение с правами администратора.\n"
                    "Возможно, UAC заблокировал запрос.",
                    "Zapret - Ошибка",
                    0x10  # MB_ICONERROR
                )
                
        except Exception as e:
            log(f"Ошибка при запуске с правами администратора: {e}", level="❌ ERROR")
            ctypes.windll.user32.MessageBoxW(
                None,
                f"Ошибка при попытке получить права администратора:\n{str(e)}",
                "Zapret - Ошибка",
                0x10  # MB_ICONERROR
            )
    
    return False