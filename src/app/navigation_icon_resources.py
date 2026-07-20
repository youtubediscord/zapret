from __future__ import annotations

from pathlib import Path

from config.runtime_layout import APPLICATION_RESOURCE_PATHS


def resolve_windows11_sidebar_icon_path(file_name: str) -> str:
    clean_name = str(file_name or "").strip()
    if not clean_name:
        return ""

    candidate = APPLICATION_RESOURCE_PATHS.sidebar_icons_dir / Path(clean_name).name
    return str(candidate) if candidate.is_file() else ""


__all__ = ["resolve_windows11_sidebar_icon_path"]
