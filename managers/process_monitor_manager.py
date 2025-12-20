from PyQt6.QtCore import QObject
from log import log


class ProcessMonitorManager(QObject):
    """Менеджер для мониторинга процессов DPI"""
    
    def __init__(self, app_instance):
        super().__init__()
        self.app = app_instance
        self.process_monitor = None
        self._is_running = False

    def initialize_process_monitor(self):
        """Инициализирует поток мониторинга процесса"""
        if hasattr(self.app, 'process_monitor') and self.app.process_monitor is not None:
            self.app.process_monitor.stop()
        
        from config.process_monitor import ProcessMonitorThread
        
        self.process_monitor = ProcessMonitorThread(self.app.dpi_starter)
        self.app.process_monitor = self.process_monitor  # Сохраняем ссылку в app
        
        # Подключаем сигнал изменения статуса
        self.process_monitor.processStatusChanged.connect(self.on_process_status_changed)
        self.process_monitor.start()
        
        log("Process Monitor инициализирован", "INFO")

    def on_process_status_changed(self, is_running):
        """Обрабатывает сигнал изменения статуса процесса"""
        try:
            # Проверяем состояние автозапуска
            from autostart.registry_check import is_autostart_enabled
            autostart_active = is_autostart_enabled() if hasattr(self.app, 'service_manager') else False
            
            # Сохраняем текущее состояние
            if not hasattr(self.app, '_prev_autostart'):
                self.app._prev_autostart = False
            if not hasattr(self.app, '_prev_running'):
                self.app._prev_running = False
                
            self.app._prev_autostart = autostart_active
            self.app._prev_running = is_running
            self._is_running = is_running
            
            # ✅ Обновляем UI через UI Manager
            if hasattr(self.app, 'ui_manager'):
                self.app.ui_manager._update_all_pages(is_running, autostart_active)
            
        except Exception as e:
            log(f"Ошибка в on_process_status_changed: {e}", level="❌ ERROR")

    def stop_monitoring(self):
        """Останавливает мониторинг процесса"""
        if self.process_monitor:
            self.process_monitor.stop()
            log("Process Monitor остановлен", "INFO")
