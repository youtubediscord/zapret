# startup/ipc_manager.py

import socket
import threading
import time
from log.log import log

from PyQt6.QtCore import QObject, pyqtSignal


IPC_COMMAND_SHOW_WINDOW = "SHOW_WINDOW"
IPC_COMMAND_EXIT_KEEP_DPI = "EXIT_KEEP_DPI"
IPC_COMMAND_EXIT_STOP_DPI = "EXIT_STOP_DPI"


class IPCManager(QObject):
    """Менеджер межпроцессного взаимодействия для показа окна из трея"""
    
    # Сигнал для показа окна (будет вызван в главном потоке Qt)
    show_window_signal = pyqtSignal()
    exit_keep_dpi_signal = pyqtSignal()
    exit_stop_dpi_signal = pyqtSignal()
    
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
        self.exit_keep_dpi_signal.connect(lambda: self._handle_exit_request(stop_dpi=False))
        self.exit_stop_dpi_signal.connect(lambda: self._handle_exit_request(stop_dpi=True))
        
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
                        
                        self._dispatch_command(data)
                            
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
            tray_manager = getattr(getattr(self.window, "visual_state", None), "tray_manager", None)
            if tray_manager is not None:
                tray_manager.show_window()
            else:
                from ui.window_adapter import show_window

                show_window(self.window)
            log("Окно показано по запросу от другого экземпляра", "INFO")

    def _handle_exit_request(self, *, stop_dpi: bool):
        """Обработчик запроса закрыть GUI (выполняется в главном потоке)."""
        if not self.window:
            return
        request_exit = getattr(self.window, "request_exit", None)
        if callable(request_exit):
            request_exit(stop_dpi=bool(stop_dpi))
            log(
                "Закрытие GUI запрошено через IPC"
                + (" с остановкой DPI" if stop_dpi else " без остановки DPI"),
                "INFO",
            )

    def _dispatch_command(self, data: str) -> bool:
        command = str(data or "").strip()
        if command == IPC_COMMAND_SHOW_WINDOW:
            # Вызываем сигнал (он выполнится в главном потоке)
            self.show_window_signal.emit()
            return True
        if command == IPC_COMMAND_EXIT_KEEP_DPI:
            self.exit_keep_dpi_signal.emit()
            return True
        if command == IPC_COMMAND_EXIT_STOP_DPI:
            self.exit_stop_dpi_signal.emit()
            return True
        return False

    def send_command(self, command: str) -> bool:
        """Отправляет команду уже запущенному экземпляру."""
        try:
            client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client.settimeout(1.0)
            client.connect(('127.0.0.1', self.port))
            client.send(str(command or "").encode("utf-8"))
            client.close()
            return True
        except:
            return False
    
    def send_show_command(self):
        """Отправляет команду показать окно уже запущенному экземпляру"""
        return self.send_command(IPC_COMMAND_SHOW_WINDOW)

    def send_exit_command(self, *, stop_dpi: bool = False):
        """Отправляет команду закрыть уже запущенный GUI."""
        return self.send_command(
            IPC_COMMAND_EXIT_STOP_DPI if stop_dpi else IPC_COMMAND_EXIT_KEEP_DPI
        )
            
    def stop(self):
        """Останавливает IPC сервер"""
        self.running = False
        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass
