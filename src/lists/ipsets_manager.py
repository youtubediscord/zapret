"""Менеджер IPset файлов.

Файлы рядом с программой:
- `lists/base/ipset-all.txt` : системная база для ipset-all
- `lists/user/ipset-all.txt` : пользовательские записи
- `lists/ipset-all.txt`      : итоговый файл (base + user)
- `lists/base/ipset-ru.txt`  : системная база исключений для --ipset-exclude
- `lists/user/ipset-ru.txt`  : пользовательские исключения
- `lists/ipset-ru.txt`       : итоговый файл исключений
"""

from __future__ import annotations

import ipaddress
import os
from urllib.parse import urlparse

from log.log import log
from lists.core.layered_runtime import LayeredListPaths, ensure_user_layer, rebuild_layered_list, reset_user_layer
from lists.core.paths import get_list_base_path, get_list_final_path, get_list_user_path, get_lists_dir

LISTS_FOLDER = get_lists_dir()

IPSET_ALL_PATH = get_list_final_path("ipset-all")
IPSET_ALL_BASE_PATH = get_list_base_path("ipset-all")
IPSET_ALL_USER_PATH = get_list_user_path("ipset-all")
IPSET_RU_PATH = get_list_final_path("ipset-ru")
IPSET_RU_BASE_PATH = get_list_base_path("ipset-ru")
IPSET_RU_USER_PATH = get_list_user_path("ipset-ru")
IPSET_ALL_LIST_PATHS = LayeredListPaths(
    base_path=IPSET_ALL_BASE_PATH,
    user_path=IPSET_ALL_USER_PATH,
    final_path=IPSET_ALL_PATH,
)
IPSET_RU_LIST_PATHS = LayeredListPaths(
    base_path=IPSET_RU_BASE_PATH,
    user_path=IPSET_RU_USER_PATH,
    final_path=IPSET_RU_PATH,
)


_BASE_CACHE_PATH: str | None = None
_BASE_CACHE_SIG: tuple[int, int] | None = None
_BASE_CACHE_ENTRIES: list[str] | None = None
_BASE_CACHE_SET: set[str] | None = None


def _file_sig(path: str) -> tuple[int, int] | None:
    try:
        st = os.stat(path)
        return int(st.st_mtime_ns), int(st.st_size)
    except OSError:
        return None


def _invalidate_base_cache() -> None:
    global _BASE_CACHE_PATH, _BASE_CACHE_SIG, _BASE_CACHE_ENTRIES, _BASE_CACHE_SET
    _BASE_CACHE_PATH = None
    _BASE_CACHE_SIG = None
    _BASE_CACHE_ENTRIES = None
    _BASE_CACHE_SET = None


def _is_cached(path: str) -> bool:
    return (
        _BASE_CACHE_PATH == path
        and _BASE_CACHE_ENTRIES is not None
        and _BASE_CACHE_SIG is not None
        and _BASE_CACHE_SIG == _file_sig(path)
    )


def _cache_base(path: str, entries: list[str]) -> None:
    global _BASE_CACHE_PATH, _BASE_CACHE_SIG, _BASE_CACHE_ENTRIES, _BASE_CACHE_SET
    _BASE_CACHE_PATH = path
    _BASE_CACHE_SIG = _file_sig(path)
    _BASE_CACHE_ENTRIES = list(entries)
    _BASE_CACHE_SET = set(entries)


def _normalize_ip_entry(text: str) -> str | None:
    line = str(text or "").strip()
    if not line or line.startswith("#"):
        return None

    if "://" in line:
        try:
            parsed = urlparse(line)
            host = parsed.netloc or parsed.path.split("/")[0]
            line = host.split(":")[0]
        except Exception:
            pass

    if "-" in line:
        return None

    if "/" in line:
        try:
            return ipaddress.ip_network(line, strict=False).with_prefixlen
        except Exception:
            return None

    try:
        return str(ipaddress.ip_address(line))
    except Exception:
        return None


