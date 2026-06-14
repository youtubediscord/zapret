import glob
import ntpath
import os
import re
import threading
import time
from dataclasses import dataclass, field

import psutil

from utils.subproc import run_hidden  # Импортируем нашу обертку для subprocess


def _path_basename(path):
    """Возвращает имя файла и для Windows-, и для POSIX-пути."""
    return ntpath.basename(str(path or ""))


def _path_dirname(path):
    """Возвращает родительскую папку и для Windows-, и для POSIX-пути."""
    text = str(path or "")
    return ntpath.dirname(text) if "\\" in text else os.path.dirname(text)


def _app_version_key(path):
    """Ключ сортировки для папок Discord app-1.2.3."""
    parent_name = _path_basename(_path_dirname(path)).lower()
    match = re.search(r"app-(\d+(?:\.\d+)*)", parent_name)
    if not match:
        return (-1,), str(path or "").lower()
    return tuple(int(part) for part in match.group(1).split(".")), str(path or "").lower()


@dataclass(frozen=True)
class DiscordProcessSnapshot:
    """Снимок процессов Discord, собранный одним обходом списка процессов."""

    processes: list = field(default_factory=list)
    running_discord_path: str | None = None
    update_exe_paths: list[str] = field(default_factory=list)


class DiscordProcessScanner:
    """Ищет живые процессы Discord и возвращает один снимок состояния."""

    def __init__(self, *, process_iter=None, process_names=None):
        self._process_iter = process_iter or psutil.process_iter
        self.process_names = set(process_names or {"discord.exe", "update.exe"})

    def _safe_process_exe(self, proc):
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

    def _is_discord_process(self, proc):
        try:
            info = getattr(proc, "info", {}) or {}
            process_name = _path_basename(info.get("name")).lower()
            if process_name in self.process_names:
                return True

            exe_path = self._safe_process_exe(proc)
            exe_name = _path_basename(exe_path).lower() if exe_path else ""
            if exe_name in self.process_names:
                return True

            for part in self._safe_process_cmdline(proc):
                if _path_basename(part).lower() == "discord.exe":
                    return True
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess, OSError):
            return False

        return False

    def scan(self):
        processes = []
        running_discord_path = None
        update_exe_paths = []

        for proc in self._process_iter(["pid", "name", "exe", "cmdline"]):
            try:
                if not self._is_discord_process(proc):
                    continue

                processes.append(proc)
                exe_path = self._safe_process_exe(proc)
                exe_name = _path_basename(exe_path).lower() if exe_path else ""
                if exe_name == "discord.exe" and not running_discord_path:
                    running_discord_path = exe_path
                elif exe_name == "update.exe" and exe_path:
                    update_exe_paths.append(exe_path)
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess, OSError):
                pass

        return DiscordProcessSnapshot(
            processes=processes,
            running_discord_path=running_discord_path,
            update_exe_paths=update_exe_paths,
        )


class DiscordInstallLocator:
    """Находит Discord.exe на диске и выбирает новую app-* версию по номеру."""

    def __init__(self, *, path_patterns=None, glob_func=None, exists_func=None):
        self.path_patterns = list(path_patterns) if path_patterns is not None else [
            os.path.expandvars(r"%LOCALAPPDATA%\Discord\app-*\Discord.exe"),
            os.path.expandvars(r"%LOCALAPPDATA%\Discord\Update.exe"),
            os.path.expandvars(r"C:\Program Files\Discord\Discord.exe"),
            os.path.expandvars(r"C:\Program Files (x86)\Discord\Discord.exe"),
        ]
        self._glob = glob_func or glob.glob
        self._exists = exists_func or os.path.exists

    def find_latest_app_exe(self, install_root):
        if not install_root:
            return None

        candidates = self._glob(os.path.join(str(install_root), "app-*", "Discord.exe"))
        if not candidates:
            return None
        return max(candidates, key=_app_version_key)

    def find_from_update_exe(self, update_exe_path):
        if not update_exe_path:
            return None

        candidate = self.find_latest_app_exe(_path_dirname(update_exe_path))
        if candidate and self._exists(candidate):
            return candidate
        return None

    def find_from_snapshot(self, snapshot):
        if snapshot and snapshot.running_discord_path:
            return snapshot.running_discord_path

        for update_exe_path in list(getattr(snapshot, "update_exe_paths", []) or []):
            discord_exe_path = self.find_from_update_exe(update_exe_path)
            if discord_exe_path:
                return discord_exe_path
        return None

    def find_installed(self):
        for path_pattern in self.path_patterns:
            if "*" in path_pattern:
                paths = self._glob(path_pattern)
                if paths:
                    return max(paths, key=_app_version_key)
            elif self._exists(path_pattern):
                return path_pattern

        return None

    def find_discord_path(self, snapshot=None):
        return self.find_from_snapshot(snapshot) or self.find_installed()


