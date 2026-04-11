from __future__ import annotations

import threading

from PyQt6.QtCore import QThread, pyqtSignal, QObject

from log import log


class WinwsOutputWorker(QObject):
    """Worker для чтения stdout/stderr от процесса winws."""

    new_output = pyqtSignal(str, str)
    process_ended = pyqtSignal(int)
    finished = pyqtSignal()

    def __init__(self):
        super().__init__()
        self._running = False
        self._process = None

    def set_process(self, process):
        self._process = process

    def run(self):
        self._running = True

        if not self._process:
            self.finished.emit()
            return

        def read_stream(stream, stream_type):
            try:
                while self._running and self._process.poll() is None:
                    line = stream.readline()
                    if line:
                        try:
                            text = line.decode("utf-8", errors="replace").rstrip()
                        except Exception:
                            text = str(line).rstrip()
                        if text:
                            self.new_output.emit(text, stream_type)
                    else:
                        if not self._running:
                            break
                        QThread.msleep(25)

                remaining = stream.read()
                if remaining:
                    try:
                        text = remaining.decode("utf-8", errors="replace").rstrip()
                    except Exception:
                        text = str(remaining).rstrip()
                    if text:
                        for line in text.split("\n"):
                            if line.strip():
                                self.new_output.emit(line.strip(), stream_type)
            except Exception as e:
                log(f"Ошибка чтения {stream_type}: {e}", "DEBUG")

        stdout_thread = None
        stderr_thread = None

        if self._process.stdout:
            stdout_thread = threading.Thread(
                target=read_stream,
                args=(self._process.stdout, "stdout"),
                daemon=True,
            )
            stdout_thread.start()

        if self._process.stderr:
            stderr_thread = threading.Thread(
                target=read_stream,
                args=(self._process.stderr, "stderr"),
                daemon=True,
            )
            stderr_thread.start()

        try:
            while self._running and self._process.poll() is None:
                QThread.msleep(200)

            if stdout_thread and stdout_thread.is_alive():
                stdout_thread.join(timeout=1.0)
            if stderr_thread and stderr_thread.is_alive():
                stderr_thread.join(timeout=1.0)

            if self._process.returncode is not None:
                self.process_ended.emit(self._process.returncode)

        except Exception as e:
            log(f"Ошибка мониторинга процесса: {e}", "DEBUG")

        self._running = False
        self.finished.emit()

    def stop(self):
        self._running = False
