# startup/ipc_manager.py

import socket
import threading
import time
from log.log import log

from PyQt6.QtCore import QObject, pyqtSignal

class IPCManager(QObject):
    """Менеджер межпроцессного взаимодействия для показа окна из трея"""
    
    # Сигнал для показа окна (будет вызван в главном потоке Qt)
    show_window_signal = pyqtSignal()
    
    def __init__(self, port=47289):
        super().__init__()
        self.port = port
        self.server_socket = None
        self.running = False
        self.window = None
        
    def start_server(self, window):
        """Запускает сервер для прослушивания команд от других экземпляров"""
        self.window = window
        self.running = True
        
        # Подключаем сигнал к методу показа окна
        self.show_window_signal.connect(self._handle_show_window)
        
        def server_thread():
            try:
                self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                self.server_socket.bind(('127.0.0.1', self.port))
                self.server_socket.listen(1)
                self.server_socket.settimeout(1.0)  # Таймаут для возможности остановки
                
                log(f"IPC сервер запущен на порту {self.port}", "INFO")
                
                while self.running:
                    try:
                        conn, addr = self.server_socket.accept()
                        data = conn.recv(1024).decode('utf-8')
                        
                        if data == "SHOW_WINDOW":
                            # Вызываем сигнал (он выполнится в главном потоке)
                            self.show_window_signal.emit()
                            
                        conn.close()
                    except socket.timeout:
                        continue
                    except Exception as e:
                        if self.running:
                            log(f"Ошибка IPC сервера: {e}", "ERROR")
                            
            except Exception as e:
                log(f"Не удалось запустить IPC сервер: {e}", "ERROR")
            finally:
                if self.server_socket:
                    self.server_socket.close()
        
        thread = threading.Thread(target=server_thread, daemon=True)
        thread.start()
    
    def _handle_show_window(self):
        """Обработчик сигнала показа окна (выполняется в главном потоке)"""
        if self.window:
            if hasattr(self.window, 'tray_manager'):
                self.window.tray_manager.show_window()
            else:
                self.window.showNormal()
                self.window.activateWindow()
                self.window.raise_()
            log("Окно показано по запросу от другого экземпляра", "INFO")
    
    def send_show_command(self):
        """Отправляет команду показать окно уже запущенному экземпляру"""
        try:
            client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client.settimeout(1.0)
            client.connect(('127.0.0.1', self.port))
            client.send(b"SHOW_WINDOW")
            client.close()
            return True
        except:
            return False
            
    def stop(self):
        """Останавливает IPC сервер"""
        self.running = False
        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass