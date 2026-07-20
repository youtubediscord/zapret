"""Разовое фоновое чтение выбранного старого журнала."""

from __future__ import annotations

import io
import os

from PyQt6.QtCore import QObject, pyqtSignal


class LogFileReaderWorker(QObject):
    new_lines = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(
        self,
        file_path: str,
        *,
        chunk_chars: int = 65536,
        max_bytes: int | None = 1024 * 1024,
    ) -> None:
        super().__init__()
        self.file_path = str(file_path)
        self.chunk_chars = max(1024, int(chunk_chars or 0))
        self.max_bytes = None if max_bytes is None else max(0, int(max_bytes))
        self._stop_requested = False

    def stop(self) -> None:
        self._stop_requested = True

    def run(self) -> None:
        try:
            if self._stop_requested or not os.path.exists(self.file_path):
                return

            start_offset = 0
            if self.max_bytes is not None:
                try:
                    size = os.path.getsize(self.file_path)
                    if size > self.max_bytes:
                        start_offset = max(0, size - self.max_bytes)
                except OSError:
                    start_offset = 0

            with open(self.file_path, "rb") as binary_stream:
                if start_offset:
                    binary_stream.seek(start_offset, os.SEEK_SET)

                with io.TextIOWrapper(
                    binary_stream,
                    encoding="utf-8-sig",
                    errors="replace",
                    newline="",
                ) as text_stream:
                    if start_offset and not self._stop_requested:
                        text_stream.readline()

                    buffer: list[str] = []
                    buffer_chars = 0
                    while not self._stop_requested:
                        line = text_stream.readline()
                        if not line:
                            break
                        buffer.append(line)
                        buffer_chars += len(line)
                        if buffer_chars >= self.chunk_chars:
                            self.new_lines.emit("".join(buffer))
                            buffer.clear()
                            buffer_chars = 0

                    if buffer and not self._stop_requested:
                        self.new_lines.emit("".join(buffer))
        finally:
            self.finished.emit()


__all__ = ["LogFileReaderWorker"]
