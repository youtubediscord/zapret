from PyQt6.QtCore import QThread, pyqtSignal

from winws_runtime.runtime.process_probe import get_canonical_winws_process_pids


class ProcessMonitorThread(QThread):
    """
    Следит за каноническими процессами winws.exe/winws2.exe через WinAPI.
    Шлёт сигнал когда состояние (запущен/остановлен) изменилось.
    """
    processStatusChanged = pyqtSignal(bool)          # True / False
    processDetailsChanged = pyqtSignal(dict)         # {"winws.exe": [pid, ...], "winws2.exe": [pid, ...]}
    checkingStarted = pyqtSignal()                   # Начало проверки
    checkingFinished = pyqtSignal()                  # Конец проверки

    def __init__(self, interval_ms: int = 5000):
        """
        Args:
            interval_ms: Интервал проверки в миллисекундах (по умолчанию 5 сек)
        """
        super().__init__()
        self.interval_ms   = interval_ms
        self._running      = True
        self._cur_state: bool | None = None
        self._cur_details: dict[str, list[int]] | None = None
        
    def _check_processes_fast(self) -> dict[str, list[int]]:
        """
        Возвращает PID канонических winws.exe/winws2.exe.

        Канонический здесь означает:
        - имя процесса совпадает;
        - полный путь процесса совпадает с ожидаемым `exe/winws*.exe` проекта.
        """
        try:
            return get_canonical_winws_process_pids()
        except Exception:
            return {}

    def _check_process_fast(self) -> bool:
        """
        Быстрая проверка через канонический WinAPI probe.
        Не блокирует GUI!
        """
        return bool(self._check_processes_fast())

    # ------------------------- ОСНОВНОЙ ЦИКЛ --------------------------
    def run(self):
        from log.log import log            # импорт здесь, чтобы не было циклических импортов
        log("Process-monitor thread started (WinAPI canonical mode)", level="INFO")

        while self._running:
            try:
                # 🔄 Сигнализируем о начале проверки
                self.checkingStarted.emit()
                
                details = self._check_processes_fast()
                is_running = bool(details)
                
                # 🔄 Сигнализируем об окончании проверки
                self.checkingFinished.emit()

                # Если детали изменились — отдаём сигнал в GUI (важно: PID может поменяться без смены bool)
                if details != self._cur_details:
                    self._cur_details = details
                    self.processDetailsChanged.emit(details)

                # Если состояние изменилось — отдаём сигнал в GUI
                if is_running != self._cur_state:
                    self._cur_state = is_running
                    log(f"canonical winws state → {is_running}", level="DEBUG")
                    self.processStatusChanged.emit(is_running)

            except Exception as e:
                from log.log import log

                log(f"Ошибка в потоке мониторинга: {e}", level="❌ ERROR")
                self.checkingFinished.emit()  # На случай ошибки тоже завершаем

            self.msleep(self.interval_ms)            # 5 сек по умолчанию

    # ------------------------ СТАНДАРТНЫЙ STOP ------------------------
    def stop(self):
        self._running = False
        self.wait()           # корректно ждём завершения run()
