from __future__ import annotations

from copy import deepcopy
import re
from typing import Any

from .defaults import COMMON_FOLDER_KEY


def normalize_folder_state(data: object, default_state: dict[str, Any]) -> dict[str, Any]:
    defaults = deepcopy(default_state if isinstance(default_state, dict) else {})
    default_folders = _normalize_folders(defaults.get("folders"), fallback={})
    raw = data if isinstance(data, dict) else {}
    folders = _normalize_folders(raw.get("folders"), fallback=default_folders)
    if default_folders:
        folders = _merge_default_folders(folders, default_folders)
    if COMMON_FOLDER_KEY in default_folders:
        folders[COMMON_FOLDER_KEY] = {
            **default_folders[COMMON_FOLDER_KEY],
            **folders.get(COMMON_FOLDER_KEY, {}),
            "system": True,
        }
    if not folders:
        folders = default_folders

    items: dict[str, dict[str, Any]] = {}
    for raw_key, raw_meta in (raw.get("items") if isinstance(raw.get("items"), dict) else {}).items():
        key = str(raw_key or "").strip()
        if not key or not isinstance(raw_meta, dict):
            continue
        folder_key = str(raw_meta.get("folder_key") or COMMON_FOLDER_KEY).strip() or COMMON_FOLDER_KEY
        if folder_key not in folders:
            folder_key = COMMON_FOLDER_KEY
        order = _as_nullable_int(raw_meta.get("order"))
        rating = _as_int(raw_meta.get("rating"), 0, minimum=0, maximum=10)
        meta = {
            "folder_key": folder_key,
            "order": order,
            "rating": rating,
        }
        if bool(raw_meta.get("pinned", False)):
            meta["pinned"] = True
        items[key] = meta

    return {
        "version": 1,
        "folders": folders,
        "items": items,
    }


class FolderLibraryStore:
    def __init__(self, state: dict[str, Any], *, default_state: dict[str, Any] | None = None) -> None:
        self._default_state = deepcopy(default_state or state)
        self._state = normalize_folder_state(state, self._default_state)

    def to_dict(self) -> dict[str, Any]:
        return deepcopy(self._state)

    def reset_to_default(self) -> dict[str, Any]:
        self._state = normalize_folder_state(self._default_state, self._default_state)
        return self.to_dict()

    def create_folder(self, name: str) -> str:
        clean_name = _clean_folder_name(name)
        key = _unique_folder_key(clean_name, self._state["folders"])
        max_order = max((int(folder.get("order", 0) or 0) for folder in self._state["folders"].values()), default=-1)
        self._state["folders"][key] = {
            "name": clean_name,
            "order": max_order + 1,
            "collapsed": False,
            "system": False,
        }
        return key

    def create_folder_after(self, name: str, after_folder_key: str = COMMON_FOLDER_KEY) -> str:
        key = self.create_folder(name)
        after_key = str(after_folder_key or "").strip()
        folders = self._ordered_folders()
        after_index = next((index for index, (folder_key, _folder) in enumerate(folders) if folder_key == after_key), -1)
        if after_index < 0:
            after_index = len(folders) - 2
        folder_keys = [folder_key for folder_key, _folder in folders if folder_key != key]
        insert_index = max(0, min(len(folder_keys), after_index + 1))
        folder_keys.insert(insert_index, key)
        self._renumber_folders(folder_keys)
        return key

    def rename_folder(self, folder_key: str, name: str) -> bool:
        key = str(folder_key or "").strip()
        folder = self._state["folders"].get(key)
        if not isinstance(folder, dict) or bool(folder.get("system", False)):
            return False
        clean_name = _clean_folder_name(name)
        if str(folder.get("name") or "") == clean_name:
            return False
        folder["name"] = clean_name
        return True

    def delete_folder(self, folder_key: str) -> bool:
        key = str(folder_key or "").strip()
        folder = self._state["folders"].get(key)
        if not isinstance(folder, dict) or bool(folder.get("system", False)):
            return False
        self._state["folders"].pop(key, None)
        for meta in self._state["items"].values():
            if meta.get("folder_key") == key:
                meta["folder_key"] = COMMON_FOLDER_KEY
        return True

    def move_folder(self, folder_key: str, order: int) -> bool:
        key = str(folder_key or "").strip()
        if key not in self._state["folders"]:
            return False
        next_order = max(0, int(order))
        if int(self._state["folders"][key].get("order", 0) or 0) == next_order:
            return False
        self._state["folders"][key]["order"] = next_order
        return True

    def move_folder_by_step(self, folder_key: str, direction: int) -> bool:
        key = str(folder_key or "").strip()
        if key not in self._state["folders"]:
            return False
        step = 1 if int(direction or 0) > 0 else -1
        folders = self._ordered_folders()
        index = next((i for i, (folder_key, _folder) in enumerate(folders) if folder_key == key), -1)
        if index < 0:
            return False
        target_index = index + step
        if target_index < 0 or target_index >= len(folders):
            return False
        folder_keys = [folder_key for folder_key, _folder in folders]
        folder_keys[index], folder_keys[target_index] = folder_keys[target_index], folder_keys[index]
        self._renumber_folders(folder_keys)
        return True

    def set_folder_collapsed(self, folder_key: str, collapsed: bool) -> bool:
        key = str(folder_key or "").strip()
        if key not in self._state["folders"]:
            return False
        next_collapsed = bool(collapsed)
        if bool(self._state["folders"][key].get("collapsed", False)) == next_collapsed:
            return False
        self._state["folders"][key]["collapsed"] = next_collapsed
        return True

    def set_item_folder(self, item_key: str, folder_key: str) -> bool:
        key = str(item_key or "").strip()
        folder = str(folder_key or "").strip() or COMMON_FOLDER_KEY
        if not key:
            return False
        if folder not in self._state["folders"]:
            folder = COMMON_FOLDER_KEY
        meta = self._state["items"].get(key)
        if not isinstance(meta, dict):
            if folder == COMMON_FOLDER_KEY:
                return False
            meta = {"folder_key": folder, "order": None, "rating": 0}
            self._state["items"][key] = meta
            return True
        if str(meta.get("folder_key") or COMMON_FOLDER_KEY) == folder:
            return False
        meta["folder_key"] = folder
        return True

    def set_item_order(self, item_key: str, order: int | None) -> bool:
        key = str(item_key or "").strip()
        if not key:
            return False
        next_order = None if order is None else max(0, int(order))
        meta = self._state["items"].get(key)
        if not isinstance(meta, dict):
            if next_order is None:
                return False
            meta = {"folder_key": COMMON_FOLDER_KEY, "order": None, "rating": 0}
            self._state["items"][key] = meta
        if meta.get("order") == next_order:
            return False
        meta["order"] = next_order
        return True

    def set_item_rating(self, item_key: str, rating: int) -> bool:
        key = str(item_key or "").strip()
        if not key:
            return False
        next_rating = max(0, min(10, int(rating or 0)))
        meta = self._state["items"].get(key)
        if not isinstance(meta, dict):
            if next_rating == 0:
                return False
            meta = {"folder_key": COMMON_FOLDER_KEY, "order": None, "rating": 0}
            self._state["items"][key] = meta
        if int(meta.get("rating", 0) or 0) == next_rating:
            return False
        meta["rating"] = next_rating
        return True

    def set_item_pinned(self, item_key: str, pinned: bool) -> bool:
        key = str(item_key or "").strip()
        if not key:
            return False
        next_pinned = bool(pinned)
        meta = self._state["items"].get(key)
        if not isinstance(meta, dict):
            if not next_pinned:
                return False
            meta = {"folder_key": COMMON_FOLDER_KEY, "order": None, "rating": 0}
            self._state["items"][key] = meta
        if bool(meta.get("pinned", False)) == next_pinned:
            return False
        if next_pinned:
            meta["pinned"] = True
        else:
            meta.pop("pinned", None)
        return True

    def _ordered_folders(self) -> list[tuple[str, dict[str, Any]]]:
        return sorted(
            self._state["folders"].items(),
            key=lambda pair: (
                int(pair[1].get("order", 0) or 0),
                str(pair[1].get("name") or pair[0]).lower(),
                pair[0],
            ),
        )

    def _renumber_folders(self, folder_keys: list[str]) -> None:
        for index, key in enumerate(folder_keys):
            folder = self._state["folders"].get(key)
            if isinstance(folder, dict):
                folder["order"] = index


