from __future__ import annotations

from typing import Any

from folders.defaults import COMMON_FOLDER_KEY, PINNED_FOLDER_KEY, build_default_preset_folders, classify_preset_folder
from folders.ordering import build_folder_rows
from folders.store import FolderLibraryStore, normalize_folder_state
from settings import store as settings_store
from settings.mode import ENGINE_WINWS1, ENGINE_WINWS2


def load_preset_folder_state(scope_key: str) -> dict[str, Any]:
    scope = _normalize_scope(scope_key)
    folders = settings_store.get_folders_settings()
    presets = folders.get("presets", {}) if isinstance(folders, dict) else {}
    raw_state = presets.get(scope) if isinstance(presets, dict) else None
    return normalize_folder_state(raw_state, build_default_preset_folders(scope))


def save_preset_folder_state(scope_key: str, state: dict[str, Any]) -> dict[str, Any]:
    scope = _normalize_scope(scope_key)
    folders = settings_store.get_folders_settings()
    presets = folders.get("presets", {}) if isinstance(folders, dict) else {}
    if not isinstance(presets, dict):
        presets = {}
    presets[scope] = normalize_folder_state(state, build_default_preset_folders(scope))
    folders["presets"] = presets
    return settings_store.set_folders_settings(folders)["presets"][scope]


def create_preset_folder(scope_key: str, name: str) -> str:
    state = load_preset_folder_state(scope_key)
    scope = _normalize_scope(scope_key)
    store = FolderLibraryStore(state, default_state=build_default_preset_folders(scope))
    folder_key = store.create_folder_after(name, COMMON_FOLDER_KEY)
    save_preset_folder_state(scope_key, store.to_dict())
    return folder_key


def rename_preset_folder(scope_key: str, folder_key: str, name: str) -> bool:
    state = load_preset_folder_state(scope_key)
    scope = _normalize_scope(scope_key)
    store = FolderLibraryStore(state, default_state=build_default_preset_folders(scope))
    if not store.rename_folder(folder_key, name):
        return False
    save_preset_folder_state(scope_key, store.to_dict())
    return True


def delete_preset_folder(scope_key: str, folder_key: str) -> bool:
    state = load_preset_folder_state(scope_key)
    scope = _normalize_scope(scope_key)
    store = FolderLibraryStore(state, default_state=build_default_preset_folders(scope))
    if not store.delete_folder(folder_key):
        return False
    save_preset_folder_state(scope_key, store.to_dict())
    return True


def move_preset_folder_by_step(scope_key: str, folder_key: str, direction: int) -> bool:
    state = load_preset_folder_state(scope_key)
    scope = _normalize_scope(scope_key)
    store = FolderLibraryStore(state, default_state=build_default_preset_folders(scope))
    if not store.move_folder_by_step(folder_key, direction):
        return False
    save_preset_folder_state(scope_key, store.to_dict())
    return True


def set_preset_folder_collapsed(scope_key: str, folder_key: str, collapsed: bool) -> bool:
    state = load_preset_folder_state(scope_key)
    if str(folder_key or "").strip() == PINNED_FOLDER_KEY:
        next_collapsed = bool(collapsed)
        folder = state.setdefault("folders", {}).get(PINNED_FOLDER_KEY)
        if isinstance(folder, dict) and bool(folder.get("collapsed", False)) == next_collapsed:
            return False
        state.setdefault("folders", {})[PINNED_FOLDER_KEY] = {
            "name": "Закрепленные",
            "order": -1,
            "collapsed": next_collapsed,
            "system": True,
        }
        save_preset_folder_state(scope_key, state)
        return True
    scope = _normalize_scope(scope_key)
    store = FolderLibraryStore(state, default_state=build_default_preset_folders(scope))
    if not store.set_folder_collapsed(folder_key, collapsed):
        return False
    save_preset_folder_state(scope_key, store.to_dict())
    return True


def reset_preset_folders(scope_key: str) -> dict[str, Any]:
    scope = _normalize_scope(scope_key)
    default_state = build_default_preset_folders(scope)
    current_state = load_preset_folder_state(scope)
    if current_state == normalize_folder_state(default_state, default_state):
        return current_state
    return save_preset_folder_state(scope, default_state)


def move_preset_to_folder(scope_key: str, file_name: str, folder_key: str) -> bool:
    state = load_preset_folder_state(scope_key)
    scope = _normalize_scope(scope_key)
    key = str(file_name or "").strip()
    if not key:
        return False
    folders = state.get("folders", {})
    target_folder = str(folder_key or "").strip() or COMMON_FOLDER_KEY
    if not isinstance(folders, dict) or target_folder not in folders:
        target_folder = COMMON_FOLDER_KEY
    current_meta = state.get("items", {}).get(key) if isinstance(state.get("items"), dict) else None
    store = FolderLibraryStore(state, default_state=build_default_preset_folders(scope))
    if not store.set_item_folder(key, target_folder):
        if isinstance(current_meta, dict):
            return False
        next_state = store.to_dict()
        next_state.setdefault("items", {})[key] = {"folder_key": target_folder, "order": None, "rating": 0}
    else:
        next_state = store.to_dict()
    _move_item_to_end(next_state, key, target_folder)
    if next_state == normalize_folder_state(state, build_default_preset_folders(scope)):
        return False
    save_preset_folder_state(scope_key, next_state)
    return True


