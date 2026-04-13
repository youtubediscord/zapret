"""Менеджер IPset файлов.

Файлы в папке приложения:
- `lists/ipset-all.base.txt`  : системная база для ipset-all
- `lists/ipset-all.user.txt`  : пользовательские записи (редактируются из GUI)
- `lists/ipset-all.txt`       : итоговый файл (base + user)
- `lists/ipset-ru.base.txt`   : системная база исключений для --ipset-exclude
- `lists/ipset-ru.user.txt`   : пользовательские исключения (редактируются из GUI)
- `lists/ipset-ru.txt`        : итоговый файл исключений (base + user)

Шаблон базы `ipset-all` хранится в `%APPDATA%/zapret/lists_template/ipset-all.txt`.
Пользовательские записи дополнительно бэкапятся в
`%APPDATA%/zapret/lists_backup/ipset-all.user.txt`.

Поддерживаются следующие рабочие модели:
- `ipset-all.base.txt` + `ipset-all.user.txt` -> `ipset-all.txt`
- `ipset-ru.base.txt` + `ipset-ru.user.txt` -> `ipset-ru.txt`
"""

from __future__ import annotations

import ipaddress
import os
from urllib.parse import urlparse

from log.log import log

from config.config import (

    LISTS_FOLDER,
    get_zapret_lists_backup_dir,
    get_zapret_lists_template_dir,
)

IPSET_ALL_PATH = os.path.join(LISTS_FOLDER, "ipset-all.txt")
IPSET_ALL_BASE_PATH = os.path.join(LISTS_FOLDER, "ipset-all.base.txt")
IPSET_ALL_USER_PATH = os.path.join(LISTS_FOLDER, "ipset-all.user.txt")
IPSET_RU_PATH = os.path.join(LISTS_FOLDER, "ipset-ru.txt")
IPSET_RU_BASE_PATH = os.path.join(LISTS_FOLDER, "ipset-ru.base.txt")
IPSET_RU_USER_PATH = os.path.join(LISTS_FOLDER, "ipset-ru.user.txt")


IPSET_ALL_BUILTIN_BASE_TEXT = """
# Cloudflare DNS
1.1.1.1
1.1.1.2
1.1.1.3
1.0.0.1
1.0.0.2
1.0.0.3
"""


_IPSET_RU_BASE_HEADER = """\
# Системная база исключений для --ipset-exclude.
# Этот файл управляется приложением.
#
# Итоговый lists/ipset-ru.txt формируется автоматически как:
#   ipset-ru.base.txt + ipset-ru.user.txt
"""


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


def _has_effective_line(path: str) -> bool:
    if not os.path.exists(path):
        return False
    try:
        if os.path.getsize(path) <= 0:
            return False
    except OSError:
        return False

    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            for raw in f:
                line = raw.strip()
                if line and not line.startswith("#"):
                    return True
    except Exception:
        return False

    return False


def _builtin_ipset_all_base_ips() -> list[str]:
    ips: list[str] = []
    for line in IPSET_ALL_BUILTIN_BASE_TEXT.strip().split("\n"):
        line = line.strip()
        if line and not line.startswith("#"):
            ips.append(line)
    return ips


def _normalize_newlines(text: str) -> str:
    normalized = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    if normalized and not normalized.endswith("\n"):
        normalized += "\n"
    return normalized


