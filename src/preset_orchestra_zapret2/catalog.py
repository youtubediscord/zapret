"""
Lightweight loader for Zapret 2 categories and strategies (TXT format).

This module intentionally avoids importing `strategy_menu` to keep parsing
and inference usable in non-GUI contexts and during development.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Optional

from core.presets.strategy_catalog_sanitizer import sanitize_strategy_catalog_dir


@dataclass(frozen=True)
class CatalogPaths:
    indexjson_dir: Path
    builtin_dir: Path
    user_dir: Path


_CACHED_PATHS: Optional[CatalogPaths] = None
_CACHED_CATEGORIES: Optional[Dict[str, Dict]] = None
_CACHED_STRATEGIES: Dict[tuple[str, Optional[str]], Dict[str, Dict]] = {}


_EXTERNAL_STRATEGY_BASENAME_MAP: Dict[str, Dict[str, str]] = {
    "basic": {
        "tcp": "tcp_zapret2_basic",
        "udp": "udp_zapret_basic",
        "http80": "http80_zapret2_basic",
        "discord_voice": "discord_voice_zapret2_basic",
    },
    "advanced": {
        "tcp": "tcp_zapret2_advanced",
        "tcp_fake": "tcp_fake_zapret2_advanced",
        "udp": "udp_zapret2_advanced",
        "http80": "http80_zapret2_advanced",
        "discord_voice": "discord_voice_zapret2_advanced",
    },
    "orchestra": {
        "tcp": "tcp_orchestra",
        "http80": "http80_orchestra",
    },
}


def _external_strategy_basenames(strategy_type: str, strategy_set_key: str) -> list[str]:
    # Strict mapping: only explicitly listed filenames are supported.
    strategy_key = (strategy_type or "").strip().lower()
    set_key = (strategy_set_key or "").strip().lower()
    mapped = _EXTERNAL_STRATEGY_BASENAME_MAP.get(set_key, {}).get(strategy_key)
    return [mapped] if mapped else []


def _candidate_indexjson_dirs() -> Iterable[Path]:
    env = os.environ.get("ZAPRET_INDEXJSON_FOLDER")
    if env:
        yield Path(env)

    try:
        from config import INDEXJSON_FOLDER  # type: ignore
        yield Path(INDEXJSON_FOLDER)
    except Exception:
        pass

    # Repo layout hint: /home/privacy/zapretgui -> /home/privacy/zapret
    try:
        here = Path(__file__).resolve()
        # preset_zapret2/catalog.py -> zapretgui -> Privacy
        privacy_dir = here.parents[2]
        yield privacy_dir / "zapret" / "json"
    except Exception:
        pass

    # Fallbacks
    yield Path.cwd() / "json"
    yield Path("/mnt/c/ProgramData/ZapretTwoDev/json")
    yield Path("/mnt/c/ProgramData/ZapretTwo/json")


def get_catalog_paths() -> Optional[CatalogPaths]:
    global _CACHED_PATHS
    if _CACHED_PATHS is not None:
        return _CACHED_PATHS

    for index_dir in _candidate_indexjson_dirs():
        index_dir = Path(index_dir)
        builtin_dir = index_dir / "strategies" / "builtin"
        if builtin_dir.exists() and any(builtin_dir.glob("*.txt")):
            user_dir = index_dir / "strategies" / "user"
            _CACHED_PATHS = CatalogPaths(
                indexjson_dir=index_dir,
                builtin_dir=builtin_dir,
                user_dir=user_dir,
            )
            return _CACHED_PATHS

    return None


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _parse_bool(value: str) -> bool:
    return value.strip().lower() in ("true", "1", "yes", "y", "on")


def load_categories() -> Dict[str, Dict]:
    global _CACHED_CATEGORIES
    if _CACHED_CATEGORIES is not None:
        return _CACHED_CATEGORIES

    def _load_one_text(text: str) -> Dict[str, Dict]:
        categories: Dict[str, Dict] = {}
        current_key: Optional[str] = None
        current: Dict[str, object] = {}
        section_index = 0

        def _flush() -> None:
            nonlocal current_key, current
            if not current_key:
                return
            # Categories are ordered strictly by section appearance in the file.
            file_order = current.get("_file_order")
            if isinstance(file_order, int):
                # Ignore any explicit `order`/`command_order` values in the file.
                current["order"] = file_order
                current["command_order"] = file_order
            categories[current_key] = dict(current)

        for raw in text.splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("[") and line.endswith("]"):
                _flush()
                # Keep category keys normalized (lower-case) to match preset parsing,
                # which infers category keys in lower-case from filter tokens/filenames.
                current_key = line[1:-1].strip().lower()
                section_index += 1
                current = {"key": current_key, "_file_order": section_index}
                continue
            if "=" not in line or current_key is None:
                continue

            k, _, v = line.partition("=")
            k = k.strip()
            v = v.strip()

            if k in ("order", "command_order"):
                # Deprecated: order/command_order are ignored; ordering is determined by section order.
                continue
            elif k in ("needs_new_separator", "strip_payload", "requires_all_ports"):
                current[k] = _parse_bool(v)
            else:
                current[k] = v

        _flush()
        return categories

    def _load_one(file_path: Path) -> Dict[str, Dict]:
        if not file_path.exists():
            return {}
        text = _read_text(file_path)
        return _load_one_text(text)

    paths = get_catalog_paths()
    if paths is None:
        return {}

    builtin = _load_one(paths.builtin_dir / "categories.txt")
    merged = dict(builtin)

    # User categories are stored outside the install folder (updates may overwrite it).
    def _user_categories_file() -> Path:
        appdata = os.environ.get("APPDATA")
        if appdata:
            return Path(appdata) / "zapret" / "user_categories.txt"
        return Path.home() / ".config" / "zapret" / "user_categories.txt"

    user = _load_one(_user_categories_file())
    for key, data in user.items():
        if key in merged:
            # Do NOT allow overriding built-in categories.
            continue
        merged[key] = data

    _CACHED_CATEGORIES = merged
    return _CACHED_CATEGORIES


def invalidate_categories_cache() -> None:
    global _CACHED_CATEGORIES
    _CACHED_CATEGORIES = None


def load_strategies(strategy_type: str, strategy_set: Optional[str] = None) -> Dict[str, Dict]:
    cache_key = (strategy_type, strategy_set)
    if cache_key in _CACHED_STRATEGIES:
        return _CACHED_STRATEGIES[cache_key]

    strategy_set_key = (strategy_set or "").strip().lower()

    # direct_zapret2 Basic/Advanced and direct_zapret2_orchestra strategies
    # live outside the install folder.
    # Inno Setup copies them to:
    #   %APPDATA%\zapret\direct_zapret2\basic_strategies\
    #   %APPDATA%\zapret\direct_zapret2\advanced_strategies\
    #   %APPDATA%\zapret\orchestra_zapret2\
    # We always load them from that stable per-user location.
    if strategy_set_key in ("basic", "advanced", "orchestra"):
        try:
            from config import get_zapret_userdata_dir
            base = (get_zapret_userdata_dir() or "").strip()
        except Exception:
            base = ""

        if strategy_set_key == "orchestra":
            set_dir = Path(base) / "orchestra_zapret2" if base else None
        else:
            set_dir = Path(base) / "direct_zapret2" / f"{strategy_set_key}_strategies" if base else None
        basenames = _external_strategy_basenames(strategy_type, strategy_set_key)

        def _load_one_external(file_path: Path) -> Dict[str, Dict]:
            if not file_path.exists():
                return {}
            text = _read_text(file_path)
            strategies: Dict[str, Dict] = {}
            current_id: Optional[str] = None
            current: Dict[str, object] = {}
            args: list[str] = []

            def _flush() -> None:
                nonlocal current_id, current, args
                if not current_id:
                    return
                current["id"] = current_id
                current["args"] = "\n".join(args).strip()
                strategies[current_id] = dict(current)

            for raw in text.splitlines():
                line = raw.rstrip()
                if not line or line.lstrip().startswith("#"):
                    continue
                if line.startswith("[") and line.endswith("]"):
                    _flush()
                    current_id = line[1:-1].strip()
                    current = {
                        "name": current_id,
                        "author": "unknown",
                        "label": None,
                        "description": "",
                        "blobs": [],
                    }
                    args = []
                    continue

                if current_id is None:
                    continue

                if line.startswith("--"):
                    args.append(line.strip())
                    continue

                if "=" in line:
                    k, _, v = line.partition("=")
                    k = k.strip().lower()
                    v = v.strip()
                    if k == "name":
                        current["name"] = v
                    elif k == "author":
                        current["author"] = v
                    elif k == "label":
                        current["label"] = v or None
                    elif k == "description":
                        current["description"] = v
                    elif k == "blobs":
                        current["blobs"] = [b.strip() for b in v.split(",") if b.strip()]

            _flush()
            return strategies

        merged: Dict[str, Dict] = {}
        if set_dir:
            try:
                set_dir.mkdir(parents=True, exist_ok=True)
            except Exception:
                pass
            if strategy_set_key in ("basic", "advanced"):
                sanitize_strategy_catalog_dir(set_dir)
            for basename in basenames:
                file_path = set_dir / f"{basename}.txt"
                if not file_path.exists():
                    continue
                merged = _load_one_external(file_path)
                break

        if merged:
            _CACHED_STRATEGIES[cache_key] = merged
        return merged

    paths = get_catalog_paths()
    if paths is None:
        # Same rationale as load_categories(): don't cache misses permanently.
        return {}

    filename = f"{strategy_type}.txt" if not strategy_set_key else f"{strategy_type}_{strategy_set_key}.txt"

    def _load_one(file_path: Path) -> Dict[str, Dict]:
        if not file_path.exists():
            return {}
        text = _read_text(file_path)
        strategies: Dict[str, Dict] = {}
        current_id: Optional[str] = None
        current: Dict[str, object] = {}
        args: list[str] = []

        def _flush() -> None:
            nonlocal current_id, current, args
            if not current_id:
                return
            current["id"] = current_id
            current["args"] = "\n".join(args).strip()
            strategies[current_id] = dict(current)

        for raw in text.splitlines():
            line = raw.rstrip()
            if not line or line.lstrip().startswith("#"):
                continue
            if line.startswith("[") and line.endswith("]"):
                _flush()
                current_id = line[1:-1].strip()
                current = {
                    "name": current_id,
                    "author": "unknown",
                    "label": None,
                    "description": "",
                    "blobs": [],
                }
                args = []
                continue

            if current_id is None:
                continue

            if line.startswith("--"):
                args.append(line.strip())
                continue

            if "=" in line:
                k, _, v = line.partition("=")
                k = k.strip().lower()
                v = v.strip()
                if k == "name":
                    current["name"] = v
                elif k == "author":
                    current["author"] = v
                elif k == "label":
                    current["label"] = v or None
                elif k == "description":
                    current["description"] = v
                elif k == "blobs":
                    current["blobs"] = [b.strip() for b in v.split(",") if b.strip()]

        _flush()
        return strategies

    builtin = _load_one(paths.builtin_dir / filename)
    user = _load_one(paths.user_dir / filename)
    merged = dict(builtin)
    merged.update(user)  # user overrides builtin by id

    # If the file(s) aren't present yet, don't cache an empty result: allow
    # later retries when an updater/extractor finishes writing the catalog.
    if merged:
        _CACHED_STRATEGIES[cache_key] = merged
    return merged