def move_preset_before(
    scope_key: str,
    source_file_name: str,
    destination_file_name: str,
    *,
    destination_folder_key: str = "",
) -> bool:
    state = load_preset_folder_state(scope_key)
    source = str(source_file_name or "").strip()
    destination = str(destination_file_name or "").strip()
    items = state.setdefault("items", {})
    if not source or not destination or source == destination:
        return False
    scope = _normalize_scope(scope_key)
    before_state = normalize_folder_state(state, build_default_preset_folders(scope))
    destination_meta = items.setdefault(destination, {"folder_key": "common", "order": None, "rating": 0})
    folder_key = str(destination_folder_key or destination_meta.get("folder_key") or "common")
    destination_meta["folder_key"] = folder_key
    source_meta = items.setdefault(source, {"folder_key": folder_key, "order": None, "rating": 0})
    source_meta["folder_key"] = folder_key
    ordered = [
        key
        for key, meta in _ordered_item_meta(items)
        if str(meta.get("folder_key") or "common") == folder_key and key != source
    ]
    if destination not in ordered:
        ordered.append(destination)
    ordered.insert(ordered.index(destination), source)
    for index, key in enumerate(ordered):
        items.setdefault(key, {"folder_key": folder_key, "order": None, "rating": 0})["order"] = index
    if normalize_folder_state(state, build_default_preset_folders(scope)) == before_state:
        return False
    save_preset_folder_state(scope_key, state)
    return True


def move_preset_after(
    scope_key: str,
    source_file_name: str,
    destination_file_name: str,
    *,
    destination_folder_key: str = "",
) -> bool:
    state = load_preset_folder_state(scope_key)
    source = str(source_file_name or "").strip()
    destination = str(destination_file_name or "").strip()
    items = state.setdefault("items", {})
    if not source or not destination or source == destination:
        return False
    scope = _normalize_scope(scope_key)
    before_state = normalize_folder_state(state, build_default_preset_folders(scope))
    destination_meta = items.setdefault(destination, {"folder_key": "common", "order": None, "rating": 0})
    folder_key = str(destination_folder_key or destination_meta.get("folder_key") or "common")
    destination_meta["folder_key"] = folder_key
    source_meta = items.setdefault(source, {"folder_key": folder_key, "order": None, "rating": 0})
    source_meta["folder_key"] = folder_key
    ordered = [
        key
        for key, meta in _ordered_item_meta(items)
        if str(meta.get("folder_key") or "common") == folder_key and key != source
    ]
    if destination not in ordered:
        ordered.append(destination)
    ordered.insert(ordered.index(destination) + 1, source)
    for index, key in enumerate(ordered):
        items.setdefault(key, {"folder_key": folder_key, "order": None, "rating": 0})["order"] = index
    if normalize_folder_state(state, build_default_preset_folders(scope)) == before_state:
        return False
    save_preset_folder_state(scope_key, state)
    return True


def move_preset_to_end(scope_key: str, file_name: str) -> bool:
    state = load_preset_folder_state(scope_key)
    source = str(file_name or "").strip()
    items = state.setdefault("items", {})
    if not source:
        return False
    scope = _normalize_scope(scope_key)
    before_state = normalize_folder_state(state, build_default_preset_folders(scope))
    meta = items.setdefault(source, {"folder_key": "common", "order": None, "rating": 0})
    folder_key = str(meta.get("folder_key") or "common")
    _move_item_to_end(state, source, folder_key)
    if normalize_folder_state(state, build_default_preset_folders(scope)) == before_state:
        return False
    save_preset_folder_state(scope_key, state)
    return True


def move_preset_by_step(
    scope_key: str,
    file_name: str,
    direction: int,
    *,
    live_items: list[dict[str, Any]],
) -> bool:
    source = str(file_name or "").strip()
    if not source:
        return False
    step = 1 if int(direction or 0) > 0 else -1
    state = load_preset_folder_state(scope_key)
    rows = build_folder_rows(
        state,
        live_items=live_items,
        include_pinned_folder=True,
    )
    ordered = [
        str(row.get("key") or "").strip()
        for row in rows
        if row.get("kind") == "item" and str(row.get("key") or "").strip()
    ]
    if source not in ordered:
        return False
    index = ordered.index(source)
    target_index = index + step
    if target_index < 0 or target_index >= len(ordered):
        return False
    if step < 0:
        return move_preset_before(scope_key, source, ordered[target_index])

    without_source = [key for key in ordered if key != source]
    target = ordered[target_index]
    after_target_index = without_source.index(target) + 1
    if after_target_index < len(without_source):
        return move_preset_before(scope_key, source, without_source[after_target_index])
    return move_preset_to_end(scope_key, source)


