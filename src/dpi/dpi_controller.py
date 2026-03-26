"""
Контроллер для управления DPI - содержит всю логику запуска и остановки
"""

from PyQt6.QtCore import QThread, QObject, pyqtSignal, QMetaObject, Qt, Q_ARG
from pathlib import Path
from strategy_menu import get_strategy_launch_method
from log import log
from dpi.process_health_check import (
    diagnose_startup_error,
    check_conflicting_processes,
    try_kill_conflicting_processes,
    get_conflicting_processes_report,
)
import time

class DPIStartWorker(QObject):
    """Worker для асинхронного запуска DPI"""
    finished = pyqtSignal(bool, str)  # success, error_message
    progress = pyqtSignal(str)        # status_message
    
    def __init__(self, app_instance, selected_mode, launch_method):
        super().__init__()
        self.app_instance = app_instance
        self.selected_mode = selected_mode
        self.launch_method = launch_method
        self.dpi_starter = app_instance.dpi_starter
        # Filled when start_* returns False to provide meaningful UI error.
        self._last_error_message: str = ""

    def _get_winws_exe(self) -> str:
        """Возвращает правильный путь к winws exe в зависимости от launch_method"""
        from config.config import get_winws_exe_for_method
        # Используем переданный launch_method так как он известен при создании worker'а
        return get_winws_exe_for_method(self.launch_method)

    def run(self):
        try:
            self.progress.emit("Подготовка к запуску...")

            from utils.process_killer import kill_winws_force
            kill_winws_force()

            # Pre-calc preset start parameters (used for safe preflight validation).
            skip_stop = False
            mode_param = self.selected_mode
            preset_path = ""
            is_preset_file = False
            try:
                if (
                    isinstance(mode_param, dict)
                    and mode_param.get("is_preset_file")
                    and self.launch_method in ("direct_zapret2", "direct_zapret2_orchestra", "direct_zapret1")
                ):
                    is_preset_file = True
                    preset_path = (mode_param.get("preset_path") or "").strip()
            except Exception:
                is_preset_file = False
                preset_path = ""

            # Проверяем, не запущен ли уже процесс
            process_running = self.dpi_starter.check_process_running_wmi(silent=True)
            if process_running:
                # direct_zapret2: если запущен ТОТ ЖЕ generated launch config (@file),
                # не останавливаем и не перезапускаем — просто "подключаемся".
                try:
                    if (
                        self.launch_method in ("direct_zapret2", "direct_zapret2_orchestra")
                        and is_preset_file
                        and preset_path
                    ):
                        from launcher_common import get_strategy_runner

                        runner = get_strategy_runner(self._get_winws_exe())
                        if hasattr(runner, "find_running_preset_pid"):
                            pid = runner.find_running_preset_pid(preset_path)
                            if pid:
                                log(
                                    f"Preset уже запущен (PID: {pid}), пропускаем остановку",
                                    "INFO",
                                )
                                skip_stop = True
                except Exception:
                    pass

            # ✅ Preflight validation: if preset references missing files,
            # do NOT stop an already running process.
            if is_preset_file and preset_path and (not skip_stop):
                try:
                    from launcher_common import get_strategy_runner

                    runner = get_strategy_runner(self._get_winws_exe())
                    if hasattr(runner, "validate_preset_file"):
                        ok, report = runner.validate_preset_file(preset_path)
                        if not ok:
                            # Log detailed report (first line as ERROR, rest as INFO)
                            lines = (report or "").splitlines()
                            if lines:
                                log(lines[0], "❌ ERROR")
                                for extra in lines[1:]:
                                    if extra.strip():
                                        log(extra, "INFO")
                                short = lines[0].strip()
                            else:
                                short = "Некорректный preset файл"

                            self._last_error_message = short
                            self.progress.emit(short)
                            self.finished.emit(False, short)
                            return
                except Exception:
                    pass

            if process_running and (not skip_stop):
                self.progress.emit("Останавливаем предыдущий процесс...")

                # Останавливаем через соответствующий метод
                if self.launch_method in ("direct_zapret2", "direct_zapret2_orchestra", "direct_zapret1"):
                    from launcher_common import get_strategy_runner

                    runner = get_strategy_runner(self._get_winws_exe())
                    runner.stop()
                else:
                    from dpi.stop import stop_dpi

                    stop_dpi(self.app_instance)

                # Ждём пока процесс действительно остановится (до 5 секунд)
                max_wait = 10
                for attempt in range(max_wait):
                    time.sleep(0.5)
                    if not self.dpi_starter.check_process_running_wmi(silent=True):
                        log(f"✅ Предыдущий процесс остановлен (попытка {attempt + 1})", "DEBUG")
                        break
                else:
                    log("⚠️ Процесс не остановился за 5 секунд, принудительное завершение...", "WARNING")
                    import subprocess

                    try:
                        subprocess.run(['taskkill', '/F', '/IM', 'winws.exe'],
                                       capture_output=True, timeout=3)
                        subprocess.run(['taskkill', '/F', '/IM', 'winws2.exe'],
                                       capture_output=True, timeout=3)
                        time.sleep(1)
                    except Exception as e:
                        log(f"Ошибка taskkill: {e}", "DEBUG")

                # Дополнительная пауза для освобождения WinDivert
                time.sleep(0.5)

            self.progress.emit("Запуск DPI...")
            
            # Выбираем метод запуска
            if self.launch_method == "orchestra":
                success = self._start_orchestra()
            elif self.launch_method in ("direct_zapret2", "direct_zapret2_orchestra", "direct_zapret1"):
                # direct_zapret2_orchestra работает так же как direct, но с другим набором стратегий
                # direct_zapret1 работает так же как direct, но использует winws.exe и tcp_zapret1.json
                success = self._start_direct()
            else:
                log(f"Неизвестный метод запуска: {self.launch_method}", "❌ ERROR")
                success = False
            
            if success:
                self.progress.emit("DPI успешно запущен")
                self.finished.emit(True, "")
            else:
                # В некоторых ситуациях старт "не был даже начат" (например, args пустые).
                # Тогда нельзя эмитить success=True, иначе дальше появится ложная ошибка
                # "процесс не найден после старта".
                fatal_reason = ""
                try:
                    mode_param = self.selected_mode
                    if isinstance(mode_param, dict) and self.launch_method in ("direct_zapret2", "direct_zapret2_orchestra", "direct_zapret1"):
                        if mode_param.get("is_preset_file"):
                            preset_path = (mode_param.get("preset_path") or "").strip()
                            if not preset_path:
                                fatal_reason = "❌ Ошибка: не указан путь к preset файлу"
                        elif mode_param.get("is_combined"):
                            args_str = (mode_param.get("args") or "").strip()
                            if not args_str:
                                fatal_reason = "⚠️ Выберите хотя бы одну категорию для запуска"
                            else:
                                if self.launch_method == "direct_zapret1":
                                    has_filters = any(f in args_str for f in ["--wf-tcp=", "--wf-udp="])
                                else:
                                    has_filters = any(f in args_str for f in ["--wf-tcp-out", "--wf-udp-out", "--wf-raw-part"])
                                if not has_filters:
                                    fatal_reason = "⚠️ Выберите хотя бы одну категорию для запуска"
                except Exception:
                    fatal_reason = ""

                error_msg = fatal_reason or (self._last_error_message or "Не удалось запустить DPI. Проверьте логи")
                self.progress.emit(error_msg)
                self.finished.emit(False, error_msg)
                
        except Exception as e:
            # Диагностируем ошибку и выводим понятное сообщение
            exe_path = getattr(self.dpi_starter, 'winws_exe', None)
            diagnosis = diagnose_startup_error(e, exe_path)
            for line in diagnosis.split('\n'):
                log(line, "❌ ERROR")
            self.finished.emit(False, diagnosis.split('\n')[0])  # Первая строка как краткое сообщение

    def _start_direct(self):
        """Запуск через прямой метод (StrategyRunner)"""
        try:
            from launcher_common import get_strategy_runner

            # Получаем runner
            runner = get_strategy_runner(self._get_winws_exe())

            mode_param = self.selected_mode

            # ✅ НОВЫЙ РЕЖИМ: Запуск из готового preset файла (без реестра)
            if isinstance(mode_param, dict) and mode_param.get('is_preset_file'):
                preset_path = mode_param.get('preset_path', '')
                strategy_name = mode_param.get('name', 'Пресет')

                log(f"Запуск из preset файла: {preset_path}", "INFO")

                if not preset_path:
                    log("Путь к preset файлу не указан", "❌ ERROR")
                    self._last_error_message = "Не указан путь к preset файлу"
                    self.progress.emit("❌ Ошибка: не указан путь к preset файлу")
                    return False

                import os
                if not os.path.exists(preset_path):
                    try:
                        from core.services import get_direct_flow_coordinator

                        regenerated_path = get_direct_flow_coordinator().ensure_runtime(self.launch_method)
                        if regenerated_path.exists():
                            preset_path = str(regenerated_path)
                            log(f"Auto-regenerated missing launch config: {preset_path}", "INFO")
                    except Exception as e:
                        log(f"Failed to auto-regenerate launch config: {e}", "WARNING")

                if not os.path.exists(preset_path):
                    log(f"Preset файл не найден: {preset_path}", "❌ ERROR")
                    self._last_error_message = f"Preset файл не найден: {preset_path}"
                    self.progress.emit("❌ Preset файл не найден")
                    return False

                # Запускаем напрямую через @file (hot-reload будет работать!)
                success = runner.start_from_preset_file(preset_path, strategy_name)

                if success:
                    log(f"Пресет '{strategy_name}' успешно запущен", "✅ SUCCESS")
                    return True
                else:
                    details = ""
                    try:
                        details = str(getattr(runner, "last_error", "") or "").strip()
                    except Exception:
                        details = ""
                    short = (details.splitlines()[0].strip() if details else "")
                    if short:
                        log(f"Не удалось запустить пресет: {short}", "❌ ERROR")
                        self._last_error_message = short
                        self.progress.emit(f"❌ {short}")
                    else:
                        log("Не удалось запустить пресет", "❌ ERROR")
                        self._last_error_message = "Не удалось запустить пресет (см. логи)"
                        self.progress.emit("❌ Не удалось запустить пресет. Проверьте логи")
                    return False

            # Обработка комбинированных стратегий
            elif isinstance(mode_param, dict) and mode_param.get('is_combined'):
                if self.launch_method == "direct_zapret2_orchestra":
                    log("Комбинированный запуск для direct_zapret2_orchestra отключён: используйте preset файл", "❌ ERROR")
                    self._last_error_message = "Режим orchestra запускается только через preset файл"
                    self.progress.emit("❌ Режим orchestra запускается только через preset файл")
                    return False

                strategy_name = mode_param.get('name', 'Комбинированная стратегия')
                args_str = mode_param.get('args', '')
                
                log(f"Запуск комбинированной стратегии: {strategy_name}", "INFO")
                
                if not args_str:
                    log("Отсутствуют аргументы для комбинированной стратегии", "❌ ERROR")
                    self._last_error_message = "Не заданы аргументы стратегии"
                    self.progress.emit("❌ Ошибка: не заданы аргументы стратегии")
                    return False
                
                # ✅ Проверка наличия WinDivert фильтров (без них winws не запустится)
                if self.launch_method == "direct_zapret1":
                    # Zapret 1 (winws.exe) использует синтаксис --wf-tcp= / --wf-udp=
                    has_filters = any(f in args_str for f in ['--wf-tcp=', '--wf-udp='])
                else:
                    # Zapret 2 (winws2.exe) использует --wf-tcp-out= / --wf-udp-out= / --wf-raw-part=
                    has_filters = any(f in args_str for f in ['--wf-tcp-out', '--wf-udp-out', '--wf-raw-part'])
                if not has_filters:
                    if self.launch_method == "direct_zapret1":
                        log("Нет активных WinDivert фильтров (--wf-tcp=, --wf-udp=)", "❌ ERROR")
                    else:
                        log("Нет активных WinDivert фильтров (--wf-tcp-out, --wf-udp-out, --wf-raw-part)", "❌ ERROR")
                    self.progress.emit("⚠️ Выберите хотя бы одну категорию для запуска")
                    self._last_error_message = "Выберите хотя бы одну категорию для запуска"
                    return False
                
                # Парсим аргументы (posix=False для Windows чтобы сохранить бэкслеши в путях)
                import shlex
                try:
                    custom_args = shlex.split(args_str, posix=False)
                    log(f"Аргументы комбинированной стратегии ({len(custom_args)} шт.)", "DEBUG")
                    
                    # Запускаем стратегию напрямую через runner
                    # Runner теперь автоматически делает retry при ошибке WinDivert
                    success = runner.start_strategy_custom(custom_args, strategy_name)
                    
                    if success:
                        log("Комбинированная стратегия успешно запущена", "✅ SUCCESS")
                        return True
                    else:
                        # Даём понятную подсказку пользователю
                        log("Не удалось запустить комбинированную стратегию", "❌ ERROR")
                        self._last_error_message = "Не удалось запустить комбинированную стратегию (см. логи)"
                        self.progress.emit("❌ Ошибка запуска. Попробуйте перезапустить программу или ПК")
                        return False
                        
                except Exception as parse_error:
                    log(f"Ошибка парсинга аргументов: {parse_error}", "❌ ERROR")
                    self._last_error_message = "Ошибка в параметрах стратегии"
                    self.progress.emit(f"❌ Ошибка в параметрах стратегии")
                    return False
            
            # Для Direct режима поддерживаются только комбинированные стратегии
            else:
                log(f"Direct режим поддерживает только комбинированные стратегии, получен: {type(mode_param)}", "❌ ERROR")
                self._last_error_message = "Неподдерживаемый тип стратегии"
                self.progress.emit("❌ Неподдерживаемый тип стратегии")
                return False
                
        except Exception as e:
            # Диагностируем ошибку и выводим понятное сообщение
            exe_path = self._get_winws_exe() if hasattr(self.app_instance, 'dpi_starter') else None
            diagnosis = diagnose_startup_error(e, exe_path)
            for line in diagnosis.split('\n'):
                log(line, "❌ ERROR")
            self.progress.emit(diagnosis.split('\n')[0])  # Первая строка как статус
            return False

    def _start_orchestra(self):
        """Запуск через оркестратор автоматического обучения"""
        try:
            from orchestra import OrchestraRunner

            log("Запуск оркестратора...", "INFO")

            # Создаём или получаем runner
            if not hasattr(self.app_instance, 'orchestra_runner') or self.app_instance.orchestra_runner is None:
                self.app_instance.orchestra_runner = OrchestraRunner()

            runner = self.app_instance.orchestra_runner

            # Подключаем callback для логов через сигнал Qt (thread-safe)
            # emit_log() эмитит сигнал с QueuedConnection - безопасно из любого потока
            has_attr = hasattr(self.app_instance, 'orchestra_page')
            page_exists = self.app_instance.orchestra_page if has_attr else None
            if has_attr and page_exists:
                runner.set_output_callback(self.app_instance.orchestra_page.emit_log)
            else:
                log("orchestra_page не существует при старте, callback будет установлен позже", "WARNING")

            # Запускаем (prepare + start)
            attempts = 2
            for attempt in range(1, attempts + 1):
                if runner.start():
                    log("Оркестратор успешно запущен", "✅ SUCCESS")

                    # Запускаем мониторинг на странице оркестра (через main thread!)
                    # ВАЖНО: start_monitoring() запускает QTimer, который нельзя создавать из другого потока
                    if hasattr(self.app_instance, 'orchestra_page') and self.app_instance.orchestra_page:
                        QMetaObject.invokeMethod(
                            self.app_instance.orchestra_page,
                            "start_monitoring",
                            Qt.ConnectionType.QueuedConnection
                        )

                    return True

                start_reason = str(getattr(runner, 'last_start_error', '') or '').strip()
                if attempt < attempts:
                    if start_reason:
                        log(
                            f"Оркестратор не стартовал (попытка {attempt}/{attempts}): {start_reason}. Повторяем...",
                            "WARNING",
                        )
                    else:
                        log(
                            f"Оркестратор не стартовал (попытка {attempt}/{attempts}). Повторяем...",
                            "WARNING",
                        )
                    time.sleep(0.7)
                    continue

                if start_reason:
                    log(f"Не удалось запустить оркестратор: {start_reason}", "❌ ERROR")
                else:
                    log("Не удалось запустить оркестратор", "❌ ERROR")

                try:
                    exit_info = getattr(runner, 'last_exit_info', None) or {}
                    config_path = str(exit_info.get('config_path') or '').strip()
                    command = exit_info.get('command') or []
                    recent_output = exit_info.get('recent_output') or []

                    if config_path:
                        log(f"Диагностика старта: конфиг={config_path}", "INFO")
                    if command:
                        cmd_preview = " ".join(str(x) for x in command)
                        if len(cmd_preview) > 500:
                            cmd_preview = cmd_preview[:500] + " ..."
                        log(f"Диагностика старта: команда={cmd_preview}", "INFO")

                    if recent_output:
                        log("Диагностика старта: последние строки winws2:", "INFO")
                        for line in recent_output[-6:]:
                            clean = str(line or '').strip()
                            if clean:
                                if len(clean) > 300:
                                    clean = clean[:300] + " ..."
                                log(f"  {clean}", "INFO")
                except Exception:
                    pass

                return False

        except Exception as e:
            # Диагностируем ошибку и выводим понятное сообщение
            exe_path = self._get_winws_exe() if hasattr(self.app_instance, 'dpi_starter') else None
            diagnosis = diagnose_startup_error(e, exe_path)
            for line in diagnosis.split('\n'):
                log(line, "❌ ERROR")
            import traceback
            log(traceback.format_exc(), "DEBUG")
            return False


