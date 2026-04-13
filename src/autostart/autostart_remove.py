from __future__ import annotations

from typing import Callable

from log.log import log

from utils.subproc import get_system_exe, run_hidden


CANONICAL_TASK_NAME = "ZapretGUI_AutoStart"


def clear_autostart_task(*, status_cb: Callable[[str], None] | None = None) -> int:
    """Удаляет только каноническую задачу автозапуска."""
    if status_cb is not None:
        try:
            status_cb("Удаление задачи автозапуска…")
        except Exception:
            pass

    schtasks = get_system_exe("schtasks.exe")
    check = run_hidden(
        [schtasks, "/Query", "/TN", CANONICAL_TASK_NAME],
        capture_output=True,
        text=True,
        encoding="cp866",
        errors="ignore",
    )
    if check.returncode != 0:
        log("Каноническая задача автозапуска не найдена", "INFO")
        return 0

    log(f"Найдена задача автозапуска {CANONICAL_TASK_NAME}, удаляем", "INFO")
    delete = run_hidden(
        [schtasks, "/Delete", "/TN", CANONICAL_TASK_NAME, "/F"],
        capture_output=True,
        text=True,
        encoding="cp866",
        errors="ignore",
    )
    if delete.returncode == 0:
        log("Каноническая задача автозапуска удалена", "INFO")
        return 1

    err = str(delete.stderr or delete.stdout or "").strip()
    log(f"Не удалось удалить задачу {CANONICAL_TASK_NAME}: {err}", "⚠ WARNING")
    return 0
