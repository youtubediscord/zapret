# strategy_menu/strategy_runner.py

import os
import subprocess
from datetime import datetime
from typing import Optional, List

import psutil

from log import log
from .constants import SW_HIDE, CREATE_NO_WINDOW, STARTF_USESHOWWINDOW


def log_full_command(cmd_list: List[str], strategy_name: str):
    """
    Записывает полную командную строку в отдельный файл для дебага
    
    Args:
        cmd_list: Список аргументов команды
        strategy_name: Название стратегии
    """
    try:
        from config import LOGS_FOLDER
        
        # Создаем папку logs если её нет
        os.makedirs(LOGS_FOLDER, exist_ok=True)
        
        # Путь к файлу командных строк
        cmd_log_file = os.path.join(LOGS_FOLDER, "commands_full.log")
        
        # Формируем полную командную строку правильно
        full_cmd_parts = []
        for i, arg in enumerate(cmd_list):
            if i == 0:  # Это путь к exe
                full_cmd_parts.append(arg)
            else:
                # Проверяем, нужны ли кавычки
                # Не добавляем кавычки если они уже есть или если это простой аргумент без пробелов
                if arg.startswith('"') and arg.endswith('"'):
                    full_cmd_parts.append(arg)
                elif ' ' in arg or '\t' in arg:
                    # Если есть пробелы, добавляем кавычки
                    full_cmd_parts.append(f'"{arg}"')
                else:
                    full_cmd_parts.append(arg)
        
        full_cmd = ' '.join(full_cmd_parts)
        
        # Подготавливаем запись
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        separator = "=" * 80
        
        # Записываем в файл (режим 'a' для добавления, не перезаписи)
        with open(cmd_log_file, 'a', encoding='utf-8') as f:
            f.write(f"\n{separator}\n")
            f.write(f"Timestamp: {timestamp}\n")
            f.write(f"Strategy: {strategy_name}\n")
            f.write(f"Command length: {len(full_cmd)} characters\n")
            f.write(f"Arguments count: {len(cmd_list) - 1}\n")  # -1 для исключения exe
            f.write(f"{separator}\n")
            f.write(f"FULL COMMAND:\n")
            f.write(f"{full_cmd}\n")
            f.write(f"{separator}\n")
            
            # Также записываем команду в формате списка для удобства анализа
            f.write(f"ARGUMENTS LIST:\n")
            for i, arg in enumerate(cmd_list):
                f.write(f"[{i:3}]: {arg}\n")
            f.write(f"{separator}\n\n")
        
        # Также создаем файл с последней командой для быстрого доступа
        last_cmd_file = os.path.join(LOGS_FOLDER, "last_command.txt")
        with open(last_cmd_file, 'w', encoding='utf-8') as f:
            f.write(f"# Last command executed at {timestamp}\n")
            f.write(f"# Strategy: {strategy_name}\n\n")
            f.write(full_cmd)
        
        # Создаем файл с историей последних 10 команд
        history_file = os.path.join(LOGS_FOLDER, "commands_history.txt")
        
        # Читаем существующую историю
        history_lines = []
        if os.path.exists(history_file):
            with open(history_file, 'r', encoding='utf-8') as f:
                content = f.read()
                # Разбиваем по разделителям
                entries = content.split('\n' + '=' * 60 + '\n')
                # Берем последние 9 записей
                if len(entries) > 9:
                    entries = entries[-9:]
                history_lines = ('\n' + '=' * 60 + '\n').join(entries)
        
        # Добавляем новую запись
        with open(history_file, 'w', encoding='utf-8') as f:
            if history_lines:
                f.write(history_lines)
                f.write('\n' + '=' * 60 + '\n')
            f.write(f"[{timestamp}] {strategy_name}\n")
            f.write(full_cmd)
        
        log(f"Команда сохранена в logs/commands_full.log", "DEBUG")
        
    except Exception as e:
        log(f"Ошибка записи команды в лог: {e}", "DEBUG")

