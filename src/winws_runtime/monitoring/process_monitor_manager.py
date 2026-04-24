from PyQt6.QtCore import QObject
from log.log import log


from winws_runtime.runtime.process_probe import get_canonical_winws_process_pids


class ProcessMonitorManager(QObject):
    """Менеджер для мониторинга процессов DPI"""
    
    def __init__(self, app_instance):
        super().__init__()
        self.app = app_instance
        self.process_monitor = None
        self._process_details: dict[str, list[int]] = {}

    def initialize_process_monitor(self):
        """Инициализирует поток мониторинга процесса"""
        if self.process_monitor is not None:
            self.process_monitor.stop()
        
        from winws_runtime.monitoring.process_monitor import ProcessMonitorThread
        
        # 2000 ms is enough for crash detection; direct start/stop already updates UI immediately.
        self.process_monitor = ProcessMonitorThread(interval_ms=2000)
        
        if hasattr(self.process_monitor, "processDetailsChanged"):
            self.process_monitor.processDetailsChanged.connect(self._on_process_details_changed)
        self.process_monitor.start()
        
        log("Process Monitor инициализирован", "INFO")

    def _apply_process_details(self, details: dict | None) -> dict[str, list[int]]:
        normalized = details or {}
        self._process_details = normalized
        self.app.process_details = normalized

        runtime_service = getattr(self.app, "launch_runtime_service", None)
        if runtime_service is not None:
            runtime_service.observe_process_details(normalized)

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
            self.process_monitor.stop()
            log("Process Monitor остановлен", "INFO")