def get_preset_item_meta(scope_key: str, file_name: str) -> dict[str, Any]:
    state = load_preset_folder_state(scope_key)
    key = str(file_name or "").strip()
    meta = state.get("items", {}).get(key) if key else None
    if not isinstance(meta, dict):
        return {"folder_key": COMMON_FOLDER_KEY, "order": None, "rating": 0}
    return {
        "folder_key": str(meta.get("folder_key") or COMMON_FOLDER_KEY),
        "order": meta.get("order"),
        "rating": int(meta.get("rating", 0) or 0),
        **({"pinned": True} if bool(meta.get("pinned", False)) else {}),
    }


def set_preset_rating(scope_key: str, file_name: str, rating: int, *, display_name: str = "") -> bool:
    state = load_preset_folder_state(scope_key)
    key = str(file_name or "").strip()
    if not key:
        return False
    try:
        normalized = int(rating)
    except Exception:
        normalized = 0
    next_rating = max(0, min(10, normalized))
    items = state.setdefault("items", {})
    meta = items.get(key)
    if not isinstance(meta, dict):
        if next_rating == 0:
            return False
        meta = _ensure_item_meta(state, key, str(display_name or key), _normalize_scope(scope_key))
    if int(meta.get("rating", 0) or 0) == next_rating:
        return False
    meta["rating"] = next_rating
    save_preset_folder_state(scope_key, state)
    return True


def toggle_preset_pin(scope_key: str, file_name: str, *, display_name: str = "") -> bool:
    meta = get_preset_item_meta(scope_key, file_name)
    next_value = not bool(meta.get("pinned", False))
    set_preset_pin(scope_key, file_name, next_value, display_name=display_name)
    return next_value


def set_preset_pin(scope_key: str, file_name: str, pinned: bool, *, display_name: str = "") -> bool:
    state = load_preset_folder_state(scope_key)
    key = str(file_name or "").strip()
    if not key:
        return False
    next_pinned = bool(pinned)
    items = state.setdefault("items", {})
    meta = items.get(key)
    if not isinstance(meta, dict):
        if not next_pinned:
            return False
        meta = _ensure_item_meta(state, key, str(display_name or key), _normalize_scope(scope_key))
    if bool(meta.get("pinned", False)) == next_pinned:
        return False
    if next_pinned:
        meta["pinned"] = True
    else:
        meta.pop("pinned", None)
    save_preset_folder_state(scope_key, state)
    return True


def rename_preset_item_meta(scope_key: str, old_file_name: str, new_file_name: str) -> bool:
    old_key = str(old_file_name or "").strip()
    new_key = str(new_file_name or "").strip()
    if not old_key or not new_key or old_key == new_key:
        return False
    state = load_preset_folder_state(scope_key)
    items = state.setdefault("items", {})
    raw = items.pop(old_key, None)
    if not isinstance(raw, dict):
        return False
    items[new_key] = raw
    save_preset_folder_state(scope_key, state)
    return True


def copy_preset_item_meta(
    scope_key: str,
    source_file_name: str,
    new_file_name: str,
    *,
    reset_pin: bool = True,
    reset_rating: bool = True,
) -> bool:
    source = str(source_file_name or "").strip()
    new_key = str(new_file_name or "").strip()
    if not source or not new_key or source == new_key:
        return False
    state = load_preset_folder_state(scope_key)
    source_meta = state.setdefault("items", {}).get(source)
    if not isinstance(source_meta, dict):
        source_meta = {"folder_key": COMMON_FOLDER_KEY, "order": None, "rating": 0}
    copied = dict(source_meta)
    copied["order"] = None
    if reset_rating:
        copied["rating"] = 0
    if reset_pin:
        copied.pop("pinned", None)
    state["items"][new_key] = copied
    save_preset_folder_state(scope_key, state)
    return True


def delete_preset_item_meta(scope_key: str, file_name: str) -> bool:
    key = str(file_name or "").strip()
    if not key:
        return False
    state = load_preset_folder_state(scope_key)
    removed = state.setdefault("items", {}).pop(key, None)
    if removed is None:
        return False
    save_preset_folder_state(scope_key, state)
    return True