def apply_wssize_parameter(args: list) -> list:
    """
    Применяет параметр --wssize=1:6 к аргументам стратегии если включено в настройках
    """
    from config import get_wssize_enabled
    
    if not get_wssize_enabled():
        return args
    
    new_args = []
    wssize_added = False
    
    i = 0
    while i < len(args):
        arg = args[i]
        new_args.append(arg)
        
        if arg.startswith("--filter-tcp="):
            ports_part = arg.split("=", 1)[1]
            ports = []
            
            for port_spec in ports_part.split(","):
                if "-" in port_spec:
                    start, end = port_spec.split("-")
                    if int(start) <= 443 <= int(end):
                        ports.append("443")
                else:
                    if port_spec.strip() == "443":
                        ports.append("443")
            
            if "443" in ports:
                next_arg = args[i + 1] if i + 1 < len(args) else None
                if next_arg != "--wssize=1:6":
                    new_args.append("--wssize=1:6")
                    wssize_added = True
                    log(f"Добавлен параметр --wssize=1:6 после {arg}", "DEBUG")
        
        i += 1
    
    if not wssize_added:
        insert_index = _find_wssize_insert_position(new_args)
        
        new_args.insert(insert_index, "--filter-tcp=443")
        new_args.insert(insert_index + 1, "--wssize=1:6")
        
        if insert_index + 2 >= len(new_args) or new_args[insert_index + 2] != "--new":
            new_args.insert(insert_index + 2, "--new")
        
        log("Добавлено глобальное правило --filter-tcp=443 --wssize=1:6 --new", "DEBUG")
    
    return new_args


def _find_wssize_insert_position(args: list) -> int:
    """Находит оптимальную позицию для вставки глобального правила wssize"""
    last_wf_index = -1
    first_filter_index = -1
    first_new_index = -1
    
    for i, arg in enumerate(args):
        if arg.startswith("--wf-tcp=") or arg.startswith("--wf-udp="):
            last_wf_index = i
        elif arg.startswith("--filter-tcp=") and first_filter_index == -1:
            first_filter_index = i
        elif arg == "--new" and first_new_index == -1:
            first_new_index = i
    
    if last_wf_index != -1:
        return last_wf_index + 1
    elif first_filter_index != -1:
        return first_filter_index
    elif first_new_index != -1:
        return first_new_index
    else:
        return len(args)

