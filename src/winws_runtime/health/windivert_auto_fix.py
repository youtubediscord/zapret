# winws_runtime/health/windivert_auto_fix.py
"""Безопасные auto-fix действия для проблем WinDivert."""

import subprocess
from typing import Tuple

from winws_runtime.health.windivert_diagnostics import _WINDIVERT_DRIVER_SERVICE_NAMES


def execute_windivert_auto_fix(action: str) -> Tuple[bool, str]:
    """Execute an auto-fix action. Returns (success, message)."""
    if action == "enable_adapters":
        return _fix_enable_adapters()
    elif action == "enable_bfe":
        return _fix_enable_bfe()
    elif action == "cleanup_driver":
        return _fix_cleanup_driver()
    elif action == "enable_driver":
        return _fix_enable_driver()
    return False, f"Неизвестное действие: {action}"


def _fix_enable_adapters() -> Tuple[bool, str]:
    """Try to enable disabled network adapters."""
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Get-NetAdapter -Physical | Where-Object {$_.Status -eq 'Disabled'} | Enable-NetAdapter -Confirm:$false"],
            capture_output=True, text=True, timeout=15,
            creationflags=0x08000000,
        )
        if result.returncode == 0:
            return True, "Сетевые адаптеры включены. Попробуйте запустить снова"
        return False, f"Не удалось включить адаптеры: {result.stderr[:200]}"
    except Exception as e:
        return False, f"Ошибка: {e}"


def _fix_enable_bfe() -> Tuple[bool, str]:
    """Enable and start Base Filtering Engine service."""
    try:
        subprocess.run(
            ["sc", "config", "BFE", "start=", "auto"],
            capture_output=True, timeout=5, creationflags=0x08000000,
        )
        result = subprocess.run(
            ["net", "start", "BFE"],
            capture_output=True, text=True, timeout=10, creationflags=0x08000000,
        )
        if result.returncode == 0 or "already been started" in (result.stderr or "").lower():
            return True, "Служба BFE запущена. Попробуйте запустить снова"
        return False, f"Не удалось запустить BFE: {result.stderr[:200]}"
    except Exception as e:
        return False, f"Ошибка: {e}"


def _fix_enable_driver() -> Tuple[bool, str]:
    """Set WinDivert service start type to demand."""
    try:
        changed = False
        last_error = ""
        for service_name in _WINDIVERT_DRIVER_SERVICE_NAMES:
            result = subprocess.run(
                ["sc", "config", service_name, "start=", "demand"],
                capture_output=True, text=True, timeout=5, creationflags=0x08000000,
            )
            if result.returncode == 0:
                changed = True
            elif result.stderr:
                last_error = result.stderr[:200]
        if changed:
            return True, "Служба драйвера WinDivert переключена на ручной запуск. Попробуйте запустить снова"
        return False, f"Не удалось изменить настройки: {last_error}"
    except Exception as e:
        return False, f"Ошибка: {e}"


def _fix_cleanup_driver() -> Tuple[bool, str]:
    """Run hard WinDivert/Monkey cleanup through the runtime WinAPI path."""
    try:
        from winws_runtime.runtime.system_ops import aggressive_windivert_cleanup_runtime

        ok = aggressive_windivert_cleanup_runtime()
        if ok:
            return True, "Драйвер WinDivert очищен через WinAPI. Попробуйте запустить снова"
        return False, "Не удалось полностью очистить драйвер WinDivert. Закройте ZapretGUI и запустите от администратора"
    except Exception as e:
        return False, f"Ошибка очистки драйвера WinDivert: {e}"
