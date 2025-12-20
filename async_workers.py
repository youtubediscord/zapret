"""
Асинхронные воркеры для всех блокирующих операций
"""
from PyQt6.QtCore import QThread, QObject, pyqtSignal, QThreadPool, QRunnable
import subprocess
from typing import Optional, Callable, List, Tuple
from log import log

class AsyncCommand(QRunnable):
    """Базовый класс для асинхронного выполнения команд"""
    def __init__(self, callback: Optional[Callable] = None):
        super().__init__()
        self.callback = callback
        self.setAutoDelete(True)
        
    def run(self):
        try:
            result = self.execute()
            if self.callback:
                self.callback(True, result)
        except Exception as e:
            log(f"Ошибка в AsyncCommand: {e}", "❌ ERROR")
            if self.callback:
                self.callback(False, str(e))
    
    def execute(self):
        """Переопределить в наследниках"""
        raise NotImplementedError

class DNSSetWorker(QObject):
    """Воркер для установки DNS в отдельном потоке"""
    finished = pyqtSignal(bool, str)  # success, message
    progress = pyqtSignal(str)
    adapter_done = pyqtSignal(str, bool)  # adapter_name, success
    
    def __init__(self, adapter_name: str, primary_dns: str, 
                 secondary_dns: Optional[str] = None, ip_version: str = 'ipv4'):
        super().__init__()
        self.adapter_name = adapter_name
        self.primary_dns = primary_dns
        self.secondary_dns = secondary_dns
        self.ip_version = ip_version
        
    def run(self):
        """Выполняет установку DNS асинхронно"""
        try:
            self.progress.emit(f"Настройка {self.ip_version} DNS для {self.adapter_name}...")
            
            interface_type = 'ipv4' if self.ip_version == 'ipv4' else 'ipv6'
            
            # Установка первичного DNS
            cmd = f'netsh interface {interface_type} set dnsservers "{self.adapter_name}" static {self.primary_dns} primary'
            
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, 
                                  encoding='cp866', errors='replace', timeout=5)  # Уменьшили timeout
            
            if result.returncode != 0:
                self.adapter_done.emit(self.adapter_name, False)
                self.finished.emit(False, f"Ошибка установки DNS для {self.adapter_name}")
                return
            
            # Установка вторичного DNS если есть
            if self.secondary_dns:
                cmd2 = f'netsh interface {interface_type} add dnsservers "{self.adapter_name}" {self.secondary_dns} index=2'
                subprocess.run(cmd2, shell=True, capture_output=True, text=True, 
                             encoding='cp866', errors='replace', timeout=5)
            
            self.adapter_done.emit(self.adapter_name, True)
            self.finished.emit(True, f"DNS установлен для {self.adapter_name}")
            
        except subprocess.TimeoutExpired:
            self.adapter_done.emit(self.adapter_name, False)
            self.finished.emit(False, f"Таймаут при установке DNS для {self.adapter_name}")
        except Exception as e:
            self.adapter_done.emit(self.adapter_name, False)
            self.finished.emit(False, str(e))

class DNSBatchWorker(QObject):
    """Воркер для пакетной установки DNS на несколько адаптеров"""
    finished = pyqtSignal(int, int)  # success_count, total_count
    progress = pyqtSignal(str)
    
    def __init__(self, dns_manager, adapters: List[str]):
        super().__init__()
        self.dns_manager = dns_manager
        self.adapters = adapters
        self.thread_pool = QThreadPool()
        self.thread_pool.setMaxThreadCount(3)  # Параллельно до 3 адаптеров
        
    def run(self):
        """Запускает установку DNS параллельно"""
        from functools import partial
        
        success_count = 0
        total = len(self.adapters)
        completed = 0
        
        def on_adapter_done(success, adapter_name):
            nonlocal success_count, completed
            completed += 1
            if success:
                success_count += 1
            
            self.progress.emit(f"Обработано {completed}/{total} адаптеров")
            
            if completed >= total:
                self.finished.emit(success_count, total)
        
        # Запускаем задачи параллельно
        for adapter in self.adapters:
            task = AsyncDNSTask(
                adapter, 
                self.dns_manager.DNS_PRIMARY,
                self.dns_manager.DNS_SECONDARY,
                callback=partial(on_adapter_done, adapter_name=adapter)
            )
            self.thread_pool.start(task)

class AsyncDNSTask(QRunnable):
    """Задача для установки DNS на один адаптер"""
    def __init__(self, adapter_name: str, primary: str, secondary: str, callback: Callable):
        super().__init__()
        self.adapter = adapter_name
        self.primary = primary
        self.secondary = secondary
        self.callback = callback
        
    def run(self):
        try:
            # IPv4
            cmd = f'netsh interface ipv4 set dnsservers "{self.adapter}" static {self.primary} primary'
            result = subprocess.run(cmd, shell=True, capture_output=True, 
                                  text=True, encoding='cp866', errors='replace', timeout=3)
            
            if result.returncode == 0 and self.secondary:
                cmd2 = f'netsh interface ipv4 add dnsservers "{self.adapter}" {self.secondary} index=2'
                subprocess.run(cmd2, shell=True, capture_output=True, 
                             text=True, encoding='cp866', errors='replace', timeout=3)
            
            self.callback(result.returncode == 0)
            
        except Exception as e:
            log(f"Ошибка DNS для {self.adapter}: {e}", "❌ ERROR")
            self.callback(False)

class HostsFileWorker(QObject):
    """Воркер для асинхронной работы с hosts файлом"""
    finished = pyqtSignal(bool, str)  # success, message
    progress = pyqtSignal(str)
    
    def __init__(self, operation: str, hosts_manager, domains: Optional[List[str]] = None):
        super().__init__()
        self.operation = operation  # 'add', 'remove', 'select'
        self.hosts_manager = hosts_manager
        self.domains = domains
        
    def run(self):
        """Выполняет операцию с hosts файлом"""
        try:
            self.progress.emit(f"Обработка hosts файла ({self.operation})...")
            
            if self.operation == 'add':
                success = self.hosts_manager.add_proxy_domains()
                msg = "Домены добавлены в hosts" if success else "Ошибка добавления"
                
            elif self.operation == 'remove':
                success = self.hosts_manager.remove_proxy_domains()
                msg = "Домены удалены из hosts" if success else "Ошибка удаления"
                
            elif self.operation == 'select' and self.domains:
                success = self.hosts_manager.apply_selected_domains(self.domains)
                msg = f"Применено {len(self.domains)} доменов" if success else "Ошибка применения"
                
            else:
                success = False
                msg = f"Неизвестная операция: {self.operation}"
            
            self.finished.emit(success, msg)
            
        except Exception as e:
            self.finished.emit(False, str(e))