class StrategyRunner:
    """Класс для запуска стратегий напрямую через subprocess. Отвечает только за Direct режим"""
    
    def __init__(self, winws_exe_path: str):
        """
        Args:
            winws_exe_path: Путь к winws.exe
        """
        self.winws_exe = os.path.abspath(winws_exe_path)
        self.running_process: Optional[subprocess.Popen] = None
        self.current_strategy_name: Optional[str] = None
        self.current_strategy_args: Optional[List[str]] = None
        
        # Проверяем существование exe
        if not os.path.exists(self.winws_exe):
            raise FileNotFoundError(f"winws.exe не найден: {self.winws_exe}")
        
        # Определяем рабочую директорию
        exe_dir = os.path.dirname(self.winws_exe)
        self.work_dir = os.path.dirname(exe_dir)
        
        self.bin_dir = os.path.join(self.work_dir, "bin")
        self.lists_dir = os.path.join(self.work_dir, "lists")
        
        log(f"StrategyRunner инициализирован. winws.exe: {self.winws_exe}", "INFO")
        log(f"Рабочая директория: {self.work_dir}", "DEBUG")
        log(f"Папка lists: {self.lists_dir}", "DEBUG")
        log(f"Папка bin: {self.bin_dir}", "DEBUG")
    
    def _create_startup_info(self):
        """Создает STARTUPINFO для скрытого запуска процесса"""
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags = STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = SW_HIDE
        return startupinfo

    def _resolve_file_paths(self, args: List[str]) -> List[str]:
        """Разрешает относительные пути к файлам"""
        from config import WINDIVERT_FILTER
        
        resolved_args = []
        
        for arg in args:
            # Обработка --wf-raw
            if arg.startswith("--wf-raw="):
                value = arg.split("=", 1)[1]
                
                # Если значение начинается с @, это означает файл
                if value.startswith("@"):
                    filename = value[1:]  # Убираем @ в начале
                    filename = filename.strip('"')
                    
                    if not os.path.isabs(filename):
                        # Используем папку WINDIVERT_FILTER для фильтров
                        windivert_dir = os.path.dirname(WINDIVERT_FILTER) if os.path.isfile(WINDIVERT_FILTER) else WINDIVERT_FILTER
                        full_path = os.path.join(windivert_dir, filename)
                        # Кавычки добавляем только вокруг пути, не всего аргумента
                        resolved_args.append(f'--wf-raw=@{full_path}')
                    else:
                        resolved_args.append(f'--wf-raw=@{filename}')
                else:
                    # Если не файл, оставляем как есть
                    resolved_args.append(arg)
                    
            elif any(arg.startswith(prefix) for prefix in [
                "--hostlist=", "--ipset=", "--hostlist-exclude=", "--ipset-exclude="
            ]):
                prefix, filename = arg.split("=", 1)
                filename = filename.strip('"')
                
                if not os.path.isabs(filename):
                    full_path = os.path.join(self.lists_dir, filename)
                    resolved_args.append(f'{prefix}={full_path}')
                else:
                    resolved_args.append(f'{prefix}={filename}')
                    
            elif any(arg.startswith(prefix) for prefix in [
                "--dpi-desync-fake-tls=", "--dpi-desync-fake-syndata=", 
                "--dpi-desync-fake-quic=", "--dpi-desync-fake-unknown-udp=",
                "--dpi-desync-split-seqovl-pattern="
            ]):
                prefix, filename = arg.split("=", 1)
                
                if filename.startswith("0x"):
                    resolved_args.append(arg)
                else:
                    filename = filename.strip('"')
                    
                    if not os.path.isabs(filename):
                        full_path = os.path.join(self.bin_dir, filename)
                        resolved_args.append(f'{prefix}={full_path}')
                    else:
                        resolved_args.append(f'{prefix}={filename}')
            else:
                resolved_args.append(arg)
        
        return resolved_args

    def _kill_process_by_name(name: str):
        killed = []
        for proc in psutil.process_iter(['pid', 'name']):
            if proc.info['name'].lower() == name.lower():
                try:
                    proc.terminate()  # soft kill
                    proc.wait(timeout=3)
                    killed.append(proc.info['pid'])
                except psutil.NoSuchProcess:
                    pass
                except psutil.TimeoutExpired:
                    proc.kill()  # if not soft killed - kill it to death hehe
                    killed.append(proc.info['pid'])
        return killed

    def _force_cleanup_windivert(self):
        """Принудительная очистка службы и драйвера WinDivert"""
        try:
            import time
            
            log("Принудительная очистка WinDivert...", "DEBUG")
            
            subprocess.run(
                ["sc", "stop", "windivert"],
                capture_output=True,
                creationflags=0x08000000,
                timeout=5
            )
            
            time.sleep(0.5)
            
            subprocess.run(
                ["sc", "delete", "windivert"],
                capture_output=True,
                creationflags=0x08000000,
                timeout=5
            )
            
            time.sleep(0.5)

            self._kill_process_by_name("winws.exe")
            
            try:
                subprocess.run(
                    ["fltmc", "unload", "windivert"],
                    capture_output=True,
                    creationflags=0x08000000,
                    timeout=5
                )
            except:
                pass
            
            log("Очистка WinDivert завершена", "DEBUG")
            
        except Exception as e:
            log(f"Ошибка при принудительной очистке WinDivert: {e}", "DEBUG")

    def start_strategy_custom(self, custom_args: List[str], strategy_name: str = "Пользовательская стратегия") -> bool:
        """
        Запускает стратегию с произвольными аргументами
        
        Args:
            custom_args: Список аргументов командной строки
            strategy_name: Название стратегии для логов
        """
        try:
            # Останавливаем предыдущий процесс
            if self.running_process and self.is_running():
                log("Останавливаем предыдущий процесс перед запуском нового", "INFO")
                self.stop()
            
            # Очистка WinDivert
            self._force_cleanup_windivert()
            
            import time
            time.sleep(0.5)
            
            if not custom_args:
                log("Нет аргументов для запуска", "ERROR")
                return False
            
            # Разрешаем пути и применяем параметры
            resolved_args = self._resolve_file_paths(custom_args)
            resolved_args = apply_allzone_replacement(resolved_args)
            resolved_args = apply_game_filter_parameter(resolved_args, self.lists_dir)
            resolved_args = apply_ipset_lists_parameter(resolved_args, self.lists_dir)
            resolved_args = apply_wssize_parameter(resolved_args)
            
            # Формируем команду
            cmd = [self.winws_exe] + resolved_args
            
            log(f"Запуск стратегии '{strategy_name}'", "INFO")
            log(f"Количество аргументов: {len(resolved_args)}", "DEBUG")
            
            # СОХРАНЯЕМ ПОЛНУЮ КОМАНДНУЮ СТРОКУ В ОТДЕЛЬНЫЙ ЛОГ
            log_full_command(cmd, strategy_name)
            
            # Формируем командную строку для отображения в основном логе (сокращенная версия)
            cmd_display_parts = []
            for arg in cmd:
                if '\\' in arg and len(arg) > 60:
                    # Сокращаем длинные пути
                    parts = arg.split('\\')
                    if len(parts) > 3:
                        # Сохраняем начало и конец пути
                        short_arg = f"{parts[0]}\\...\\{parts[-1]}"
                    else:
                        short_arg = arg
                    cmd_display_parts.append(short_arg)
                else:
                    cmd_display_parts.append(arg)
            
            cmd_display = ' '.join(cmd_display_parts)
            
            # Выводим в лог
            if len(cmd_display) > 500:
                log("─" * 60, "INFO")
                log("📋 КОМАНДНАЯ СТРОКА (сокращенная):", "INFO")
                log(cmd_display, "INFO")
                log("💡 Полная команда сохранена в logs/commands_full.log", "INFO")
                log("─" * 60, "INFO")
            else:
                log("─" * 60, "INFO")
                log("📋 КОМАНДНАЯ СТРОКА:", "INFO")
                log(cmd_display, "INFO")
                log("─" * 60, "INFO")
            
            # Запускаем процесс
            self.running_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.PIPE,
                startupinfo=self._create_startup_info(),
                creationflags=CREATE_NO_WINDOW,
                cwd=self.work_dir
            )
            
            # Сохраняем информацию
            self.current_strategy_name = strategy_name
            self.current_strategy_args = resolved_args.copy()
            
            # Проверяем запуск
            if self.running_process.poll() is None:
                log(f"Стратегия '{strategy_name}' успешно запущена (PID: {self.running_process.pid})", "✅ SUCCESS")
                return True
            else:
                log("Процесс завершился сразу после запуска", "❌ ERROR")
                self.running_process = None
                self.current_strategy_name = None
                self.current_strategy_args = None
                return False
                
        except Exception as e:
            log(f"Ошибка запуска стратегии: {e}", "❌ ERROR")
            self.running_process = None
            self.current_strategy_name = None
            self.current_strategy_args = None
            return False
    
    def stop(self) -> bool:
        """Останавливает запущенный процесс"""
        try:
            success = True
            
            if self.running_process and self.is_running():
                pid = self.running_process.pid
                strategy_name = self.current_strategy_name or "неизвестная"
                
                log(f"Остановка стратегии '{strategy_name}' (PID: {pid})", "INFO")
                
                # Мягкая остановка
                self.running_process.terminate()
                
                try:
                    self.running_process.wait(timeout=5)
                    log(f"Процесс остановлен (PID: {pid})", "✅ SUCCESS")
                except subprocess.TimeoutExpired:
                    log("Мягкая остановка не сработала, используем принудительную", "⚠ WARNING")
                    self.running_process.kill()
                    self.running_process.wait()
                    log(f"Процесс принудительно завершен (PID: {pid})", "✅ SUCCESS")
            else:
                log("Нет запущенного процесса для остановки", "INFO")
            
            # Дополнительная очистка
            self._stop_windivert_service()
            self._kill_all_winws_processes()
            
            # Очищаем состояние
            self.running_process = None
            self.current_strategy_name = None
            self.current_strategy_args = None
            
            return success
            
        except Exception as e:
            log(f"Ошибка остановки процесса: {e}", "❌ ERROR")
            return False
    
    def _stop_windivert_service(self):
        """Останавливает и удаляет службу WinDivert"""
        try:
            subprocess.run(
                ["sc", "stop", "windivert"],
                capture_output=True,
                creationflags=CREATE_NO_WINDOW,
                timeout=10
            )
            
            import time
            time.sleep(1)
            
            subprocess.run(
                ["sc", "delete", "windivert"],
                capture_output=True,
                creationflags=CREATE_NO_WINDOW,
                timeout=10
            )
            
            log("Служба WinDivert остановлена и удалена", "INFO")
            
        except Exception as e:
            log(f"Ошибка при остановке службы WinDivert: {e}", "DEBUG")
    
    def _kill_all_winws_processes(self):
        """Принудительно завершает все процессы winws.exe"""
        try:
            self._kill_process_by_name("winws.exe")
            log("Все процессы winws.exe завершены", "DEBUG")
            
        except Exception as e:
            log(f"Ошибка при завершении процессов winws.exe: {e}", "DEBUG")
    
    def is_running(self) -> bool:
        """Проверяет, запущен ли процесс"""
        if not self.running_process:
            return False
        
        poll_result = self.running_process.poll()
        is_running = poll_result is None
        
        if not is_running and self.current_strategy_name:
            log(f"Процесс стратегии завершился (код: {poll_result})", "⚠ WARNING")
        
        return is_running
    
    def get_current_strategy_info(self) -> dict:
        """Возвращает информацию о текущей запущенной стратегии"""
        if not self.is_running():
            return {}
        
        return {
            'name': self.current_strategy_name,
            'pid': self.running_process.pid if self.running_process else None,
            'args_count': len(self.current_strategy_args) if self.current_strategy_args else 0
        }

