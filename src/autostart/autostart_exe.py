"""
Канонический автозапуск приложения через Планировщик заданий Windows.

Поддерживаемый сценарий ровно один:
- задача `ZapretGUI_AutoStart`;
- запуск текущего GUI exe с параметром `--tray`.
"""

from __future__ import annotations

import sys
from datetime import datetime
from typing import Callable, Optional

from autostart.task_scheduler_api import (
    CANONICAL_TASK_NAME,
    is_canonical_autostart_enabled,
    register_canonical_autostart_task,
)


def _log(message: str, level: str = "INFO"):
    timestamp = datetime.now().strftime("[%H:%M:%S]")
    print(f"{timestamp} [{level}] {message}")


def setup_autostart_for_exe(
    status_cb: Optional[Callable[[str], None]] = None,
) -> bool:
    def _status(message: str):
        if status_cb:
            status_cb(message)

    try:
        from .autostart_remove import clear_autostart_task

        exe_path = sys.executable
        _log("Включаем канонический автозапуск GUI", "INFO")

        # Перед созданием новой задачи убираем только её текущую каноническую версию.
        clear_autostart_task(status_cb=_status)

        ok = register_canonical_autostart_task(exe_path)
        if not ok:
            _log("Ошибка создания задачи автозапуска через Task Scheduler API", "❌ ERROR")
            _status("Не удалось создать задачу автозапуска")
            return False

        _log(f"Создана задача автозапуска: {CANONICAL_TASK_NAME}", "INFO")
        _status("Автозапуск программы включён")
        return True
    except Exception as exc:
        _log(f"setup_autostart_for_exe: {exc}", "❌ ERROR")
        _status(f"Ошибка: {exc}")
        return False

def is_autostart_enabled() -> bool:
    try:
        return bool(is_canonical_autostart_enabled())
    except Exception:
        return False
