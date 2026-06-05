from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath, PureWindowsPath
import re
from typing import Any

from profile.match_filters import filter_values


@dataclass(frozen=True)
class ProfileDisplayItem:
    key: str
    persistent_key: str
    profile_index: int
    display_name: str
    enabled: bool
    in_preset: bool
    strategy_id: str
    strategy_name: str
    match_lines: tuple[str, ...]
    list_type: str
    rating: str
    favorite: bool
    group: str
    group_name: str
    order: int
    order_is_manual: bool = False
    group_collapsed: bool = False
    user_profile_id: str = ""


def build_profile_display_items(items: tuple[Any, ...]) -> tuple[ProfileDisplayItem, ...]:
    rows = [_display_item_from_profile(item) for item in tuple(items or ())]
    rows.sort(key=profile_display_sort_key)
    return tuple(rows)


def profile_display_sort_key(item: Any) -> tuple[int, int, int, str, str]:
    order_is_manual = bool(getattr(item, "order_is_manual", False))
    return (
        0 if order_is_manual else 1,
        int(getattr(item, "order", 0) or 0) if order_is_manual else _protocol_sort_rank(tuple(getattr(item, "match_lines", ()) or ())),
        0 if order_is_manual else int(getattr(item, "order", 0) or 0),
        str(getattr(item, "display_name", "") or "").lower(),
        str(getattr(item, "key", "") or ""),
    )


def _display_item_from_profile(item: Any) -> ProfileDisplayItem:
    return ProfileDisplayItem(
        key=str(getattr(item, "key", "") or ""),
        persistent_key=str(getattr(item, "persistent_key", "") or ""),
        profile_index=int(getattr(item, "profile_index", -1) or -1),
        display_name=_logical_display_name(item),
        enabled=bool(getattr(item, "enabled", False)),
        in_preset=bool(getattr(item, "in_preset", False)),
        strategy_id=str(getattr(item, "strategy_id", "") or "none"),
        strategy_name=str(getattr(item, "strategy_name", "") or "Стратегия не выбрана"),
        match_lines=tuple(getattr(item, "match_lines", ()) or ()),
        list_type=str(getattr(item, "list_type", "") or ""),
        rating=str(getattr(item, "rating", "") or ""),
        favorite=bool(getattr(item, "favorite", False)),
        group=str(getattr(item, "group", "") or "common"),
        group_name=str(getattr(item, "group_name", "") or getattr(item, "group", "") or "Общие"),
        order=int(getattr(item, "order", 0) or 0),
        order_is_manual=bool(getattr(item, "order_is_manual", False)),
        group_collapsed=bool(getattr(item, "group_collapsed", False)),
        user_profile_id=str(getattr(item, "user_profile_id", "") or ""),
    )


def _protocol_sort_rank(match_lines: tuple[str, ...]) -> int:
    if filter_values(match_lines, "--filter-tcp"):
        return 0
    if filter_values(match_lines, "--filter-udp") and not filter_values(match_lines, "--filter-l7"):
        return 1
    if filter_values(match_lines, "--filter-l7"):
        return 2
    return 3


def _resource_identity(match_lines: tuple[str, ...], list_type: str) -> str:
    if list_type == "hostlist":
        values = (
            *filter_values(match_lines, "--hostlist"),
            *filter_values(match_lines, "--hostlist-domains"),
        )
    elif list_type == "ipset":
        values = (
            *filter_values(match_lines, "--ipset"),
            *filter_values(match_lines, "--ipset-ip"),
        )
    else:
        values = ()
    if not values:
        return ""
    return _normalize_resource_name(values[0])


def _normalize_resource_name(value: str) -> str:
    text = str(value or "").strip().replace("\\", "/")
    if "/" in text:
        text = PurePosixPath(text).name
    else:
        text = PureWindowsPath(text).name
    text = re.sub(r"\.(txt|lst|list|json)$", "", text, flags=re.IGNORECASE).lower()
    for prefix in ("ipset-", "hostlist-"):
        if text.startswith(prefix):
            text = text[len(prefix):]
    text = re.sub(r"[^a-z0-9а-яё]+", "-", text, flags=re.IGNORECASE).strip("-")
    return text


def _logical_display_name(item: Any) -> str:
    explicit_name = str(getattr(item, "profile_name", "") or "").strip()
    if explicit_name:
        return explicit_name

    list_type = str(getattr(item, "list_type", "") or "").strip().lower()
    identity = _resource_identity(tuple(getattr(item, "match_lines", ()) or ()), list_type)
    known = {
        "youtube": "YouTube",
        "googlevideo": "googlevideo.com",
        "discord": "Discord",
        "discord-updates": "Discord Updates",
        "russia-youtube": "YouTube Russia CDN",
        "russia-youtube-rtmps": "YouTube Russia RTMPS",
    }
    if identity in known:
        return known[identity]
    if identity:
        return identity
    name = str(getattr(item, "display_name", "") or "").strip()
    name = re.sub(r"\s*\((?:IPset|Hostlist)\)\s*", "", name, flags=re.IGNORECASE).strip()
    name = re.sub(r"\s*[•|-]\s*(?:hostlist|ipset)\s+[^|]+", "", name, flags=re.IGNORECASE).strip()
    return name or "Профиль"


__all__ = ["ProfileDisplayItem", "build_profile_display_items", "profile_display_sort_key"]
