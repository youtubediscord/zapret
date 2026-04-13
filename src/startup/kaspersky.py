# startup/kaspersky.py
from __future__ import annotations
import os
import sys

from app_notifications import advisory_notification, notification_action
from utils.windows_process_probe import iter_process_names_winapi, iter_uninstall_display_names


def _resolve_kaspersky_paths() -> tuple[str, str]:
    """Возвращает путь к exe и рабочую папку приложения."""
    if getattr(sys, "frozen", False):
        exe_path = os.path.abspath(sys.executable)
        base_dir = os.path.dirname(exe_path)
    else:
        exe_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "zapret.pyw")
        )
        base_dir = os.path.dirname(exe_path)
    return exe_path, base_dir

_KASPERSKY_PROCESS_NAMES = frozenset(
    {
        "avp.exe",
        "kavfs.exe",
        "klnagent.exe",
        "ksde.exe",
        "kavfswp.exe",
        "kavfswh.exe",
        "kavfsslp.exe",
    }
)


def _check_kaspersky_antivirus() -> bool:
    """Проверяет наличие Kaspersky через WinAPI-процессы и uninstall-реестр."""
    try:
        for process_name in iter_process_names_winapi():
            if str(process_name or "").strip().casefold() in _KASPERSKY_PROCESS_NAMES:
                return True

        for product_name in iter_uninstall_display_names():
            normalized = str(product_name or "").casefold()
            if "kaspersky" in normalized or "каспер" in normalized:
                return True
        return False
    except Exception:
        return False

def _check_kaspersky_warning_disabled():
    """
    Проверяет, отключено ли предупреждение о Kaspersky в реестре.
    
    Returns:
        bool: True если предупреждение отключено, False если нет
    """
    try:
        import winreg
        from config.config import REGISTRY_PATH

        key_path = REGISTRY_PATH
        value_name = "DisableKasperskyWarning"
        
        # Пытаемся открыть ключ
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_READ) as key:
                value, _ = winreg.QueryValueEx(key, value_name)
                return value == 1
        except (FileNotFoundError, OSError):
            return False
            
    except ImportError:
        # Если winreg недоступен (не Windows), возвращаем False
        return False

def _set_kaspersky_warning_disabled(disabled: bool) -> bool:
    """
    Сохраняет в реестре настройку отключения предупреждения о Kaspersky.
    
    Args:
        disabled: True для отключения предупреждения, False для включения
    """
    try:
        import winreg
        from config.config import REGISTRY_PATH

        key_path = REGISTRY_PATH
        value_name = "DisableKasperskyWarning"
        
        # Создаем или открываем ключ
        try:
            with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_WRITE) as key:
                winreg.SetValueEx(key, value_name, 0, winreg.REG_DWORD, 1 if disabled else 0)
            return True
        except Exception as e:
            print(f"Ошибка при записи в реестр: {e}")
            return False
            
    except ImportError:
        # Если winreg недоступен (не Windows), ничего не делаем
        return False


def disable_kaspersky_warning_forever() -> bool:
    """Отключает дальнейшие предупреждения о Kaspersky."""
    return _set_kaspersky_warning_disabled(True)


def build_kaspersky_notification() -> dict | None:
    """Возвращает нормализованное неблокирующее событие для центра уведомлений."""
    if _check_kaspersky_warning_disabled():
        return None

    exe_path, base_dir = _resolve_kaspersky_paths()
    return advisory_notification(
        level="warning",
        title="Обнаружен Kaspersky",
        content=(
            "Обнаружен антивирус Kaspersky.\n"
            "Чтобы Zapret работал стабильнее, лучше добавить программу в исключения.\n"
            f"Папка: {base_dir}\n"
            f"Файл: {exe_path}\n"
            "Без исключения антивирус может мешать запуску и работе программы."
        ),
        source="startup.kaspersky",
        queue="startup",
        duration=20000,
        dedupe_key="startup.kaspersky",
        buttons=[
            notification_action(
                "copy_text",
                "Копировать папку",
                value=base_dir,
                feedback_label="Путь к папке",
            ),
            notification_action(
                "copy_text",
                "Копировать exe",
                value=exe_path,
                feedback_label="Путь к exe",
            ),
            notification_action("disable_kaspersky_warning", "Не напоминать"),
        ],
    )
