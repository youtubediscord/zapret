from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Callable, Iterable

from config.config import get_zapret_userdata_dir



_SCOPE_KEY_ALIASES = {
    "preset_zapret1": "direct_preset_winws1",
    "preset_zapret2": "direct_preset_winws2",
}


def _canonical_scope_key(scope_key: str) -> str:
    raw = str(scope_key or "").strip().lower()
    if not raw:
        return ""
    return _SCOPE_KEY_ALIASES.get(raw, raw)


def _safe_scope_name(scope_key: str, *, canonicalize: bool = True) -> str:
    raw = _canonical_scope_key(scope_key) if canonicalize else str(scope_key or "").strip().lower()
    if not raw:
        raw = "default"
    raw = re.sub(r"[^a-z0-9_.-]+", "_", raw)
    return raw or "default"


def _storage_dir() -> Path:
    return Path(get_zapret_userdata_dir()) / "preset_library"


def _default_state() -> dict:
    return {
        "version": 3,
        "presets": {},
    }


def _normalize_preset_meta(raw: dict) -> dict:
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
        "rating": rating,
        "pinned": pinned,
        "order": order,
    }


@dataclass
class PresetHierarchyStore:
    scope_key: str
    _state: dict | None = None
    _display_name_by_key: dict[str, str] | None = None

    @property
    def canonical_scope_key(self) -> str:
        return _canonical_scope_key(self.scope_key) or "default"

    @property
    def state_path(self) -> Path:
        return _storage_dir() / f"{_safe_scope_name(self.canonical_scope_key)}.json"

    def _legacy_state_paths(self) -> list[Path]:
        canonical = self.canonical_scope_key
        legacy: list[Path] = []
        for alias, target in _SCOPE_KEY_ALIASES.items():
            if target != canonical:
                continue
            legacy.append(_storage_dir() / f"{_safe_scope_name(alias, canonicalize=False)}.json")
        return legacy

    def _migrate_legacy_state_if_needed(self) -> None:
        path = self.state_path
        if path.exists():
            return
        for legacy_path in self._legacy_state_paths():
            if not legacy_path.exists():
                continue
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                legacy_path.replace(path)
            except Exception:
                try:
                    path.write_text(legacy_path.read_text(encoding="utf-8"), encoding="utf-8")
                    legacy_path.unlink()
                except Exception:
                    pass
            if path.exists():
                return

    def _ensure_loaded(self) -> None:
        if self._state is not None:
            return

        path = self.state_path
        self._migrate_legacy_state_if_needed()
        state = _default_state()
        if path.exists():
            try:
                loaded = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    state.update(loaded)
            except Exception:
                state = _default_state()

        presets = {}
        for key, raw in (state.get("presets", {}) or {}).items():
            preset_key = str(key or "").strip()
            if preset_key and isinstance(raw, dict):
                presets[preset_key] = _normalize_preset_meta(raw)

        self._state = {
            "version": 3,
            "presets": presets,
        }
        self._display_name_by_key = {}

    def _save(self) -> None:
        assert self._state is not None
        path = self.state_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(self._state, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def _normalize_preset_entries(
        self,
        presets: Iterable[object],
        *,
        is_builtin_resolver: Callable[[str], bool] | None = None,
    ) -> list[dict]:
        builtin_resolver = is_builtin_resolver or (lambda _name: False)
        entries: list[dict] = []
        seen_keys: set[str] = set()

        for raw in presets:
            if isinstance(raw, dict):
                key = str(raw.get("file_name") or raw.get("key") or raw.get("name") or "").strip()
                display_name = str(raw.get("display_name") or raw.get("name") or "").strip()
                builtin_value = raw.get("is_builtin")
            else:
                key = str(raw or "").strip()
                display_name = key
                builtin_value = None

            if not key:
                continue
            if not display_name:
                display_name = Path(key).stem or key

            lowered_key = key.lower()
            if lowered_key in seen_keys:
                continue
            seen_keys.add(lowered_key)

            if builtin_value is None:
                is_builtin = bool(builtin_resolver(key))
            else:
                is_builtin = bool(builtin_value)

            entries.append(
                {
                    "key": key,
                    "display_name": display_name,
                    "is_builtin": is_builtin,
                }
            )

        return entries

    def _register_entries(self, entries: list[dict]) -> None:
        self._display_name_by_key = {}
        for entry in entries:
            key = str(entry.get("key") or "").strip()
            display_name = str(entry.get("display_name") or "").strip() or key
            if key:
                self._display_name_by_key[key] = display_name

    def _resolve_preset_key(self, preset_key: str, *, display_name: str | None = None) -> str:
        _ = display_name
        self._ensure_loaded()
        assert self._state is not None

        candidate = str(preset_key or "").strip()
        if candidate and candidate in self._state["presets"]:
            return candidate
        if self._display_name_by_key and candidate and candidate in self._display_name_by_key:
            return candidate
        return candidate

    def get_preset_meta(self, preset_name: str, *, display_name: str | None = None) -> dict:
        self._ensure_loaded()
        assert self._state is not None
        key = self._resolve_preset_key(preset_name, display_name=display_name)
        raw = self._state["presets"].get(key) or {}
        return _normalize_preset_meta(raw)

    def rename_preset_meta(
        self,
        old_name: str,
        new_name: str,
        *,
        old_display_name: str | None = None,
        new_display_name: str | None = None,
    ) -> None:
        _ = new_display_name
        self._ensure_loaded()
        assert self._state is not None

        old_key = self._resolve_preset_key(old_name, display_name=old_display_name)
        new_key = str(new_name or "").strip()
        if not old_key or not new_key or old_key == new_key:
            return

        raw = self._state["presets"].pop(old_key, None)
        if raw is None and old_display_name:
            raw = self._state["presets"].pop(str(old_display_name).strip(), None)
        if raw is not None:
            self._state["presets"][new_key] = _normalize_preset_meta(raw)
            self._save()

    def copy_preset_meta_to_new(
        self,
        source_name: str,
        new_name: str,
        *,
        source_display_name: str | None = None,
        new_display_name: str | None = None,
        reset_pin: bool = True,
        reset_rating: bool = True,
    ) -> None:
        _ = new_display_name
        source = self.get_preset_meta(source_name, display_name=source_display_name)
        copied = dict(source)
        if reset_pin:
            copied["pinned"] = False
        if reset_rating:
            copied["rating"] = 0
        copied["order"] = None
        self._set_preset_meta(new_name, copied)

    def delete_preset_meta(self, preset_name: str, *, display_name: str | None = None) -> None:
        self._ensure_loaded()
        assert self._state is not None
        key = self._resolve_preset_key(preset_name, display_name=display_name)
        if key and self._state["presets"].pop(key, None) is not None:
            self._save()

    def toggle_preset_pin(self, preset_name: str, *, display_name: str | None = None) -> bool:
        meta = self.get_preset_meta(preset_name, display_name=display_name)
        next_value = not bool(meta.get("pinned", False))
        self.set_preset_pin(preset_name, next_value, display_name=display_name)
        return next_value

    def set_preset_pin(self, preset_name: str, pinned: bool, *, display_name: str | None = None) -> None:
        self._ensure_loaded()
        assert self._state is not None
        key = self._resolve_preset_key(preset_name, display_name=display_name)
        if not key:
            return
        meta = self.get_preset_meta(key, display_name=display_name)
        meta["pinned"] = bool(pinned)
        self._set_preset_meta(key, meta)

    def set_preset_rating(self, preset_name: str, rating: int, *, display_name: str | None = None) -> None:
        self._ensure_loaded()
        assert self._state is not None
        key = self._resolve_preset_key(preset_name, display_name=display_name)
        if not key:
            return
        meta = self.get_preset_meta(key, display_name=display_name)
        try:
            normalized = int(rating)
        except Exception:
            normalized = 0
        meta["rating"] = max(0, min(10, normalized))
        self._set_preset_meta(key, meta)

    def _set_preset_meta(self, preset_name: str, meta: dict) -> None:
        assert self._state is not None
        normalized = _normalize_preset_meta(meta)
        if (
            int(normalized.get("rating", 0)) == 0
            and not bool(normalized.get("pinned", False))
            and normalized.get("order") is None
        ):
            self._state["presets"].pop(preset_name, None)
        else:
            self._state["presets"][preset_name] = normalized
        self._save()

    def _display_name_for_key(self, preset_key: str) -> str:
        return str((self._display_name_by_key or {}).get(preset_key) or preset_key)

    def _sort_preset_keys(self, names: Iterable[str]) -> list[str]:
        def sort_key(name: str) -> tuple[int, int, int, int, str]:
            meta = self.get_preset_meta(name, display_name=self._display_name_for_key(name))
            order = meta.get("order")
            return (
                0 if meta.get("pinned") else 1,
                0 if order is not None else 1,
                int(order or 0),
                -int(meta.get("rating", 0) or 0),
                self._display_name_for_key(name).lower(),
            )

        return sorted((str(name or "").strip() for name in names if str(name or "").strip()), key=sort_key)

    def list_presets_flat(
        self,
        preset_names: Iterable[object],
        *,
        is_builtin_resolver: Callable[[str], bool] | None = None,
    ) -> list[str]:
        self._ensure_loaded()
        assert self._state is not None
        entries = self._normalize_preset_entries(preset_names, is_builtin_resolver=is_builtin_resolver)
        self._register_entries(entries)
        live_keys = {
            str(item.get("key") or "").strip()
            for item in entries
            if str(item.get("key") or "").strip()
        }

        stale_keys = [
            key
            for key in list((self._state.get("presets", {}) or {}).keys())
            if key not in live_keys
        ]
        if stale_keys:
            for key in stale_keys:
                self._state["presets"].pop(key, None)
            self._save()

        names = [
            str(item.get("key") or "").strip()
            for item in entries
            if str(item.get("key") or "").strip()
        ]
        return self._sort_preset_keys(names)

    def _apply_preset_order_list(self, ordered_names: Iterable[str]) -> None:
        for index, name in enumerate(ordered_names):
            meta = self.get_preset_meta(name, display_name=self._display_name_for_key(name))
            meta["order"] = index
            self._state["presets"][name] = _normalize_preset_meta(meta)
        self._save()

    def move_preset_to_end_flat(
        self,
        preset_names: Iterable[object],
        preset_name: str,
        *,
        is_builtin_resolver: Callable[[str], bool] | None = None,
    ) -> bool:
        ordered_names = self.list_presets_flat(preset_names, is_builtin_resolver=is_builtin_resolver)
        source_name = self._resolve_preset_key(preset_name)
        if not source_name or source_name not in ordered_names:
            return False
        reordered = [name for name in ordered_names if name != source_name]
        reordered.append(source_name)
        if reordered == ordered_names:
            return False
        self._apply_preset_order_list(reordered)
        return True

    def move_preset_before_flat(
        self,
        preset_names: Iterable[object],
        preset_name: str,
        target_name: str,
        *,
        is_builtin_resolver: Callable[[str], bool] | None = None,
    ) -> bool:
        ordered_names = self.list_presets_flat(preset_names, is_builtin_resolver=is_builtin_resolver)
        source_name = self._resolve_preset_key(preset_name)
        target_preset = self._resolve_preset_key(target_name)
        if (
            not source_name
            or not target_preset
            or source_name == target_preset
            or source_name not in ordered_names
            or target_preset not in ordered_names
        ):
            return False
        reordered = [name for name in ordered_names if name != source_name]
        insert_at = reordered.index(target_preset)
        reordered.insert(insert_at, source_name)
        if reordered == ordered_names:
            return False
        self._apply_preset_order_list(reordered)
        return True

    def move_preset_by_step_flat(
        self,
        preset_names: Iterable[object],
        preset_name: str,
        direction: int,
        *,
        is_builtin_resolver: Callable[[str], bool] | None = None,
    ) -> bool:
        ordered_names = self.list_presets_flat(preset_names, is_builtin_resolver=is_builtin_resolver)
        source_name = self._resolve_preset_key(preset_name)
        if not source_name or source_name not in ordered_names:
            return False
        idx = ordered_names.index(source_name)
        new_idx = idx + int(direction)
        if new_idx < 0 or new_idx >= len(ordered_names):
            return False
        ordered_names[idx], ordered_names[new_idx] = ordered_names[new_idx], ordered_names[idx]
        self._apply_preset_order_list(ordered_names)
        return True
