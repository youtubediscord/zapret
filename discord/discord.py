import os
import subprocess
import time
import threading
import glob
import psutil
from utils import run_hidden # Импортируем нашу обертку для subprocess

class DiscordManager:
    """Класс для управления процессом Discord"""
    
    def __init__(self, status_callback=None):
        """
        Инициализирует DiscordManager.
        
        Args:
            status_callback (callable): Функция обратного вызова для отображения статуса
        """
        self.status_callback = status_callback
        
        # Возможные пути к Discord
        self.discord_exes = [
            os.path.expandvars(r"%LOCALAPPDATA%\Discord\app-*\Discord.exe"),
            os.path.expandvars(r"%LOCALAPPDATA%\Discord\Update.exe"),
            os.path.expandvars(r"C:\Program Files\Discord\Discord.exe"),
            os.path.expandvars(r"C:\Program Files (x86)\Discord\Discord.exe"),
        ]
        self.discord_process_names = ["Discord.exe", "Update.exe"]
        self.restart_thread = None
    
    def set_status(self, text):
        """Отображает статусное сообщение."""
        if self.status_callback:
            self.status_callback(text)
        else:
            print(text)
    
    def find_discord_path(self):
        """
        Находит путь к исполняемому файлу Discord.
        
        Returns:
            str: Путь к Discord.exe или None, если не найден
        """
        # Проверяем все возможные пути
        for path_pattern in self.discord_exes:
            if "*" in path_pattern:
                paths = glob.glob(path_pattern)
                if paths:
                    # Сортируем, чтобы получить новейшую версию
                    paths.sort(reverse=True)
                    return paths[0]
            elif os.path.exists(path_pattern):
                return path_pattern
        
        return None
    
    def is_discord_running(self):
        """
        Проверяет, запущен ли Discord.
        
        Returns:
            bool: True если Discord запущен, False если не запущен
        """
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                if proc.info['name'] in self.discord_process_names:
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
        return False
    
    def _restart_discord_thread(self):
        from log import log
        """Фоновый поток для перезапуска Discord"""
        try:
            # Проверяем, запущен ли Discord
            was_running = self.is_discord_running()
            
            if was_running:
                self.set_status("Discord запущен. Перезапускаем...")
                
                # Закрываем все процессы Discord
                for proc in psutil.process_iter(['pid', 'name']):
                    try:
                        if proc.info['name'] in self.discord_process_names:
                            proc.terminate()
                    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                        pass
                
                # Даем время на закрытие
                time.sleep(1)
                
                # Убеждаемся, что Discord точно закрыт
                for proc in psutil.process_iter(['pid', 'name']):
                    try:
                        if proc.info['name'] in self.discord_process_names:
                            proc.kill()
                    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                        pass
                
                # Небольшая пауза перед запуском
                time.sleep(0.5)
                
                # Запускаем Discord снова
                discord_path = self.find_discord_path()
                if discord_path:
                    run_hidden(discord_path)
                    log(f"Discord перезапущен: {discord_path}", level="INFO")
                else:
                    self.set_status("Не удалось найти путь к Discord для перезапуска")
            else:
                log("Discord не запущен, перезапуск не требуется", level="INFO")
        
        except Exception as e:
            log(f"Ошибка при перезапуске Discord: {str(e)}", level="ERROR")
            self.set_status(f"Ошибка при перезапуске Discord: {str(e)}")
    
    def restart_discord_if_running(self):
        """
        Перезапускает Discord если он запущен.
        Выполняется в отдельном потоке, чтобы не блокировать интерфейс.
        """
        # Запускаем в отдельном потоке, чтобы не блокировать основной поток
        if self.restart_thread is None or not self.restart_thread.is_alive():
            self.restart_thread = threading.Thread(target=self._restart_discord_thread)
            self.restart_thread.daemon = True
            self.restart_thread.start()
            return True
        return False