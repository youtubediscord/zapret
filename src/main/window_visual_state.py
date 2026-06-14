from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class WindowVisualState:
    """Временные визуальные объекты главного окна."""

    holiday_effects: Any | None = None
    theme_manager: Any | None = None
    windows_system_theme_watcher: Any | None = None
