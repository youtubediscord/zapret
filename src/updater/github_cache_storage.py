from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from config.runtime_layout import APPLICATION_PATHS
from utils.atomic_text import atomic_write_text


GITHUB_CACHE_FILE_NAME = "updater_github_cache.json"


def get_github_cache_path() -> Path:
    return APPLICATION_PATHS.tmp_dir / GITHUB_CACHE_FILE_NAME


def load_github_cache() -> dict[str, Any]:
    path = get_github_cache_path()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return raw if isinstance(raw, dict) else {}


def save_github_cache(cache_data: dict[str, Any]) -> None:
    path = get_github_cache_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = cache_data if isinstance(cache_data, dict) else {}
    atomic_write_text(
        path,
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )


__all__ = [
    "get_github_cache_path",
    "load_github_cache",
    "save_github_cache",
]
