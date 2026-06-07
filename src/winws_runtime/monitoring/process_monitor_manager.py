from PyQt6.QtCore import QObject
from log.log import log


from winws_runtime.runtime.process_probe import get_canonical_winws_process_pids


class ProcessMonitorManager(QObject):
    """Менеджер для мониторинга процессов DPI"""
    
    def __init__(self, *, observe_process_details):
        super().__init__()
        self._observe_process_details = observe_process_details
        self.process_monitor = None
        self._retired_process_monitors = []
        self._process_details: dict[str, list[int]] = {}

    def initialize_process_monitor(self):
        """Инициализирует поток мониторинга процесса"""
        if self.process_monitor is not None:
            self._retire_process_monitor(self.process_monitor)
        
        from winws_runtime.monitoring.process_monitor import ProcessMonitorThread
        
        # 2000 ms хватает для обнаружения падения; start/stop режима preset обновляет UI сразу.
        self.process_monitor = ProcessMonitorThread(interval_ms=2000)
        
        if hasattr(self.process_monitor, "processDetailsChanged"):
            self.process_monitor.processDetailsChanged.connect(self._on_process_details_changed)
        self.process_monitor.start()
        
        log("Process Monitor инициализирован", "INFO")

    def _apply_process_details(self, details: dict | None) -> dict[str, list[int]]:
        normalized = details or {}
        self._process_details = normalized
        if callable(self._observe_process_details):
            self._observe_process_details(normalized)

        return normalized

    def refresh_now(self) -> dict[str, list[int]]:
        """Синхронно перечитывает канонические winws-процессы тем же путём, что и monitor."""
        try:
            details = get_canonical_winws_process_pids()
        except Exception as e:
            log(f"Ошибка канонического probe при refresh_now: {e}", level="DEBUG")
            details = {}
        return self._apply_process_details(details)

    def _on_process_details_changed(self, details: dict):
        """Получает детали процессов (PID) от мониторинга и кэширует для UI"""
        try:
            self._apply_process_details(details)
        except Exception as e:
            log(f"Ошибка в _on_process_details_changed: {e}", level="❌ ERROR")

    def stop_monitoring(self):
        """Останавливает мониторинг процесса"""
        if self.process_monitor:
            self._retire_process_monitor(self.process_monitor)
            self.process_monitor = None
            log("Process Monitor остановлен", "INFO")

    def _retire_process_monitor(self, monitor) -> None:
        if monitor is None:
            return
        if monitor not in self._retired_process_monitors:
            self._retired_process_monitors.append(monitor)
        try:
            finished = getattr(monitor, "finished", None)
            if finished is not None:
                finished.connect(lambda m=monitor: self._forget_retired_process_monitor(m))
        except Exception:
            pass
        monitor.stop()

    def _forget_retired_process_monitor(self, monitor) -> None:
        try:
            self._retired_process_monitors.remove(monitor)
        except ValueError:
            pass
