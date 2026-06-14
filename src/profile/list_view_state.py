from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from folders.defaults import build_default_profile_folders
from profile.display_items import ProfileDisplayItem, build_profile_display_items, profile_display_sort_key
from profile.icons import resolve_profile_icon
from profile.match_filters import is_voice_match, ports_label_from_match_lines, protocol_label_from_match_lines


@dataclass(slots=True)
class ProfileListViewState:
    all_items: tuple[ProfileDisplayItem, ...]
    profile_items: dict[str, ProfileDisplayItem]
    group_expanded: dict[str, bool]
    active_profile_types: set[str]
    search_query: str
    show_only_added: bool
    rows: list[dict[str, Any]]


def build_profile_list_view_state(
    items: tuple[Any, ...],
    *,
    active_profile_types: set[str] | None = None,
    search_query: str = "",
    show_only_added: bool = False,
    group_expanded: dict[str, bool] | None = None,
    folder_state: dict[str, Any] | None = None,
) -> ProfileListViewState:
    display_items = build_profile_display_items(tuple(items or ()))
    display_items = apply_profile_folder_state_to_items(display_items, folder_state)
    active = _normalized_profile_types(active_profile_types)
    normalized_search = _normalized_search_query(search_query)
    next_group_expanded = dict(group_expanded or _initial_group_expanded(display_items))
    for item in display_items:
        next_group_expanded.setdefault(str(item.group or "common"), True)
    return ProfileListViewState(
        all_items=display_items,
        profile_items={item.key: item for item in display_items},
        group_expanded=next_group_expanded,
        active_profile_types=active,
        search_query=normalized_search,
        show_only_added=bool(show_only_added),
        rows=_build_profile_rows_from(
            display_items,
            next_group_expanded,
            active_profile_types=active,
            search_query=normalized_search,
            show_only_added=bool(show_only_added),
        ),
    )


def apply_profile_folder_state_to_items(
    items: tuple[ProfileDisplayItem, ...],
    folder_state: dict[str, Any] | None,
) -> tuple[ProfileDisplayItem, ...]:
    if not isinstance(folder_state, dict):
        return tuple(items or ())

    from profile.folders import profile_folder_collapsed, profile_folder_for_profile

    next_items: list[ProfileDisplayItem] = []
    for item in tuple(items or ()):
        folder_key, folder_name, order = profile_folder_for_profile(item, folder_state)
        next_items.append(
            replace(
                item,
                group=folder_key,
                group_name=folder_name,
                order=int(order) if order is not None else int(item.order or 0),
                order_is_manual=order is not None,
                group_collapsed=profile_folder_collapsed(folder_key, folder_state),
            )
        )
    return tuple(sorted(next_items, key=profile_display_sort_key))


def row_for_profile(item: ProfileDisplayItem) -> dict[str, Any]:
    match_lines = tuple(item.match_lines or ())
    ports = ports_label_from_match_lines(match_lines)
    description_parts = [
        part
        for part in (
            protocol_label_from_match_lines(match_lines),
            f"порты: {ports}" if ports else "",
        )
        if part
    ]
    tooltip = match_summary(item)
    if not item.in_preset:
        tooltip = f"{tooltip}\nПрофиля ещё нет в пресете. Включите его или выберите готовую стратегию."
    elif not item.enabled:
        tooltip = f"{tooltip}\nПрофиль есть в пресете, но сейчас выключен. В файле это записано через --skip."
    icon = resolve_profile_icon(item.display_name, match_lines)
    return {
        "kind": "profile",
        "key": item.key,
        "persistent_key": item.persistent_key,
        "display_name": item.display_name,
        "description": " | ".join(description_parts),
        "strategy_id": item.strategy_id,
        "strategy_name": item.strategy_name,
        "match_lines": match_lines,
        "list_type": item.list_type,
        "rating": item.rating,
        "favorite": item.favorite,
        "in_preset": item.in_preset,
        "enabled": item.enabled,
        "group": item.group,
        "group_name": item.group_name,
        "icon_name": icon.icon_name,
        "icon_color": icon.color if item.in_preset else "#888888",
        "tooltip": tooltip,
    }


