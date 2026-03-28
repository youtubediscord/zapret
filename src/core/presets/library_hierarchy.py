from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
from typing import Callable, Iterable
from uuid import uuid4

from config import get_zapret_userdata_dir


ROOT_FOLDER_ID = "__root__"
STOCK_REGULAR_ID = "__stock_regular__"
STOCK_GAMES_ID = "__stock_games__"
STOCK_ALL_TCP_UDP_ID = "__stock_all_tcp_udp__"
STOCK_FOLDER_IDS = (
    STOCK_REGULAR_ID,
    STOCK_GAMES_ID,
    STOCK_ALL_TCP_UDP_ID,
)

DEFAULT_TOP_LEVEL_ORDER = [
    ROOT_FOLDER_ID,
    STOCK_REGULAR_ID,
    STOCK_GAMES_ID,
    STOCK_ALL_TCP_UDP_ID,
]

ROOT_FOLDER_NAME = "Без папки"
STOCK_FOLDER_NAMES = {
    STOCK_REGULAR_ID: "Обычные",
    STOCK_GAMES_ID: "Игры (game filter)",
    STOCK_ALL_TCP_UDP_ID: "Все сайты и игры (ALL TCP/UDP)",
}


def _safe_scope_name(scope_key: str) -> str:
    raw = str(scope_key or "").strip().lower()
    if not raw:
        raw = "default"
    raw = re.sub(r"[^a-z0-9_.-]+", "_", raw)
    return raw or "default"


def _storage_dir() -> Path:
    return Path(get_zapret_userdata_dir()) / "preset_library"


def _default_state() -> dict:
    return {
        "version": 1,
        "top_level_order": list(DEFAULT_TOP_LEVEL_ORDER),
        "folder_state": {},
        "folders": [],
        "presets": {},
    }


def classify_stock_folder_id(preset_name: str) -> str:
    low = str(preset_name or "").strip().lower()
    if "all tcp" in low:
        return STOCK_ALL_TCP_UDP_ID
    if "game filter" in low:
        return STOCK_GAMES_ID
    return STOCK_REGULAR_ID


def _normalize_folder_record(raw: dict) -> dict:
    folder_id = str(raw.get("id") or "").strip()
    if not folder_id or folder_id in STOCK_FOLDER_IDS or folder_id == ROOT_FOLDER_ID:
        folder_id = f"folder_{uuid4().hex}"

    name = str(raw.get("name") or "").strip() or "Новая папка"
    parent_id = raw.get("parent_id")
    parent_id = str(parent_id).strip() if parent_id not in (None, "") else None
    if parent_id in STOCK_FOLDER_IDS or parent_id == ROOT_FOLDER_ID:
        parent_id = None

    order = raw.get("order", 0)
    try:
        order = int(order)
    except Exception:
        order = 0

    return {
        "id": folder_id,
        "name": name,
        "parent_id": parent_id,
        "order": order,
    }


def _normalize_preset_meta(raw: dict) -> dict:
    folder_id = raw.get("folder_id")
    if folder_id in ("", None):
        folder_id = None
    else:
        folder_id = str(folder_id).strip() or None

    rating = raw.get("rating", 0)
    try:
        rating = int(rating)
    except Exception:
        rating = 0
    rating = max(0, min(10, rating))

    pinned = bool(raw.get("pinned", False))
    order = raw.get("order")
    if order in ("", None):
        order = None
    else:
        try:
            order = int(order)
        except Exception:
            order = None

    return {
        "folder_id": folder_id,
        "rating": rating,
        "pinned": pinned,
        "order": order,
    }


def _sort_folders(records: Iterable[dict]) -> list[dict]:
    return sorted(records, key=lambda item: (int(item.get("order", 0)), str(item.get("name", "")).lower()))


def _folder_depth(folder_id: str, by_id: dict[str, dict]) -> int:
    depth = 0
    current = by_id.get(folder_id)
    visited: set[str] = set()
    while current is not None:
        parent_id = current.get("parent_id")
        if not parent_id:
            break
        if parent_id in visited:
            break
        visited.add(parent_id)
        depth += 1
        current = by_id.get(parent_id)
    return depth


