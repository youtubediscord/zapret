from __future__ import annotations

import os

from config.config import is_dev_build_channel
from config.runtime_layout import APPLICATION_PATHS


def resolve_existing_app_icon_path() -> str:
    preferred_path = APPLICATION_PATHS.dev_icon if is_dev_build_channel() else APPLICATION_PATHS.stable_icon
    for candidate in (preferred_path, APPLICATION_PATHS.stable_icon):
        clean_path = str(candidate)
        if clean_path and os.path.exists(clean_path):
            return os.path.abspath(clean_path)
    return ""


__all__ = ["resolve_existing_app_icon_path"]
