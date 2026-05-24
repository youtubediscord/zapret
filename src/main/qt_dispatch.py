from __future__ import annotations

from collections.abc import Callable

from PyQt6.QtCore import QTimer


def run_queued(callback: Callable[[], None]) -> None:
    QTimer.singleShot(0, callback)
