"""Общая сборка итоговых файлов списков."""

from __future__ import annotations

from lists.core.files import write_text_file


def dedup_preserve_order(items: list[str]) -> list[str]:
    """Убирает повторы, сохраняя исходный порядок строк."""
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


def merge_base_and_user(base_entries: list[str], user_entries: list[str]) -> list[str]:
    """Объединяет базовые и пользовательские строки, сохраняя базу первой."""
    base_set = set(base_entries)
    combined: list[str] = list(base_entries)
    for item in user_entries:
        if item not in base_set:
            combined.append(item)
    return dedup_preserve_order(combined)


def build_combined_content(base_entries: list[str], user_entries: list[str]) -> str:
    """Собирает текст итогового файла из базовых и пользовательских строк."""
    combined = merge_base_and_user(base_entries, user_entries)
    return "\n".join(combined) + ("\n" if combined else "")


def write_combined_file(final_path: str, base_entries: list[str], user_entries: list[str]) -> None:
    """Собирает и записывает итоговый файл."""
    write_text_file(final_path, build_combined_content(base_entries, user_entries))
