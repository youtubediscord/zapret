from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, Optional


_CACHED_TARGET_METADATA: Optional[Dict[str, Dict]] = None


def load_target_metadata() -> Dict[str, Dict]:
    global _CACHED_TARGET_METADATA
    if _CACHED_TARGET_METADATA is not None:
        return _CACHED_TARGET_METADATA

    merged: Dict[str, Dict] = {}
    for key, data in _load_one(_target_metadata_file_path()).items():
        merged[key] = data
    for key, data in _load_one(_broad_target_metadata_file_path()).items():
        if key not in merged:
            merged[key] = data
    for key, data in _load_one(_user_target_metadata_file_path()).items():
        if key not in merged:
            merged[key] = data
    for key, data in _load_one(_user_broad_target_metadata_file_path()).items():
        if key not in merged:
            merged[key] = data

    _CACHED_TARGET_METADATA = merged
    return _CACHED_TARGET_METADATA


def invalidate_target_metadata_cache() -> None:
    global _CACHED_TARGET_METADATA
    _CACHED_TARGET_METADATA = None


def _target_metadata_file_path() -> Path:
    user_candidate = _user_target_metadata_file_path()
    if user_candidate.exists():
        return user_candidate

    package_candidate = _package_target_metadata_file_path()
    if package_candidate.exists():
        return package_candidate
    return Path("__missing_target_metadata__.txt")


def _package_target_metadata_file_path() -> Path:
    return Path(__file__).resolve().parents[1] / "metadata" / "targets.txt"


def _broad_target_metadata_file_path() -> Path:
    user_candidate = _user_broad_target_metadata_file_path()
    if user_candidate.exists():
        return user_candidate

    package_candidate = _package_broad_target_metadata_file_path()
    if package_candidate.exists():
        return package_candidate
    return Path("__missing_broad_target_metadata__.txt")


def _package_broad_target_metadata_file_path() -> Path:
    return Path(__file__).resolve().parents[1] / "metadata" / "broad_targets.txt"


def _user_target_metadata_file_path() -> Path:
    try:
        from config.config import get_zapret_userdata_dir


        base = (get_zapret_userdata_dir() or "").strip()
        if base:
            return Path(base) / "direct_preset" / "metadata" / "targets.txt"
    except Exception:
        pass

    appdata = os.environ.get("APPDATA")
    if appdata:
        return Path(appdata) / "zapret" / "direct_preset" / "metadata" / "targets.txt"
    return Path.home() / ".config" / "zapret" / "direct_preset" / "metadata" / "targets.txt"


def _user_broad_target_metadata_file_path() -> Path:
    try:
        from config.config import get_zapret_userdata_dir


        base = (get_zapret_userdata_dir() or "").strip()
        if base:
            return Path(base) / "direct_preset" / "metadata" / "broad_targets.txt"
    except Exception:
        pass

    appdata = os.environ.get("APPDATA")
    if appdata:
        return Path(appdata) / "zapret" / "direct_preset" / "metadata" / "broad_targets.txt"
    return Path.home() / ".config" / "zapret" / "direct_preset" / "metadata" / "broad_targets.txt"


def _load_one(path: Path) -> Dict[str, Dict]:
    if not path.exists() or not path.is_file():
        return {}

    items: Dict[str, Dict] = {}
    current_key: Optional[str] = None
    current: Dict[str, object] = {}
    section_index = 0

    def flush() -> None:
        nonlocal current_key, current
        if not current_key:
            return
        file_order = current.get("_file_order")
        if isinstance(file_order, int):
            current["order"] = file_order
            current["command_order"] = file_order
        items[current_key] = dict(current)

    text = path.read_text(encoding="utf-8", errors="replace")
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            flush()
            current_key = line[1:-1].strip().lower()
            section_index += 1
            current = {"key": current_key, "_file_order": section_index}
            continue
        if "=" not in line or current_key is None:
            continue

        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()

        if key in ("order", "command_order"):
            continue
        if key in ("needs_new_separator", "strip_payload", "requires_all_ports"):
            current[key] = value.lower() in ("true", "1", "yes", "y", "on")
            continue
        current[key] = value

    flush()
    return items
