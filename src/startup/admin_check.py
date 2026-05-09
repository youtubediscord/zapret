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

def request_admin_restart(
    *,
    prompt_message: str | None = None,
    prompt_title: str | None = None,
    failure_message: str | None = None,
    failure_title: str | None = None,
) -> bool:
    """Просит Windows перезапустить приложение с правами администратора."""
    if is_admin():
        log("✅ Приложение запущено с правами администратора", level="INFO")
        return True

    if "--elevated" in sys.argv:
        ctypes.windll.user32.MessageBoxW(
            None,
            failure_message or (
                "Не удалось получить права администратора.\n"
                "Попробуйте запустить приложение от имени администратора вручную:\n\n"
                "1. Нажмите правой кнопкой на файле программы\n"
                "2. Выберите 'Запуск от имени администратора'"
            ),
            failure_title or "Zapret - Ошибка получения прав",
            0x10  # MB_ICONERROR
        )
        return False

    log("⚠️ Приложение запущено БЕЗ прав администратора", level="⚠ WARNING")

    result = ctypes.windll.user32.MessageBoxW(
        None,
        prompt_message or (
            "Zapret требует права администратора для корректной работы.\n\n"
            "Нажмите OK для перезапуска с правами администратора."
        ),
        prompt_title or "Zapret - Требуются права администратора",
        0x41  # MB_OKCANCEL | MB_ICONINFORMATION
    )

    if result == 1:
        try:
            args = sys.argv[1:] + ["--elevated"]
            params = " ".join(f'"{arg}"' if " " in arg else arg for arg in args)

            if getattr(sys, 'frozen', False):
                exe_path = sys.executable
            else:
                exe_path = sys.executable
                script_path = os.path.abspath(sys.argv[0])
                params = f'"{script_path}" {params}'

            log(f"Запуск с правами администратора: {exe_path} {params}", level="INFO")

            ret = ctypes.windll.shell32.ShellExecuteW(
                None,
                "runas",
                exe_path,
                params,
                None,
                1  # SW_SHOWNORMAL
            )
            
            if ret > 32:
                return True
            else:
                ctypes.windll.user32.MessageBoxW(
                    None,
                    failure_message or (
                        "Не удалось запустить приложение с правами администратора.\n"
                        "Возможно, UAC заблокировал запрос."
                    ),
                    failure_title or "Zapret - Ошибка",
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

def ensure_admin_rights():
    """Убеждается, что приложение запущено с правами администратора"""
    if is_admin():
        return True
    request_admin_restart()
    return False