class DPIStopWorker(QObject):
    """Worker для асинхронной остановки DPI"""
    finished = pyqtSignal(bool, str)  # success, error_message
    progress = pyqtSignal(str)        # status_message

    def __init__(self, app_instance, launch_method):
        super().__init__()
        self.app_instance = app_instance
        self.launch_method = launch_method

    def _get_winws_exe(self) -> str:
        """Возвращает правильный путь к winws exe в зависимости от launch_method"""
        from config.config import get_winws_exe_for_method
        # Используем переданный launch_method так как он известен при создании worker'а
        return get_winws_exe_for_method(self.launch_method)

    def run(self):
        try:
            self.progress.emit("Остановка DPI...")
            
            # Проверяем, запущен ли процесс
            if not self.app_instance.dpi_starter.check_process_running_wmi(silent=True):
                self.progress.emit("DPI уже остановлен")
                self.finished.emit(True, "DPI уже был остановлен")
                return
            
            self.progress.emit("Завершение процессов...")
            
            # Выбираем метод остановки
            if self.launch_method == "orchestra":
                success = self._stop_orchestra()
            elif self.launch_method in ("direct_zapret2", "direct_zapret2_orchestra", "direct_zapret1"):
                success = self._stop_direct()
            else:
                # Fallback: try direct stop for any unrecognised launch method
                success = self._stop_direct()
            
            if success:
                self.progress.emit("DPI успешно остановлен")
                self.finished.emit(True, "")
            else:
                self.finished.emit(False, "Не удалось полностью остановить процесс")
                
        except Exception as e:
            error_msg = f"Ошибка остановки DPI: {str(e)}"
            log(error_msg, "❌ ERROR")
            self.finished.emit(False, error_msg)
    
    def _stop_direct(self):
        """Остановка через новый метод"""
        try:
            from launcher_common import get_strategy_runner
            from utils.process_killer import kill_winws_all

            runner = get_strategy_runner(self._get_winws_exe())
            success = runner.stop()
            
            # Дополнительно убиваем все процессы через Win API
            if not success or self.app_instance.dpi_starter.check_process_running_wmi(silent=True):
                kill_winws_all()
            
            # Проверяем результат
            return not self.app_instance.dpi_starter.check_process_running_wmi(silent=True)
            
        except Exception as e:
            log(f"Ошибка прямой остановки: {e}", "❌ ERROR")
            return False
    
    def _stop_orchestra(self):
        """Остановка оркестратора"""
        try:
            from utils.process_killer import kill_winws_all

            # Останавливаем через runner если есть
            if hasattr(self.app_instance, 'orchestra_runner') and self.app_instance.orchestra_runner:
                self.app_instance.orchestra_runner.stop()

                # Останавливаем мониторинг на странице оркестра
                if hasattr(self.app_instance, 'orchestra_page'):
                    self.app_instance.orchestra_page.stop_monitoring()

            # Дополнительно убиваем все процессы через Win API
            if self.app_instance.dpi_starter.check_process_running_wmi(silent=True):
                kill_winws_all()

            # Проверяем результат
            return not self.app_instance.dpi_starter.check_process_running_wmi(silent=True)

        except Exception as e:
            log(f"Ошибка остановки оркестратора: {e}", "❌ ERROR")
            return False


