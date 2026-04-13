import glob
import ntpath
import os
import threading
import time

import psutil

from utils.subproc import run_hidden  # Импортируем нашу обертку для subprocess


def _path_basename(path):
    """Возвращает имя файла и для Windows-, и для POSIX-пути."""
    return ntpath.basename(str(path or ""))

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
        self.discord_process_names = {"discord.exe", "update.exe"}
        self.restart_thread = None
    
    def set_status(self, text):
        """Отображает статусное сообщение."""
        if self.status_callback:
            self.status_callback(text)
        else:
            print(text)
    
    def _safe_process_exe(self, proc):
        """Возвращает путь к exe процесса, если его удалось получить."""
        try:
            info = getattr(proc, "info", {}) or {}
            exe_path = info.get("exe")
            if exe_path:
                return str(exe_path)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            return None

        try:
            exe_path = proc.exe()
            if exe_path:
                return str(exe_path)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess, OSError):
            return None

        return None

    def _safe_process_cmdline(self, proc):
        """Возвращает командную строку процесса как список строк."""
        try:
            info = getattr(proc, "info", {}) or {}
            cmdline = info.get("cmdline")
            if cmdline is not None:
                return [str(part) for part in cmdline]
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            return []

        try:
            return [str(part) for part in proc.cmdline()]
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess, OSError):
            return []

    def _resolve_discord_path_from_update_exe(self, update_exe_path):
        """
        Для Squirrel-установок Discord восстанавливает путь к Discord.exe
        через соседние app-* каталоги рядом с Update.exe.
        """
        if not update_exe_path:
            return None

        install_root = os.path.dirname(update_exe_path)
        candidates = glob.glob(os.path.join(install_root, "app-*", "Discord.exe"))
        if candidates:
            candidates.sort(reverse=True)
            return candidates[0]
        return None

    def _is_discord_process(self, proc):
        """Определяет, относится ли процесс к Discord."""
        try:
            info = getattr(proc, "info", {}) or {}
            process_name = _path_basename(info.get("name")).lower()
            if process_name in self.discord_process_names:
                return True

            exe_path = self._safe_process_exe(proc)
            exe_name = _path_basename(exe_path).lower() if exe_path else ""
            if exe_name in self.discord_process_names:
                return True

            for part in self._safe_process_cmdline(proc):
                if _path_basename(part).lower() == "discord.exe":
                    return True
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess, OSError):
            return False

        return False

    def _iter_discord_processes(self):
        """Итерирует только по тем процессам, которые действительно похожи на Discord."""
        for proc in psutil.process_iter(["pid", "name", "exe", "cmdline"]):
            try:
                if self._is_discord_process(proc):
                    yield proc
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess, OSError):
                pass

    def get_running_discord_path(self):
        """
        Возвращает реальный путь к запущенному Discord, если процесс уже жив.
        Это основной источник истины для перезапуска.
        """
        update_exe_candidates = []

        for proc in self._iter_discord_processes():
            exe_path = self._safe_process_exe(proc)
            if not exe_path:
                continue

            exe_name = _path_basename(exe_path).lower()
            if exe_name == "discord.exe" and os.path.exists(exe_path):
                return exe_path
            if exe_name == "update.exe":
                update_exe_candidates.append(exe_path)

        for update_exe_path in update_exe_candidates:
            discord_exe_path = self._resolve_discord_path_from_update_exe(update_exe_path)
            if discord_exe_path and os.path.exists(discord_exe_path):
                return discord_exe_path

        return None

    def find_discord_path(self):
        """
        Находит путь к исполняемому файлу Discord.
        
        Returns:
            str: Путь к Discord.exe или None, если не найден
        """
        running_path = self.get_running_discord_path()
        if running_path:
            return running_path

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
        return any(True for _ in self._iter_discord_processes())
    
    def _restart_discord_thread(self):
        from log.log import log

        """Фоновый поток для перезапуска Discord"""
        try:
            discord_path = self.find_discord_path()
            discord_processes = list(self._iter_discord_processes())
            was_running = bool(discord_processes)
            
            if was_running:
                self.set_status("Discord запущен. Перезапускаем...")
                
                # Закрываем все процессы Discord
                for proc in discord_processes:
                    try:
                        proc.terminate()
                    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                        pass
                
                # Даем время на закрытие
                time.sleep(1)
                
                # Убеждаемся, что Discord точно закрыт
                for proc in self._iter_discord_processes():
                    try:
                        proc.kill()
                    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                        pass
                
                # Небольшая пауза перед запуском
                time.sleep(0.5)
                
                # Запускаем Discord снова
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