# Глобальный экземпляр
_strategy_runner_instance: Optional[StrategyRunner] = None

def get_strategy_runner(winws_exe_path: str) -> StrategyRunner:
    """Получает или создает глобальный экземпляр StrategyRunner"""
    global _strategy_runner_instance
    if _strategy_runner_instance is None:
        _strategy_runner_instance = StrategyRunner(winws_exe_path)
    return _strategy_runner_instance

def reset_strategy_runner():
    """Сбрасывает глобальный экземпляр"""
    global _strategy_runner_instance
    if _strategy_runner_instance:
        _strategy_runner_instance.stop()
    _strategy_runner_instance = None

def apply_game_filter_parameter(args: list, lists_dir: str) -> list:
    """
    Применяет Game Filter - добавляет порты 1024-65535 для стратегий с other.txt или allzone.txt
    """
    from config import get_game_filter_enabled
    
    if not get_game_filter_enabled():
        return args
    
    new_args = []
    i = 0
    ports_modified = False
    
    while i < len(args):
        arg = args[i]
        new_args.append(arg)
        
        if arg.startswith("--filter-tcp="):
            has_other_hostlist = False
            j = i + 1
            
            while j < len(args) and args[j] != "--new":
                if "--hostlist=" in args[j]:
                    hostlist_value = args[j].split("=", 1)[1].strip('"')
                    hostlist_filename = os.path.basename(hostlist_value)
                    if hostlist_filename in ["other.txt", "other2.txt", "russia-blacklist.txt", "allzone.txt"]:
                        has_other_hostlist = True
                        break
                j += 1
            
            if has_other_hostlist:
                ports_part = arg.split("=", 1)[1]
                ports_list = ports_part.split(",")
                
                if "1024-65535" not in ports_list:
                    ports_list.append("1024-65535")
                    new_args[-1] = f"--filter-tcp={','.join(ports_list)}"
                    ports_modified = True
                    log(f"Game Filter: расширен диапазон портов до {','.join(ports_list)}", "INFO")
        
        i += 1
    
    if ports_modified:
        log("Game Filter применен (добавлены порты 1024-65535)", "✅ SUCCESS")
    
    return new_args

