# lists/hostlists_manager.py
"""Менеджер hostlist-файлов.

Файлы рядом с программой:
- `lists/base/other.txt` : системная база от установщика
- `lists/user/other.txt` : пользовательский файл (редактируется из GUI)
- `lists/other.txt`      : итоговый файл для движка (base + user)
"""

from __future__ import annotations

import os
from pathlib import Path

from log.log import log
from lists.core.layered_files import rebuild_profile_list_file
from lists.core.paths import get_list_final_path, get_list_user_path

OTHER_PATH = get_list_final_path("other")
OTHER_USER_PATH = get_list_user_path("other")
LISTS_ROOT = Path(OTHER_PATH).parent


def _read_effective_entries(path: str) -> list[str]:
    """Reads non-empty lines excluding comments (#), lowercased."""
    if not os.path.exists(path):
        return []

    result: list[str] = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            for raw in f:
                line = raw.strip().lower()
                if not line or line.startswith("#"):
                    continue
                result.append(line)
    except Exception:
        return []
    return result

def _count_effective_entries(path: str) -> int:
    return len(_read_effective_entries(path))


def rebuild_other_files() -> bool:
    """Пересобирает other.txt из системной базы и пользовательских правок."""
    try:
        rebuild_profile_list_file(LISTS_ROOT, "other.txt")
        return bool(_read_effective_entries(OTHER_PATH))
    except Exception as exc:
        log(f"Ошибка rebuild_other_files: {exc}", "ERROR")
        return False


def ensure_hostlists_exist() -> bool:
    """Проверяет hostlist-файлы и создает other.txt при необходимости."""
    return rebuild_other_files()


def startup_hostlists_check() -> bool:
    """Проверка hostlist-файлов при запуске программы."""
    try:
        log("=== Проверка хостлистов при запуске ===", "HOSTLISTS")

        ok = rebuild_other_files()
        if ok:
            total = _count_effective_entries(OTHER_PATH)
            user = _count_effective_entries(OTHER_USER_PATH)
            log(f"other.txt: {total} строк, user: {user}", "INFO")
        else:
            log("Хостлисты не готовы", "WARNING")

        return ok

    except Exception as e:
        log(f"Ошибка при проверке хостлистов: {e}", "ERROR")
        return False
