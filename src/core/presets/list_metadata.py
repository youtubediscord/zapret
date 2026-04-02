from __future__ import annotations

from datetime import datetime
from pathlib import Path
import re


_DESCRIPTION_HEADER_RE = re.compile(r"#\s*Description:\s*(.*)", re.IGNORECASE)
_ICON_COLOR_HEADER_RE = re.compile(r"#\s*IconColor:\s*(.+)", re.IGNORECASE)
_PRESET_LIST_METADATA_CACHE: dict[tuple[str, int, int], dict[str, str]] = {}


def _mtime_ns(stat_result) -> int:
    try:
        return int(getattr(stat_result, "st_mtime_ns"))
    except Exception:
        try:
            return int(float(stat_result.st_mtime) * 1_000_000_000)
        except Exception:
            return 0


def _format_file_modified_display(stat_result) -> str:
    try:
        return datetime.fromtimestamp(float(stat_result.st_mtime)).strftime("%d.%m.%Y %H:%M")
    except Exception:
        return ""


def read_preset_list_metadata(path: Path) -> dict[str, str]:
    """
    Reads lightweight preset metadata for list rendering.

    The date source of truth is the filesystem modification time.
    In Windows production runs, `Path.stat()` exposes that directly from the
    file metadata managed by the OS.
    """
    result = {
        "description": "",
        "modified_display": "",
        "icon_color": "",
    }
    cache_key: tuple[str, int, int] | None = None

    try:
        stat_result = path.stat()
        result["modified_display"] = _format_file_modified_display(stat_result)
        cache_key = (str(path), _mtime_ns(stat_result), int(getattr(stat_result, "st_size", 0) or 0))
        cached = _PRESET_LIST_METADATA_CACHE.get(cache_key)
        if cached is not None:
            return dict(cached)
    except Exception:
        pass

    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            for raw in handle:
                stripped = raw.strip()
                if not stripped:
                    continue
                if not stripped.startswith("#"):
                    break

                desc_match = _DESCRIPTION_HEADER_RE.match(stripped)
                if desc_match:
                    result["description"] = desc_match.group(1).strip()
                    continue

                icon_color_match = _ICON_COLOR_HEADER_RE.match(stripped)
                if icon_color_match:
                    result["icon_color"] = icon_color_match.group(1).strip()
                    continue
    except Exception:
        pass

    if cache_key is not None:
        try:
            _PRESET_LIST_METADATA_CACHE[cache_key] = dict(result)
        except Exception:
            pass

    return result