def apply_ipset_lists_parameter(args: list, lists_dir: str) -> list:
    """
    Добавляет --ipset=ipset-all.txt после определенных групп хостлистов:
    1. После хостлистов other.txt, other2.txt, russia-blacklist.txt
    2. После --filter-udp=443 --hostlist=youtube.txt --hostlist=list-general.txt
    
    Args:
        args: Список аргументов командной строки
        lists_dir: Путь к директории с файлами списков
        
    Returns:
        Модифицированный список аргументов с добавленным --ipset=ipset-all.txt
    """
    from config import get_ipset_lists_enabled
    
    # Если функция выключена, возвращаем аргументы без изменений
    if not get_ipset_lists_enabled():
        return args
    
    ipset_all_path = os.path.join(lists_dir, "ipset-all.txt")
    
    if not os.path.exists(ipset_all_path):
        log(f"Файл ipset-all.txt не найден: {ipset_all_path}", "⚠ WARNING")
        return args
    
    GROUP_1 = ["other.txt", "other2.txt", "russia-blacklist.txt", "allzone.txt"]
    GROUP_2 = ["youtube.txt", "list-general.txt"]
    
    new_args = []
    i = 0
    ipset_added_count = 0
    
    while i < len(args):
        arg = args[i]
        new_args.append(arg)
        
        # Проверяем группу 1: хостлисты other/russia
        if arg.startswith("--hostlist="):
            hostlist_value = arg.split("=", 1)[1].strip('"')
            hostlist_filename = os.path.basename(hostlist_value)
            
            # Если это хостлист из первой группы
            if hostlist_filename in GROUP_1:
                # Собираем все последовательные хостлисты из первой группы
                j = i + 1
                last_hostlist_index = i
                
                while j < len(args):
                    next_arg = args[j]
                    
                    if next_arg.startswith("--hostlist="):
                        next_hostlist = next_arg.split("=", 1)[1].strip('"')
                        next_filename = os.path.basename(next_hostlist)
                        
                        if next_filename in GROUP_1:
                            new_args.append(next_arg)
                            last_hostlist_index = j
                            j += 1
                            i = j - 1
                        else:
                            break
                    else:
                        break
                
                # После всех хостлистов первой группы добавляем ipset
                if not _check_and_add_ipset(args, new_args, last_hostlist_index, ipset_all_path):
                    new_args.append(f'--ipset={ipset_all_path}')
                    ipset_added_count += 1
                    log("Добавлен --ipset=ipset-all.txt после группы other/russia", "INFO")
        
        # Проверяем группу 2: после --filter-udp=443
        elif arg == "--filter-udp=443":
            # Проверяем, идут ли далее хостлисты из второй группы
            j = i + 1
            found_group2 = False
            last_hostlist_index = i
            
            while j < len(args):
                next_arg = args[j]
                
                if next_arg.startswith("--hostlist="):
                    next_hostlist = next_arg.split("=", 1)[1].strip('"')
                    next_filename = os.path.basename(next_hostlist)
                    
                    if next_filename in GROUP_2:
                        found_group2 = True
                        new_args.append(next_arg)
                        last_hostlist_index = j
                        j += 1
                        i = j - 1
                    else:
                        break
                else:
                    break
            
            # Если нашли хостлисты из второй группы, добавляем ipset
            if found_group2:
                if not _check_and_add_ipset(args, new_args, last_hostlist_index, ipset_all_path):
                    new_args.append(f'--ipset={ipset_all_path}')
                    ipset_added_count += 1
                    log("Добавлен --ipset=ipset-all.txt после группы youtube/list-general", "INFO")
        
        i += 1
    
    if ipset_added_count > 0:
        log(f"IPset списки применены (добавлено {ipset_added_count} ipset-all.txt)", "✅ SUCCESS")
    
    return new_args


