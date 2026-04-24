"""Общие файловые helper-функции для списков."""

from __future__ import annotations

import os


def normalize_newlines(text: str) -> str:
    """Приводит переводы строк к `\\n` и добавляет финальный перевод строки."""
    normalized = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    if normalized and not normalized.endswith("\n"):
        normalized += "\n"
    return normalized


def read_text_file(path: str) -> str:
    """Читает текстовый файл как UTF-8."""
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def read_text_file_safe(path: str) -> str | None:
    """Пытается прочитать текстовый файл и возвращает `None` при ошибке."""
    try:
        return read_text_file(path)
    except Exception:
        return None


def write_text_file(path: str, content: str) -> None:
    """Записывает текстовый файл в UTF-8 и создаёт родительскую папку при необходимости."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(normalize_newlines(content))


def ensure_user_file_exists(user_path: str) -> bool:
    """Гарантирует наличие user-файла внутри `lists`."""
    try:
        os.makedirs(os.path.dirname(user_path), exist_ok=True)

        if os.path.exists(user_path):
            return True

        write_text_file(user_path, "")
        return True
    except Exception:
        return False


def prepare_user_file(
    user_path: str,
    *,
    error_message: str | None = None,
    log_func=None,
) -> bool:
    """Готовит user-файл и пишет лог при ошибке."""
    try:
        return ensure_user_file_exists(user_path)
    except Exception as exc:
        if error_message and log_func is not None:
            log_func(f"{error_message}: {exc}", "ERROR")
        return False
