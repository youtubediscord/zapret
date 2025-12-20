# dns/dns_worker.py
"""
Воркеры для DNS операций (упрощенная Win32 версия)
"""
from PyQt6.QtCore import QThread, pyqtSignal, QTimer
from log import log
import time

# ══════════════════════════════════════════════════════════════════════
#  SafeDNSWorker - фоновый воркер для применения DNS
# ══════════════════════════════════════════════════════════════════════

class SafeDNSWorker(QThread):
    """Безопасный воркер для применения DNS в фоновом режиме"""
    
    status_update = pyqtSignal(str)
    finished_with_result = pyqtSignal(bool)
    
    def __init__(self, skip_on_startup=False):
        super().__init__()
        self.skip_on_startup = skip_on_startup
    
    def run(self):
        """Выполнение DNS операций"""
        try:
            # Задержка при запуске для стабильности
            if self.skip_on_startup:
                log("DNS worker: задержка перед применением", "DEBUG")
                time.sleep(2)
            
            from .dns_force import DNSForceManager, ensure_default_force_dns
            
            # Создаем ключ если нет
            ensure_default_force_dns()
            
            # Создаем менеджер
            manager = DNSForceManager(status_callback=self.status_update.emit)
            
            # Проверяем, включен ли принудительный DNS
            if not manager.is_force_dns_enabled():
                self.status_update.emit("⚙️ Принудительный DNS отключен")
                self.finished_with_result.emit(False)
                return
            
            # Применяем DNS
            self.status_update.emit("⏳ Применение DNS настроек...")
            
            success, total = manager.force_dns_on_all_adapters(
                include_disconnected=False,
                enable_ipv6=True
            )
            
            # Результат
            if success > 0:
                msg = f"✅ DNS применен: {success}/{total} адаптеров"
                self.status_update.emit(msg)
                log(msg, "DNS")
                self.finished_with_result.emit(True)
            else:
                msg = "⚠️ DNS не применен ни к одному адаптеру"
                self.status_update.emit(msg)
                log(msg, "WARNING")
                self.finished_with_result.emit(False)
        
        except Exception as e:
            error_msg = f"❌ Ошибка DNS worker: {e}"
            log(error_msg, "ERROR")
            self.status_update.emit("❌ Ошибка применения DNS")
            self.finished_with_result.emit(False)

# ══════════════════════════════════════════════════════════════════════
#  DNSUIManager - менеджер UI для DNS операций
# ══════════════════════════════════════════════════════════════════════

class DNSUIManager:
    """Менеджер UI для DNS операций"""
    
    def __init__(self, parent, status_callback=None):
        """
        Args:
            parent: родительский виджет
            status_callback: функция для обновления статуса
        """
        self.parent = parent
        self.status_callback = status_callback or (lambda msg: None)
        self.dns_worker = None
    
    def apply_dns_settings_async(self, skip_on_startup=False):
        """
        Асинхронное применение DNS настроек
        
        Args:
            skip_on_startup: добавить задержку перед применением
            
        Returns:
            bool: True если запущено успешно
        """
        try:
            # Проверяем, не запущен ли уже воркер
            if self.dns_worker and self.dns_worker.isRunning():
                log("DNS worker уже запущен", "WARNING")
                return False
            
            log("Запуск DNS worker", "DEBUG")
            
            # Создаем и запускаем воркер
            self.dns_worker = SafeDNSWorker(skip_on_startup)
            self.dns_worker.status_update.connect(self.status_callback)
            self.dns_worker.finished_with_result.connect(self._on_finished)
            self.dns_worker.start()
            
            return True
            
        except Exception as e:
            log(f"Ошибка запуска DNS worker: {e}", "ERROR")
            self.status_callback("❌ Ошибка запуска DNS")
            return False
    
    def _on_finished(self, success):
        """Обработчик завершения DNS операции"""
        try:
            if success:
                log("DNS операция завершена успешно", "DNS")
            else:
                log("DNS операция завершена с ошибками", "WARNING")
            
            # Очищаем воркер
            if self.dns_worker:
                self.dns_worker.quit()
                self.dns_worker.wait(500)
                self.dns_worker.deleteLater()
                self.dns_worker = None
                
        except Exception as e:
            log(f"Ошибка в обработчике завершения DNS: {e}", "DEBUG")
    
    def cleanup(self):
        """Очистка ресурсов"""
        try:
            if self.dns_worker:
                if self.dns_worker.isRunning():
                    log("Останавливаем DNS worker...", "DEBUG")
                    self.dns_worker.quit()
                    if not self.dns_worker.wait(2000):
                        log("⚠ DNS worker не завершился, принудительно завершаем", "WARNING")
                        try:
                            self.dns_worker.terminate()
                            self.dns_worker.wait(500)
                        except:
                            pass
                try:
                    self.dns_worker.deleteLater()
                except:
                    pass
                self.dns_worker = None
        except Exception as e:
            log(f"Ошибка очистки DNS worker: {e}", "DEBUG")

# ══════════════════════════════════════════════════════════════════════
#  DNSStartupManager - менеджер DNS при запуске приложения
# ══════════════════════════════════════════════════════════════════════

