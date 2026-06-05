from __future__ import annotations

import os

from config.config import ICON_DEV_PATH, ICON_PATH, is_dev_build_channel


def resolve_existing_app_icon_path() -> str:
    preferred_path = ICON_DEV_PATH if is_dev_build_channel() else ICON_PATH
    for candidate in (preferred_path, ICON_PATH):
        clean_path = str(candidate or "")
        if clean_path and os.path.exists(clean_path):
            return os.path.abspath(clean_path)
    return ""


__all__ = ["resolve_existing_app_icon_path"]