def _check_and_add_ipset(original_args: list, new_args: list, last_index: int, ipset_path: str) -> bool:
    """
    Проверяет, есть ли уже ipset-all.txt после указанной позиции
    
    Args:
        original_args: Оригинальный список аргументов
        new_args: Новый список аргументов (не используется в текущей версии)
        last_index: Индекс последнего обработанного элемента в original_args
        ipset_path: Путь к файлу ipset-all.txt
        
    Returns:
        True если ipset уже присутствует, False если нужно добавить
    """
    next_idx = last_index + 1
    if next_idx < len(original_args) and original_args[next_idx].startswith("--ipset="):
        ipset_value = original_args[next_idx].split("=", 1)[1].strip('"')
        if os.path.basename(ipset_value) == "ipset-all.txt":
            log("--ipset=ipset-all.txt уже присутствует", "DEBUG")
            return True
    return False

def apply_allzone_replacement(args: list) -> list:
    """
    Заменяет other.txt на allzone.txt в хостлистах если включено в настройках
    
    Args:
        args: Список аргументов командной строки
        
    Returns:
        Модифицированный список аргументов с замененными хостлистами
    """
    from config import get_allzone_hostlist_enabled
    
    # Если замена выключена, возвращаем аргументы без изменений
    if not get_allzone_hostlist_enabled():
        return args
    
    new_args = []
    replacements_count = 0
    
    for arg in args:
        if arg.startswith("--hostlist="):
            hostlist_value = arg.split("=", 1)[1]
            
            # Проверяем, содержит ли путь other.txt
            if "other.txt" in hostlist_value:
                # Заменяем other.txt на allzone.txt
                new_value = hostlist_value.replace("other.txt", "allzone.txt")
                new_args.append(f"--hostlist={new_value}")
                replacements_count += 1
                log(f"Заменен хостлист: other.txt → allzone.txt", "DEBUG")
            else:
                new_args.append(arg)
        else:
            new_args.append(arg)
    
    if replacements_count > 0:
        log(f"Выполнена замена other.txt на allzone.txt ({replacements_count} замен)", "✅ SUCCESS")
    
    return new_args