from __future__ import annotations

import threading
from collections.abc import Callable

from PyQt6.QtCore import QTimer


def start_daemon_thread(name: str, target: Callable[[], None]) -> threading.Thread:
    thread = threading.Thread(target=target, daemon=True, name=str(name or "StartupPostInitWorker"))
    thread.start()
    return thread


def schedule_after(delay_ms: int, callback: Callable[[], None]) -> None:
    QTimer.singleShot(int(delay_ms), callback)
