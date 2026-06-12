from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Any

from .models import Preset, Profile


@dataclass(frozen=True)
class PresetProfileMoveResult:
    profile_key: str
    key_map: dict[str, str]

    def __bool__(self) -> bool:
        return bool(str(self.profile_key or "").strip())

    def __str__(self) -> str:
        return str(self.profile_key or "")

    def __eq__(self, other) -> bool:
        if isinstance(other, str):
            return str(self) == other
        if isinstance(other, PresetProfileMoveResult):
            return self.profile_key == other.profile_key and self.key_map == other.key_map
        return False


def resolve_preset_profile_row_index(preset: Preset, profile_key: str) -> int | None:
    key = str(profile_key or "").strip()
    if not key:
        return None
    for index, profile in enumerate(tuple(getattr(preset, "profiles", ()) or ())):
        if str(getattr(profile, "key", "") or "") == key:
            return index
    return None


def resolve_preset_profile_reference_index(preset: Preset, profile_key: str) -> int | None:
    row_index = resolve_preset_profile_row_index(preset, profile_key)
    if row_index is not None:
        return row_index

    key = str(profile_key or "").strip()
    if not key:
        return None
    matches = [
        index
        for index, profile in enumerate(tuple(getattr(preset, "profiles", ()) or ()))
        if str(getattr(profile, "persistent_key", "") or "") == key
    ]
    return matches[0] if len(matches) == 1 else None


def find_profile_list_source(sources, profile_key: str):
    key = str(profile_key or "").strip()
    if not key:
        return None
    exact = next(
        (source for source in tuple(sources or ()) if str(getattr(source, "key", "") or "") == key),
        None,
    )
    if exact is not None:
        return exact
    matches = [
        source
        for source in tuple(sources or ())
        if str(getattr(getattr(source, "profile", None), "persistent_key", "") or "") == key
    ]
    return matches[0] if len(matches) == 1 else None


def build_preset_profile_key_map(before: tuple[Profile, ...], after: tuple[Profile, ...]) -> dict[str, str]:
    after_keys_by_signature: dict[tuple[str, ...], deque[str]] = defaultdict(deque)
    for profile in tuple(after or ()):
        after_keys_by_signature[_profile_content_signature(profile)].append(str(getattr(profile, "key", "") or ""))

    result: dict[str, str] = {}
    for profile in tuple(before or ()):
        old_key = str(getattr(profile, "key", "") or "")
        if not old_key:
            continue
        candidates = after_keys_by_signature.get(_profile_content_signature(profile))
        if not candidates:
            continue
        new_key = candidates.popleft()
        if new_key:
            result[old_key] = new_key
    return result


def remap_profile_item_keys(items: tuple[Any, ...], key_map: dict[str, str]) -> tuple[Any, ...]:
    clean_map = {
        str(old_key or "").strip(): str(new_key or "").strip()
        for old_key, new_key in dict(key_map or {}).items()
        if str(old_key or "").strip() and str(new_key or "").strip()
    }
    if not clean_map:
        return tuple(items or ())

    result: list[Any] = []
    for row, item in enumerate(tuple(items or ())):
        old_key = str(getattr(item, "key", "") or "").strip()
        new_key = clean_map.get(old_key)
        if not new_key or new_key == old_key:
            result.append(item)
            continue
        result.append(_profile_item_with_key(item, new_key, row))
    return tuple(result)


def remap_profile_operation_keys(operation: dict[str, str], key_map: dict[str, str]) -> dict[str, str]:
    clean_map = {
        str(old_key or "").strip(): str(new_key or "").strip()
        for old_key, new_key in dict(key_map or {}).items()
        if str(old_key or "").strip() and str(new_key or "").strip()
    }
    if not clean_map:
        return dict(operation or {})
    result = dict(operation or {})
    for field in ("profile_key", "source_profile_key", "destination_profile_key"):
        value = str(result.get(field) or "").strip()
        if value in clean_map:
            result[field] = clean_map[value]
    return result


def profile_order_row_identity(item: Any) -> str:
    return str(getattr(item, "key", "") or getattr(item, "persistent_key", "") or "")


def preset_profile_move_result_key(result) -> str:
    return str(getattr(result, "profile_key", result or "") or "").strip()


def preset_profile_move_key_map(result) -> dict[str, str]:
    value = getattr(result, "key_map", None)
    return dict(value or {}) if isinstance(value, dict) else {}


def _profile_content_signature(profile: Profile) -> tuple[str, ...]:
    return tuple(
        str(getattr(segment, "text", "") or "").strip()
        for segment in tuple(getattr(profile, "segments", ()) or ())
        if str(getattr(segment, "text", "") or "").strip()
    )


def _profile_item_with_key(item: Any, key: str, row: int):
    changes = {
        "key": key,
        "profile_index": _profile_index_from_key(key, fallback=row),
        "order": row,
    }
    try:
        from dataclasses import replace

        return replace(item, **changes)
    except Exception:
        from types import SimpleNamespace

        data = dict(getattr(item, "__dict__", {}) or {})
        data.update(changes)
        return SimpleNamespace(**data)


def _profile_index_from_key(key: str, *, fallback: int) -> int:
    prefix, separator, value = str(key or "").partition(":")
    if prefix == "profile" and separator:
        try:
            return int(value)
        except ValueError:
            return int(fallback)
    return int(fallback)


__all__ = [
    "PresetProfileMoveResult",
    "build_preset_profile_key_map",
    "find_profile_list_source",
    "preset_profile_move_key_map",
    "preset_profile_move_result_key",
    "profile_order_row_identity",
    "remap_profile_item_keys",
    "remap_profile_operation_keys",
    "resolve_preset_profile_reference_index",
    "resolve_preset_profile_row_index",
]
