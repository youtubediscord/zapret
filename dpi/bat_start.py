# dpi/bat_start.py
import os
import time
import subprocess
import psutil
from typing import Optional, Callable, Dict, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from strategy_menu.bat_zapret1_manager import BatZapret1Manager
    from main import LupiDPIApp

from log import log
from utils import run_hidden, get_system_exe, get_system32_path

from dpi.process_health_check import (
    check_process_health,
    get_last_crash_info,
    check_common_crash_causes,
    check_conflicting_processes,
    get_conflicting_processes_report,
    diagnose_startup_error
)

class BatDPIStart:
    """Класс для запуска DPI. Отвечает только за BAT режим"""

    def __init__(self, winws_exe: str, status_callback: Optional[Callable[[str], None]] = None, 
                 ui_callback: Optional[Callable[[bool], None]] = None, 
                 app_instance: Optional['LupiDPIApp'] = None):
        """
        Инициализирует BatDPIStart.
        
        Args:
            winws_exe: Путь к исполняемому файлу winws.exe
            status_callback: Функция обратного вызова для отображения статуса
            ui_callback: Функция обратного вызова для обновления UI
            app_instance: Ссылка на главное приложение
        """
        self.winws_exe = winws_exe
        self.status_callback = status_callback
        self.ui_callback = ui_callback
        self.app_instance = app_instance

    def _set_status(self, text: str) -> None:
        """Внутренний метод для установки статуса"""
        if self.status_callback:
            self.status_callback(text)

    def _update_ui(self, running: bool) -> None:
        """Внутренний метод для обновления UI"""
        if self.ui_callback:
            self.ui_callback(running)
    
    def set_status(self, text: str) -> None:
        """Отображает статусное сообщение."""
        if self.status_callback:
            self.status_callback(text)
        else:
            print(text)

    def check_process_running_fast(self, silent: bool = False) -> bool:
        """
        ⚡ БЫСТРАЯ проверка через psutil (~1-10ms вместо 100-2000ms у WMI)
        Основной метод проверки — используйте его везде!
        """
        try:
            for proc in psutil.process_iter(['name']):
                try:
                    proc_name = proc.info['name']
                    if proc_name and proc_name.lower() in ('winws.exe', 'winws2.exe'):
                        if not silent:
                            log(f"winws/winws2 state → True (psutil)", "DEBUG")
                        return True
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue
            if not silent:
                log(f"winws/winws2 state → False (psutil)", "DEBUG")
            return False
        except Exception as e:
            if not silent:
                log(f"psutil check error: {e}", "DEBUG")
            # psutil не работает - возвращаем False (процесс не найден)
            return False

    def check_process_running_wmi(self, silent: bool = False) -> bool:
        """
        Проверка процесса (теперь использует psutil, WMI как резерв)
        ✅ Оставлен для обратной совместимости — внутри вызывает check_process_running_fast()
        """
        return self.check_process_running_fast(silent)

    def check_process_running(self, silent: bool = False) -> bool:
        """
        Проверка процесса (теперь использует psutil)
        ✅ Оставлен для обратной совместимости — внутри вызывает check_process_running_fast()
        """
        return self.check_process_running_fast(silent)

    def cleanup_windivert_service(self) -> bool:
        """Очистка службы через PowerShell - без окон"""
        ps_script = """
        $service = Get-Service -Name windivert -ErrorAction SilentlyContinue
        if ($service) {
            Stop-Service -Name windivert -Force -ErrorAction SilentlyContinue
            Start-Sleep -Seconds 2
            sc.exe delete windivert | Out-Null
            Stop-Service -Name Monkey -Force -ErrorAction SilentlyContinue
            Start-Sleep -Seconds 2
            sc.exe delete Monkey | Out-Null
        }
        """
        
        try:
            ps_exe = os.path.join(get_system32_path(), 'WindowsPowerShell', 'v1.0', 'powershell.exe')
            run_hidden(
                [ps_exe, '-WindowStyle', 'Hidden', '-NoProfile', '-Command', ps_script],
                wait=True
            )
            return True
        except Exception as e:
            log(f"Ошибка очистки службы: {e}", "⚠ WARNING")
            return True

    def stop_all_processes(self) -> bool:
        """Останавливает все процессы DPI через Win API"""
        log("Останавливаем все процессы winws через Win API...", "INFO")
        
        try:
            from utils.process_killer import kill_winws_all
            kill_winws_all()
        except Exception as e:
            log(f"Ошибка остановки через Win API: {e}", "⚠ WARNING")

        time.sleep(0.3)
        ok = not self.check_process_running_wmi(silent=True)
        log("Все процессы остановлены" if ok else "winws/winws2 ещё работает",
            "✅ SUCCESS" if ok else "⚠ WARNING")
        return ok

    def _get_strategy_manager(self) -> Optional['BatZapret1Manager']:
        """Получает strategy_manager с правильной типизацией"""
        if not self.app_instance:
            return None
        
        if hasattr(self.app_instance, 'strategy_manager'):
            return self.app_instance.strategy_manager
        
        return None

    def start_dpi(self, selected_mode: Optional[Any] = None) -> bool:
        """
        Запускает DPI через BAT файлы.
        Для Direct режима используйте DPIController напрямую.
        """
        return self._start_dpi_bat(selected_mode)

    def _start_dpi_direct(self, selected_mode: Optional[Any]) -> bool:
        """Запускает DPI напрямую через StrategyRunner"""
        try:
            from strategy_menu.strategy_runner import get_strategy_runner
            
            runner = get_strategy_runner(self.winws_exe)
            
            log("Прямой запуск поддерживает только комбинированные стратегии", "ERROR")
            return False
            
        except Exception as e:
            log(f"Ошибка прямого запуска DPI: {e}", "❌ ERROR")
            return False
    
    def _start_dpi_bat(self, selected_mode: Optional[Any]) -> bool:
        """Запуск через .bat файлы"""
        try:
            log("======================== Start DPI (BAT) ========================", level="START")
            # Диагностика: выводим что передано в selected_mode
            log(f"selected_mode значение: {selected_mode}", "DEBUG")
            
            # Проверяем наличие BAT файлов
            from config import BAT_FOLDER
            bat_dir = BAT_FOLDER

            if os.path.exists(bat_dir):
                bat_files = [f for f in os.listdir(bat_dir) if f.endswith('.bat')]
                log(f"Найдено .bat файлов: {len(bat_files)}", "DEBUG")
                if len(bat_files) < 10:  # Если мало файлов, выведем список
                    log(f"Список .bat файлов: {bat_files}", "DEBUG")
            else:
                log(f"Папка bat не найдена: {bat_dir}", "⚠ WARNING")
            
            # Проверяем, запущен ли уже процесс
            if self.check_process_running_wmi(silent=True):
                log("Процесс winws/winws2 уже запущен, перезапускаем...", level="⚠ WARNING")
                if self.app_instance:
                    from dpi.stop import stop_dpi
                    stop_dpi(self.app_instance)
                time.sleep(2)
            
            # Определяем путь к .bat файлу
            bat_file: Optional[str] = None
            strategy_name = "Неизвестная стратегия"
            
            if selected_mode:
                if isinstance(selected_mode, dict):
                    # Передан словарь с информацией о стратегии
                    file_path = selected_mode.get('file_path')
                    strategy_name = selected_mode.get('name', 'Неизвестная стратегия')
                    
                    if file_path:
                        bat_file = os.path.join(BAT_FOLDER, file_path)
                        log(f"Используем file_path из словаря: {file_path}", "DEBUG")
                    else:
                        log("В словаре стратегии отсутствует file_path", "⚠ WARNING")
                        self.set_status("Ошибка: отсутствует file_path в информации о стратегии")
                        return False
                        
                elif isinstance(selected_mode, str):
                    # Передано имя стратегии - ищем в strategy_manager
                    strategy_name = selected_mode
                    log(f"Поиск стратегии по имени: {strategy_name}", "DEBUG")
                    
                    strategy_manager = self._get_strategy_manager()
                    if strategy_manager:
                        # Ищем стратегию по имени
                        strategy = strategy_manager.get_strategy_by_name(strategy_name)
                        if strategy:
                            file_path = strategy.get('file_path')
                            if file_path:
                                bat_file = os.path.join(BAT_FOLDER, file_path)
                                log(f"Найден file_path для '{strategy_name}': {file_path}", "SUCCESS")
                        
                        # Если не нашли по имени, пробуем как имя файла
                        if not bat_file:
                            # Проверяем, может это имя файла напрямую
                            if strategy_name.endswith('.bat'):
                                potential_path = os.path.join(BAT_FOLDER, strategy_name)
                            else:
                                potential_path = os.path.join(BAT_FOLDER, f"{strategy_name}.bat")
                            
                            if os.path.exists(potential_path):
                                bat_file = potential_path
                                log(f"Найден .bat файл напрямую: {bat_file}", "DEBUG")
                    
                    if not bat_file:
                        log(f"Стратегия '{strategy_name}' не найдена", "ERROR")
                        self.set_status(f"Стратегия '{strategy_name}' не найдена")
                        return False
            else:
                # Используем стратегию по умолчанию
                log("Используем стратегию по умолчанию", "DEBUG")
                
                # Получаем strategy_manager для поиска дефолтной стратегии
                strategy_manager = self._get_strategy_manager()
                
                if strategy_manager:
                    # Ищем рекомендуемую стратегию
                    recommended = strategy_manager.get_recommended_strategy()
                    if recommended:
                        file_path = recommended.get('file_path')
                        strategy_name = recommended.get('name', 'Рекомендуемая стратегия')
                        if file_path:
                            bat_file = os.path.join(BAT_FOLDER, file_path)
                            log(f"Используем рекомендуемую стратегию: {strategy_name}", "INFO")
                
                # Fallback - ищем любой .bat файл
                if not bat_file and os.path.exists(bat_dir):
                    bat_files = [f for f in os.listdir(bat_dir) if f.endswith('.bat')]
                    if bat_files:
                        bat_file = os.path.join(bat_dir, bat_files[0])
                        strategy_name = bat_files[0].replace('.bat', '').replace('_', ' ').title()
                        log(f"Используем первый доступный .bat: {bat_files[0]}", "⚠ WARNING")
            
            if not bat_file:
                log("Не удалось определить BAT файл для запуска", "❌ ERROR")
                self.set_status("Ошибка: не удалось определить файл стратегии")
                return False
            
            # Проверяем существование .bat файла
            log(f"Проверяем существование файла: {bat_file}", "DEBUG")
            if not os.path.exists(bat_file):
                log(f"BAT файл не найден: {bat_file}", level="❌ ERROR")
                self.set_status(f"Файл стратегии не найден: {os.path.basename(bat_file)}")
                return False
            
            # Запускаем .bat файл
            return self._execute_bat_file(bat_file, strategy_name)
                
        except Exception as e:
            log(f"Критическая ошибка в _start_dpi_bat: {e}", level="❌ ERROR")
            self.set_status(f"Критическая ошибка: {e}")
            return False

    def _execute_bat_file(self, bat_file: str, strategy_name: str) -> bool:
        """
        Запуск стратегии.

        Логика по расширению файла:
        - .txt → парсинг аргументов, запуск через StrategyRunner
        - .bat → запуск напрямую как BAT скрипт (fallback)
        """
        self.set_status(f"Запуск стратегии: {strategy_name}")
        file_ext = os.path.splitext(bat_file)[1].lower()
        log(f"Запуск файла: {bat_file} (формат: {file_ext})", level="INFO")

        conflicting = check_conflicting_processes()
        if conflicting:
            warning_report = get_conflicting_processes_report()
            log(warning_report, "⚠ WARNING")

        # Агрессивная очистка служб WinDivert перед запуском
        try:
            from utils.service_manager import cleanup_windivert_services
            import time

            if cleanup_windivert_services():
                log("🧹 Очистка служб WinDivert выполнена", "DEBUG")
                time.sleep(0.3)  # Даём Windows время удалить службы
        except Exception as e:
            log(f"Ошибка очистки служб: {e}", "DEBUG")

        # .BAT файлы запускаем напрямую как скрипты (старый формат)
        if file_ext == '.bat':
            log("Формат BAT - запуск как скрипт", "INFO")
            return self._execute_bat_file_fallback(bat_file, strategy_name)

        # .TXT файлы парсим и запускаем через StrategyRunner (новый формат)
        try:
            from utils.bat_parser import parse_bat_file, create_process_direct

            parsed = parse_bat_file(bat_file)
            if not parsed:
                log("Не удалось распарсить файл стратегии", "WARNING")
                return False

            exe_path, args = parsed

            # Новый формат TXT: exe_path = None, используем StrategyRunner
            if exe_path is None:
                log(f"Используем StrategyRunner ({len(args)} аргументов)", "INFO")
                return self._execute_with_strategy_runner(args, strategy_name)

            # Если парсер вернул exe_path - это смешанный формат, запускаем напрямую
            log(f"Извлечена команда: {os.path.basename(exe_path)} с {len(args)} аргументами", "DEBUG")

            # Запускаем напрямую через CreateProcess (быстрее чем ShellExecuteEx + bat)
            working_dir = os.path.dirname(exe_path)
            result = create_process_direct(exe_path, args, working_dir)
            
            if not result:
                log("❌ Ошибка CreateProcess, используем fallback", "WARNING")
                return self._execute_bat_file_fallback(bat_file, strategy_name)
            
            log("✅ winws запущен напрямую через CreateProcess (быстрый метод)", "SUCCESS")
            
            # ⚡ ПРОВЕРКА ЗАПУСКА с несколькими попытками
            max_attempts = 5
            for attempt in range(max_attempts):
                time.sleep(0.5)  # Уменьшенная пауза - прямой запуск быстрее
                
                if self.check_process_running_fast(silent=True):
                    log(f"✅ DPI успешно запущен: {strategy_name}", level="SUCCESS")
                    self.set_status(f"✅ DPI запущен: {strategy_name}")
                    self._update_ui(True)
                    return True
                    
                # Логируем только на последней попытке
                if attempt == max_attempts - 1:
                    log(f"⚠️ DPI не запустился после {max_attempts} проверок", level="WARNING")
            
            # Процесс упал - добавляем диагностику
            log("💡 Процесс winws запустился но сразу упал. Диагностика...", level="WARNING")
            
            # Проверяем возможные причины
            from dpi.process_health_check import check_common_crash_causes
            causes = check_common_crash_causes()
            if causes:
                log(f"💡 Возможные причины падения:\n{causes}", "INFO")
            
            # Не показываем ошибку сразу — ProcessMonitorThread продолжит следить
            log("DPI ещё не запущен, продолжаем мониторинг...", level="INFO")
            self.set_status("⏳ Ожидание запуска DPI...")

            # Возвращаем True чтобы ProcessMonitorThread продолжил работать
            return True

        except Exception as e:
            # Диагностируем ошибку и выводим понятное сообщение
            diagnosis = diagnose_startup_error(e, self.winws_exe)
            for line in diagnosis.split('\n'):
                log(line, "❌ ERROR")
            import traceback
            log(traceback.format_exc(), "DEBUG")
            # Последняя попытка - fallback
            return self._execute_bat_file_fallback(bat_file, strategy_name)

    def _execute_with_strategy_runner(self, args: list, strategy_name: str) -> bool:
        """
        Запуск через StrategyRunner для НОВОГО формата BAT файлов.

        StrategyRunner автоматически:
        - Находит winws.exe
        - Подставляет пути к --hostlist=, --ipset=, --dpi-desync-fake-*=
        - Запускает процесс
        """
        try:
            from strategy_menu.strategy_runner import get_strategy_runner

            # Получаем runner с путём к winws.exe
            runner = get_strategy_runner(self.winws_exe)

            log(f"Запуск через StrategyRunner: {strategy_name}", "INFO")

            # Запускаем стратегию
            success = runner.start_strategy_custom(args, strategy_name)

            if success:
                log(f"✅ DPI успешно запущен через StrategyRunner: {strategy_name}", "SUCCESS")
                self.set_status(f"✅ DPI запущен: {strategy_name}")
                self._update_ui(True)
                return True
            else:
                log(f"❌ Ошибка запуска через StrategyRunner", "ERROR")
                self.set_status("❌ Ошибка запуска DPI")
                return False

        except Exception as e:
            # Диагностируем ошибку и выводим понятное сообщение
            diagnosis = diagnose_startup_error(e, self.winws_exe)
            for line in diagnosis.split('\n'):
                log(line, "❌ ERROR")
            import traceback
            log(traceback.format_exc(), "DEBUG")
            return False

    def _execute_bat_file_fallback(self, bat_file: str, strategy_name: str) -> bool:
        """Fallback: запуск через ShellExecuteEx (медленно, но надёжно)"""
        log("Используем fallback метод (ShellExecuteEx)", "WARNING")
        
        try:
            import ctypes
            from ctypes import wintypes, byref
            
            # Получаем абсолютный путь
            abs_bat_file = os.path.abspath(bat_file)
            
            # Структура SHELLEXECUTEINFO
            class SHELLEXECUTEINFO(ctypes.Structure):
                _fields_ = [
                    ("cbSize", wintypes.DWORD),
                    ("fMask", wintypes.ULONG),
                    ("hwnd", wintypes.HWND),
                    ("lpVerb", wintypes.LPCWSTR),
                    ("lpFile", wintypes.LPCWSTR),
                    ("lpParameters", wintypes.LPCWSTR),
                    ("lpDirectory", wintypes.LPCWSTR),
                    ("nShow", ctypes.c_int),
                    ("hInstApp", wintypes.HINSTANCE),
                    ("lpIDList", ctypes.c_void_p),
                    ("lpClass", wintypes.LPCWSTR),
                    ("hkeyClass", wintypes.HKEY),
                    ("dwHotKey", wintypes.DWORD),
                    ("hIcon", wintypes.HANDLE),
                    ("hProcess", wintypes.HANDLE)
                ]
            
            # Константы
            SEE_MASK_NOCLOSEPROCESS = 0x00000040
            SW_HIDE = 0
            
            # Заполняем структуру
            sei = SHELLEXECUTEINFO()
            sei.cbSize = ctypes.sizeof(SHELLEXECUTEINFO)
            sei.fMask = SEE_MASK_NOCLOSEPROCESS
            sei.hwnd = None
            sei.lpVerb = "open"
            sei.lpFile = abs_bat_file
            sei.lpParameters = None
            sei.lpDirectory = None
            sei.nShow = SW_HIDE
            
            # Запускаем
            shell32 = ctypes.windll.shell32
            result = shell32.ShellExecuteExW(byref(sei))
            
            if result:
                if sei.hProcess:
                    ctypes.windll.kernel32.CloseHandle(sei.hProcess)
                log("BAT запущен через ShellExecuteEx (fallback)", "INFO")
            else:
                log("Ошибка ShellExecuteEx (fallback)", "ERROR")
                return False
            
            # Проверка запуска
            max_attempts = 8  # Больше попыток для медленного метода
            for attempt in range(max_attempts):
                time.sleep(1)
                
                if self.check_process_running_fast(silent=True):
                    log(f"✅ DPI успешно запущен через fallback: {strategy_name}", "SUCCESS")
                    self.set_status(f"✅ DPI запущен: {strategy_name}")
                    self._update_ui(True)
                    return True
                    
                if attempt == max_attempts - 1:
                    log(f"⚠️ DPI не запустился после {max_attempts} проверок (fallback)", "WARNING")
            
            log("DPI ещё не запущен, продолжаем мониторинг...", "INFO")
            self.set_status("⏳ Ожидание запуска DPI...")
            return True
            
        except Exception as e:
            log(f"Критическая ошибка fallback: {e}", "ERROR")
            import traceback
            log(traceback.format_exc(), "DEBUG")
            return False
