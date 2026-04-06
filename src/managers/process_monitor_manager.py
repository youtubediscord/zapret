from PyQt6.QtCore import QObject
from log import log


class ProcessMonitorManager(QObject):
    """Менеджер для мониторинга процессов DPI"""
    
    def __init__(self, app_instance):
        super().__init__()
        self.app = app_instance
        self.process_monitor = None
        self._process_details: dict[str, list[int]] = {}

    def initialize_process_monitor(self):
        """Инициализирует поток мониторинга процесса"""
        if hasattr(self.app, 'process_monitor') and self.app.process_monitor is not None:
            self.app.process_monitor.stop()
        
        from config.process_monitor import ProcessMonitorThread
        
        # 2000 ms is enough for crash detection; direct start/stop already updates UI immediately.
        self.process_monitor = ProcessMonitorThread(self.app.dpi_starter, interval_ms=2000)
        self.app.process_monitor = self.process_monitor  # Сохраняем ссылку в app
        
        if hasattr(self.process_monitor, "processDetailsChanged"):
            self.process_monitor.processDetailsChanged.connect(self._on_process_details_changed)
        self.process_monitor.start()
        
        log("Process Monitor инициализирован", "INFO")

    def _on_process_details_changed(self, details: dict):
        """Получает детали процессов (PID) от мониторинга и кэширует для UI"""
        try:
            self._process_details = details or {}
            self.app.process_details = self._process_details
            runtime_service = getattr(self.app, "dpi_runtime_service", None)
            if runtime_service is not None:
                runtime_service.observe_process_details(self._process_details)
        except Exception as e:
            log(f"Ошибка в _on_process_details_changed: {e}", level="❌ ERROR")

    def stop_monitoring(self):
        """Останавливает мониторинг процесса"""
        if self.process_monitor:
            self.process_monitor.stop()
            log("Process Monitor остановлен", "INFO")
