# startup/kaspersky.py
from __future__ import annotations
import os
import sys

from app_notifications import advisory_notification, notification_action
from config.runtime_layout import APPLICATION_PATHS
from utils.antivirus_probe import is_kaspersky_present


def _resolve_kaspersky_paths() -> tuple[str, str]:
    """Возвращает путь к exe и рабочую папку приложения."""
    base_dir = str(APPLICATION_PATHS.root)
    # Исходники не являются режимом запуска; защитнику всегда передаётся текущий exe.
    exe_path = os.path.abspath(sys.executable)
    return exe_path, base_dir


def _check_kaspersky_antivirus() -> bool:
    """Проверяет наличие Kaspersky через WinAPI-процессы и uninstall-реестр."""
    try:
        return bool(is_kaspersky_present())
    except Exception:
        return False

def _check_kaspersky_warning_disabled():
    """
    Проверяет, отключено ли предупреждение о Kaspersky в settings.json.
    
    Returns:
        bool: True если предупреждение отключено, False если нет
    """
    try:
        from settings.store import get_kaspersky_warning_disabled

        return bool(get_kaspersky_warning_disabled())
    except Exception:
        return False

def _set_kaspersky_warning_disabled(disabled: bool) -> bool:
    """
    Сохраняет в settings.json настройку отключения предупреждения о Kaspersky.
    
    Args:
        disabled: True для отключения предупреждения, False для включения
    """
    try:
        from settings.store import set_kaspersky_warning_disabled

        return bool(set_kaspersky_warning_disabled(bool(disabled)))
    except Exception:
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
