"""Общий runtime-helper для списков по схеме base/user/final."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from lists.core.builders import write_combined_file
from lists.core.files import prepare_user_file, write_text_file


@dataclass(frozen=True)
class LayeredListPaths:
    base_path: str
    user_path: str
    final_path: str


def ensure_user_layer(paths: LayeredListPaths, *, error_message: str, log_func) -> bool:
    """Гарантирует наличие пользовательского файла."""
    return prepare_user_file(paths.user_path, error_message=error_message, log_func=log_func)


def rebuild_layered_list(
    paths: LayeredListPaths,
    *,
    get_base_entries: Callable[[], list[str]],
    read_entries: Callable[[str], list[str]],
    log_func,
    user_error_message: str,
    final_error_label: str,
    require_non_empty: bool = False,
) -> bool:
    """Пересобирает итоговый файл из системной базы и user-слоя."""
    if not ensure_user_layer(paths, error_message=user_error_message, log_func=log_func):
        return False

    try:
        write_combined_file(paths.final_path, get_base_entries(), read_entries(paths.user_path))
    except Exception as exc:
        log_func(f"{final_error_label}: {exc}", "ERROR")
        return False

    if require_non_empty:
        return bool(read_entries(paths.final_path))
    return True


def reset_user_layer(
    paths: LayeredListPaths,
    *,
    rebuild_fn: Callable[[], bool],
    log_func,
    reset_error_label: str,
    success_message: str,
) -> bool:
    """Очищает user-слой и пересобирает итоговый файл."""
    try:
        write_text_file(paths.user_path, "")
        ok = rebuild_fn()
        if ok:
            log_func(success_message, "SUCCESS")
        return ok
    except Exception as exc:
        log_func(f"{reset_error_label}: {exc}", "ERROR")
        return False
