# telegram_proxy/proxy_logger.py
"""File-based rotating logger + ring buffer for Telegram proxy logs.

Writes logs to LOGS_FOLDER/tg_proxy.log with rotation (max 5MB, keep 3 files).
Maintains a ring buffer of last 100 lines for efficient GUI display.
"""

from __future__ import annotations

import logging
import os
import threading
from collections import deque
from logging.handlers import RotatingFileHandler
from typing import Optional

from config.config import LOGS_FOLDER


_LOG_FILENAME = "tg_proxy.log"
_MAX_BYTES = 10 * 1024 * 1024  # 10 MB
_BACKUP_COUNT = 5
_RING_BUFFER_SIZE = 100


class ProxyLogger:
    """Thread-safe logger that writes to file and maintains a ring buffer.

    Usage:
        logger = ProxyLogger()
        logger.log("Connection from 127.0.0.1:54321")
        recent = logger.drain()  # returns list of new lines since last drain
    """

    def __init__(self, ring_size: int = _RING_BUFFER_SIZE):
        self._lock = threading.Lock()
        # Ring buffer for GUI display (bounded deque)
        self._ring: deque[str] = deque(maxlen=ring_size)
        # New lines since last drain() — GUI reads these in batches
        self._pending: list[str] = []
        self._logger = self._create_file_logger()

    def _create_file_logger(self) -> logging.Logger:
        """Create a rotating file logger."""
        os.makedirs(LOGS_FOLDER, exist_ok=True)
        log_path = os.path.join(LOGS_FOLDER, _LOG_FILENAME)

        logger = logging.getLogger("tg_proxy_file")
        # Avoid duplicate handlers on re-creation
        if logger.handlers:
            return logger

        logger.setLevel(logging.INFO)
        logger.propagate = False

        handler = RotatingFileHandler(
            log_path,
            maxBytes=_MAX_BYTES,
            backupCount=_BACKUP_COUNT,
            encoding="utf-8",
        )
        formatter = logging.Formatter(
            "%(asctime)s  %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        return logger

    def log(self, message: str) -> None:
        """Write a log line to file and ring buffer. Thread-safe."""
        # Write to file
        try:
            self._logger.info(message)
        except Exception:
            pass

        # Add to ring buffer + pending list
        with self._lock:
            self._ring.append(message)
            self._pending.append(message)

    def drain(self) -> list[str]:
        """Return and clear pending log lines (new since last drain).

        Called by QTimer in the GUI thread every 500ms.
        Returns empty list if nothing new.
        """
        with self._lock:
            if not self._pending:
                return []
            lines = self._pending
            self._pending = []
            return lines

    def get_recent(self) -> list[str]:
        """Return a snapshot of the ring buffer (last N lines)."""
        with self._lock:
            return list(self._ring)

    @property
    def log_file_path(self) -> str:
        return os.path.join(LOGS_FOLDER, _LOG_FILENAME)


# Module-level singleton
_instance: Optional[ProxyLogger] = None
_instance_lock = threading.Lock()


def get_proxy_logger() -> ProxyLogger:
    """Get or create the singleton ProxyLogger instance."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = ProxyLogger()
    return _instance
