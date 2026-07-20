"""Канонические пути для файлов списков рядом с программой."""

from __future__ import annotations

import os

from config.runtime_layout import APPLICATION_PATHS


def get_lists_dir() -> str:
    """Возвращает папку `lists` рядом с программой."""
    return str(APPLICATION_PATHS.lists_dir)


def get_lists_base_dir() -> str:
    """Возвращает папку `lists/base` с системными базами."""
    return str(APPLICATION_PATHS.lists_base_dir)


def get_lists_user_dir() -> str:
    """Возвращает папку `lists/user` с пользовательскими правками."""
    return str(APPLICATION_PATHS.lists_user_dir)


def get_list_path(file_name: str) -> str:
    """Возвращает путь файла из канонической папки `lists`."""
    return os.path.join(get_lists_dir(), file_name)


def get_list_base_path(list_name: str) -> str:
    """Возвращает путь файла `<name>.txt` из папки `lists/base`."""
    return os.path.join(get_lists_base_dir(), f"{list_name}.txt")


def get_list_user_path(list_name: str) -> str:
    """Возвращает путь файла `<name>.txt` из папки `lists/user`."""
    return os.path.join(get_lists_user_dir(), f"{list_name}.txt")


def get_list_final_path(list_name: str) -> str:
    """Возвращает путь итогового файла `<name>.txt` из папки `lists`."""
    return get_list_path(f"{list_name}.txt")
