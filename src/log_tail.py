# log_tail.py
from PyQt6.QtCore import QObject, pyqtSignal
import time, os, io

class LogTailWorker(QObject):
    """
    Фоновое чтение файла журнала (аналог `tail -f`).
    """
    new_lines  = pyqtSignal(str)   # отправляет пачку строк в GUI
    finished   = pyqtSignal()

    def __init__(
        self,
        file_path: str,
        poll_interval: float = .4,
        initial_chunk_chars: int = 65536,
        initial_max_bytes: int | None = None,
    ):
        super().__init__()
        self.file_path      = file_path
        self.poll_interval  = poll_interval
        self.initial_chunk_chars = max(1024, int(initial_chunk_chars or 0))
        self.initial_max_bytes = None if initial_max_bytes is None else max(0, int(initial_max_bytes))
        self._stop_requested = False

    def stop(self):
        self._stop_requested = True

    def _read_available_text(self, stream) -> str:
        """Читает уже доступные строки одним ограниченным куском."""
        live_buf = []
        live_buf_len = 0
        while not self._stop_requested:
            line = stream.readline()
            if not line:
                break
            live_buf.append(line)
            live_buf_len += len(line)
            if live_buf_len >= self.initial_chunk_chars:
                break
        return "".join(live_buf)

    def run(self):
        try:
            # ждём, пока файл появится
            while not os.path.exists(self.file_path) and not self._stop_requested:
                time.sleep(self.poll_interval)

            if self._stop_requested:
                return

            start_offset = 0
            try:
                if self.initial_max_bytes is not None:
                    size = os.path.getsize(self.file_path)
                    if size > self.initial_max_bytes:
                        start_offset = max(0, size - self.initial_max_bytes)
            except Exception:
                start_offset = 0

            # открываем с правильной кодировкой (через binary seek + TextIOWrapper)
            with open(self.file_path, "rb") as fb:
                if start_offset:
                    try:
                        fb.seek(start_offset, os.SEEK_SET)
                    except Exception:
                        fb.seek(0, os.SEEK_SET)

                with io.TextIOWrapper(fb, encoding="utf-8-sig", errors="replace", newline="") as f:
                    if start_offset and not self._stop_requested:
                        # пропускаем "обрезанную" первую строку
                        try:
                            f.readline()
                        except Exception:
                            pass

                    # читаем «историю» порциями, чтобы не подвесить UI большим emit()
                    buf = []
                    buf_len = 0
                    while not self._stop_requested:
                        line = f.readline()
                        if not line:
                            break
                        buf.append(line)
                        buf_len += len(line)
                        if buf_len >= self.initial_chunk_chars:
                            self.new_lines.emit("".join(buf))
                            buf.clear()
                            buf_len = 0

                    if buf and not self._stop_requested:
                        self.new_lines.emit("".join(buf))

                    # «хвостим» файл
                    base_sleep = max(0.1, float(self.poll_interval or 0.4))
                    max_sleep = 1.2
                    idle_sleep = base_sleep
                    while not self._stop_requested:
                        # Забираем доступные строки пачкой. При всплеске логов
                        # это создаёт один сигнал Qt вместо сотен сигналов по
                        # одной строке и заметно снижает нагрузку на UI-поток.
                        live_text = self._read_available_text(f)
                        if live_text:
                            self.new_lines.emit(live_text)
                            idle_sleep = base_sleep
                        else:
                            time.sleep(idle_sleep)
                            idle_sleep = min(max_sleep, idle_sleep + base_sleep)
        finally:
            self.finished.emit()
