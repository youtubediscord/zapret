from __future__ import annotations

from settings.dpi.commands import get_launch_method


def get_current_launch_method(*, default: str = "") -> str:
    try:
        return str(get_launch_method() or "").strip().lower()
    except Exception:
        return str(default or "").strip().lower()


__all__ = [
    "get_current_launch_method",
]
