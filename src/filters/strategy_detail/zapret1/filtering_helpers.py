"""Search/sort helper'ы для страницы деталей стратегии Zapret 1."""

from __future__ import annotations


def normalize_search_text(text: str) -> str:
    return (text or "").strip().lower()


def resolve_sort_mode_change(*, sort_combo, current_sort_mode: str) -> str | None:
    if not sort_combo:
        return None
    mode = sort_combo.currentData()
    mode = str(mode or "recommended")
    if mode == current_sort_mode:
        return None
    return mode