def _read_effective_ip_entries(path: str) -> list[str]:
    if not os.path.exists(path):
        return []

    result: list[str] = []
    seen: set[str] = set()
    try:
        with open(path, "r", encoding="utf-8") as f:
            for raw in f:
                norm = _normalize_ip_entry(raw)
                if not norm or norm in seen:
                    continue
                seen.add(norm)
                result.append(norm)
    except Exception:
        return []
    return result


def _read_effective_ip_entries_from_text(text: str) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for raw in str(text or "").splitlines():
        norm = _normalize_ip_entry(raw)
        if not norm or norm in seen:
            continue
        seen.add(norm)
        result.append(norm)
    return result


def _count_effective_entries(path: str) -> int:
    return len(_read_effective_ip_entries(path))


def get_ipset_all_base_entries() -> list[str]:
    if _is_cached(IPSET_ALL_BASE_PATH):
        return list(_BASE_CACHE_ENTRIES or [])

    if os.path.exists(IPSET_ALL_BASE_PATH):
        base_entries = _read_effective_ip_entries(IPSET_ALL_BASE_PATH)
        if base_entries:
            _cache_base(IPSET_ALL_BASE_PATH, base_entries)
            return list(base_entries)

    log("Не найдена системная база lists/base/ipset-all.txt", "ERROR")
    return []


def get_ipset_all_base_set() -> set[str]:
    entries = get_ipset_all_base_entries()
    if _BASE_CACHE_ENTRIES == entries and _BASE_CACHE_SET is not None:
        return set(_BASE_CACHE_SET)
    return {x for x in entries if x}


def get_user_ipset_entries() -> list[str]:
    return _read_effective_ip_entries(IPSET_ALL_USER_PATH)


def ensure_ipset_all_user_file() -> bool:
    """Публичный helper: гарантирует наличие ipset-all.user.txt."""
    return ensure_user_layer(IPSET_ALL_LIST_PATHS, error_message="Ошибка подготовки ipset-all.user.txt", log_func=log)


def sync_ipset_all_after_user_change() -> bool:
    """Быстрый sync после правки user-файла.

    Не пересоздаёт системную базу без необходимости на каждом вызове.
    Используется в GUI-автосохранении, чтобы не блокировать интерфейс.
    """
    try:
        return rebuild_layered_list(
            IPSET_ALL_LIST_PATHS,
            get_base_entries=get_ipset_all_base_entries,
            read_entries=_read_effective_ip_entries,
            log_func=log,
            user_error_message="Ошибка подготовки ipset-all.user.txt",
            final_error_label="Ошибка генерации ipset-all.txt",
        )
    except Exception as exc:
        log(f"Ошибка sync_ipset_all_after_user_change: {exc}", "ERROR")
        return False


def rebuild_ipset_all_files() -> bool:
    """Пересобирает итоговый ipset-all.txt из системной базы и user-слоя."""
    try:
        return rebuild_layered_list(
            IPSET_ALL_LIST_PATHS,
            get_base_entries=get_ipset_all_base_entries,
            read_entries=_read_effective_ip_entries,
            log_func=log,
            user_error_message="Ошибка подготовки ipset-all.user.txt",
            final_error_label="Ошибка генерации ipset-all.txt",
            require_non_empty=True,
        )
    except Exception as exc:
        log(f"Ошибка rebuild_ipset_all_files: {exc}", "ERROR")
        return False


def reset_ipset_all_user_file() -> bool:
    """Очищает ipset-all.user.txt и пересобирает ipset-all.txt из системной базы."""
    return reset_user_layer(
        IPSET_ALL_LIST_PATHS,
        rebuild_fn=rebuild_ipset_all_files,
        log_func=log,
        reset_error_label="Ошибка сброса ipset-all.user.txt",
        success_message="ipset-all.user.txt очищен, ipset-all.txt пересобран из системной базы",
    )