class StopAndExitWorker(QObject):
    """Worker для остановки DPI и выхода из программы"""
    finished = pyqtSignal()
    progress = pyqtSignal(str)

    def __init__(self, app_instance):
        super().__init__()
        self.app_instance = app_instance
        self.launch_method = get_strategy_launch_method()

    def _get_winws_exe(self) -> str:
        """Возвращает правильный путь к winws exe в зависимости от launch_method"""
        from config.config import get_winws_exe_for_method
        # Используем launch_method определённый в __init__
        return get_winws_exe_for_method(self.launch_method)

    def run(self):
        try:
            self.progress.emit("Остановка DPI перед закрытием...")

            # Выбираем метод остановки
            if self.launch_method == "orchestra":
                # Останавливаем оркестратор
                if hasattr(self.app_instance, 'orchestra_runner') and self.app_instance.orchestra_runner:
                    self.app_instance.orchestra_runner.stop()
                # Дополнительная очистка
                from utils.process_killer import kill_winws_all
                kill_winws_all()
            elif self.launch_method in ("direct_zapret2", "direct_zapret2_orchestra", "direct_zapret1"):
                from launcher_common import get_strategy_runner
                runner = get_strategy_runner(self._get_winws_exe())
                runner.stop()

                # Дополнительная очистка
                from dpi.stop import stop_dpi_direct
                stop_dpi_direct(self.app_instance)
            else:
                from dpi.stop import stop_dpi
                stop_dpi(self.app_instance)

            self.progress.emit("Завершение работы...")
            self.finished.emit()
            
        except Exception as e:
            log(f"Ошибка при остановке перед закрытием: {e}", "❌ ERROR")
            self.finished.emit()


