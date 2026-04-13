from __future__ import annotations

from typing import Callable

from autostart.task_scheduler_api import (
    CANONICAL_TASK_NAME,
    delete_canonical_autostart_task,
    is_canonical_autostart_enabled,
)
from log.log import log


def clear_autostart_task(*, status_cb: Callable[[str], None] | None = None) -> int:
    """Удаляет только каноническую задачу автозапуска."""
    if status_cb is not None:
        try:
            status_cb("Удаление задачи автозапуска…")
        except Exception:
            pass

    if not is_canonical_autostart_enabled():
        log("Каноническая задача автозапуска не найдена", "INFO")
        return 0

    log(f"Найдена задача автозапуска {CANONICAL_TASK_NAME}, удаляем", "INFO")
    if delete_canonical_autostart_task():
        log("Каноническая задача автозапуска удалена", "INFO")
        return 1

    log(f"Не удалось удалить задачу {CANONICAL_TASK_NAME}", "⚠ WARNING")
    return 0
