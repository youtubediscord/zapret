from __future__ import annotations

from typing import Any

from .defaults import COMMON_FOLDER_KEY, PINNED_FOLDER_KEY
from .store import normalize_folder_state


def build_folder_rows(
    state: dict[str, Any],
    *,
    live_items: list[dict[str, Any]],
    include_pinned_folder: bool = False,
    query: str = "",
) -> list[dict[str, Any]]:
    normalized = normalize_folder_state(state, state)
    folders = normalized["folders"]
    item_meta = normalized["items"]
    normalized_query = str(query or "").strip().lower()

    grouped: dict[str, list[dict[str, Any]]] = {key: [] for key in folders}
    pinned_rows: list[dict[str, Any]] = []

    for live_item in live_items:
        key = str(live_item.get("key") or "").strip()
        name = str(live_item.get("name") or key).strip() or key
        if not key:
            continue
        if normalized_query and normalized_query not in name.lower() and normalized_query not in key.lower():
            continue
        meta = dict(item_meta.get(key) or {})
        default_folder_key = str(live_item.get("folder_key") or COMMON_FOLDER_KEY).strip() or COMMON_FOLDER_KEY
        folder_key = str(meta.get("folder_key") or default_folder_key).strip() or COMMON_FOLDER_KEY
        if folder_key not in folders:
            folder_key = COMMON_FOLDER_KEY
        row = {
            "kind": "item",
            "key": key,
            "name": name,
            "folder_key": folder_key,
            "order": meta.get("order"),
            "rating": _item_rating(meta, live_item),
            "pinned": bool(meta.get("pinned", False) or live_item.get("pinned", False)),
            "payload": live_item,
        }
        if include_pinned_folder and row["pinned"]:
            pinned_rows.append(row)
            continue
        grouped.setdefault(folder_key, []).append(row)

    rows: list[dict[str, Any]] = []
    if pinned_rows:
        pinned_meta = folders.get(PINNED_FOLDER_KEY, {})
        pinned_collapsed = bool(pinned_meta.get("collapsed", False)) if isinstance(pinned_meta, dict) else False
        rows.append(
            {
                "kind": "folder",
                "key": PINNED_FOLDER_KEY,
                "name": "Закрепленные",
                "collapsed": pinned_collapsed,
                "system": True,
                "service": True,
                "count": len(pinned_rows),
            }
        )
        if not pinned_collapsed or normalized_query:
            rows.extend(_sort_items(pinned_rows))

    for folder_key, folder in _sort_folders(folders):
        if folder_key == PINNED_FOLDER_KEY:
            continue
        items = _sort_items(grouped.get(folder_key, []))
        if normalized_query and not items:
            continue
        rows.append(
            {
                "kind": "folder",
                "key": folder_key,
                "name": str(folder.get("name") or folder_key),
                "collapsed": bool(folder.get("collapsed", False)),
                "system": bool(folder.get("system", False)),
                "service": False,
                "count": len(items),
            }
        )
        if not bool(folder.get("collapsed", False)) or normalized_query:
            rows.extend(items)

    return rows


def _sort_folders(folders: dict[str, dict[str, Any]]) -> list[tuple[str, dict[str, Any]]]:
    return sorted(
        folders.items(),
        key=lambda pair: (
            int(pair[1].get("order", 0) or 0),
            str(pair[1].get("name") or pair[0]).lower(),
            pair[0],
        ),
    )


def _sort_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        items,
        key=lambda item: (
            0 if item.get("order") is not None else 1,
            int(item.get("order") or 0),
            -int(item.get("rating") or 0),
            str(item.get("name") or "").lower(),
            str(item.get("key") or ""),
        ),
    )


def _item_rating(meta: dict[str, Any], live_item: dict[str, Any]) -> int:
    for source in (meta, live_item):
        try:
            return max(0, min(10, int(source.get("rating", 0) or 0)))
        except Exception:
            continue
    return 0


__all__ = ["build_folder_rows"]
