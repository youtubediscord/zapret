from __future__ import annotations

from contextlib import contextmanager
import threading
from typing import Any

from folders.defaults import COMMON_FOLDER_KEY, build_default_profile_folders, classify_profile_folder
from folders.store import FolderLibraryStore, normalize_folder_state
from settings import store as settings_store

from .identity import is_profile_uid

# Сериализует read-modify-write состояния папок: воркеры перемещения и
# folder-действия страницы работают из разных потоков.
_PROFILE_FOLDER_STATE_LOCK = threading.RLock()


@contextmanager
def profile_folder_state_lock():
    with _PROFILE_FOLDER_STATE_LOCK:
        yield


def load_profile_folder_state() -> dict[str, Any]:
    try:
        folders = settings_store.get_folders_settings()
        raw_state = folders.get("profiles") if isinstance(folders, dict) else None
    except Exception:
        raw_state = None
    return normalize_folder_state(raw_state, build_default_profile_folders())


def save_profile_folder_state(state: dict[str, Any]) -> dict[str, Any]:
    with profile_folder_state_lock():
        default_state = build_default_profile_folders()
        next_state = normalize_folder_state(state, default_state)
        folders = settings_store.get_folders_settings()
        current_state = normalize_folder_state(folders.get("profiles"), default_state)
        if current_state == next_state:
            return current_state
        folders["profiles"] = next_state
        return settings_store.set_folders_settings(folders)["profiles"]


def create_profile_folder(name: str) -> str:
    with profile_folder_state_lock():
        state = load_profile_folder_state()
        store = FolderLibraryStore(state, default_state=build_default_profile_folders())
        folder_key = store.create_folder_after(name, COMMON_FOLDER_KEY)
        save_profile_folder_state(store.to_dict())
        return folder_key


def rename_profile_folder(folder_key: str, name: str) -> bool:
    with profile_folder_state_lock():
        state = load_profile_folder_state()
        store = FolderLibraryStore(state, default_state=build_default_profile_folders())
        if not store.rename_folder(folder_key, name):
            return False
        save_profile_folder_state(store.to_dict())
        return True


def delete_profile_folder(folder_key: str) -> bool:
    with profile_folder_state_lock():
        state = load_profile_folder_state()
        store = FolderLibraryStore(state, default_state=build_default_profile_folders())
        if not store.delete_folder(folder_key):
            return False
        save_profile_folder_state(store.to_dict())
        return True


def move_profile_folder_by_step(folder_key: str, direction: int) -> bool:
    with profile_folder_state_lock():
        state = load_profile_folder_state()
        store = FolderLibraryStore(state, default_state=build_default_profile_folders())
        if not store.move_folder_by_step(folder_key, direction):
            return False
        save_profile_folder_state(store.to_dict())
        return True


def set_profile_folder_collapsed(folder_key: str, collapsed: bool) -> bool:
    with profile_folder_state_lock():
        state = load_profile_folder_state()
        store = FolderLibraryStore(state, default_state=build_default_profile_folders())
        if not store.set_folder_collapsed(folder_key, collapsed):
            return False
        save_profile_folder_state(store.to_dict())
        return True


def set_profile_folders_collapsed(collapsed_by_key: dict[str, bool]) -> bool:
    changes = {
        str(folder_key or "").strip(): bool(collapsed)
        for folder_key, collapsed in dict(collapsed_by_key or {}).items()
        if str(folder_key or "").strip()
    }
    if not changes:
        return False
    with profile_folder_state_lock():
        state = load_profile_folder_state()
        store = FolderLibraryStore(state, default_state=build_default_profile_folders())
        changed = False
        for folder_key, collapsed in changes.items():
            changed = bool(store.set_folder_collapsed(folder_key, collapsed)) or changed
        if not changed:
            return False
        save_profile_folder_state(store.to_dict())
        return True


def materialize_profile_folder_items(folder_by_profile_key: dict[str, str]) -> bool:
    """Первичное размещение: закрепляет папку за профилем, у которого ещё нет
    меты. Классификация — правило ПЕРВОГО появления; уже размещённые профили
    не трогаются, дальнейшие изменения текста профиля папку не меняют."""
    assignments = {
        str(profile_key or "").strip(): str(folder_key or "").strip()
        for profile_key, folder_key in dict(folder_by_profile_key or {}).items()
        if str(profile_key or "").strip()
    }
    if not assignments:
        return False
    with profile_folder_state_lock():
        state = load_profile_folder_state()
        folders = state.get("folders", {})
        items = state.setdefault("items", {})
        changed = False
        for profile_key, folder_key in assignments.items():
            if isinstance(items.get(profile_key), dict):
                continue
            target = folder_key if isinstance(folders, dict) and folder_key in folders else COMMON_FOLDER_KEY
            items[profile_key] = {"folder_key": target, "order": None, "rating": 0}
            changed = True
        if not changed:
            return False
        save_profile_folder_state(state)
        return True