class DiscordRestartService:
    """Выполняет один перезапуск Discord без управления потоками."""

    def __init__(
        self,
        *,
        scanner=None,
        locator=None,
        runner=None,
        sleep=None,
        status_callback=None,
        log_func=None,
    ):
        self.scanner = scanner or DiscordProcessScanner()
        self.locator = locator or DiscordInstallLocator()
        self.runner = runner or run_hidden
        self.sleep = sleep or time.sleep
        self.status_callback = status_callback
        self._log_func = log_func

    def set_status(self, text):
        if self.status_callback:
            self.status_callback(text)
        else:
            print(text)

    def _log(self, message, level="INFO"):
        if self._log_func:
            self._log_func(message, level=level)
            return

        try:
            from log.log import log

            log(message, level=level)
        except Exception:
            pass

    def find_discord_path(self, snapshot=None):
        return self.locator.find_discord_path(snapshot)

    def is_discord_running(self):
        return bool(self.scanner.scan().processes)

    def restart_once(self):
        snapshot = self.scanner.scan()
        discord_processes = list(snapshot.processes)

        if not discord_processes:
            self._log("Discord не запущен, перезапуск не требуется", level="INFO")
            return False

        discord_path = self.find_discord_path(snapshot)
        self.set_status("Discord запущен. Перезапускаем...")

        for proc in discord_processes:
            try:
                proc.terminate()
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass

        self.sleep(1)

        for proc in self.scanner.scan().processes:
            try:
                proc.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass

        self.sleep(0.5)

        if discord_path:
            self.runner(discord_path)
            self._log(f"Discord перезапущен: {discord_path}", level="INFO")
            return True

        self.set_status("Не удалось найти путь к Discord для перезапуска")
        return False


class DiscordManager:
    """Класс для управления процессом Discord"""

    def __init__(
        self,
        status_callback=None,
        *,
        scanner=None,
        locator=None,
        restart_service=None,
        thread_factory=None,
    ):
        """
        Инициализирует DiscordManager.

        Args:
            status_callback (callable): Функция обратного вызова для отображения статуса
        """
        self.status_callback = status_callback
        self._restart_lock = threading.Lock()
        self._thread_factory = thread_factory or threading.Thread
        self._restart_service = restart_service or DiscordRestartService(
            scanner=scanner,
            locator=locator,
            status_callback=status_callback,
        )
        self.discord_exes = self._restart_service.locator.path_patterns
        self.discord_process_names = self._restart_service.scanner.process_names
        self.restart_thread = None

    def set_status(self, text):
        """Отображает статусное сообщение."""
        self._restart_service.set_status(text)

    def _safe_process_exe(self, proc):
        """Возвращает путь к exe процесса, если его удалось получить."""
        return self._restart_service.scanner._safe_process_exe(proc)

    def _safe_process_cmdline(self, proc):
        """Возвращает командную строку процесса как список строк."""
        return self._restart_service.scanner._safe_process_cmdline(proc)

    def _resolve_discord_path_from_update_exe(self, update_exe_path):
        """
        Для Squirrel-установок Discord восстанавливает путь к Discord.exe
        через соседние app-* каталоги рядом с Update.exe.
        """
        return self._restart_service.locator.find_from_update_exe(update_exe_path)

    def _is_discord_process(self, proc):
        """Определяет, относится ли процесс к Discord."""
        return self._restart_service.scanner._is_discord_process(proc)

    def _iter_discord_processes(self):
        """Итерирует только по тем процессам, которые действительно похожи на Discord."""
        yield from self._restart_service.scanner.scan().processes

    def get_running_discord_path(self):
        """
        Возвращает реальный путь к запущенному Discord, если процесс уже жив.
        Это основной источник истины для перезапуска.
        """
        snapshot = self._restart_service.scanner.scan()
        return self._restart_service.locator.find_from_snapshot(snapshot)

    def find_discord_path(self):
        """
        Находит путь к исполняемому файлу Discord.
        
        Returns:
            str: Путь к Discord.exe или None, если не найден
        """
        return self._restart_service.find_discord_path(self._restart_service.scanner.scan())
    
    def is_discord_running(self):
        """
        Проверяет, запущен ли Discord.
        
        Returns:
            bool: True если Discord запущен, False если не запущен
        """
        return self._restart_service.is_discord_running()
    
    def _restart_discord_thread(self):
        """Фоновый поток для перезапуска Discord"""
        try:
            self._restart_service.restart_once()
        except Exception as e:
            self._restart_service._log(f"Ошибка при перезапуске Discord: {str(e)}", level="ERROR")
            self.set_status(f"Ошибка при перезапуске Discord: {str(e)}")
    
    def restart_discord_if_running(self):
        """
        Перезапускает Discord если он запущен.
        Выполняется в отдельном потоке, чтобы не блокировать интерфейс.
        """
        with self._restart_lock:
            if self.restart_thread is not None and self.restart_thread.is_alive():
                return False

            try:
                self.restart_thread = self._thread_factory(
                    target=self._restart_discord_thread,
                    daemon=True,
                )
            except TypeError:
                self.restart_thread = self._thread_factory(target=self._restart_discord_thread)
                self.restart_thread.daemon = True

            self.restart_thread.start()
            return True