def _normalize_folders(value: object, *, fallback: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    folders: dict[str, dict[str, Any]] = {}
    if isinstance(value, dict):
        for raw_key, raw_folder in value.items():
            key = str(raw_key or "").strip()
            if not key or not isinstance(raw_folder, dict):
                continue
            name = _clean_folder_name(raw_folder.get("name") or key)
            folders[key] = {
                "name": name,
                "order": _as_int(raw_folder.get("order"), len(folders), minimum=0),
                "collapsed": bool(raw_folder.get("collapsed", False)),
                "system": bool(raw_folder.get("system", False)),
            }
    if folders:
        return folders
    return deepcopy(fallback)


def _merge_default_folders(
    folders: dict[str, dict[str, Any]],
    default_folders: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    result = deepcopy(folders)
    if not result:
        return deepcopy(default_folders)

    for key, default_folder in default_folders.items():
        if key in result:
            result[key] = {
                **default_folder,
                **result[key],
                "system": bool(default_folder.get("system", False) or result[key].get("system", False)),
            }
            continue

        folder = deepcopy(default_folder)
        wanted_order = _as_int(folder.get("order"), len(result), minimum=0)
        _make_order_slot(result, wanted_order)
        folder["order"] = wanted_order
        result[key] = folder

    return result


def _make_order_slot(folders: dict[str, dict[str, Any]], order: int) -> None:
    for folder in folders.values():
        if not isinstance(folder, dict):
            continue
        current_order = _as_int(folder.get("order"), 0, minimum=0)
        if current_order >= order:
            folder["order"] = current_order + 1


def _clean_folder_name(value: object) -> str:
    text = re.sub(r"\s+", " ", str(value or "").strip())
    return text[:80] or "Новая папка"


def _unique_folder_key(name: str, folders: dict[str, Any]) -> str:
    base = re.sub(r"[^a-z0-9а-яё]+", "-", name.lower(), flags=re.IGNORECASE).strip("-") or "folder"
    key = base
    counter = 2
    while key in folders:
        key = f"{base}-{counter}"
        counter += 1
    return key


def _as_nullable_int(value: object) -> int | None:
    if value in ("", None):
        return None
    try:
        return max(0, int(value))  # type: ignore[arg-type]
    except Exception:
        return None


def _as_int(value: object, default: int, *, minimum: int | None = None, maximum: int | None = None) -> int:
    try:
        result = int(value)  # type: ignore[arg-type]
    except Exception:
        result = int(default)
    if minimum is not None:
        result = max(minimum, result)
    if maximum is not None:
        result = min(maximum, result)
    return result


__all__ = ["FolderLibraryStore", "normalize_folder_state"]
