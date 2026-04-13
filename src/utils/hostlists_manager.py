# utils/hostlists_manager.py
"""Менеджер hostlist-файлов.

Файлы в папке приложения (рядом с Zapret.exe):
- `lists/other.base.txt` : база (системный шаблон; пересоздаётся автоматически)
- `lists/other.user.txt` : пользовательский файл (редактируется пользователем)
- `lists/other.txt`      : итоговый файл для движка (base + user), генерируется автоматически

Шаблон базы хранится в `%APPDATA%/zapret/lists_template/other.txt`.
Для защиты от обновлений/portable-сценариев пользовательский файл дополнительно
копируется в `%APPDATA%/zapret/lists_backup/other.user.txt`.

Примечание:
Поддерживается только новая модель:
- `other.base.txt` как системная база;
- `other.user.txt` как пользовательский файл;
- `other.txt` как автоматически собираемый итоговый файл для движка.
"""

from __future__ import annotations

import os

from log.log import log

from config.config import (

    OTHER_PATH,
    OTHER_BASE_PATH,
    OTHER_USER_PATH,
    get_other_template_path,
    get_other_user_backup_path,
)


def _fallback_base_domains() -> list[str]:
    return ["youtube.com", "googlevideo.com", "discord.com", "discord.gg"]


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


def _dedup_preserve_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for x in items:
        if x in seen:
            continue
        seen.add(x)
        out.append(x)
    return out


def ensure_other_template_updated() -> bool:
    """Гарантирует валидный системный шаблон other.txt в lists_template."""
    try:
        template_path = get_other_template_path()

        if _count_effective_entries(template_path) > 0:
            return True

        fallback_content = "\n".join(sorted(set(_fallback_base_domains()))) + "\n"
        _write_text_file(template_path, fallback_content)
        log("Создан аварийный шаблон other.txt", "WARNING")
        return True

    except Exception as e:
        log(f"Ошибка обновления шаблона other.txt: {e}", "ERROR")
        return False


def get_base_domains() -> list[str]:
    """Возвращает базовые домены из шаблона или аварийного минимума."""
    template_domains = _read_effective_entries(get_other_template_path())
    if template_domains:
        return template_domains

    log("WARNING: Не найден валидный шаблон other.txt, использую аварийный минимум", "WARNING")
    return _fallback_base_domains()


def get_base_domains_set() -> set[str]:
    """Возвращает set базовых доменов (lowercase)."""
    return {d.strip().lower() for d in get_base_domains() if d and d.strip()}


def get_user_domains() -> list[str]:
    """Возвращает effective-строки (без комментариев) из other.user.txt."""
    return _read_effective_entries(OTHER_USER_PATH)


def build_other_template_content() -> str:
    """Формирует содержимое системного шаблона other.txt."""
    template_path = get_other_template_path()
    if os.path.exists(template_path):
        try:
            content = _read_text_file(template_path)
            if _read_effective_entries(template_path):
                return _normalize_newlines(content)
        except Exception:
            pass

    domains = sorted(set(_fallback_base_domains()))
    return "\n".join(domains) + "\n"

def _ensure_user_file_exists() -> bool:
    """Ensures OTHER_USER_PATH exists; restores/migrates only if missing."""
    try:
        os.makedirs(os.path.dirname(OTHER_USER_PATH), exist_ok=True)

        if os.path.exists(OTHER_USER_PATH):
            return True

        # 1) New backup (raw user file).
        new_bkp = get_other_user_backup_path()
        if os.path.exists(new_bkp):
            content = _read_text_file_safe(new_bkp)
            if content is not None:
                _write_text_file(OTHER_USER_PATH, content)
                log("other.user.txt восстановлен из backup", "SUCCESS")
                return True

        # Nothing to restore: create empty user file.
        _write_text_file(OTHER_USER_PATH, "")
        return True

    except Exception as e:
        log(f"Ошибка подготовки other.user.txt: {e}", "ERROR")
        return False


def _write_base_file_from_template() -> bool:
    """Writes OTHER_BASE_PATH from the current template (raw)."""
    try:
        if not ensure_other_template_updated():
            return False

        template_content = _read_text_file_safe(get_other_template_path())
        if template_content is None:
            template_content = "\n".join(get_base_domains()) + "\n"
        _write_text_file(OTHER_BASE_PATH, template_content)
        return True

    except Exception as e:
        log(f"Ошибка обновления other.base.txt: {e}", "ERROR")
        return False


def _write_combined_other_file() -> bool:
    """Generates OTHER_PATH = base + user (dedup)."""
    try:
        base_entries = get_base_domains()
        base_set = set(base_entries)
        user_entries = _read_effective_entries(OTHER_USER_PATH)

        combined: list[str] = list(base_entries)
        for e in user_entries:
            if e not in base_set:
                combined.append(e)

        combined = _dedup_preserve_order(combined)
        content = "\n".join(combined) + ("\n" if combined else "")
        _write_text_file(OTHER_PATH, content)
        return True

    except Exception as e:
        log(f"Ошибка генерации other.txt: {e}", "ERROR")
        return False


def _sync_user_backup() -> None:
    """Saves raw user file to the new backup path."""
    try:
        content = _read_text_file_safe(OTHER_USER_PATH)
        if content is None:
            return
        _write_text_file(get_other_user_backup_path(), content)
    except Exception:
        pass


def rebuild_other_files() -> bool:
    """Пересобирает other.base.txt, other.user.txt (если отсутствует) и other.txt."""
    try:
        if not ensure_other_template_updated():
            return False
        if not _ensure_user_file_exists():
            return False
        if not _write_base_file_from_template():
            return False
        if not _write_combined_other_file():
            return False

        _sync_user_backup()
        return _count_effective_entries(OTHER_PATH) > 0

    except Exception as e:
        log(f"Ошибка rebuild_other_files: {e}", "ERROR")
        return False


def reset_other_file_from_template() -> bool:
    """Очищает other.user.txt и пересобирает other.txt из базы."""
    try:
        if not ensure_other_template_updated():
            return False

        _write_text_file(OTHER_USER_PATH, "")
        _sync_user_backup()

        ok = rebuild_other_files()
        if ok:
            log("other.user.txt очищен, other.txt пересобран из шаблона", "SUCCESS")
        return ok

    except Exception as e:
        log(f"Ошибка сброса my hostlist: {e}", "ERROR")
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