def build_preset_folder_rows(
    *,
    all_presets: dict[str, dict[str, Any]],
    visible_entries: list[dict[str, Any]],
    active_file_name: str,
    folder_state: dict[str, Any] | None = None,
    scope_key: str = ENGINE_WINWS2,
    query: str = "",
) -> list[dict[str, Any]]:
    scope = _normalize_scope(scope_key)
    state = normalize_folder_state(folder_state, build_default_preset_folders(scope))
    live_items: list[dict[str, Any]] = []
    for entry in visible_entries:
        file_name = str(entry.get("file_name") or "").strip()
        if not file_name:
            continue
        preset = all_presets.get(file_name) or {}
        display_name = str(preset.get("display_name") or entry.get("display_name") or file_name).strip()
        meta = _ensure_item_meta(state, file_name, display_name, scope)
        folder_key = str(meta.get("folder_key") or classify_preset_folder(display_name or file_name, scope))
        live_items.append(
            {
                "key": file_name,
                "name": display_name,
                "folder_key": folder_key,
                "rating": int(meta.get("rating", 0) or 0),
                "pinned": bool(meta.get("pinned", False)),
            }
        )

    folder_rows = build_folder_rows(
        state,
        live_items=live_items,
        include_pinned_folder=True,
        query=query,
    )
    rows: list[dict[str, Any]] = []
    for row in folder_rows:
        if row.get("kind") == "folder":
            rows.append(
                {
                    "kind": "folder",
                    "folder_key": str(row.get("key") or ""),
                    "name": str(row.get("name") or ""),
                    "text": str(row.get("name") or ""),
                    "is_collapsed": bool(row.get("collapsed", False)),
                    "is_system": bool(row.get("system", False)),
                    "is_service": bool(row.get("service", False)),
                    "count": int(row.get("count", 0) or 0),
                    "depth": 0,
                }
            )
            continue

        file_name = str(row.get("key") or "").strip()
        preset = all_presets.get(file_name) or {}
        meta = state.get("items", {}).get(file_name) or {}
        rows.append(
            {
                "kind": "preset",
                "name": str(preset.get("display_name") or row.get("name") or file_name).strip(),
                "file_name": file_name,
                "description": str(preset.get("description") or ""),
                "date": str(preset.get("modified_display") or ""),
                "is_active": bool(file_name and file_name == str(active_file_name or "").strip()),
                "is_builtin": bool(preset.get("is_builtin", False)),
                "icon_color": str(preset.get("icon_color") or ""),
                "depth": 1,
                "folder_key": str(row.get("folder_key") or ""),
                "is_pinned": bool(meta.get("pinned", False)),
                "rating": int(meta.get("rating", 0) or 0),
            }
        )
    return rows


def _ensure_item_meta(
    state: dict[str, Any],
    file_name: str,
    display_name: str,
    scope_key: str = ENGINE_WINWS2,
) -> dict[str, Any]:
    items = state.setdefault("items", {})
    item = items.setdefault(
        file_name,
        {
            "folder_key": classify_preset_folder(display_name or file_name, scope_key),
            "order": None,
            "rating": 0,
        },
    )
    return item


def _normalize_scope(scope_key: str) -> str:
    scope = str(scope_key or "").strip().lower()
    return scope if scope in {ENGINE_WINWS1, ENGINE_WINWS2} else ENGINE_WINWS2


def _move_item_to_end(state: dict[str, Any], file_name: str, folder_key: str) -> None:
    items = state.setdefault("items", {})
    folder_items = [
        key
        for key, meta in _ordered_item_meta(items)
        if str(meta.get("folder_key") or "common") == folder_key and key != file_name
    ]
    folder_items.append(file_name)
    for index, key in enumerate(folder_items):
        meta = items.setdefault(key, {"folder_key": folder_key, "order": None, "rating": 0})
        meta["folder_key"] = folder_key
        meta["order"] = index


def _ordered_item_meta(items: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    normalized: list[tuple[str, dict[str, Any]]] = []
    for key, meta in items.items():
        if isinstance(meta, dict):
            normalized.append((str(key), meta))
    return sorted(
        normalized,
        key=lambda pair: (
            0 if pair[1].get("order") is not None else 1,
            int(pair[1].get("order") or 0),
            str(pair[0]).lower(),
        ),
    )


__all__ = [
    "build_preset_folder_rows",
    "copy_preset_item_meta",
    "create_preset_folder",
    "delete_preset_folder",
    "delete_preset_item_meta",
    "get_preset_item_meta",
    "load_preset_folder_state",
    "move_preset_by_step",
    "move_preset_folder_by_step",
    "move_preset_before",
    "move_preset_after",
    "move_preset_to_end",
    "move_preset_to_folder",
    "rename_preset_folder",
    "rename_preset_item_meta",
    "reset_preset_folders",
    "save_preset_folder_state",
    "set_preset_pin",
    "set_preset_rating",
    "set_preset_folder_collapsed",
    "toggle_preset_pin",
]
