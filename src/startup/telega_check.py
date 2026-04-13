# startup/telega_check.py
"""
Обнаружение поддельного клиента «Telega Desktop» —
неофициальная модификация Telegram, которая может перехватывать переписку.
"""
from __future__ import annotations

from app_notifications import advisory_notification, notification_action
from utils.windows_process_probe import iter_process_names_winapi, iter_uninstall_display_names


_TELEGA_PROCESS_NAMES = frozenset({"telega.exe"})
_TELEGA_DISPLAY_NAME_MARKERS = (
    "telega desktop",
    "telegadesktop",
)


def _detect_telega_evidence() -> str | None:
    """Возвращает сильный признак установки/работы Telega без опоры на папки и ярлыки."""
    try:
        for process_name in iter_process_names_winapi():
            normalized = str(process_name or "").strip().casefold()
            if normalized in _TELEGA_PROCESS_NAMES:
                return f"Запущенный процесс: {process_name}"

        for display_name in iter_uninstall_display_names():
            normalized = str(display_name or "").strip().casefold()
            if any(marker in normalized for marker in _TELEGA_DISPLAY_NAME_MARKERS):
                return f"Установленное приложение: {display_name}"
    except Exception:
        return None

    return None


def _check_telega_installed() -> str | None:
    """
    Проверяет наличие «Telega Desktop» в системе.

    Returns:
        Строку с подтверждённым признаком установки/запуска, или None если не найдено.
    """
    try:
        return _detect_telega_evidence()
    except Exception:
        return None


def _check_telega_warning_disabled() -> bool:
    """Проверяет, отключено ли предупреждение о Telega в реестре."""
    try:
        import winreg
        from config.config import REGISTRY_PATH

        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, REGISTRY_PATH, 0, winreg.KEY_READ
        ) as key:
            value, _ = winreg.QueryValueEx(key, "DisableTelegaWarning")
            return value == 1
    except Exception:
        return False


def _set_telega_warning_disabled(disabled: bool) -> bool:
    """Сохраняет в реестре настройку отключения предупреждения о Telega."""
    try:
        import winreg
        from config.config import REGISTRY_PATH

        with winreg.CreateKeyEx(
            winreg.HKEY_CURRENT_USER, REGISTRY_PATH, 0, winreg.KEY_WRITE
        ) as key:
            winreg.SetValueEx(key, "DisableTelegaWarning", 0, winreg.REG_DWORD, 1 if disabled else 0)
        return True
    except Exception:
        return False


def disable_telega_warning_forever() -> bool:
    """Отключает дальнейшие предупреждения о Telega Desktop."""
    return _set_telega_warning_disabled(True)


def build_telega_notification(found_path: str = "") -> dict | None:
    """Возвращает нормализованное неблокирующее событие для центра уведомлений."""
    if _check_telega_warning_disabled():
        return None

    path_line = f"\nПодтверждено: {found_path}" if found_path else ""
    return advisory_notification(
        level="error",
        title="Обнаружена Telega Desktop",
        content=(
            "Обнаружена установленная или запущенная Telega Desktop.\n"
            "Это неофициальная модификация Telegram, которая может читать переписку."
            f"{path_line}\n"
            "Рекомендуется удалить её, поставить официальный Telegram и завершить сторонние сессии."
        ),
        source="deferred.telega",
        queue="startup",
        duration=20000,
        dedupe_key="deferred.telega",
        buttons=[
            notification_action(
                "open_url",
                "Открыть сайт Telegram",
                value="https://desktop.telegram.org",
            ),
            notification_action("disable_telega_warning", "Не напоминать"),
        ],
    )