def reset_profile_folders(folder_by_profile_key: dict[str, str] | None = None) -> dict[str, Any]:
    """Сброс к начальному правилу: дефолтные папки + первичное размещение всех
    переданных профилей (ключ → папка от классификатора). Детерминирован и
    всегда возвращает свежее состояние — UI обязан перерисоваться."""
    with profile_folder_state_lock():
        state = build_default_profile_folders()
        folders = state["folders"]
        items = state["items"]
        for profile_key, folder_key in dict(folder_by_profile_key or {}).items():
            key = str(profile_key or "").strip()
            if not key:
                continue
            target = str(folder_key or "").strip()
            items[key] = {
                "folder_key": target if target in folders else COMMON_FOLDER_KEY,
                "order": None,
                "rating": 0,
            }
        return save_profile_folder_state(state)


def profile_folder_for_profile(profile, state: dict[str, Any] | None = None) -> tuple[str, str, int | None]:
    # Горячий путь: доверяем уже нормализованному состоянию, None → загрузка.
    folder_state = state if isinstance(state, dict) else load_profile_folder_state()
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
    # Горячий путь: доверяем уже нормализованному состоянию, None → загрузка.
    folder_state = state if isinstance(state, dict) else load_profile_folder_state()
    folders = folder_state.get("folders", {}) if isinstance(folder_state, dict) else {}
    folder = folders.get(key) if isinstance(folders, dict) else None
    return bool(folder.get("collapsed", False)) if isinstance(folder, dict) else False


def set_profile_folder_order(profile_key: str, order: int | None) -> bool:
    key = str(profile_key or "").strip()
    if not key:
        return False
    next_order = None if order is None else max(0, int(order))
    with profile_folder_state_lock():
        state = load_profile_folder_state()
        items = state.setdefault("items", {})
        meta = items.get(key)
        if not isinstance(meta, dict):
            if next_order is None:
                return False
            meta = {"folder_key": COMMON_FOLDER_KEY, "order": None, "rating": 0}
            items[key] = meta
        if meta.get("order") == next_order:
            return False
        meta["order"] = next_order
        save_profile_folder_state(state)
        return True


def set_profile_folder(profile_key: str, folder_key: str) -> bool:
    key = str(profile_key or "").strip()
    target_folder = str(folder_key or "").strip() or COMMON_FOLDER_KEY
    if not key:
        return False
    with profile_folder_state_lock():
        state = load_profile_folder_state()
        folders = state.get("folders", {})
        if not isinstance(folders, dict) or target_folder not in folders:
            return False
        items = state.setdefault("items", {})
        meta = items.get(key)
        if not isinstance(meta, dict):
            if target_folder == COMMON_FOLDER_KEY:
                return False
            meta = {"folder_key": target_folder, "order": None, "rating": 0}
            items[key] = meta
            save_profile_folder_state(state)
            return True
        if str(meta.get("folder_key") or COMMON_FOLDER_KEY) == target_folder:
            return False
        meta["folder_key"] = target_folder
        save_profile_folder_state(state)
        return True


def profile_classification_text(profile) -> str:
    """Текст для правила первичного размещения. Стабильные uid-ключи не несут
    классификационного сигнала и в текст не включаются; контентные ключи
    (шаблоны, legacy) — включаются, в них есть имена hostlist-ов."""
    persistent_key = str(getattr(profile, "persistent_key", "") or "")
    parts: list[str] = [
        str(getattr(profile, "display_name", "") or ""),
        str(getattr(profile, "name", "") or ""),
        "" if is_profile_uid(persistent_key) else persistent_key,
    ]
    try:
        parts.extend(str(line or "") for line in profile.match.all_lines())
    except Exception:
        pass
    return " ".join(part for part in parts if part)


_profile_classification_text = profile_classification_text


__all__ = [
    "create_profile_folder",
    "delete_profile_folder",
    "load_profile_folder_state",
    "materialize_profile_folder_items",
    "profile_classification_text",
    "move_profile_folder_by_step",
    "profile_folder_collapsed",
    "profile_folder_for_profile",
    "profile_folder_state_lock",
    "rename_profile_folder",
    "reset_profile_folders",
    "save_profile_folder_state",
    "set_profile_folder_collapsed",
    "set_profile_folders_collapsed",
    "set_profile_folder",
    "set_profile_folder_order",
]
