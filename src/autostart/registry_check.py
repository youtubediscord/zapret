from __future__ import annotations

from log import log


def is_autostart_enabled() -> bool:
    try:
        from autostart.autostart_exe import is_autostart_enabled as is_task_enabled

        return bool(is_task_enabled())
    except Exception as exc:
        log(f"Ошибка проверки канонического автозапуска: {exc}", "❌ ERROR")
        return False


def verify_autostart_status() -> bool:
    try:
        from autostart.autostart_remove import clear_legacy_autostart, has_legacy_autostart
        from autostart.autostart_exe import is_autostart_enabled as is_task_enabled

        if has_legacy_autostart():
            removed = int(clear_legacy_autostart() or 0)
            if removed > 0:
                log(f"Удалены legacy-механизмы автозапуска: {removed}", "INFO")

        return bool(is_task_enabled())
    except Exception as exc:
        log(f"Ошибка синхронизации автозапуска: {exc}", "❌ ERROR")
        return False
