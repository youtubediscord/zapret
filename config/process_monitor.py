from PyQt6.QtCore import QThread, pyqtSignal
import psutil


class ProcessMonitorThread(QThread):
    """
    ⚡ Следит за процессом winws.exe/winws2.exe через psutil (быстро!)
    Шлёт сигнал когда состояние (запущен/остановлен) изменилось.
    """
    processStatusChanged = pyqtSignal(bool)          # True / False
    checkingStarted = pyqtSignal()                   # Начало проверки
    checkingFinished = pyqtSignal()                  # Конец проверки

    def __init__(self, dpi_starter, interval_ms: int = 5000):
        """
        Args:
            dpi_starter: Экземпляр BatDPIStart для fallback проверки
            interval_ms: Интервал проверки в миллисекундах (по умолчанию 5 сек)
        """
        super().__init__()
        self.dpi_starter   = dpi_starter
        self.interval_ms   = interval_ms
        self._running      = True
        self._cur_state: bool | None = None
        
        # Кэш имен процессов для быстрого поиска
        self._target_names = frozenset(['winws.exe', 'winws2.exe'])

    def _check_process_fast(self) -> bool:
        """
        ⚡ Быстрая проверка через psutil (~1-10ms)
        Не блокирует GUI!
        """
        try:
            for proc in psutil.process_iter(['name']):
                try:
                    proc_name = proc.info['name']
                    if proc_name and proc_name.lower() in self._target_names:
                        return True
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue
            return False
        except Exception:
            # Fallback на метод из dpi_starter если psutil сломался
            return self.dpi_starter.check_process_running_fast(silent=True)

    # ------------------------- ОСНОВНОЙ ЦИКЛ --------------------------
    def run(self):
        from log import log            # импорт здесь, чтобы не было циклических импортов
        log("Process-monitor thread started (psutil mode)", level="INFO")

        while self._running:
            try:
                # 🔄 Сигнализируем о начале проверки
                self.checkingStarted.emit()
                
                # ⚡ Используем быструю проверку через psutil
                is_running = self._check_process_fast()
                
                # 🔄 Сигнализируем об окончании проверки
                self.checkingFinished.emit()

                # Если состояние изменилось — отдаём сигнал в GUI
                if is_running != self._cur_state:
                    self._cur_state = is_running
                    log(f"winws.exe state → {is_running}", level="DEBUG")
                    self.processStatusChanged.emit(is_running)

            except Exception as e:
                from log import log
                log(f"Ошибка в потоке мониторинга: {e}", level="❌ ERROR")
                self.checkingFinished.emit()  # На случай ошибки тоже завершаем

            self.msleep(self.interval_ms)            # 5 сек по умолчанию

    # ------------------------ СТАНДАРТНЫЙ STOP ------------------------
    def stop(self):
        self._running = False
        self.wait()           # корректно ждём завершения run()