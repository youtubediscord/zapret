# log_tail.py
from PyQt6.QtCore import QObject, pyqtSignal, QThread
import time, os, codecs

class LogTailWorker(QObject):
    """
    Фоновое чтение файла журнала (аналог `tail -f`).
    """
    new_lines  = pyqtSignal(str)   # отправляет пачку строк в GUI
    finished   = pyqtSignal()

    def __init__(self, file_path:str, poll_interval:float = .4):
        super().__init__()
        self.file_path      = file_path
        self.poll_interval  = poll_interval
        self._stop_requested = False

    def stop(self):
        self._stop_requested = True

    def run(self):
        try:
            # ждём, пока файл появится
            while not os.path.exists(self.file_path) and not self._stop_requested:
                time.sleep(self.poll_interval)

            if self._stop_requested:
                return

            # открываем с правильной кодировкой
            with codecs.open(self.file_path, "r", encoding="utf-8-sig",
                             errors="replace") as f:
                # читаем «историю» (можно ограничить размер, если нужно)
                start_text = f.read()
                if start_text:
                    self.new_lines.emit(start_text)

                # «хвостим» файл
                while not self._stop_requested:
                    line = f.readline()
                    if line:
                        self.new_lines.emit(line)
                    else:
                        time.sleep(self.poll_interval)
        finally:
            self.finished.emit()