def build_profile_rows_from(
    items: tuple[ProfileDisplayItem, ...],
    group_expanded: dict[str, bool],
    *,
    active_profile_types: set[str],
    search_query: str,
    show_only_added: bool = False,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    grouped = grouped_items(items)
    if not grouped:
        return rows
    for group_key in ordered_group_keys(grouped):
        group_items = tuple(
            item
            for item in grouped.get(group_key, ())
            if profile_matches_filter(
                item,
                active_profile_types=active_profile_types,
                search_query=search_query,
                show_only_added=show_only_added,
            )
        )
        if not group_items:
            continue
        group_items = tuple(sorted(group_items, key=profile_display_sort_key))
        group_name = str(group_items[0].group_name or group_key.title())
        expanded = group_expanded.get(group_key, True)
        rows.append({
            "kind": "folder",
            "group": group_key,
            "group_name": group_name,
            "collapsed": not expanded,
            "count": len(group_items),
        })
        if not expanded:
            continue
        rows.extend(row_for_profile(item) for item in group_items)
    return rows


def profile_matches_filter(
    item: ProfileDisplayItem,
    *,
    active_profile_types: set[str],
    search_query: str,
    show_only_added: bool = False,
) -> bool:
    if bool(show_only_added) and not bool(getattr(item, "in_preset", False)):
        return False
    return profile_matches_type_filter(item, active_profile_types) and profile_matches_search_query(item, search_query)


def profile_matches_type_filter(item: ProfileDisplayItem, active_profile_types: set[str]) -> bool:
    if "all" in active_profile_types:
        return True
    match_lines = tuple(item.match_lines or ())
    protocol = protocol_label_from_match_lines(match_lines).upper()
    summary = match_summary(item)
    text = f"{item.display_name} {summary} {item.group}".lower()
    if "tcp" in active_profile_types and "TCP" in protocol:
        return True
    if "udp" in active_profile_types and ("UDP" in protocol or "L7" in protocol):
        return True
    if "discord" in active_profile_types and "discord" in text:
        return True
    if "voice" in active_profile_types and is_voice_match(match_lines):
        return True
    if "games" in active_profile_types and "game" in text:
        return True
    return False


def profile_matches_search_query(item: ProfileDisplayItem, search_query: str) -> bool:
    query = str(search_query or "")
    if not query:
        return True
    search_text = profile_search_text(item)
    return all(part in search_text for part in query.split())


def normalized_profile_types(profile_types: set[str] | None) -> set[str]:
    active = {str(value) for value in (profile_types or {"all"}) if str(value or "").strip()}
    if not active:
        active = {"all"}
    return active


def normalized_search_query(query: str | None) -> str:
    return " ".join(str(query or "").strip().lower().split())


def grouped_items(items: tuple[ProfileDisplayItem, ...]) -> dict[str, list[ProfileDisplayItem]]:
    grouped: dict[str, list[ProfileDisplayItem]] = {}
    for item in tuple(items or ()):
        group_key = str(item.group or "common")
        grouped.setdefault(group_key, []).append(item)
    return grouped


def initial_group_expanded(items: tuple[ProfileDisplayItem, ...]) -> dict[str, bool]:
    result: dict[str, bool] = {}
    for item in tuple(items or ()):
        group_key = str(item.group or "common")
        result.setdefault(group_key, not bool(item.group_collapsed))
    return result


def ordered_group_keys(grouped: dict[str, list[ProfileDisplayItem]]) -> list[str]:
    default_state = build_default_profile_folders()
    folders = default_state.get("folders", {})
    order_by_key = {
        str(key): folder_order(folder.get("order"))
        for key, folder in folders.items()
        if isinstance(folder, dict)
    }
    return sorted(grouped, key=lambda key: (order_by_key.get(str(key), 10_000), str(key).lower()))


def group_name_for_key(group_key: str, items: tuple[ProfileDisplayItem, ...]) -> str:
    key = str(group_key or "").strip() or "common"
    for item in tuple(items or ()):
        if str(item.group or "common") == key and str(item.group_name or "").strip():
            return str(item.group_name or "").strip()
    folder = build_default_profile_folders().get("folders", {}).get(key)
    if isinstance(folder, dict):
        return str(folder.get("name") or key)
    return key.title()


def folder_order(value: object) -> int:
    try:
        return int(value)
    except Exception:
        return 10_000


def match_summary(item: ProfileDisplayItem) -> str:
    parts = [
        part
        for part in (
            protocol_label_from_match_lines(tuple(item.match_lines or ())),
            ports_label_from_match_lines(tuple(item.match_lines or ())),
            item.list_type,
        )
        if part
    ]
    return " • ".join(parts) or "без явных условий"


def profile_search_text(item: ProfileDisplayItem) -> str:
    match_lines = tuple(item.match_lines or ())
    parts = [
        item.display_name,
        item.group,
        item.group_name,
        item.strategy_id,
        item.strategy_name,
        item.list_type,
        match_summary(item),
        " ".join(match_lines),
    ]
    return " ".join(str(part or "") for part in parts).lower()


_build_profile_rows_from = build_profile_rows_from
_folder_order = folder_order
_group_name_for_key = group_name_for_key
_grouped_items = grouped_items
_initial_group_expanded = initial_group_expanded
_match_summary = match_summary
_normalized_profile_types = normalized_profile_types
_normalized_search_query = normalized_search_query
_ordered_group_keys = ordered_group_keys
_profile_matches_filter = profile_matches_filter
_profile_matches_search_query = profile_matches_search_query
_profile_matches_type_filter = profile_matches_type_filter
_profile_search_text = profile_search_text
_row_for_profile = row_for_profile


__all__ = [
    "ProfileListViewState",
    "build_profile_list_view_state",
    "build_profile_rows_from",
    "group_name_for_key",
    "grouped_items",
    "initial_group_expanded",
    "normalized_profile_types",
    "normalized_search_query",
    "ordered_group_keys",
    "profile_matches_filter",
    "profile_matches_search_query",
    "profile_matches_type_filter",
    "profile_search_text",
    "row_for_profile",
]
