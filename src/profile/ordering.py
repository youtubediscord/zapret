"""Единый источник истины для порядка профилей внутри папок.

Адаптер над generic-ядром `folders.ordering`: и отображение, и планирование
перемещений (оптимистичное в UI и персист в сервисе) обязаны проходить через
этот модуль. Без Qt и без I/O.
"""
from __future__ import annotations

from typing import Any

from folders.defaults import build_default_profile_folders, classify_profile_folder
from folders.ordering import FolderOrderView, plan_item_move, resolve_folder_order
from folders.store import normalize_folder_state
from profile.identity import is_profile_uid
from profile.match_filters import filter_values


def live_items_from_sources(sources: tuple[Any, ...]) -> list[dict[str, Any]]:
    """ProfileListSource (сервисный путь: пресет + шаблоны) -> generic live_items."""
    live_items: list[dict[str, Any]] = []
    for source in tuple(sources or ()):
        profile = getattr(source, "profile", None)
        if profile is None:
            continue
        try:
            match_lines = tuple(str(line or "") for line in profile.match.all_lines())
        except Exception:
            match_lines = ()
        name = str(
            getattr(source, "resolved_display_name", "")
            or getattr(profile, "display_name", "")
            or getattr(profile, "name", "")
            or ""
        ).strip()
        live_items.append(
            _live_item(
                persistent_key=str(getattr(profile, "persistent_key", "") or "").strip(),
                name=name,
                match_lines=match_lines,
                fallback_index=int(getattr(source, "order", 0) or 0),
                classification_extra=str(getattr(profile, "name", "") or ""),
            )
        )
    return [item for item in live_items if item["key"]]


def live_items_from_display_items(items: tuple[Any, ...]) -> list[dict[str, Any]]:
    """ProfileDisplayItem/ProfileListItem (UI-путь) -> generic live_items."""
    live_items: list[dict[str, Any]] = []
    for item in tuple(items or ()):
        key = str(getattr(item, "persistent_key", "") or "").strip()
        if not key:
            continue
        match_lines = tuple(getattr(item, "match_lines", ()) or ())
        live_items.append(
            _live_item(
                persistent_key=key,
                name=str(getattr(item, "display_name", "") or "").strip(),
                match_lines=match_lines,
                fallback_index=int(getattr(item, "source_order", getattr(item, "profile_index", 0)) or 0),
                classification_extra=str(getattr(item, "profile_name", "") or ""),
            )
        )
    return live_items


def resolve_profile_order_view(live_items: list[dict[str, Any]], folder_state: dict[str, Any] | None) -> FolderOrderView:
    return resolve_folder_order(_normalized_state(folder_state), live_items)


def plan_profile_move(
    live_items: list[dict[str, Any]],
    folder_state: dict[str, Any] | None,
    *,
    action: str,
    source_key: str,
    destination_key: str = "",
    destination_folder_key: str = "",
) -> dict[str, Any] | None:
    return plan_item_move(
        _normalized_state(folder_state),
        live_items,
        action=action,
        source_key=source_key,
        destination_key=destination_key,
        destination_folder_key=destination_folder_key,
    )


def protocol_sort_rank(match_lines: tuple[str, ...]) -> int:
    if filter_values(match_lines, "--filter-tcp"):
        return 0
    if filter_values(match_lines, "--filter-udp") and not filter_values(match_lines, "--filter-l7"):
        return 1
    if filter_values(match_lines, "--filter-l7"):
        return 2
    return 3


def _live_item(
    *,
    persistent_key: str,
    name: str,
    match_lines: tuple[str, ...],
    fallback_index: int,
    classification_extra: str = "",
) -> dict[str, Any]:
    # Стабильные uid-ключи не несут классификационного сигнала; контентные
    # ключи (шаблоны, legacy) содержат имена hostlist-ов и остаются в тексте.
    key_text = "" if is_profile_uid(persistent_key) else persistent_key
    classification_text = " ".join(
        part for part in (name, classification_extra, key_text, " ".join(match_lines)) if part
    )
    folder_key = classify_profile_folder(classification_text)
    return {
        "key": persistent_key,
        "name": name,
        "folder_key": folder_key,
        "manual_tie": (),
        "auto_rank": (
            _profile_folder_tail_rank(folder_key, classification_text),
            protocol_sort_rank(match_lines),
            fallback_index,
        ),
    }


def _profile_folder_tail_rank(folder_key: str, classification_text: str) -> int:
    if folder_key == "discord" and "vencord" in classification_text.lower():
        return 1
    return 0


def _normalized_state(folder_state: dict[str, Any] | None) -> dict[str, Any]:
    return normalize_folder_state(folder_state, build_default_profile_folders())


__all__ = [
    "live_items_from_display_items",
    "live_items_from_sources",
    "plan_profile_move",
    "protocol_sort_rank",
    "resolve_profile_order_view",
]
