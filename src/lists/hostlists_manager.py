# lists/hostlists_manager.py
"""Менеджер hostlist-файлов.

Файлы рядом с программой:
- `lists/base/other.txt` : системная база от установщика
- `lists/user/other.txt` : пользовательский файл (редактируется из GUI)
- `lists/other.txt`      : итоговый файл для движка (base + user)
"""

from __future__ import annotations

import os

from log.log import log
from lists.core.layered_runtime import LayeredListPaths, rebuild_layered_list, reset_user_layer
from lists.core.paths import get_list_base_path, get_list_final_path, get_list_user_path

OTHER_PATH = get_list_final_path("other")
OTHER_BASE_PATH = get_list_base_path("other")
OTHER_USER_PATH = get_list_user_path("other")
OTHER_LIST_PATHS = LayeredListPaths(
    base_path=OTHER_BASE_PATH,
    user_path=OTHER_USER_PATH,
    final_path=OTHER_PATH,
)


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


def get_base_domains() -> list[str]:
    """Возвращает базовые домены из системной базы установщика."""
    base_domains = _read_effective_entries(OTHER_BASE_PATH)
    if base_domains:
        return base_domains

    log("Не найдена системная база lists/base/other.txt", "ERROR")
    return []


def get_base_domains_set() -> set[str]:
    """Возвращает set базовых доменов (lowercase)."""
    return {d.strip().lower() for d in get_base_domains() if d and d.strip()}


def get_user_domains() -> list[str]:
    """Возвращает effective-строки (без комментариев) из other.user.txt."""
    return _read_effective_entries(OTHER_USER_PATH)


def rebuild_other_files() -> bool:
    """Пересобирает other.txt из системной базы и пользовательских правок."""
    try:
        return rebuild_layered_list(
            OTHER_LIST_PATHS,
            get_base_entries=get_base_domains,
            read_entries=_read_effective_entries,
            log_func=log,
            user_error_message="Ошибка подготовки other.user.txt",
            final_error_label="Ошибка генерации other.txt",
            require_non_empty=True,
        )
    except Exception as exc:
        log(f"Ошибка rebuild_other_files: {exc}", "ERROR")
        return False


def reset_other_user_file() -> bool:
    """Очищает other.user.txt и пересобирает other.txt из системной базы."""
    return reset_user_layer(
        OTHER_LIST_PATHS,
        rebuild_fn=rebuild_other_files,
        log_func=log,
        reset_error_label="Ошибка сброса my hostlist",
        success_message="other.user.txt очищен, other.txt пересобран из системной базы",
    )


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
