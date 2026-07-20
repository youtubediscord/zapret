"""Жизненный цикл отдельных журналов длительных диагностических запусков."""

from __future__ import annotations

import atexit
import os
import threading
from pathlib import Path
from typing import TextIO


class RunLogSessionRegistry:
    """Держит по одному открытому файлу на активный диагностический запуск."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._handles: dict[str, TextIO] = {}

    @staticmethod
    def _key(path: str | os.PathLike[str]) -> str:
        return os.path.normcase(os.path.abspath(os.fspath(path)))

    def start(self, path: str | os.PathLike[str], header: str) -> bool:
        key = self._key(path)
        file_path = Path(path)
        with self._lock:
            self._close_locked(key)
            try:
                file_path.parent.mkdir(parents=True, exist_ok=True)
                handle = file_path.open(
                    "w",
                    encoding="utf-8-sig",
                    buffering=1,
                    newline="",
                )
                handle.write(str(header or ""))
                handle.flush()
                self._handles[key] = handle
                return True
            except Exception:
                return False

    def append(self, path: str | os.PathLike[str] | None, text: str) -> None:
        if not path:
            return
        key = self._key(path)
        payload = str(text or "")
        if not payload.endswith("\n"):
            payload += "\n"

        with self._lock:
            handle = self._handles.get(key)
            if handle is None:
                try:
                    file_path = Path(path)
                    file_path.parent.mkdir(parents=True, exist_ok=True)
                    # Файл уже мог содержать BOM от start(); при восстановлении
                    # сеанса не вставляем второй BOM в середину.
                    handle = file_path.open(
                        "a",
                        encoding="utf-8",
                        buffering=1,
                        newline="",
                    )
                    self._handles[key] = handle
                except Exception:
                    return
            try:
                handle.write(payload)
            except Exception:
                self._close_locked(key)

    def close(self, path: str | os.PathLike[str] | None) -> None:
        if not path:
            return
        with self._lock:
            self._close_locked(self._key(path))

    def close_all(self) -> None:
        with self._lock:
            for key in list(self._handles):
                self._close_locked(key)

    @property
    def active_session_count(self) -> int:
        with self._lock:
            return len(self._handles)

    def _close_locked(self, key: str) -> None:
        handle = self._handles.pop(key, None)
        if handle is None:
            return
        try:
            handle.flush()
        except Exception:
            pass
        try:
            handle.close()
        except Exception:
            pass


run_log_sessions = RunLogSessionRegistry()
atexit.register(run_log_sessions.close_all)


__all__ = ["RunLogSessionRegistry", "run_log_sessions"]
