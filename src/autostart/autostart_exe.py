"""
Канонический автозапуск приложения через Планировщик заданий Windows.

Поддерживаемый сценарий ровно один:
- задача `ZapretGUI_AutoStart`;
- запуск текущего GUI exe с параметром `--tray`.
"""

from __future__ import annotations

import subprocess
import sys
from datetime import datetime
from typing import Any, Callable, Optional

from utils import get_system_exe

TASK_NAME = "ZapretGUI_AutoStart"


def _log(message: str, level: str = "INFO"):
    timestamp = datetime.now().strftime("[%H:%M:%S]")
    print(f"{timestamp} [{level}] {message}")


def _run_schtasks(args: list[str], *, check_output: bool = True) -> Any:
    cmd = [get_system_exe("schtasks.exe")] + args

    for encoding in ("utf-8", "cp866", "cp1251"):
        try:
            return subprocess.run(
                cmd,
                capture_output=check_output,
                text=True,
                encoding=encoding,
                errors="replace",
                timeout=30,
            )
        except (UnicodeDecodeError, subprocess.TimeoutExpired):
            continue
        except Exception:
            continue

    try:
        return subprocess.run(cmd, capture_output=check_output, timeout=30)
    except Exception as exc:
        class ErrorResult:
            returncode = -1
            stdout = ""
            stderr = str(exc)

        return ErrorResult()


def setup_autostart_for_exe(
    status_cb: Optional[Callable[[str], None]] = None,
) -> bool:
    def _status(message: str):
        if status_cb:
            status_cb(message)

    try:
        from .autostart_remove import clear_existing_autostart

        exe_path = sys.executable
        _log("Включаем канонический автозапуск GUI", "INFO")

        # Перед созданием новой задачи убираем и её прежнюю версию, и legacy-хвосты.
        clear_existing_autostart(status_cb=_status)

        create_args = [
            "/Create",
            "/TN",
            TASK_NAME,
            "/TR",
            f'"{exe_path}" --tray',
            "/SC",
            "ONLOGON",
            "/RL",
            "HIGHEST",
            "/F",
        ]
        result = _run_schtasks(create_args)

        if result.returncode != 0:
            error_msg = getattr(result, "stderr", "Неизвестная ошибка")
            _log(f"Ошибка создания задачи автозапуска: {error_msg}", "❌ ERROR")
            _status("Не удалось создать задачу автозапуска")
            return False

        _log(f"Создана задача автозапуска: {TASK_NAME}", "INFO")
        _status("Автозапуск программы включён")
        return True
    except Exception as exc:
        _log(f"setup_autostart_for_exe: {exc}", "❌ ERROR")
        _status(f"Ошибка: {exc}")
        return False

def is_autostart_enabled() -> bool:
    try:
        result = _run_schtasks(["/Query", "/TN", TASK_NAME])
        return result.returncode == 0
    except Exception:
        return False