class DPIController:
    """Основной контроллер для управления DPI"""
    
    def __init__(self, app_instance):
        self.app = app_instance
        self._dpi_start_thread = None
        self._dpi_stop_thread = None
        self._stop_exit_thread = None
        # Generation token for async start verification.
        # Prevents stale QTimer checks from previous start attempts.
        self._dpi_start_verify_generation = 0

    def _show_launch_error_top(self, message: str) -> None:
        """Показывает человеко-понятную ошибку запуска через верхний InfoBar."""
        text = str(message or "").strip()
        if not text:
            return
        try:
            while text.startswith(("❌", "⚠️", "⚠")):
                text = text[1:].strip()
        except Exception:
            pass
        if not text:
            text = "Не удалось запустить DPI"

        try:
            if hasattr(self.app, "show_dpi_launch_error"):
                self.app.show_dpi_launch_error(text)
        except Exception as e:
            log(f"Не удалось показать InfoBar ошибки запуска: {e}", "DEBUG")

    def start_dpi_async(self, selected_mode=None, launch_method=None):
        """Асинхронно запускает DPI без блокировки UI

        Args:
            selected_mode: Стратегия для запуска
            launch_method: Метод запуска ("direct_zapret2", "direct_zapret1", "orchestra" и т.д.). Если None - читается из реестра
        """
        # Проверка на уже запущенный поток
        try:
            if self._dpi_start_thread and self._dpi_start_thread.isRunning():
                log("Запуск DPI уже выполняется", "DEBUG")
                return
        except RuntimeError:
            self._dpi_start_thread = None

        # Проверка конфликтующих процессов (Process Hacker, Process Explorer и т.д.)
        conflicting = check_conflicting_processes()
        if conflicting:
            report = get_conflicting_processes_report()
            log(report, "WARNING")

            names = ", ".join(c['name'] for c in conflicting)
            from PyQt6.QtWidgets import QMessageBox
            msg = QMessageBox(self.app)
            msg.setWindowTitle("Обнаружены конфликтующие программы")
            msg.setIcon(QMessageBox.Icon.Warning)
            msg.setText(
                f"Обнаружены программы, которые блокируют WinDivert:\n\n"
                f"{names}\n\n"
                f"Эти программы перехватывают системные вызовы и не дают "
                f"WinDivert драйверу запуститься."
            )
            msg.setInformativeText("Закрыть их автоматически и продолжить запуск?")

            btn_kill = msg.addButton("Закрыть и продолжить", QMessageBox.ButtonRole.AcceptRole)
            btn_ignore = msg.addButton("Продолжить без закрытия", QMessageBox.ButtonRole.DestructiveRole)
            btn_cancel = msg.addButton("Отмена", QMessageBox.ButtonRole.RejectRole)
            msg.setDefaultButton(btn_kill)

            msg.exec()
            clicked = msg.clickedButton()

            if clicked == btn_cancel:
                log("Запуск DPI отменён пользователем из-за конфликтующих процессов", "INFO")
                return

            if clicked == btn_kill:
                log("Пользователь выбрал закрыть конфликтующие процессы", "INFO")
                killed = try_kill_conflicting_processes(auto_kill=True)
                if killed:
                    log("Конфликтующие процессы закрыты, ожидание 1с...", "INFO")
                    time.sleep(1)
                else:
                    log("Не удалось закрыть все конфликтующие процессы", "WARNING")
                    retry_msg = QMessageBox.warning(
                        self.app,
                        "Не удалось закрыть процессы",
                        "Некоторые конфликтующие процессы не удалось закрыть.\n"
                        "Запуск DPI может завершиться ошибкой.\n\n"
                        "Продолжить запуск?",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                        QMessageBox.StandardButton.No
                    )
                    if retry_msg == QMessageBox.StandardButton.No:
                        log("Запуск DPI отменён после неудачного закрытия процессов", "INFO")
                        return

            # btn_ignore — продолжаем без закрытия, логируем предупреждение
            if clicked == btn_ignore:
                log("Пользователь продолжил запуск несмотря на конфликтующие процессы", "WARNING")

        # Invalidate any pending verification loop from older starts.
        self._dpi_start_verify_generation += 1

        # Проверяем выбранный метод запуска (явно переданный или из реестра)
        if launch_method is None:
            launch_method = get_strategy_launch_method()
        log(f"Используется метод запуска: {launch_method}", "INFO")

        # Для оркестра не нужно выбирать стратегию - он работает автоматически
        if launch_method == "orchestra":
            selected_mode = {'is_orchestra': True, 'name': 'Оркестр'}

        # ✅ ИСПРАВЛЕНИЕ: Если стратегия не выбрана - используем готовый preset файл
        elif selected_mode is None or selected_mode == 'default':
            if launch_method in ("direct_zapret2", "direct_zapret2_orchestra", "direct_zapret1"):
                # Для Direct режимов используем готовый preset файл.
                # direct_zapret2/direct_zapret1: generated launch config from the selected preset
                # direct_zapret2_orchestra: legacy orchestra-specific flow
                if launch_method == "direct_zapret2_orchestra":
                    from preset_orchestra_zapret2 import (
                        ensure_default_preset_exists,
                        get_active_preset_path,
                        get_active_preset_name,
                    )

                    ensure_default_preset_exists()
                    preset_path = get_active_preset_path()
                    preset_name = get_active_preset_name() or "Default"
                else:
                    try:
                        from core.services import get_direct_flow_coordinator

                        profile = get_direct_flow_coordinator().ensure_launch_profile(
                            launch_method,
                            require_filters=True,
                        )
                        selected_mode = profile.to_selected_mode()
                        log(f"Используется generated launch config: {profile.launch_config_path}", "INFO")
                    except Exception as e:
                        log(f"Ошибка подготовки direct запуска: {e}", "❌ ERROR")
                        self.app.set_status(f"❌ {e}")
                        self._show_launch_error_top(str(e))
                        if hasattr(self.app, 'ui_manager'):
                            self.app.ui_manager.update_ui_state(running=False)
                        return

                    preset_path = Path(str(selected_mode["preset_path"]))
                    preset_name = str(profile.preset_name or "Default")

                if not preset_path.exists():
                    log(f"Preset файл не найден: {preset_path}", "❌ ERROR")
                    self.app.set_status("❌ Preset файл не найден. Создайте пресет в настройках")
                    self._show_launch_error_top("Preset файл не найден. Создайте пресет в настройках")
                    if hasattr(self.app, 'ui_manager'):
                        self.app.ui_manager.update_ui_state(running=False)
                    return

                # Проверяем что файл не пустой
                try:
                    content = preset_path.read_text(encoding='utf-8').strip()

                    # 🧹 Sanitize placeholder categories that reference non-existent stub lists.
                    # If preset contains `lists/unknown.txt` or `lists/ipset-unknown.txt`,
                    # drop that whole category to prevent winws2 from exiting immediately.
                    if launch_method in ("direct_zapret2", "direct_zapret2_orchestra"):
                        content_l = content.lower()
                        if ("unknown.txt" in content_l) or ("ipset-unknown.txt" in content_l):
                            try:
                                if launch_method == "direct_zapret2_orchestra":
                                    from preset_orchestra_zapret2.txt_preset_parser import (
                                        parse_preset_file,
                                        generate_preset_file,
                                    )
                                else:
                                    from preset_zapret2.txt_preset_parser import (
                                        parse_preset_file,
                                        generate_preset_file,
                                    )

                                data = parse_preset_file(preset_path)
                                if generate_preset_file(data, preset_path, atomic=True):
                                    content = preset_path.read_text(encoding="utf-8").strip()
                            except Exception as e:
                                log(f"Ошибка очистки preset файла от unknown.txt: {e}", "DEBUG")
                    # Проверяем наличие WinDivert фильтров
                    if launch_method == "direct_zapret1":
                        # Zapret 1 (winws.exe) использует синтаксис --wf-tcp= / --wf-udp=
                        has_filters = any(f in content for f in ['--wf-tcp=', '--wf-udp='])
                    else:
                        # Zapret 2 (winws2.exe) использует --wf-tcp-out= / --wf-udp-out= / --wf-raw-part=
                        has_filters = any(f in content for f in ['--wf-tcp-out', '--wf-udp-out', '--wf-raw-part'])
                    if not has_filters:
                        log("Preset файл не содержит активных фильтров", "WARNING")
                        self.app.set_status("⚠️ Выберите хотя бы одну категорию для запуска")
                        self._show_launch_error_top("Выберите хотя бы одну категорию для запуска")
                        if hasattr(self.app, 'ui_manager'):
                            self.app.ui_manager.update_ui_state(running=False)
                        return
                except Exception as e:
                    log(f"Ошибка чтения preset файла: {e}", "❌ ERROR")
                    self.app.set_status(f"❌ Ошибка чтения preset: {e}")
                    self._show_launch_error_top(f"Ошибка чтения preset: {e}")
                    if hasattr(self.app, 'ui_manager'):
                        self.app.ui_manager.update_ui_state(running=False)
                    return

                if launch_method == "direct_zapret2_orchestra":
                    selected_mode = {
                        'is_preset_file': True,
                        'name': f"Пресет оркестра: {preset_name}",
                        'preset_path': str(preset_path)
                    }
                else:
                    selected_mode = {
                        'is_preset_file': True,
                        'name': f"Пресет: {preset_name}",
                        'preset_path': str(preset_path)
                    }
                log(f"Используется launch config: {preset_path}", "INFO")
                
            else:
                log(f"Неизвестный метод запуска '{launch_method}': стратегия не выбрана", "❌ ERROR")
                self.app.set_status("❌ Неизвестный метод запуска")
                self._show_launch_error_top("Неизвестный метод запуска")
                return
        
        # ✅ ОБРАБОТКА всех типов стратегий (остальной код без изменений)
        mode_name = "Неизвестная стратегия"
        
        if isinstance(selected_mode, dict) and selected_mode.get('is_combined'):
            # Комбинированная стратегия
            mode_name = selected_mode.get('name', 'Комбинированная стратегия')
            log(f"Обработка комбинированной стратегии: {mode_name}", "DEBUG")

            # Сохраняем выборы в реестр для будущего использования
            if 'selections' in selected_mode and launch_method != "direct_zapret2_orchestra":
                from strategy_menu import set_direct_strategy_selections
                selections = selected_mode['selections']
                set_direct_strategy_selections(selections)
            
        elif isinstance(selected_mode, tuple) and len(selected_mode) == 2:
            # Встроенная стратегия (ID, название)
            strategy_id, strategy_name = selected_mode
            mode_name = strategy_name
            log(f"Обработка встроенной стратегии: {strategy_name} (ID: {strategy_id})", "DEBUG")
            
        elif isinstance(selected_mode, dict):
            # Preset file strategy (is_preset_file) или другой dict
            mode_name = selected_mode.get('name', str(selected_mode))
            log(f"Обработка стратегии: {mode_name}", "DEBUG")

        elif isinstance(selected_mode, str):
            # Строковое название стратегии
            mode_name = selected_mode
            log(f"Обработка строковой стратегии: {mode_name}", "DEBUG")
        
        # Показываем состояние запуска
        if launch_method == "orchestra":
            method_name = "оркестр"
        elif launch_method == "direct_zapret2":
            method_name = "прямой"
        elif launch_method == "direct_zapret2_orchestra":
            method_name = "оркестратор Z2"
        elif launch_method == "direct_zapret1":
            method_name = "прямой Z1"
        else:
            method_name = "классический"
        self.app.set_status(f"🚀 Запуск DPI ({method_name}): {mode_name}")
        
        # ✅ Показываем спиннер загрузки
        if hasattr(self.app, 'main_window') and hasattr(self.app.main_window, 'strategies_page'):
            self.app.main_window.strategies_page.show_loading()
        
        # ✅ Показываем индикатор загрузки на страницах
        if hasattr(self.app, 'control_page'):
            self.app.control_page.set_loading(True, "Запуск Zapret...")
        if hasattr(self.app, 'zapret2_direct_control_page'):
            try:
                self.app.zapret2_direct_control_page.set_loading(True, "Запуск Zapret...")
            except Exception:
                pass
        if hasattr(self.app, 'orchestra_zapret2_control_page'):
            try:
                self.app.orchestra_zapret2_control_page.set_loading(True, "Запуск Zapret...")
            except Exception:
                pass
        if hasattr(self.app, 'home_page'):
            self.app.home_page.set_loading(True, "Запуск Zapret...")
        
        # Блокируем кнопки во время операции
        if hasattr(self.app, 'start_btn'):
            self.app.start_btn.setEnabled(False)
        if hasattr(self.app, 'stop_btn'):
            self.app.stop_btn.setEnabled(False)
        
        # Создаем поток и worker
        self._dpi_start_thread = QThread()
        self._dpi_start_worker = DPIStartWorker(self.app, selected_mode, launch_method)
        self._dpi_start_worker.moveToThread(self._dpi_start_thread)
        
        # Подключение сигналов
        self._dpi_start_thread.started.connect(self._dpi_start_worker.run)
        self._dpi_start_worker.progress.connect(self.app.set_status)
        self._dpi_start_worker.finished.connect(self._on_dpi_start_finished)
        
        # Очистка ресурсов
        def cleanup_start_thread():
            try:
                if self._dpi_start_thread:
                    self._dpi_start_thread.quit()
                    self._dpi_start_thread.wait(2000)
                    self._dpi_start_thread = None
                    
                if hasattr(self, '_dpi_start_worker'):
                    self._dpi_start_worker.deleteLater()
                    self._dpi_start_worker = None
            except Exception as e:
                log(f"Ошибка при очистке потока запуска: {e}", "❌ ERROR")
        
        self._dpi_start_worker.finished.connect(cleanup_start_thread)
        
        # Запускаем поток
        self._dpi_start_thread.start()
        
        log(f"Запуск асинхронного старта DPI: {mode_name} (метод: {method_name})", "INFO")    

    def stop_dpi_async(self):
        """Асинхронно останавливает DPI без блокировки UI"""
        # Проверка на уже запущенный поток
        try:
            if self._dpi_stop_thread and self._dpi_stop_thread.isRunning():
                log("Остановка DPI уже выполняется", "DEBUG")
                return
        except RuntimeError:
            self._dpi_stop_thread = None
        
        launch_method = get_strategy_launch_method()

        # Показываем состояние остановки
        if launch_method == "orchestra":
            method_name = "оркестр"
        elif launch_method == "direct_zapret2":
            method_name = "прямой"
        elif launch_method == "direct_zapret2_orchestra":
            method_name = "оркестратор Z2"
        elif launch_method == "direct_zapret1":
            method_name = "прямой Z1"
        else:
            method_name = "классический"
        self.app.set_status(f"🛑 Остановка DPI ({method_name})...")
        
        # ✅ Показываем спиннер загрузки
        if hasattr(self.app, 'main_window') and hasattr(self.app.main_window, 'strategies_page'):
            self.app.main_window.strategies_page.show_loading()
        
        # ✅ Показываем индикатор загрузки на страницах
        if hasattr(self.app, 'control_page'):
            self.app.control_page.set_loading(True, "Остановка Zapret...")
        if hasattr(self.app, 'zapret2_direct_control_page'):
            try:
                self.app.zapret2_direct_control_page.set_loading(True, "Остановка Zapret...")
            except Exception:
                pass
        if hasattr(self.app, 'orchestra_zapret2_control_page'):
            try:
                self.app.orchestra_zapret2_control_page.set_loading(True, "Остановка Zapret...")
            except Exception:
                pass
        if hasattr(self.app, 'home_page'):
            self.app.home_page.set_loading(True, "Остановка Zapret...")
        
        # Блокируем кнопки во время операции
        if hasattr(self.app, 'start_btn'):
            self.app.start_btn.setEnabled(False)
        if hasattr(self.app, 'stop_btn'):
            self.app.stop_btn.setEnabled(False)
        
        # Создаем поток и worker
        self._dpi_stop_thread = QThread()
        self._dpi_stop_worker = DPIStopWorker(self.app, launch_method)
        self._dpi_stop_worker.moveToThread(self._dpi_stop_thread)
        
        # Подключение сигналов
        self._dpi_stop_thread.started.connect(self._dpi_stop_worker.run)
        self._dpi_stop_worker.progress.connect(self.app.set_status)
        self._dpi_stop_worker.finished.connect(self._on_dpi_stop_finished)
        
        # Очистка ресурсов
        def cleanup_stop_thread():
            try:
                if self._dpi_stop_thread:
                    self._dpi_stop_thread.quit()
                    self._dpi_stop_thread.wait(2000)
                    self._dpi_stop_thread = None
                    
                if hasattr(self, '_dpi_stop_worker'):
                    self._dpi_stop_worker.deleteLater()
                    self._dpi_stop_worker = None
            except Exception as e:
                log(f"Ошибка при очистке потока остановки: {e}", "❌ ERROR")
        
        self._dpi_stop_worker.finished.connect(cleanup_stop_thread)
        
        # Устанавливаем флаг ручной остановки
        self.app.manually_stopped = True
        
        # Запускаем поток
        self._dpi_stop_thread.start()
        
        log(f"Запуск асинхронной остановки DPI (метод: {method_name})", "INFO")
    
    def stop_and_exit_async(self):
        """Асинхронно останавливает DPI и закрывает программу"""
        self.app._is_exiting = True
        
        # Создаем worker и поток
        self._stop_exit_thread = QThread()
        self._stop_exit_worker = StopAndExitWorker(self.app)
        self._stop_exit_worker.moveToThread(self._stop_exit_thread)
        
        # Подключаем сигналы
        self._stop_exit_thread.started.connect(self._stop_exit_worker.run)
        self._stop_exit_worker.progress.connect(self.app.set_status)
        self._stop_exit_worker.finished.connect(self._on_stop_and_exit_finished)
        self._stop_exit_worker.finished.connect(self._stop_exit_thread.quit)
        self._stop_exit_worker.finished.connect(self._stop_exit_worker.deleteLater)
        self._stop_exit_thread.finished.connect(self._stop_exit_thread.deleteLater)
        
        # Запускаем поток
        self._stop_exit_thread.start()
    
    def _on_dpi_start_finished(self, success, error_message):
        """Обрабатывает завершение асинхронного запуска DPI"""
        try:
            # Восстанавливаем кнопки
            if hasattr(self.app, 'start_btn'):
                self.app.start_btn.setEnabled(True)
            if hasattr(self.app, 'stop_btn'):
                self.app.stop_btn.setEnabled(True)
            
            # ✅ Скрываем индикатор загрузки на страницах
            if hasattr(self.app, 'control_page'):
                self.app.control_page.set_loading(False)
            if hasattr(self.app, 'zapret2_direct_control_page'):
                try:
                    self.app.zapret2_direct_control_page.set_loading(False)
                except Exception:
                    pass
            if hasattr(self.app, 'orchestra_zapret2_control_page'):
                try:
                    self.app.orchestra_zapret2_control_page.set_loading(False)
                except Exception:
                    pass
            if hasattr(self.app, 'home_page'):
                self.app.home_page.set_loading(False)

            # ✅ Показываем галочку успеха (скрываем спиннер)
            if hasattr(self.app, 'main_window') and hasattr(self.app.main_window, 'strategies_page'):
                self.app.main_window.strategies_page.show_success()
            
            if success:
                # ✅ РЕАЛЬНАЯ ПРОВЕРКА: процесс действительно запущен?
                # Используем QTimer вместо time.sleep чтобы не блокировать main thread.
                self._dpi_start_verify_retry = 0
                verify_gen = self._dpi_start_verify_generation
                self._verify_dpi_process_running(verify_gen)
                    
            else:
                log(f"Ошибка асинхронного запуска DPI: {error_message}", "❌ ERROR")
                self.app.set_status(f"❌ Ошибка запуска: {error_message}")
                self._show_launch_error_top(error_message)
                
                # ✅ ИСПОЛЬЗУЕМ UI MANAGER вместо app.update_ui
                if hasattr(self.app, 'ui_manager'):
                    self.app.ui_manager.update_ui_state(running=False)
                
                # ✅ ИСПОЛЬЗУЕМ PROCESS MONITOR MANAGER
                if hasattr(self.app, 'process_monitor_manager'):
                    self.app.process_monitor_manager.on_process_status_changed(False)
                
        except Exception as e:
            log(f"Ошибка при обработке результата запуска DPI: {e}", "❌ ERROR")
            self.app.set_status(f"Ошибка: {e}")
    
    def _verify_dpi_process_running(self, verify_gen=None):
        """Неблокирующая проверка запуска процесса DPI через QTimer (вместо time.sleep в main thread)."""
        from PyQt6.QtCore import QTimer

        if verify_gen is None:
            verify_gen = self._dpi_start_verify_generation

        # Ignore stale verification callbacks from older start attempts.
        if verify_gen != self._dpi_start_verify_generation:
            return

        # Startup of winws/winws2 can take noticeable time (driver init, UAC, first launch,
        # competing stop/start when user rapidly switches presets, etc.).
        # Too short window causes false negatives like:
        #   "DPI не запустился - процесс не найден после старта"
        # even though the process appears moments later (process monitor sees it).
        # 25 retries × 300ms = 7.5s — enough for first-run WinDivert driver install.
        MAX_RETRIES = 25
        RETRY_DELAY_MS = 300

        is_actually_running = self.app.dpi_starter.check_process_running_wmi(silent=True)

        if is_actually_running:
            self._on_dpi_process_confirmed(running=True, verify_gen=verify_gen)
        elif self._dpi_start_verify_retry < MAX_RETRIES:
            self._dpi_start_verify_retry += 1
            QTimer.singleShot(RETRY_DELAY_MS, lambda g=verify_gen: self._verify_dpi_process_running(g))
        else:
            self._on_dpi_process_confirmed(running=False, verify_gen=verify_gen)

    def _on_dpi_process_confirmed(self, running: bool, verify_gen=None):
        """Вызывается после подтверждения (или отказа) запуска DPI процесса."""
        if verify_gen is not None and verify_gen != self._dpi_start_verify_generation:
            return

        if running:
            log("DPI запущен асинхронно", "INFO")
            self.app.set_status("✅ DPI успешно запущен")

            # Один вызов ui_manager — process_monitor_manager подхватит через свой поток
            if hasattr(self.app, 'ui_manager'):
                self.app.ui_manager.update_ui_state(running=True)

            # Устанавливаем флаг намеренного запуска
            self.app.intentional_start = True

            # Перезапускаем Discord если нужно
            try:
                from discord.discord_restart import get_discord_restart_setting
                is_first = getattr(self.app, '_first_dpi_start', True)
                if not is_first and get_discord_restart_setting():
                    if hasattr(self.app, 'discord_manager'):
                        self.app.discord_manager.restart_discord_if_running()
                else:
                    self.app._first_dpi_start = False
            except Exception as e:
                log(f"Discord restart check error: {e}", "DEBUG")
        else:
            # Процесс не запустился или сразу упал
            log("DPI не запустился - процесс не найден после старта", "❌ ERROR")
            self.app.set_status("❌ Процесс не запустился. Проверьте логи")
            self._show_launch_error_top("Процесс не запустился. Проверьте логи")

            if hasattr(self.app, 'ui_manager'):
                self.app.ui_manager.update_ui_state(running=False)

    def _on_dpi_stop_finished(self, success, error_message):
        """Обрабатывает завершение асинхронной остановки DPI"""
        try:
            # Восстанавливаем кнопки
            if hasattr(self.app, 'start_btn'):
                self.app.start_btn.setEnabled(True)
            if hasattr(self.app, 'stop_btn'):
                self.app.stop_btn.setEnabled(True)
            
            # ✅ Скрываем индикатор загрузки на страницах
            if hasattr(self.app, 'control_page'):
                self.app.control_page.set_loading(False)
            if hasattr(self.app, 'zapret2_direct_control_page'):
                try:
                    self.app.zapret2_direct_control_page.set_loading(False)
                except Exception:
                    pass
            if hasattr(self.app, 'orchestra_zapret2_control_page'):
                try:
                    self.app.orchestra_zapret2_control_page.set_loading(False)
                except Exception:
                    pass
            if hasattr(self.app, 'home_page'):
                self.app.home_page.set_loading(False)

            # ✅ Показываем галочку (скрываем спиннер)
            if hasattr(self.app, 'main_window') and hasattr(self.app.main_window, 'strategies_page'):
                self.app.main_window.strategies_page.show_success()
            
            if success:
                # ✅ РЕАЛЬНАЯ ПРОВЕРКА: процесс действительно остановлен?
                is_still_running = self.app.dpi_starter.check_process_running_wmi(silent=True)
                
                if not is_still_running:
                    log("DPI остановлен асинхронно", "INFO")
                    if error_message:
                        self.app.set_status(f"✅ {error_message}")
                    else:
                        self.app.set_status("✅ DPI успешно остановлен")
                    
                    # ✅ ИСПОЛЬЗУЕМ UI MANAGER вместо app.update_ui
                    if hasattr(self.app, 'ui_manager'):
                        self.app.ui_manager.update_ui_state(running=False)
                    
                    # ✅ ИСПОЛЬЗУЕМ PROCESS MONITOR MANAGER
                    if hasattr(self.app, 'process_monitor_manager'):
                        self.app.process_monitor_manager.on_process_status_changed(False)
                else:
                    # Процесс всё ещё работает
                    log("DPI всё ещё работает после попытки остановки", "⚠ WARNING")
                    self.app.set_status("⚠ Процесс всё ещё работает")
                    
                    if hasattr(self.app, 'ui_manager'):
                        self.app.ui_manager.update_ui_state(running=True)
                    if hasattr(self.app, 'process_monitor_manager'):
                        self.app.process_monitor_manager.on_process_status_changed(True)
                
            else:
                log(f"Ошибка асинхронной остановки DPI: {error_message}", "❌ ERROR")
                self.app.set_status(f"❌ Ошибка остановки: {error_message}")
                
                # Проверяем реальный статус процесса
                is_running = self.app.dpi_starter.check_process_running_wmi(silent=True)
                
                # ✅ ИСПОЛЬЗУЕМ UI MANAGER вместо app.update_ui
                if hasattr(self.app, 'ui_manager'):
                    self.app.ui_manager.update_ui_state(running=is_running)
                
                # ✅ ИСПОЛЬЗУЕМ PROCESS MONITOR MANAGER
                if hasattr(self.app, 'process_monitor_manager'):
                    self.app.process_monitor_manager.on_process_status_changed(is_running)
                
        except Exception as e:
            log(f"Ошибка при обработке результата остановки DPI: {e}", "❌ ERROR")
            self.app.set_status(f"Ошибка: {e}")
    
    def _on_stop_and_exit_finished(self):
        """Завершает приложение после остановки DPI"""
        self.app.set_status("Завершение...")
        from PyQt6.QtWidgets import QApplication

        try:
            QApplication.closeAllWindows()
            QApplication.processEvents()
        except Exception:
            pass

        QApplication.quit()
    
    def cleanup_threads(self):
        """Очищает все потоки при закрытии приложения"""
        try:
            if self._dpi_start_thread and self._dpi_start_thread.isRunning():
                log("Останавливаем поток запуска DPI...", "DEBUG")
                self._dpi_start_thread.quit()
                if not self._dpi_start_thread.wait(2000):
                    log("⚠ Поток запуска DPI не завершился, принудительно завершаем", "WARNING")
                    try:
                        self._dpi_start_thread.terminate()
                        self._dpi_start_thread.wait(500)
                    except:
                        pass
            
            if self._dpi_stop_thread and self._dpi_stop_thread.isRunning():
                log("Останавливаем поток остановки DPI...", "DEBUG")
                self._dpi_stop_thread.quit()
                if not self._dpi_stop_thread.wait(2000):
                    log("⚠ Поток остановки DPI не завершился, принудительно завершаем", "WARNING")
                    try:
                        self._dpi_stop_thread.terminate()
                        self._dpi_stop_thread.wait(500)
                    except:
                        pass
            
            # Обнуляем ссылки
            self._dpi_start_thread = None
            self._dpi_stop_thread = None

        except Exception as e:
            log(f"Ошибка при очистке потоков DPI контроллера: {e}", "❌ ERROR")

    def is_running(self) -> bool:
        """
        Проверяет запущен ли DPI процесс.

        Returns:
            True если процесс запущен, False иначе
        """
        return self.app.dpi_starter.check_process_running_wmi(silent=True)

    def restart_dpi_async(self):
        """
        Перезапускает DPI асинхронно (останавливает и снова запускает).

        Если DPI не запущен - просто запускает.
        Если запущен - останавливает, ждёт 500ms, затем запускает.
        """
        from PyQt6.QtCore import QTimer

        log("Перезапуск DPI...", "INFO")

        if self.is_running():
            # DPI запущен - останавливаем, потом запускаем через таймер
            log("DPI запущен, останавливаем перед перезапуском", "DEBUG")
            self.stop_dpi_async()

            # Запускаем снова через 500ms (чтобы остановка успела завершиться)
            QTimer.singleShot(500, lambda: self.start_dpi_async())
        else:
            # DPI не запущен - просто запускаем
            log("DPI не запущен, запускаем", "DEBUG")
            self.start_dpi_async()
