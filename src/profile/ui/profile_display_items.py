from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath, PureWindowsPath
import re
from typing import Any

from profile.match_filters import filter_values


@dataclass(frozen=True)
class ProfileDisplayVariant:
    filter_kind: str
    label: str


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
    order: int
    variants: tuple[ProfileDisplayVariant, ...]


def build_profile_display_items(items: tuple[Any, ...]) -> tuple[ProfileDisplayItem, ...]:
    rows = [_display_item_from_profile(item) for item in tuple(items or ())]
    rows.sort(key=lambda item: (item.order, item.display_name.lower(), item.key))
    return tuple(rows)


def _display_item_from_profile(item: Any) -> ProfileDisplayItem:
    variants = _variants_for_item(item)
    return ProfileDisplayItem(
        key=str(getattr(item, "key", "") or ""),
        persistent_key=str(getattr(item, "persistent_key", "") or ""),
        profile_index=int(getattr(item, "profile_index", -1) or -1),
        display_name=_logical_display_name(item),
        enabled=bool(getattr(item, "enabled", False)),
        in_preset=bool(getattr(item, "in_preset", False)),
        strategy_id=str(getattr(item, "strategy_id", "") or "none"),
        strategy_name=str(getattr(item, "strategy_name", "") or "Отключено"),
        match_lines=tuple(getattr(item, "match_lines", ()) or ()),
        list_type=str(getattr(item, "list_type", "") or ""),
        rating=str(getattr(item, "rating", "") or ""),
        favorite=bool(getattr(item, "favorite", False)),
        group=_display_group(item),
        order=int(getattr(item, "order", 0) or 0),
        variants=variants,
    )


def _variants_for_item(item: Any) -> tuple[ProfileDisplayVariant, ...]:
    if not bool(getattr(item, "in_preset", False)):
        return ()
    list_type = str(getattr(item, "list_type", "") or "").strip().lower()
    match_lines = tuple(getattr(item, "match_lines", ()) or ())
    if list_type not in {"hostlist", "ipset"} or not _has_file_based_filter(match_lines, list_type):
        return ()
    return (
        ProfileDisplayVariant(filter_kind="hostlist", label="Hostlist"),
        ProfileDisplayVariant(filter_kind="ipset", label="IPset"),
    )


def _display_group(item: Any) -> str:
    if bool(getattr(item, "in_preset", False)):
        return "current"
    return str(getattr(item, "group", "") or "default")


def _has_file_based_filter(match_lines: tuple[str, ...], list_type: str) -> bool:
    prefix = "--hostlist=" if list_type == "hostlist" else "--ipset="
    return any(str(line or "").strip().lower().startswith(prefix) for line in match_lines)


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


__all__ = ["ProfileDisplayItem", "ProfileDisplayVariant", "build_profile_display_items"]