def get_ipset_ru_base_entries() -> list[str]:
    base_entries = _read_effective_ip_entries(IPSET_RU_BASE_PATH)
    if base_entries:
        return base_entries
    log("Не найдена системная база lists/base/ipset-ru.txt", "ERROR")
    return []


def get_ipset_ru_base_set() -> set[str]:
    return set(get_ipset_ru_base_entries())


def get_user_ipset_ru_entries() -> list[str]:
    return _read_effective_ip_entries(IPSET_RU_USER_PATH)


def ensure_ipset_ru_user_file() -> bool:
    """Публичный helper: гарантирует наличие ipset-ru.user.txt."""
    return ensure_user_layer(IPSET_RU_LIST_PATHS, error_message="Ошибка подготовки ipset-ru.user.txt", log_func=log)


def sync_ipset_ru_after_user_change() -> bool:
    """Быстрый sync после правки ipset-ru.user.txt."""
    try:
        return rebuild_layered_list(
            IPSET_RU_LIST_PATHS,
            get_base_entries=get_ipset_ru_base_entries,
            read_entries=_read_effective_ip_entries,
            log_func=log,
            user_error_message="Ошибка подготовки ipset-ru.user.txt",
            final_error_label="Ошибка генерации ipset-ru.txt",
        )
    except Exception as exc:
        log(f"Ошибка sync_ipset_ru_after_user_change: {exc}", "ERROR")
        return False


def rebuild_ipset_ru_files() -> bool:
    """Пересобирает итоговый ipset-ru.txt из системной базы и user-слоя."""
    try:
        return rebuild_layered_list(
            IPSET_RU_LIST_PATHS,
            get_base_entries=get_ipset_ru_base_entries,
            read_entries=_read_effective_ip_entries,
            log_func=log,
            user_error_message="Ошибка подготовки ipset-ru.user.txt",
            final_error_label="Ошибка генерации ipset-ru.txt",
        )
    except Exception as exc:
        log(f"Ошибка rebuild_ipset_ru_files: {exc}", "ERROR")
        return False


def ensure_ipsets_exist() -> bool:
    """Проверяет существование файлов IPsets и создает их если нужно."""
    try:
        os.makedirs(LISTS_FOLDER, exist_ok=True)

        if not rebuild_ipset_all_files():
            log("Не удалось подготовить ipset-all файлы", "WARNING")
            return False

        if not rebuild_ipset_ru_files():
            log("Не удалось подготовить ipset-ru файлы", "WARNING")
            return False

        return True

    except Exception as e:
        log(f"Ошибка создания файлов IPsets: {e}", "❌ ERROR")
        return False


def startup_ipsets_check() -> bool:
    """Проверка IPsets при запуске программы."""
    try:
        log("=== Проверка IPsets при запуске ===", "IPSETS")

        os.makedirs(LISTS_FOLDER, exist_ok=True)

        ipset_all_ok = rebuild_ipset_all_files()
        ipset_ru_ok = rebuild_ipset_ru_files()

        if ipset_all_ok and ipset_ru_ok:
            total_all = _count_effective_entries(IPSET_ALL_PATH)
            user_all = _count_effective_entries(IPSET_ALL_USER_PATH)
            total_ru = _count_effective_entries(IPSET_RU_PATH)
            user_ru = _count_effective_entries(IPSET_RU_USER_PATH)
            log(f"ipset-all.txt: {total_all} строк, user: {user_all}", "INFO")
            log(f"ipset-ru.txt: {total_ru} строк, user: {user_ru}", "INFO")
            return True

        log(
            f"Проблемы с IPset файлами: ipset-all={ipset_all_ok}, ipset-ru={ipset_ru_ok}",
            "WARNING",
        )
        return False

    except Exception as e:
        log(f"❌ Ошибка при проверке IPsets: {e}", "ERROR")
        return False