def _read_text_file(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _read_text_file_safe(path: str) -> str | None:
    try:
        return _read_text_file(path)
    except Exception:
        return None


def _write_text_file(path: str, content: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(_normalize_newlines(content))


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


def _dedup_preserve_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for x in items:
        if x in seen:
            continue
        seen.add(x)
        out.append(x)
    return out


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


def _count_effective_entries(path: str) -> int:
    return len(_read_effective_ip_entries(path))


def _get_ipset_all_template_path() -> str:
    return os.path.join(get_zapret_lists_template_dir(), "ipset-all.txt")


def _get_ipset_all_user_backup_path() -> str:
    return os.path.join(get_zapret_lists_backup_dir(), "ipset-all.user.txt")


def _get_ipset_ru_template_path() -> str:
    return os.path.join(get_zapret_lists_template_dir(), "ipset-ru.txt")

def ensure_ipset_all_template_updated() -> bool:
    """Гарантирует валидный системный шаблон ipset-all в lists_template."""
    try:
        template_path = _get_ipset_all_template_path()

        if _has_effective_line(template_path):
            return True

        fallback_content = "\n".join(_builtin_ipset_all_base_ips()) + "\n"
        _write_text_file(template_path, fallback_content)
        log("Создан аварийный шаблон ipset-all.txt", "WARNING")
        return True

    except Exception as e:
        log(f"Ошибка обновления шаблона ipset-all.txt: {e}", "ERROR")
        return False


def get_ipset_all_base_entries() -> list[str]:
    if _is_cached(IPSET_ALL_BASE_PATH):
        return list(_BASE_CACHE_ENTRIES or [])

    if os.path.exists(IPSET_ALL_BASE_PATH):
        base_entries = _read_effective_ip_entries(IPSET_ALL_BASE_PATH)
        if base_entries:
            _cache_base(IPSET_ALL_BASE_PATH, base_entries)
            return list(base_entries)

    template_path = _get_ipset_all_template_path()
    if _is_cached(template_path):
        return list(_BASE_CACHE_ENTRIES or [])

    template_entries = _read_effective_ip_entries(template_path)
    if template_entries:
        merged_entries = _dedup_preserve_order(list(template_entries) + _builtin_ipset_all_base_ips())
        _cache_base(template_path, merged_entries)
        return list(merged_entries)

    return _builtin_ipset_all_base_ips()


def get_ipset_all_base_set() -> set[str]:
    entries = get_ipset_all_base_entries()
    if _BASE_CACHE_ENTRIES == entries and _BASE_CACHE_SET is not None:
        return set(_BASE_CACHE_SET)
    return {x for x in entries if x}


def get_user_ipset_entries() -> list[str]:
    return _read_effective_ip_entries(IPSET_ALL_USER_PATH)


def _ensure_ipset_all_user_file_exists() -> bool:
    """Ensures IPSET_ALL_USER_PATH exists; restore only from dedicated backup."""
    try:
        os.makedirs(os.path.dirname(IPSET_ALL_USER_PATH), exist_ok=True)

        if os.path.exists(IPSET_ALL_USER_PATH):
            return True

        user_backup = _get_ipset_all_user_backup_path()
        if os.path.exists(user_backup):
            content = _read_text_file_safe(user_backup)
            if content is not None:
                _write_text_file(IPSET_ALL_USER_PATH, content)
                log("ipset-all.user.txt восстановлен из backup", "SUCCESS")
                return True

        _write_text_file(IPSET_ALL_USER_PATH, "")
        return True

    except Exception as e:
        log(f"Ошибка подготовки ipset-all.user.txt: {e}", "ERROR")
        return False


def ensure_ipset_all_user_file() -> bool:
    """Публичный helper: гарантирует наличие ipset-all.user.txt."""
    return _ensure_ipset_all_user_file_exists()


def _write_ipset_all_base_file_from_template() -> bool:
    """Writes IPSET_ALL_BASE_PATH from template (raw)."""
    try:
        if not ensure_ipset_all_template_updated():
            return False

        template_content = _read_text_file_safe(_get_ipset_all_template_path())
        if template_content is None:
            merged_content = "\n".join(get_ipset_all_base_entries()) + "\n"
        else:
            normalized_template = _normalize_newlines(template_content)
            template_entries = _read_effective_ip_entries(_get_ipset_all_template_path())
            template_set = set(template_entries)
            extra_entries = [ip for ip in _builtin_ipset_all_base_ips() if ip not in template_set]
            merged_content = normalized_template
            if extra_entries:
                if merged_content and not merged_content.endswith("\n"):
                    merged_content += "\n"
                if merged_content and not merged_content.endswith("\n\n"):
                    merged_content += "\n"
                merged_content += "\n".join(extra_entries) + "\n"

        _write_text_file(IPSET_ALL_BASE_PATH, merged_content)
        _invalidate_base_cache()
        return True

    except Exception as e:
        log(f"Ошибка обновления ipset-all.base.txt: {e}", "ERROR")
        return False


def _write_combined_ipset_all_file() -> bool:
    """Generates IPSET_ALL_PATH = base + user (dedup, base-first)."""
    try:
        base_entries = get_ipset_all_base_entries()
        base_set = set(base_entries)
        user_entries = _read_effective_ip_entries(IPSET_ALL_USER_PATH)

        combined: list[str] = list(base_entries)
        for e in user_entries:
            if e not in base_set:
                combined.append(e)

        combined = _dedup_preserve_order(combined)
        content = "\n".join(combined) + ("\n" if combined else "")
        _write_text_file(IPSET_ALL_PATH, content)
        return True

    except Exception as e:
        log(f"Ошибка генерации ipset-all.txt: {e}", "ERROR")
        return False


def _sync_ipset_all_user_backup() -> None:
    try:
        content = _read_text_file_safe(IPSET_ALL_USER_PATH)
        if content is None:
            return
        _write_text_file(_get_ipset_all_user_backup_path(), content)
    except Exception:
        pass


def sync_ipset_all_after_user_change() -> bool:
    """Быстрый sync после правки user-файла.

    Не пересобирает шаблон из source на каждом вызове.
    Используется в GUI-автосохранении, чтобы не блокировать интерфейс.
    """
    try:
        if not _ensure_ipset_all_user_file_exists():
            return False

        if not os.path.exists(IPSET_ALL_BASE_PATH) or os.path.getsize(IPSET_ALL_BASE_PATH) <= 0:
            if not _write_ipset_all_base_file_from_template():
                return False

        if not _write_combined_ipset_all_file():
            return False

        _sync_ipset_all_user_backup()
        return True

    except Exception as e:
        log(f"Ошибка sync_ipset_all_after_user_change: {e}", "ERROR")
        return False


def rebuild_ipset_all_files() -> bool:
    """Пересобирает ipset-all.base.txt, ipset-all.user.txt (если отсутствует) и ipset-all.txt."""
    try:
        if not ensure_ipset_all_template_updated():
            return False
        if not _ensure_ipset_all_user_file_exists():
            return False
        if not _write_ipset_all_base_file_from_template():
            return False
        if not _write_combined_ipset_all_file():
            return False

        _sync_ipset_all_user_backup()
        return _count_effective_entries(IPSET_ALL_PATH) > 0

    except Exception as e:
        log(f"Ошибка rebuild_ipset_all_files: {e}", "ERROR")
        return False


def reset_ipset_all_from_template() -> bool:
    """Очищает ipset-all.user.txt и пересобирает ipset-all.txt из базы."""
    try:
        if not ensure_ipset_all_template_updated():
            return False

        _write_text_file(IPSET_ALL_USER_PATH, "")
        _sync_ipset_all_user_backup()

        ok = rebuild_ipset_all_files()
        if ok:
            log("ipset-all.user.txt очищен, ipset-all.txt пересобран из шаблона", "SUCCESS")
        return ok

    except Exception as e:
        log(f"Ошибка сброса ipset-all.user.txt: {e}", "ERROR")
        return False


def _get_default_ipset_ru_base_entries() -> list[str]:
    """Системная база ipset-ru (чистая установка)."""
    return []


def _build_ipset_ru_base_content() -> str:
    lines: list[str] = [ln.rstrip() for ln in _IPSET_RU_BASE_HEADER.split("\n")]
    while lines and not lines[-1]:
        lines.pop()
    lines.extend(_get_default_ipset_ru_base_entries())
    return "\n".join(lines) + "\n"


def _read_ipset_ru_template_content() -> str | None:
    template_path = _get_ipset_ru_template_path()
    if not _has_effective_line(template_path):
        return None
    content = _read_text_file_safe(template_path)
    if content is None:
        return None
    return _normalize_newlines(content)


def _ensure_ipset_ru_base_updated() -> bool:
    try:
        template_content = _read_ipset_ru_template_content()
        expected = template_content if template_content is not None else _build_ipset_ru_base_content()
        current = _read_text_file_safe(IPSET_RU_BASE_PATH)

        if _normalize_newlines(current or "") != _normalize_newlines(expected):
            _write_text_file(IPSET_RU_BASE_PATH, expected)
            if current is None:
                log("Создан ipset-ru.base.txt", "INFO")
            else:
                log("Обновлен ipset-ru.base.txt", "DEBUG")

        return True
    except Exception as e:
        log(f"Ошибка подготовки ipset-ru.base.txt: {e}", "ERROR")
        return False


def _ensure_ipset_ru_user_file_exists() -> bool:
    try:
        os.makedirs(os.path.dirname(IPSET_RU_USER_PATH), exist_ok=True)
        if os.path.exists(IPSET_RU_USER_PATH):
            return True
        _write_text_file(IPSET_RU_USER_PATH, "")
        return True
    except Exception as e:
        log(f"Ошибка подготовки ipset-ru.user.txt: {e}", "ERROR")
        return False


def get_ipset_ru_base_entries() -> list[str]:
    return _read_effective_ip_entries(IPSET_RU_BASE_PATH)


def get_ipset_ru_base_set() -> set[str]:
    return set(get_ipset_ru_base_entries())


def get_user_ipset_ru_entries() -> list[str]:
    return _read_effective_ip_entries(IPSET_RU_USER_PATH)


def _write_combined_ipset_ru_file() -> bool:
    """Generates IPSET_RU_PATH = base + user (dedup, base-first)."""
    try:
        base_entries = get_ipset_ru_base_entries()
        base_set = set(base_entries)
        user_entries = _read_effective_ip_entries(IPSET_RU_USER_PATH)

        combined: list[str] = list(base_entries)
        for entry in user_entries:
            if entry not in base_set:
                combined.append(entry)

        combined = _dedup_preserve_order(combined)
        content = "\n".join(combined) + ("\n" if combined else "")
        _write_text_file(IPSET_RU_PATH, content)
        return True
    except Exception as e:
        log(f"Ошибка генерации ipset-ru.txt: {e}", "ERROR")
        return False


def ensure_ipset_ru_user_file() -> bool:
    """Публичный helper: гарантирует наличие ipset-ru.user.txt."""
    if not _ensure_ipset_ru_base_updated():
        return False
    return _ensure_ipset_ru_user_file_exists()


def sync_ipset_ru_after_user_change() -> bool:
    """Быстрый sync после правки ipset-ru.user.txt."""
    try:
        if not _ensure_ipset_ru_base_updated():
            return False
        if not _ensure_ipset_ru_user_file_exists():
            return False
        return _write_combined_ipset_ru_file()
    except Exception as e:
        log(f"Ошибка sync_ipset_ru_after_user_change: {e}", "ERROR")
        return False


def rebuild_ipset_ru_files() -> bool:
    """Пересобирает ipset-ru.base.txt, ipset-ru.user.txt и ipset-ru.txt."""
    try:
        if not _ensure_ipset_ru_base_updated():
            return False
        if not _ensure_ipset_ru_user_file_exists():
            return False
        if not _write_combined_ipset_ru_file():
            return False
        return True
    except Exception as e:
        log(f"Ошибка rebuild_ipset_ru_files: {e}", "ERROR")
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