class DNSStartupManager:
    """Менеджер для применения DNS при запуске приложения"""
    
    # Флаг для временного отключения (если есть проблемы)
    DISABLE_ON_STARTUP = False
    
    @staticmethod
    def apply_dns_on_startup_async(status_callback=None):
        """
        Применяет DNS настройки при запуске приложения (отложенно)
        
        Args:
            status_callback: функция для обновления статуса
            
        Returns:
            bool: True если задача запланирована
        """
        try:
            # Проверяем флаг отключения
            if DNSStartupManager.DISABLE_ON_STARTUP:
                log("⚠️ DNS при запуске отключен (DISABLE_ON_STARTUP=True)", "WARNING")
                if status_callback:
                    status_callback("DNS при запуске отключен")
                return False
            
            log("Планирование применения DNS при запуске", "INFO")
            
            # Отложенное применение через QTimer
            def delayed_apply():
                try:
                    from .dns_force import DNSForceManager
                    
                    manager = DNSForceManager()
                    
                    # Проверяем, включен ли принудительный DNS
                    if not manager.is_force_dns_enabled():
                        log("Принудительный DNS отключен в настройках", "INFO")
                        if status_callback:
                            status_callback("DNS отключен")
                        return
                    
                    if status_callback:
                        status_callback("⏳ Применение DNS...")
                    
                    # Применяем DNS
                    success, total = manager.force_dns_on_all_adapters(
                        include_disconnected=False,
                        enable_ipv6=True
                    )
                    
                    if success > 0:
                        msg = f"✅ DNS применен при запуске: {success}/{total}"
                        log(msg, "SUCCESS")
                        if status_callback:
                            status_callback(msg)
                    else:
                        msg = "⚠️ DNS не применен при запуске"
                        log(msg, "WARNING")
                        if status_callback:
                            status_callback(msg)
                            
                except Exception as e:
                    error_msg = f"Ошибка применения DNS при запуске: {e}"
                    log(error_msg, "ERROR")
                    if status_callback:
                        status_callback("❌ Ошибка DNS")
            
            # Запускаем через 3 секунды после старта приложения
            QTimer.singleShot(3000, delayed_apply)
            
            if status_callback:
                status_callback("DNS будет применен через 3 сек")
            
            return True
            
        except Exception as e:
            log(f"Ошибка планирования DNS при запуске: {e}", "ERROR")
            if status_callback:
                status_callback("❌ Ошибка планирования DNS")
            return False
    
    @staticmethod
    def apply_dns_on_startup_sync(status_callback=None):
        """
        Синхронное применение DNS при запуске (блокирующее)
        
        Args:
            status_callback: функция для обновления статуса
            
        Returns:
            bool: True если применено успешно
        """
        try:
            if DNSStartupManager.DISABLE_ON_STARTUP:
                log("DNS при запуске отключен", "WARNING")
                return False
            
            from .dns_force import DNSForceManager
            
            manager = DNSForceManager(status_callback=status_callback)
            
            if not manager.is_force_dns_enabled():
                log("Принудительный DNS отключен", "INFO")
                return False
            
            success, total = manager.force_dns_on_all_adapters(
                include_disconnected=False,
                enable_ipv6=True
            )
            
            return success > 0
            
        except Exception as e:
            log(f"Ошибка синхронного применения DNS: {e}", "ERROR")
            return False
    
    @staticmethod
    def disable_dns_on_startup():
        """Отключает применение DNS при запуске"""
        DNSStartupManager.DISABLE_ON_STARTUP = True
        log("DNS при запуске отключен программно", "INFO")
    
    @staticmethod
    def enable_dns_on_startup():
        """Включает применение DNS при запуске"""
        DNSStartupManager.DISABLE_ON_STARTUP = False
        log("DNS при запуске включен программно", "INFO")

# ══════════════════════════════════════════════════════════════════════
#  Утилиты
# ══════════════════════════════════════════════════════════════════════

def reset_crash_counter():
    """Сбрасывает счетчик крашей DNS (для аварийного отключения)"""
    try:
        import winreg
        path = r"Software\ZapretReg2"
        
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path, 0, 
                           winreg.KEY_SET_VALUE) as key:
            try:
                winreg.DeleteValue(key, "DNSCrashCount")
                log("Счетчик DNS крашей сброшен", "DEBUG")
            except:
                pass
    except Exception as e:
        log(f"Ошибка сброса счетчика крашей: {e}", "DEBUG")

def disable_dns_if_crashing():
    """
    Аварийное отключение DNS если обнаружены множественные краши
    
    Returns:
        bool: True если DNS был отключен из-за крашей
    """
    try:
        import winreg
        path = r"Software\ZapretReg2"
        
        # Читаем счетчик крашей
        crash_count = 0
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path) as key:
                crash_count, _ = winreg.QueryValueEx(key, "DNSCrashCount")
        except:
            pass
        
        # Если больше 3 крашей - отключаем DNS
        if crash_count > 3:
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, path) as key:
                winreg.SetValueEx(key, "ForceDNS", 0, winreg.REG_DWORD, 0)
                winreg.DeleteValue(key, "DNSCrashCount")
            
            log("⚠️ DNS автоматически отключен после множественных крашей", "WARNING")
            return True
        
        # Увеличиваем счетчик
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, path) as key:
            winreg.SetValueEx(key, "DNSCrashCount", 0, winreg.REG_DWORD, crash_count + 1)
        
        return False
        
    except Exception as e:
        log(f"Ошибка в disable_dns_if_crashing: {e}", "DEBUG")
        return False