from __future__ import annotations

from typing import Any

from folders.defaults import COMMON_FOLDER_KEY, build_default_profile_folders, classify_profile_folder
from folders.store import FolderLibraryStore, normalize_folder_state
from settings import store as settings_store


def load_profile_folder_state() -> dict[str, Any]:
    try:
        folders = settings_store.get_folders_settings()
        raw_state = folders.get("profiles") if isinstance(folders, dict) else None
    except Exception:
        raw_state = None
    return normalize_folder_state(raw_state, build_default_profile_folders())


def save_profile_folder_state(state: dict[str, Any]) -> dict[str, Any]:
    folders = settings_store.get_folders_settings()
    folders["profiles"] = normalize_folder_state(state, build_default_profile_folders())
    return settings_store.set_folders_settings(folders)["profiles"]


def create_profile_folder(name: str) -> str:
    state = load_profile_folder_state()
    store = FolderLibraryStore(state, default_state=build_default_profile_folders())
    folder_key = store.create_folder_after(name, COMMON_FOLDER_KEY)
    save_profile_folder_state(store.to_dict())
    return folder_key


def rename_profile_folder(folder_key: str, name: str) -> bool:
    state = load_profile_folder_state()
    store = FolderLibraryStore(state, default_state=build_default_profile_folders())
    if not store.rename_folder(folder_key, name):
        return False
    save_profile_folder_state(store.to_dict())
    return True


def delete_profile_folder(folder_key: str) -> bool:
    state = load_profile_folder_state()
    store = FolderLibraryStore(state, default_state=build_default_profile_folders())
    if not store.delete_folder(folder_key):
        return False
    save_profile_folder_state(store.to_dict())
    return True


def move_profile_folder_by_step(folder_key: str, direction: int) -> bool:
    state = load_profile_folder_state()
    store = FolderLibraryStore(state, default_state=build_default_profile_folders())
    if not store.move_folder_by_step(folder_key, direction):
        return False
    save_profile_folder_state(store.to_dict())
    return True


def set_profile_folder_collapsed(folder_key: str, collapsed: bool) -> bool:
    state = load_profile_folder_state()
    store = FolderLibraryStore(state, default_state=build_default_profile_folders())
    if not store.set_folder_collapsed(folder_key, collapsed):
        return False
    save_profile_folder_state(store.to_dict())
    return True


def reset_profile_folders() -> dict[str, Any]:
    return save_profile_folder_state(build_default_profile_folders())


def profile_folder_for_profile(profile, state: dict[str, Any] | None = None) -> tuple[str, str, int | None]:
    folder_state = normalize_folder_state(state, build_default_profile_folders())
    profile_key = str(getattr(profile, "persistent_key", "") or "").strip()
    items = folder_state.get("items", {})
    item_meta = items.get(profile_key) if isinstance(items, dict) else None
    folder_key = ""
    order = None
    if isinstance(item_meta, dict):
        folder_key = str(item_meta.get("folder_key") or "").strip()
        try:
            order = int(item_meta["order"]) if item_meta.get("order") is not None else None
        except Exception:
            order = None
    if not folder_key:
        folder_key = classify_profile_folder(_profile_classification_text(profile))
    folders = folder_state.get("folders", {})
    if not isinstance(folders, dict) or folder_key not in folders:
        folder_key = COMMON_FOLDER_KEY
    folder = folders.get(folder_key) if isinstance(folders, dict) else {}
    folder_name = str(folder.get("name") or "Общие") if isinstance(folder, dict) else "Общие"
    return folder_key, folder_name, order


def profile_folder_collapsed(folder_key: str, state: dict[str, Any] | None = None) -> bool:
    key = str(folder_key or "").strip()
    folder_state = normalize_folder_state(state, build_default_profile_folders())
    folder = folder_state.get("folders", {}).get(key)
    return bool(folder.get("collapsed", False)) if isinstance(folder, dict) else False


def set_profile_folder_order(profile_key: str, order: int | None) -> None:
    key = str(profile_key or "").strip()
    if not key:
        return
    state = load_profile_folder_state()
    items = state.setdefault("items", {})
    meta = items.setdefault(key, {"folder_key": COMMON_FOLDER_KEY, "order": None, "rating": 0})
    meta["order"] = None if order is None else max(0, int(order))
    save_profile_folder_state(state)


def set_profile_folder(profile_key: str, folder_key: str) -> bool:
    key = str(profile_key or "").strip()
    target_folder = str(folder_key or "").strip() or COMMON_FOLDER_KEY
    if not key:
        return False
    state = load_profile_folder_state()
    folders = state.get("folders", {})
    if not isinstance(folders, dict) or target_folder not in folders:
        return False
    items = state.setdefault("items", {})
    meta = items.setdefault(key, {"folder_key": target_folder, "order": None, "rating": 0})
    meta["folder_key"] = target_folder
    save_profile_folder_state(state)
    return True