@dataclass
class PresetHierarchyStore:
    scope_key: str
    _state: dict | None = None

    @property
    def state_path(self) -> Path:
        return _storage_dir() / f"{_safe_scope_name(self.scope_key)}.json"

    def _ensure_loaded(self) -> None:
        if self._state is not None:
            return

        path = self.state_path
        state = _default_state()
        if path.exists():
            try:
                loaded = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    state.update(loaded)
            except Exception:
                state = _default_state()

        folders = []
        for raw in state.get("folders", []) or []:
            if isinstance(raw, dict):
                folders.append(_normalize_folder_record(raw))

        presets = {}
        for key, raw in (state.get("presets", {}) or {}).items():
            preset_name = str(key or "").strip()
            if preset_name and isinstance(raw, dict):
                presets[preset_name] = _normalize_preset_meta(raw)

        folder_state = {}
        for key, raw in (state.get("folder_state", {}) or {}).items():
            folder_id = str(key or "").strip()
            if not folder_id:
                continue
            collapsed = False
            if isinstance(raw, dict):
                collapsed = bool(raw.get("collapsed", False))
            else:
                collapsed = bool(raw)
            folder_state[folder_id] = {"collapsed": collapsed}

        top_level_order = []
        for item in state.get("top_level_order", []) or []:
            folder_id = str(item or "").strip()
            if folder_id:
                top_level_order.append(folder_id)

        self._state = {
            "version": 1,
            "folders": folders,
            "presets": presets,
            "folder_state": folder_state,
            "top_level_order": top_level_order or list(DEFAULT_TOP_LEVEL_ORDER),
        }
        self._normalize_state()

    def _normalize_state(self) -> None:
        assert self._state is not None

        folders = self._state["folders"]
        by_id = {item["id"]: item for item in folders}

        # Drop invalid parents and self-references.
        for folder in folders:
            parent_id = folder.get("parent_id")
            if parent_id == folder["id"] or parent_id not in by_id:
                folder["parent_id"] = None

        top_level_custom_ids = [item["id"] for item in folders if not item.get("parent_id")]
        order = []
        seen: set[str] = set()
        for folder_id in self._state.get("top_level_order", []):
            if folder_id in seen:
                continue
            if folder_id in DEFAULT_TOP_LEVEL_ORDER or folder_id in top_level_custom_ids:
                order.append(folder_id)
                seen.add(folder_id)

        for folder_id in DEFAULT_TOP_LEVEL_ORDER:
            if folder_id not in seen:
                order.append(folder_id)
                seen.add(folder_id)

        for folder_id in top_level_custom_ids:
            if folder_id not in seen:
                order.append(folder_id)
                seen.add(folder_id)

        self._state["top_level_order"] = order

        # Reset preset folder links that point to non-existing or protected folders.
        for meta in self._state["presets"].values():
            folder_id = meta.get("folder_id")
            if folder_id in STOCK_FOLDER_IDS or folder_id == ROOT_FOLDER_ID:
                meta["folder_id"] = None
            elif folder_id and folder_id not in by_id:
                meta["folder_id"] = None

        valid_folder_state_ids = {ROOT_FOLDER_ID, *STOCK_FOLDER_IDS, *by_id.keys()}
        normalized_folder_state = {}
        for folder_id, raw in (self._state.get("folder_state", {}) or {}).items():
            if folder_id not in valid_folder_state_ids:
                continue
            normalized_folder_state[folder_id] = {"collapsed": bool((raw or {}).get("collapsed", False))}
        self._state["folder_state"] = normalized_folder_state

    def _save(self) -> None:
        assert self._state is not None
        path = self.state_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(self._state, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def list_custom_folders(self) -> list[dict]:
        self._ensure_loaded()
        assert self._state is not None
        return [dict(item) for item in self._state["folders"]]

    def get_folder_meta(self, folder_id: str) -> dict | None:
        self._ensure_loaded()
        if folder_id == ROOT_FOLDER_ID:
            return {
                "id": ROOT_FOLDER_ID,
                "name": ROOT_FOLDER_NAME,
                "parent_id": None,
                "builtin": True,
                "depth": 0,
            }
        if folder_id in STOCK_FOLDER_NAMES:
            return {
                "id": folder_id,
                "name": STOCK_FOLDER_NAMES[folder_id],
                "parent_id": None,
                "builtin": True,
                "depth": 0,
            }

        for folder in self._state["folders"]:
            if folder["id"] == folder_id:
                by_id = {item["id"]: item for item in self._state["folders"]}
                out = dict(folder)
                out["builtin"] = False
                out["depth"] = _folder_depth(folder_id, by_id)
                return out
        return None

    def get_preset_meta(self, preset_name: str) -> dict:
        self._ensure_loaded()
        assert self._state is not None
        key = str(preset_name or "").strip()
        raw = self._state["presets"].get(key) or {}
        return _normalize_preset_meta(raw)

    def rename_preset_meta(self, old_name: str, new_name: str) -> None:
        self._ensure_loaded()
        assert self._state is not None
        old_key = str(old_name or "").strip()
        new_key = str(new_name or "").strip()
        if not old_key or not new_key or old_key == new_key:
            return
        raw = self._state["presets"].pop(old_key, None)
        if raw is not None:
            self._state["presets"][new_key] = _normalize_preset_meta(raw)
            self._save()

    def copy_preset_meta_to_new(
        self,
        source_name: str,
        new_name: str,
        *,
        reset_pin: bool = True,
        reset_rating: bool = True,
    ) -> None:
        source = self.get_preset_meta(source_name)
        copied = dict(source)
        if reset_pin:
            copied["pinned"] = False
        if reset_rating:
            copied["rating"] = 0
        copied["order"] = None
        self._set_preset_meta(new_name, copied)

    def delete_preset_meta(self, preset_name: str) -> None:
        self._ensure_loaded()
        assert self._state is not None
        key = str(preset_name or "").strip()
        if not key:
            return
        if self._state["presets"].pop(key, None) is not None:
            self._save()

    def toggle_preset_pin(self, preset_name: str) -> bool:
        meta = self.get_preset_meta(preset_name)
        next_value = not bool(meta.get("pinned", False))
        self.set_preset_pin(preset_name, next_value)
        return next_value

    def set_preset_pin(self, preset_name: str, pinned: bool) -> None:
        self._ensure_loaded()
        assert self._state is not None
        key = str(preset_name or "").strip()
        if not key:
            return
        meta = self.get_preset_meta(key)
        meta["pinned"] = bool(pinned)
        self._set_preset_meta(key, meta)

    def set_preset_rating(self, preset_name: str, rating: int) -> None:
        self._ensure_loaded()
        assert self._state is not None
        key = str(preset_name or "").strip()
        if not key:
            return
        meta = self.get_preset_meta(key)
        try:
            normalized = int(rating)
        except Exception:
            normalized = 0
        meta["rating"] = max(0, min(10, normalized))
        self._set_preset_meta(key, meta)

    def set_preset_folder(self, preset_name: str, folder_id: str | None, *, reset_order: bool = True) -> None:
        self._ensure_loaded()
        assert self._state is not None
        key = str(preset_name or "").strip()
        if not key:
            return

        target = str(folder_id or "").strip() or None
        custom_ids = {item["id"] for item in self._state["folders"]}
        if target not in custom_ids:
            target = None

        meta = self.get_preset_meta(key)
        meta["folder_id"] = target
        if reset_order:
            meta["order"] = None
        self._set_preset_meta(key, meta)

    def is_folder_collapsed(self, folder_id: str) -> bool:
        self._ensure_loaded()
        assert self._state is not None
        key = str(folder_id or "").strip()
        if not key:
            return False
        raw = (self._state.get("folder_state", {}) or {}).get(key) or {}
        return bool(raw.get("collapsed", False))

    def set_folder_collapsed(self, folder_id: str, collapsed: bool) -> None:
        self._ensure_loaded()
        assert self._state is not None
        key = str(folder_id or "").strip()
        if not key:
            return
        self._state.setdefault("folder_state", {})[key] = {"collapsed": bool(collapsed)}
        self._save()

    def toggle_folder_collapsed(self, folder_id: str) -> bool:
        next_value = not self.is_folder_collapsed(folder_id)
        self.set_folder_collapsed(folder_id, next_value)
        return next_value

    def get_effective_folder_id(
        self,
        preset_name: str,
        *,
        is_builtin: bool = False,
    ) -> str:
        if is_builtin:
            return classify_stock_folder_id(preset_name)
        meta = self.get_preset_meta(preset_name)
        folder_id = meta.get("folder_id")
        custom_ids = {item["id"] for item in self.list_custom_folders()}
        if folder_id and folder_id in custom_ids:
            return folder_id
        return ROOT_FOLDER_ID

    def list_presets_in_folder(
        self,
        preset_names: Iterable[str],
        folder_id: str,
        *,
        is_builtin_name: Callable[[str], bool] | None = None,
    ) -> list[str]:
        self._ensure_loaded()
        assert self._state is not None

        target = str(folder_id or ROOT_FOLDER_ID).strip() or ROOT_FOLDER_ID
        builtin_resolver = is_builtin_name or (lambda _name: False)

        names = []
        for raw_name in preset_names:
            name = str(raw_name or "").strip()
            if not name:
                continue
            if self.get_effective_folder_id(name, is_builtin=builtin_resolver(name)) == target:
                names.append(name)
        return self._sort_preset_names(names)

    def move_preset_to_folder_end(
        self,
        preset_names: Iterable[str],
        preset_name: str,
        target_folder_id: str | None,
        *,
        is_builtin_name: Callable[[str], bool] | None = None,
    ) -> bool:
        self._ensure_loaded()
        assert self._state is not None

        builtin_resolver = is_builtin_name or (lambda _name: False)
        source_name = str(preset_name or "").strip()
        if not source_name:
            return False
        source_is_builtin = bool(builtin_resolver(source_name))

        target_folder = self._normalize_target_folder_id(target_folder_id)
        source_folder = self.get_effective_folder_id(source_name, is_builtin=source_is_builtin)
        if source_is_builtin and target_folder != source_folder:
            return False
        source_names = self.list_presets_in_folder(preset_names, source_folder, is_builtin_name=builtin_resolver)
        target_names = self.list_presets_in_folder(preset_names, target_folder, is_builtin_name=builtin_resolver)

        if source_folder == target_folder:
            reordered = [name for name in target_names if name != source_name]
            reordered.append(source_name)
            changed = reordered != target_names
            if not source_is_builtin:
                self.set_preset_folder(source_name, None if target_folder == ROOT_FOLDER_ID else target_folder, reset_order=False)
            self._apply_preset_order_list(reordered)
            return changed

        source_names = [name for name in source_names if name != source_name]
        target_names = [name for name in target_names if name != source_name]
        target_names.append(source_name)
        if not source_is_builtin:
            self.set_preset_folder(source_name, None if target_folder == ROOT_FOLDER_ID else target_folder, reset_order=False)
        self._apply_preset_order_list(source_names)
        self._apply_preset_order_list(target_names)
        return True

    def move_preset_before(
        self,
        preset_names: Iterable[str],
        preset_name: str,
        target_name: str,
        *,
        is_builtin_name: Callable[[str], bool] | None = None,
    ) -> bool:
        self._ensure_loaded()
        assert self._state is not None

        builtin_resolver = is_builtin_name or (lambda _name: False)
        source_name = str(preset_name or "").strip()
        target_preset = str(target_name or "").strip()
        if not source_name or not target_preset or source_name == target_preset:
            return False
        source_is_builtin = bool(builtin_resolver(source_name))

        source_folder = self.get_effective_folder_id(source_name, is_builtin=source_is_builtin)
        target_folder = self.get_effective_folder_id(target_preset, is_builtin=builtin_resolver(target_preset))
        if source_is_builtin and target_folder != source_folder:
            return False
        source_names = self.list_presets_in_folder(preset_names, source_folder, is_builtin_name=builtin_resolver)
        target_names = self.list_presets_in_folder(preset_names, target_folder, is_builtin_name=builtin_resolver)

        if source_folder == target_folder:
            reordered = [name for name in target_names if name != source_name]
            if target_preset not in reordered:
                return False
            insert_at = reordered.index(target_preset)
            reordered.insert(insert_at, source_name)
            changed = reordered != target_names
            if not source_is_builtin:
                self.set_preset_folder(source_name, None if target_folder == ROOT_FOLDER_ID else target_folder, reset_order=False)
            self._apply_preset_order_list(reordered)
            return changed

        source_names = [name for name in source_names if name != source_name]
        target_names = [name for name in target_names if name != source_name]
        if target_preset not in target_names:
            return False
        insert_at = target_names.index(target_preset)
        target_names.insert(insert_at, source_name)
        if not source_is_builtin:
            self.set_preset_folder(source_name, None if target_folder == ROOT_FOLDER_ID else target_folder, reset_order=False)
        self._apply_preset_order_list(source_names)
        self._apply_preset_order_list(target_names)
        return True

    def move_preset_by_step(
        self,
        preset_names: Iterable[str],
        preset_name: str,
        direction: int,
        *,
        is_builtin_name: Callable[[str], bool] | None = None,
    ) -> bool:
        builtin_resolver = is_builtin_name or (lambda _name: False)
        source_name = str(preset_name or "").strip()
        if not source_name:
            return False

        source_is_builtin = bool(builtin_resolver(source_name))
        source_folder = self.get_effective_folder_id(source_name, is_builtin=source_is_builtin)
        ordered_names = self.list_presets_in_folder(preset_names, source_folder, is_builtin_name=builtin_resolver)
        if source_name not in ordered_names:
            return False

        idx = ordered_names.index(source_name)
        new_idx = idx + int(direction)
        if new_idx < 0 or new_idx >= len(ordered_names):
            return False

        ordered_names[idx], ordered_names[new_idx] = ordered_names[new_idx], ordered_names[idx]
        self._apply_preset_order_list(ordered_names)
        return True

    def _set_preset_meta(self, preset_name: str, meta: dict) -> None:
        assert self._state is not None
        normalized = _normalize_preset_meta(meta)
        if (
            normalized.get("folder_id") in (None, "")
            and int(normalized.get("rating", 0)) == 0
            and not bool(normalized.get("pinned", False))
            and normalized.get("order") is None
        ):
            self._state["presets"].pop(preset_name, None)
        else:
            self._state["presets"][preset_name] = normalized
        self._save()

    def _normalize_target_folder_id(self, folder_id: str | None) -> str:
        target = str(folder_id or ROOT_FOLDER_ID).strip() or ROOT_FOLDER_ID
        if target in (ROOT_FOLDER_ID, *STOCK_FOLDER_IDS):
            return target
        custom_ids = {item["id"] for item in self.list_custom_folders()}
        return target if target in custom_ids else ROOT_FOLDER_ID

    def _sort_preset_names(self, names: Iterable[str]) -> list[str]:
        def sort_key(name: str) -> tuple[int, int, int, str]:
            meta = self.get_preset_meta(name)
            order = meta.get("order")
            return (
                0 if meta.get("pinned") else 1,
                0 if order is not None else 1,
                int(order or 0),
                name.lower(),
            )

        return sorted((str(name or "").strip() for name in names if str(name or "").strip()), key=sort_key)

    def _apply_preset_order_list(self, ordered_names: Iterable[str]) -> None:
        for index, name in enumerate(ordered_names):
            meta = self.get_preset_meta(name)
            meta["order"] = index
            self._state["presets"][name] = _normalize_preset_meta(meta)
        self._save()

    def create_folder(self, name: str, parent_id: str | None = None) -> dict:
        self._ensure_loaded()
        assert self._state is not None

        normalized_name = str(name or "").strip()
        if not normalized_name:
            raise ValueError("Folder name is required")

        parent = str(parent_id or "").strip() or None
        custom_ids = {item["id"] for item in self._state["folders"]}
        if parent and parent not in custom_ids:
            parent = None

        siblings = [item for item in self._state["folders"] if item.get("parent_id") == parent]
        next_order = (max((int(item.get("order", 0)) for item in siblings), default=-1) + 1)
        record = {
            "id": f"folder_{uuid4().hex}",
            "name": normalized_name,
            "parent_id": parent,
            "order": next_order,
        }
        self._state["folders"].append(record)
        if parent is None:
            self._state["top_level_order"].append(record["id"])
        self._normalize_state()
        self._save()
        return dict(record)

    def update_folder(self, folder_id: str, *, name: str, parent_id: str | None = None) -> dict:
        self._ensure_loaded()
        assert self._state is not None

        folder = self._require_custom_folder(folder_id)
        normalized_name = str(name or "").strip()
        if not normalized_name:
            raise ValueError("Folder name is required")

        target_parent = str(parent_id or "").strip() or None
        if target_parent == folder_id:
            target_parent = None

        custom_ids = {item["id"] for item in self._state["folders"]}
        if target_parent and target_parent not in custom_ids:
            target_parent = None

        # Prevent moving inside own subtree.
        descendants = self._descendant_ids(folder_id)
        if target_parent in descendants:
            target_parent = None

        old_parent = folder.get("parent_id")
        folder["name"] = normalized_name

        if old_parent != target_parent:
            folder["parent_id"] = target_parent
            if target_parent is None and folder_id not in self._state["top_level_order"]:
                self._state["top_level_order"].append(folder_id)
            if old_parent is None and target_parent is not None:
                self._state["top_level_order"] = [
                    item for item in self._state["top_level_order"] if item != folder_id
                ]
            siblings = [item for item in self._state["folders"] if item.get("parent_id") == target_parent]
            folder["order"] = max((int(item.get("order", 0)) for item in siblings if item["id"] != folder_id), default=-1) + 1

        self._resequence_siblings(old_parent)
        self._resequence_siblings(target_parent)
        self._normalize_state()
        self._save()
        return dict(folder)

    def delete_folder(self, folder_id: str) -> None:
        self._ensure_loaded()
        assert self._state is not None

        folder = self._require_custom_folder(folder_id)
        parent_id = folder.get("parent_id")

        for child in self._state["folders"]:
            if child.get("parent_id") == folder_id:
                child["parent_id"] = parent_id

        for meta in self._state["presets"].values():
            if meta.get("folder_id") == folder_id:
                meta["folder_id"] = parent_id if parent_id else None

        self._state["folders"] = [item for item in self._state["folders"] if item["id"] != folder_id]
        self._state["top_level_order"] = [item for item in self._state["top_level_order"] if item != folder_id]
        self._resequence_siblings(parent_id)
        self._normalize_state()
        self._save()

    def move_folder_up(self, folder_id: str) -> bool:
        return self._move_folder(folder_id, direction=-1)

    def move_folder_down(self, folder_id: str) -> bool:
        return self._move_folder(folder_id, direction=1)

    def move_folder_before(self, folder_id: str, target_folder_id: str) -> bool:
        self._ensure_loaded()
        assert self._state is not None

        source_id = str(folder_id or "").strip()
        target_id = str(target_folder_id or "").strip()
        if not source_id or not target_id or source_id == target_id:
            return False

        source_folder = self.get_folder_meta(source_id)
        target_folder = self.get_folder_meta(target_id)
        if source_folder is None or target_folder is None:
            return False

        source_parent = None if source_id in DEFAULT_TOP_LEVEL_ORDER else self._find_custom_folder(source_id).get("parent_id") if self._find_custom_folder(source_id) else None
        target_parent = None if target_id in DEFAULT_TOP_LEVEL_ORDER else self._find_custom_folder(target_id).get("parent_id") if self._find_custom_folder(target_id) else None

        if source_parent is None and target_parent is None:
            order = self._state["top_level_order"]
            if source_id not in order:
                order.append(source_id)
            if target_id not in order:
                order.append(target_id)
            order[:] = [item for item in order if item != source_id]
            target_index = order.index(target_id)
            order.insert(target_index, source_id)
            self._save()
            return True

        if source_id in DEFAULT_TOP_LEVEL_ORDER or target_id in DEFAULT_TOP_LEVEL_ORDER:
            return False

        source_custom = self._require_custom_folder(source_id)
        target_custom = self._require_custom_folder(target_id)
        if source_custom.get("parent_id") != target_custom.get("parent_id"):
            return False

        parent_id = source_custom.get("parent_id")
        siblings = _sort_folders(item for item in self._state["folders"] if item.get("parent_id") == parent_id)
        sibling_ids = [item["id"] for item in siblings if item["id"] != source_id]
        if target_id not in sibling_ids:
            return False
        target_index = sibling_ids.index(target_id)
        sibling_ids.insert(target_index, source_id)
        for order_index, item_id in enumerate(sibling_ids):
            sibling = self._find_custom_folder(item_id)
            if sibling is not None:
                sibling["order"] = order_index
        self._save()
        return True

    def _move_folder(self, folder_id: str, direction: int) -> bool:
        self._ensure_loaded()
        assert self._state is not None

        if folder_id in DEFAULT_TOP_LEVEL_ORDER:
            order = self._state["top_level_order"]
            if folder_id not in order:
                order.append(folder_id)
            idx = order.index(folder_id)
            new_idx = idx + direction
            if new_idx < 0 or new_idx >= len(order):
                return False
            order[idx], order[new_idx] = order[new_idx], order[idx]
            self._save()
            return True

        folder = self._require_custom_folder(folder_id)
        parent_id = folder.get("parent_id")

        if parent_id is None:
            order = self._state["top_level_order"]
            if folder_id not in order:
                order.append(folder_id)
            idx = order.index(folder_id)
            new_idx = idx + direction
            if new_idx < 0 or new_idx >= len(order):
                return False
            order[idx], order[new_idx] = order[new_idx], order[idx]
            self._save()
            return True

        siblings = _sort_folders(item for item in self._state["folders"] if item.get("parent_id") == parent_id)
        ids = [item["id"] for item in siblings]
        idx = ids.index(folder_id)
        new_idx = idx + direction
        if new_idx < 0 or new_idx >= len(ids):
            return False
        ids[idx], ids[new_idx] = ids[new_idx], ids[idx]
        for order_index, item_id in enumerate(ids):
            sibling = self._find_custom_folder(item_id)
            if sibling is not None:
                sibling["order"] = order_index
        self._save()
        return True

    def get_folder_choices(self, *, include_root: bool = True, exclude_folder_id: str | None = None) -> list[dict]:
        self._ensure_loaded()
        assert self._state is not None

        excluded = {str(exclude_folder_id or "").strip()} if exclude_folder_id else set()
        if exclude_folder_id:
            excluded.update(self._descendant_ids(exclude_folder_id))

        by_parent: dict[str | None, list[dict]] = {}
        for folder in self._state["folders"]:
            if folder["id"] in excluded:
                continue
            by_parent.setdefault(folder.get("parent_id"), []).append(folder)

        for parent_id, items in by_parent.items():
            by_parent[parent_id] = _sort_folders(items)

        result: list[dict] = []
        if include_root:
            result.append({"id": ROOT_FOLDER_ID, "name": ROOT_FOLDER_NAME, "depth": 0, "builtin": True})

        def append_branch(parent_id: str | None, depth: int) -> None:
            for folder in by_parent.get(parent_id, []):
                result.append(
                    {
                        "id": folder["id"],
                        "name": folder["name"],
                        "depth": depth,
                        "builtin": False,
                    }
                )
                append_branch(folder["id"], depth + 1)

        top_level_ids = [item for item in self._state["top_level_order"] if item not in DEFAULT_TOP_LEVEL_ORDER]
        top_level_items = [self._find_custom_folder(item_id) for item_id in top_level_ids]
        top_level_items = [item for item in top_level_items if item is not None and item["id"] not in excluded]
        seen_top = {item["id"] for item in top_level_items}
        for folder in _sort_folders(item for item in self._state["folders"] if item.get("parent_id") is None):
            if folder["id"] not in seen_top and folder["id"] not in excluded:
                top_level_items.append(folder)

        by_parent[None] = top_level_items
        append_branch(None, 0)
        return result

    def build_rows(
        self,
        preset_names: Iterable[str],
        *,
        query: str = "",
        is_builtin_name: Callable[[str], bool] | None = None,
    ) -> list[dict]:
        self._ensure_loaded()
        assert self._state is not None

        query_text = str(query or "").strip().lower()
        builtin_resolver = is_builtin_name or (lambda _name: False)
        by_id = {item["id"]: item for item in self._state["folders"]}

        custom_presets_by_folder: dict[str | None, list[str]] = {None: []}
        builtin_presets_by_folder: dict[str, list[str]] = {
            STOCK_REGULAR_ID: [],
            STOCK_GAMES_ID: [],
            STOCK_ALL_TCP_UDP_ID: [],
        }

        def matches_name(name: str) -> bool:
            if not query_text:
                return True
            return query_text in name.lower()

        for raw_name in sorted((str(item or "").strip() for item in preset_names), key=lambda value: value.lower()):
            if not raw_name or not matches_name(raw_name):
                continue
            meta = self.get_preset_meta(raw_name)
            if builtin_resolver(raw_name):
                builtin_presets_by_folder[classify_stock_folder_id(raw_name)].append(raw_name)
                continue

            folder_id = meta.get("folder_id")
            if folder_id and folder_id in by_id:
                custom_presets_by_folder.setdefault(folder_id, []).append(raw_name)
            else:
                custom_presets_by_folder.setdefault(None, []).append(raw_name)

        def preset_sort_key(name: str) -> tuple[int, int, str]:
            meta = self.get_preset_meta(name)
            return (
                0 if meta.get("pinned") else 1,
                0 if meta.get("order") is not None else 1,
                int(meta.get("order") or 0),
                -int(meta.get("rating", 0) or 0),
                name.lower(),
            )

        for names in custom_presets_by_folder.values():
            names.sort(key=preset_sort_key)
        for names in builtin_presets_by_folder.values():
            names.sort(key=preset_sort_key)

        child_folders: dict[str | None, list[dict]] = {}
        for folder in self._state["folders"]:
            child_folders.setdefault(folder.get("parent_id"), []).append(folder)
        for parent_id, items in child_folders.items():
            child_folders[parent_id] = _sort_folders(items)

        rows: list[dict] = []

        def append_preset_rows(names: list[str], depth: int) -> None:
            for preset_name in names:
                meta = self.get_preset_meta(preset_name)
                rows.append(
                    {
                        "kind": "preset",
                        "name": preset_name,
                        "depth": depth,
                        "is_pinned": bool(meta.get("pinned", False)),
                        "rating": int(meta.get("rating", 0) or 0),
                    }
                )

        def branch_has_content(folder_id: str) -> bool:
            if custom_presets_by_folder.get(folder_id):
                return True
            for child in child_folders.get(folder_id, []):
                if branch_has_content(child["id"]):
                    return True
            return False

        def append_custom_folder(folder: dict, depth: int) -> None:
            if query_text and not branch_has_content(folder["id"]):
                return

            collapsed = False if query_text else self.is_folder_collapsed(folder["id"])

            rows.append(
                {
                    "kind": "folder",
                    "folder_id": folder["id"],
                    "text": folder["name"],
                    "depth": depth,
                    "is_builtin_folder": False,
                    "is_collapsed": collapsed,
                }
            )
            if collapsed:
                return
            for child in child_folders.get(folder["id"], []):
                append_custom_folder(child, depth + 1)
            append_preset_rows(custom_presets_by_folder.get(folder["id"], []), depth + 1)

        top_level_order = list(self._state["top_level_order"])
        seen_custom_top: set[str] = set()

        for item_id in top_level_order:
            if item_id == ROOT_FOLDER_ID:
                root_names = custom_presets_by_folder.get(None, [])
                if root_names:
                    collapsed = False if query_text else self.is_folder_collapsed(ROOT_FOLDER_ID)
                    rows.append(
                        {
                            "kind": "folder",
                            "folder_id": ROOT_FOLDER_ID,
                            "text": ROOT_FOLDER_NAME,
                            "depth": 0,
                            "is_builtin_folder": True,
                            "is_collapsed": collapsed,
                        }
                    )
                    if not collapsed:
                        append_preset_rows(root_names, 1)
                continue

            if item_id in STOCK_FOLDER_IDS:
                builtin_names = builtin_presets_by_folder.get(item_id, [])
                if builtin_names:
                    collapsed = False if query_text else self.is_folder_collapsed(item_id)
                    rows.append(
                        {
                            "kind": "folder",
                            "folder_id": item_id,
                            "text": STOCK_FOLDER_NAMES[item_id],
                            "depth": 0,
                            "is_builtin_folder": True,
                            "is_collapsed": collapsed,
                        }
                    )
                    if not collapsed:
                        append_preset_rows(builtin_names, 1)
                continue

            folder = by_id.get(item_id)
            if folder is None or folder.get("parent_id") is not None:
                continue
            seen_custom_top.add(folder["id"])
            append_custom_folder(folder, 0)

        for folder in _sort_folders(item for item in self._state["folders"] if item.get("parent_id") is None):
            if folder["id"] in seen_custom_top:
                continue
            append_custom_folder(folder, 0)

        return rows

    def _require_custom_folder(self, folder_id: str) -> dict:
        folder = self._find_custom_folder(folder_id)
        if folder is None:
            raise ValueError("Folder not found")
        return folder

    def _find_custom_folder(self, folder_id: str) -> dict | None:
        self._ensure_loaded()
        assert self._state is not None
        for folder in self._state["folders"]:
            if folder["id"] == folder_id:
                return folder
        return None

    def _descendant_ids(self, folder_id: str) -> set[str]:
        self._ensure_loaded()
        assert self._state is not None

        out: set[str] = set()

        def visit(current_id: str) -> None:
            for folder in self._state["folders"]:
                if folder.get("parent_id") == current_id and folder["id"] not in out:
                    out.add(folder["id"])
                    visit(folder["id"])

        visit(folder_id)
        return out

    def _resequence_siblings(self, parent_id: str | None) -> None:
        self._ensure_loaded()
        assert self._state is not None
        siblings = _sort_folders(item for item in self._state["folders"] if item.get("parent_id") == parent_id)
        for index, folder in enumerate(siblings):
            folder["order"] = index
