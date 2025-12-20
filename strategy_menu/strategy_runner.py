# strategy_menu/strategy_runner.py

import os
import subprocess
import shlex
from typing import Optional, List, Dict
from log import log
from datetime import datetime

from .apply_filters import apply_all_filters
from .constants import SW_HIDE, CREATE_NO_WINDOW, STARTF_USESHOWWINDOW
from dpi.process_health_check import (
    check_process_health,
    get_last_crash_info,
    check_common_crash_causes,
    check_conflicting_processes,
    get_conflicting_processes_report,
    diagnose_startup_error
)

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
            # Обработка --wf-raw-part (новый формат для winws2)
            if arg.startswith("--wf-raw-part="):
                value = arg.split("=", 1)[1]
                
                # Если значение начинается с @, это означает файл
                if value.startswith("@"):
                    filename = value[1:]  # Убираем @ в начале
                    filename = filename.strip('"')
                    
                    if not os.path.isabs(filename):
                        # WINDIVERT_FILTER - это путь к папке windivert.filter
                        # Файлы фильтров лежат прямо в ней
                        full_path = os.path.join(WINDIVERT_FILTER, filename)
                        
                        # Проверяем существование файла
                        if not os.path.exists(full_path):
                            log(f"Предупреждение: файл фильтра не найден: {full_path}", "WARNING")
                        
                        resolved_args.append(f'--wf-raw-part=@{full_path}')
                    else:
                        resolved_args.append(f'--wf-raw-part=@{filename}')
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
                "--dpi-desync-fake-tls=",
                "--dpi-desync-fake-syndata=", 
                "--dpi-desync-fake-quic=",
                "--dpi-desync-fake-unknown-udp=",
                "--dpi-desync-split-seqovl-pattern=",
                "--dpi-desync-fake-http=", 
                "--dpi-desync-fake-unknown=",
                "--dpi-desync-fakedsplit-pattern="
            ]):
                prefix, filename = arg.split("=", 1)
                
                # Проверяем специальные значения (hex или модификаторы)
                if filename.startswith("0x") or filename.startswith("0x00") or filename.startswith("!") or filename.startswith("^"):
                    resolved_args.append(arg)
                else:
                    filename = filename.strip('"')
                    
                    if not os.path.isabs(filename):
                        full_path = os.path.join(self.bin_dir, filename)
                        
                        # Проверяем существование файла
                        if not os.path.exists(full_path):
                            log(f"Предупреждение: бинарный файл не найден: {full_path}", "WARNING")
                        
                        resolved_args.append(f'{prefix}={full_path}')
                    else:
                        resolved_args.append(f'{prefix}={filename}')
            else:
                resolved_args.append(arg)
        
        return resolved_args

    def _fast_cleanup_services(self):
        """Быстрая очистка служб через Win API (для обычного запуска)"""
        try:
            from utils.service_manager import cleanup_windivert_services
            
            # Очищаем все службы WinDivert через Win API
            cleanup_windivert_services()
            
            # Не ждём - winws сам пересоздаст службу если нужно
            
        except Exception as e:
            log(f"Ошибка быстрой очистки: {e}", "DEBUG")
    
    def _force_cleanup_multiple_services(self, service_names, processes_to_kill=None, drivers_to_unload=None):
        """Принудительная очистка списка служб через Win API"""
        try:
            from utils.service_manager import stop_and_delete_service, unload_driver
            from utils.process_killer import kill_process_by_name
            import time
            
            log(f"Принудительная очистка служб через Win API: {', '.join(service_names)}...", "DEBUG")
            
            # Убиваем процессы сразу, если указаны
            if processes_to_kill:
                for process_name in processes_to_kill:
                    try:
                        killed = kill_process_by_name(process_name, kill_all=True)
                        if killed > 0:
                            log(f"Процесс {process_name} завершён через Win API", "DEBUG")
                    except Exception as e:
                        log(f"Ошибка при завершении процесса {process_name}: {e}", "DEBUG")
            
            time.sleep(0.1)
            
            # Выгружаем драйверы, если указаны
            if drivers_to_unload:
                for driver_name in drivers_to_unload:
                    try:
                        unload_driver(driver_name)
                    except Exception as e:
                        log(f"Ошибка при выгрузке драйвера {driver_name}: {e}", "DEBUG")
            
            time.sleep(0.1)
            
            # Останавливаем и удаляем все службы через Win API
            for service_name in service_names:
                try:
                    stop_and_delete_service(service_name, retry_count=1)
                except Exception as e:
                    log(f"Ошибка при очистке службы {service_name}: {e}", "DEBUG")
            
            log("Очистка завершена", "DEBUG")
            
        except Exception as e:
            log(f"Ошибка при принудительной очистке: {e}", "DEBUG")

    def _is_windivert_conflict_error(self, stderr: str, exit_code: int) -> bool:
        """Проверяет, является ли ошибка конфликтом WinDivert (GUID/LUID уже существует)"""
        windivert_error_signatures = [
            "GUID or LUID already exists",
            "object with that GUID",
            "error opening filter",
            "WinDivert",
            "access denied"
        ]
        
        # Код 9 - типичный код ошибки WinDivert при конфликте
        if exit_code == 9:
            return True
        
        stderr_lower = stderr.lower()
        return any(sig.lower() in stderr_lower for sig in windivert_error_signatures)

    def _aggressive_windivert_cleanup(self):
        """Агрессивная очистка WinDivert через Win API - для случаев когда обычная не помогает"""
        from utils.service_manager import stop_and_delete_service, unload_driver
        import time
        
        log("🔧 Выполняем агрессивную очистку WinDivert через Win API...", "INFO")
        
        # 1. Сначала убиваем ВСЕ процессы которые могут держать хэндлы
        self._kill_all_winws_processes()
        time.sleep(0.3)
        
        # 2. Выгружаем драйверы через fltmc (до удаления служб!)
        drivers = ["WinDivert", "WinDivert14", "WinDivert64", "Monkey"]
        for driver in drivers:
            try:
                unload_driver(driver)
            except:
                pass
        
        time.sleep(0.2)
        
        # 3. Останавливаем и удаляем службы через Win API
        services = ["WinDivert", "WinDivert14", "WinDivert64", "windivert", "Monkey"]
        for service in services:
            try:
                stop_and_delete_service(service, retry_count=3)
            except:
                pass
        
        time.sleep(0.3)
        
        # 4. Финальная очистка процессов
        self._kill_all_winws_processes()
        
        log("✅ Агрессивная очистка завершена", "INFO")

    def start_strategy_custom(self, custom_args: List[str], strategy_name: str = "Пользовательская стратегия", _retry_count: int = 0) -> bool:
        """
        Запускает стратегию с произвольными аргументами
        
        Args:
            custom_args: Список аргументов командной строки
            strategy_name: Название стратегии для логов
            _retry_count: Внутренний счетчик попыток (не передавать извне)
        """
        MAX_RETRIES = 2  # Максимум 2 повторные попытки при ошибке WinDivert
        
        conflicting = check_conflicting_processes()
        if conflicting:
            warning_report = get_conflicting_processes_report()
            log(warning_report, "⚠ WARNING")
            
        try:
            # Останавливаем предыдущий процесс
            if self.running_process and self.is_running():
                log("Останавливаем предыдущий процесс перед запуском нового", "INFO")
                self.stop()
            
            # Агрессивная очистка перед запуском
            import time
            from utils.process_killer import kill_winws_force

            if _retry_count > 0:
                # Агрессивная очистка только при повторной попытке
                self._aggressive_windivert_cleanup()
            else:
                # ✅ ВСЕГДА вызываем kill_winws_force - psutil может не видеть процесс
                # но WinDivert драйвер всё ещё может быть занят
                log("Очистка предыдущих процессов winws...", "DEBUG")
                kill_winws_force()

                # Быстрая очистка служб
                self._fast_cleanup_services()

                # ✅ Выгружаем драйверы WinDivert для полной очистки
                try:
                    from utils.service_manager import unload_driver
                    for driver in ["WinDivert", "WinDivert14", "WinDivert64", "Monkey"]:
                        try:
                            unload_driver(driver)
                        except:
                            pass
                except:
                    pass

                time.sleep(0.3)  # Пауза для освобождения ресурсов WinDivert
            
            if not custom_args:
                log("Нет аргументов для запуска", "ERROR")
                return False
            
            # Разрешаем пути
            resolved_args = self._resolve_file_paths(custom_args)
            
            # ✅ Применяем ВСЕ фильтры в правильном порядке
            resolved_args = apply_all_filters(resolved_args, self.lists_dir)
            
            # Формируем команду
            cmd = [self.winws_exe] + resolved_args
            
            log(f"Запуск стратегии '{strategy_name}'" + (f" (попытка {_retry_count + 1})" if _retry_count > 0 else ""), "INFO")
            log(f"Количество аргументов: {len(resolved_args)}", "DEBUG")
            
            # СОХРАНЯЕМ ПОЛНУЮ КОМАНДНУЮ СТРОКУ
            log_full_command(cmd, strategy_name)
            
            # Запускаем процесс
            # Примечание: stdin=subprocess.DEVNULL вместо PIPE - Cygwin программы могут крашиться с PIPE
            self.running_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.DEVNULL,
                startupinfo=self._create_startup_info(),
                creationflags=CREATE_NO_WINDOW,
                cwd=self.work_dir
            )
            
            # Сохраняем информацию
            self.current_strategy_name = strategy_name
            self.current_strategy_args = resolved_args.copy()
            
            # ⚡ ОЧЕНЬ БЫСТРАЯ ПРОВЕРКА ЗАПУСКА
            # ProcessMonitorThread следит за состоянием в фоне
            import time
            time.sleep(0.2)  # Минимальная пауза для инициализации
            
            # Проверяем что процесс не упал сразу после запуска
            if self.running_process.poll() is None:
                # Процесс запущен и работает
                log(f"✅ Стратегия '{strategy_name}' запущена (PID: {self.running_process.pid})", "SUCCESS")
                return True
            else:
                # Процесс уже завершился - это ошибка
                exit_code = self.running_process.returncode
                log(f"❌ Стратегия '{strategy_name}' завершилась сразу (код: {exit_code})", "ERROR")
                
                # Получаем вывод ошибки
                stderr_output = ""
                try:
                    stderr_output = self.running_process.stderr.read().decode('utf-8', errors='ignore')
                    if stderr_output:
                        log(f"Ошибка: {stderr_output[:500]}", "ERROR")
                except:
                    pass
                
                # Очищаем состояние
                self.running_process = None
                self.current_strategy_name = None
                self.current_strategy_args = None
                
                # 🔄 АВТОМАТИЧЕСКИЙ RETRY при ошибке WinDivert
                if self._is_windivert_conflict_error(stderr_output, exit_code) and _retry_count < MAX_RETRIES:
                    log(f"🔄 Обнаружен конфликт WinDivert, автоматическая повторная попытка ({_retry_count + 1}/{MAX_RETRIES})...", "INFO")
                    return self.start_strategy_custom(custom_args, strategy_name, _retry_count + 1)
                
                # Проверяем типичные причины падения
                from dpi.process_health_check import check_common_crash_causes
                causes = check_common_crash_causes()
                if causes:
                    log("💡 Возможные причины:", "INFO")
                    for line in causes.split('\n')[:5]:  # Только первые 5 строк
                        log(f"  {line}", "INFO")
                
                return False
                
        except Exception as e:
            # Диагностируем ошибку и выводим понятное сообщение
            diagnosis = diagnose_startup_error(e, self.winws_exe)
            for line in diagnosis.split('\n'):
                log(line, "❌ ERROR")

            import traceback
            log(traceback.format_exc(), "DEBUG")
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
            self._stop_monkey_service()
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
        """Останавливает и удаляет службу WinDivert через Win API"""
        from utils.service_manager import stop_and_delete_service
        
        # Пробуем разные варианты имени службы
        for service_name in ["WinDivert", "windivert", "WinDivert14", "WinDivert64"]:
            stop_and_delete_service(service_name, retry_count=3)

    def _stop_monkey_service(self):
        """Останавливает и удаляет службу Monkey через Win API"""
        from utils.service_manager import stop_and_delete_service
        stop_and_delete_service("Monkey", retry_count=3)

    def _force_delete_service(self, service_name: str, max_retries: int = 5):
        """Принудительно удаляет службу через Win API с повторными попытками"""
        from utils.service_manager import stop_and_delete_service, service_exists
        import time
        
        try:
            # Пробуем удалить через Win API
            for attempt in range(max_retries):
                if stop_and_delete_service(service_name, retry_count=1):
                    log(f"Служба {service_name} удалена через Win API", "INFO")
                    return True
                
                # Если не получилось - убиваем процессы и пробуем снова
                if attempt < max_retries - 1:
                    log(f"Попытка {attempt + 1}/{max_retries} удаления {service_name}", "DEBUG")
                    self._kill_all_winws_processes()
                    time.sleep(0.3)
            
            # Проверяем результат
            if not service_exists(service_name):
                log(f"Служба {service_name} успешно удалена", "INFO")
                return True
            else:
                log(f"Служба {service_name} всё ещё существует", "WARNING")
                return False
                
        except Exception as e:
            log(f"Ошибка при удалении службы {service_name}: {e}", "DEBUG")
            return False

    def _kill_all_winws_processes(self):
        """Принудительно завершает все процессы winws.exe и winws2.exe через Win API"""
        try:
            from utils.process_killer import kill_winws_force
            kill_winws_force()
        except Exception as e:
            log(f"Ошибка при завершении процессов winws: {e}", "DEBUG")
    
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

    def get_process(self) -> Optional[subprocess.Popen]:
        """Возвращает текущий запущенный процесс для чтения вывода"""
        if self.is_running():
            return self.running_process
        return None

# Глобальный экземпляр
_strategy_runner_instance: Optional[StrategyRunner] = None

def get_strategy_runner(winws_exe_path: str) -> StrategyRunner:
    """Получает или создает глобальный экземпляр StrategyRunner"""
    global _strategy_runner_instance
    if _strategy_runner_instance is None:
        _strategy_runner_instance = StrategyRunner(winws_exe_path)
    return _strategy_runner_instance

def reset_strategy_runner():
    """Сбрасывает глобальный экземпляр (синхронно останавливает процесс)"""
    global _strategy_runner_instance
    if _strategy_runner_instance:
        _strategy_runner_instance.stop()
    _strategy_runner_instance = None

def invalidate_strategy_runner():
    """Помечает runner для пересоздания без синхронной остановки.
    Используется при смене метода запуска - UI обновляется мгновенно,
    а старый процесс будет остановлен при следующем запуске DPI."""
    global _strategy_runner_instance
    _strategy_runner_instance = None

def get_current_runner() -> Optional[StrategyRunner]:
    """Возвращает текущий экземпляр runner без создания нового"""
    return _strategy_runner_instance