def move_profile_before_in_folder_state(
    source_profile_key: str,
    destination_profile_key: str,
    ordered_profile_keys: list[str],
    *,
    destination_folder_key: str = "",
) -> None:
    source = str(source_profile_key or "").strip()
    destination = str(destination_profile_key or "").strip()
    keys = [str(key or "").strip() for key in ordered_profile_keys if str(key or "").strip()]
    if not source or not destination or source == destination or source not in keys or destination not in keys:
        return
    state = load_profile_folder_state()
    items = state.setdefault("items", {})
    destination_meta = items.setdefault(destination, {"folder_key": COMMON_FOLDER_KEY, "order": None, "rating": 0})
    folder_key = str(destination_folder_key or destination_meta.get("folder_key") or COMMON_FOLDER_KEY)
    source_meta = items.setdefault(source, {"folder_key": folder_key, "order": None, "rating": 0})
    source_meta["folder_key"] = folder_key
    keys = [key for key in keys if key != source]
    keys.insert(keys.index(destination), source)
    for index, key in enumerate(keys):
        meta = items.setdefault(key, {"folder_key": folder_key, "order": None, "rating": 0})
        if str(meta.get("folder_key") or COMMON_FOLDER_KEY) == folder_key:
            meta["order"] = index
    save_profile_folder_state(state)


def move_profile_to_end_in_folder_state(profile_key: str, ordered_profile_keys: list[str], *, source_folder_key: str = "") -> None:
    source = str(profile_key or "").strip()
    keys = [str(key or "").strip() for key in ordered_profile_keys if str(key or "").strip()]
    if not source or source not in keys:
        return
    state = load_profile_folder_state()
    items = state.setdefault("items", {})
    source_meta = items.setdefault(source, {"folder_key": COMMON_FOLDER_KEY, "order": None, "rating": 0})
    folder_key = str(source_folder_key or source_meta.get("folder_key") or COMMON_FOLDER_KEY)
    source_meta["folder_key"] = folder_key
    keys = [key for key in keys if key != source]
    keys.append(source)
    for index, key in enumerate(keys):
        meta = items.setdefault(key, {"folder_key": folder_key, "order": None, "rating": 0})
        if str(meta.get("folder_key") or COMMON_FOLDER_KEY) == folder_key:
            meta["order"] = index
    save_profile_folder_state(state)


def move_profile_to_folder_in_folder_state(profile_key: str, folder_key: str, ordered_profile_keys: list[str]) -> None:
    source = str(profile_key or "").strip()
    target_folder = str(folder_key or "").strip() or COMMON_FOLDER_KEY
    keys = [str(key or "").strip() for key in ordered_profile_keys if str(key or "").strip()]
    if not source or source not in keys:
        return
    state = load_profile_folder_state()
    folders = state.get("folders", {})
    if not isinstance(folders, dict) or target_folder not in folders:
        return
    items = state.setdefault("items", {})
    source_meta = items.setdefault(source, {"folder_key": target_folder, "order": None, "rating": 0})
    source_meta["folder_key"] = target_folder
    target_keys = [
        key
        for key in keys
        if key != source
        and str(items.setdefault(key, {"folder_key": COMMON_FOLDER_KEY, "order": None, "rating": 0}).get("folder_key") or COMMON_FOLDER_KEY) == target_folder
    ]
    target_keys.append(source)
    for index, key in enumerate(target_keys):
        meta = items.setdefault(key, {"folder_key": target_folder, "order": None, "rating": 0})
        meta["folder_key"] = target_folder
        meta["order"] = index
    save_profile_folder_state(state)


def _profile_classification_text(profile) -> str:
    parts: list[str] = [
        str(getattr(profile, "display_name", "") or ""),
        str(getattr(profile, "name", "") or ""),
        str(getattr(profile, "persistent_key", "") or ""),
    ]
    try:
        parts.extend(str(line or "") for line in profile.match.all_lines())
    except Exception:
        pass
    return " ".join(parts)


__all__ = [
    "create_profile_folder",
    "delete_profile_folder",
    "load_profile_folder_state",
    "move_profile_folder_by_step",
    "move_profile_before_in_folder_state",
    "move_profile_to_end_in_folder_state",
    "move_profile_to_folder_in_folder_state",
    "profile_folder_collapsed",
    "profile_folder_for_profile",
    "rename_profile_folder",
    "reset_profile_folders",
    "save_profile_folder_state",
    "set_profile_folder_collapsed",
    "set_profile_folder",
    "set_profile_folder_order",
]
