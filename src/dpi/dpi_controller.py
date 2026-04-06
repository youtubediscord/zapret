"""
Контроллер для управления DPI - содержит всю логику запуска и остановки
"""

from dataclasses import dataclass
import os
import time

from PyQt6.QtCore import QThread, QObject, pyqtSignal, QMetaObject, Qt, QTimer
from pathlib import Path
from strategy_menu import get_strategy_launch_method
from app_notifications import advisory_notification, notification_action
from log import log
from dpi.process_health_check import (
    diagnose_startup_error,
    check_conflicting_processes,
    try_kill_conflicting_processes,
    get_conflicting_processes_report,
)


@dataclass(frozen=True)
class PreparedDpiStartRequest:
    launch_method: str
    selected_mode: object
    mode_name: str
    method_name: str

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

    def _extract_preset_launch_input(self) -> tuple[bool, str]:
        mode_param = self.selected_mode
        try:
            if (
                isinstance(mode_param, dict)
                and mode_param.get("is_preset_file")
                and self.launch_method in ("direct_zapret2", "direct_zapret2_orchestra", "direct_zapret1")
            ):
                return True, str(mode_param.get("preset_path") or "").strip()
        except Exception:
            pass
        return False, ""

    def _can_reuse_running_process(self, *, is_preset_file: bool, preset_path: str) -> bool:
        if not is_preset_file or not preset_path:
            return False
        if self.launch_method not in ("direct_zapret2", "direct_zapret2_orchestra"):
            return False
        try:
            from launcher_common import get_strategy_runner

            runner = get_strategy_runner(self._get_winws_exe())
            if hasattr(runner, "find_running_preset_pid"):
                pid = runner.find_running_preset_pid(preset_path)
                if pid:
                    log(
                        f"Preset уже запущен (PID: {pid}), пропускаем остановку",
                        "INFO",
                    )
                    return True
        except Exception:
            pass
        return False

    def _validate_preset_before_stop(self, *, is_preset_file: bool, preset_path: str, skip_stop: bool) -> bool:
        if not is_preset_file or not preset_path or skip_stop:
            return True
        try:
            from launcher_common import get_strategy_runner

            runner = get_strategy_runner(self._get_winws_exe())
            if hasattr(runner, "validate_preset_file"):
                ok, report = runner.validate_preset_file(preset_path)
                if ok:
                    return True

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
                return False
        except Exception:
            pass
        return True

    def _stop_previous_process_if_needed(self, *, skip_stop: bool) -> None:
        process_running = self.dpi_starter.check_process_running_wmi(silent=True)
        if (not process_running) or skip_stop:
            return

        self.progress.emit("Останавливаем предыдущий процесс...")

        if self.launch_method in ("direct_zapret2", "direct_zapret2_orchestra", "direct_zapret1"):
            from launcher_common import get_strategy_runner

            runner = get_strategy_runner(self._get_winws_exe())
            runner.stop()
        else:
            from dpi.stop import stop_dpi

            stop_dpi(self.app_instance)

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
                subprocess.run(['taskkill', '/F', '/IM', 'winws.exe'], capture_output=True, timeout=3)
                subprocess.run(['taskkill', '/F', '/IM', 'winws2.exe'], capture_output=True, timeout=3)
                time.sleep(1)
            except Exception as e:
                log(f"Ошибка taskkill: {e}", "DEBUG")

        time.sleep(0.5)

    def _run_launch_method(self) -> bool:
        if self.launch_method == "orchestra":
            return self._start_orchestra()
        if self.launch_method in ("direct_zapret2", "direct_zapret2_orchestra", "direct_zapret1"):
            return self._start_direct()
        log(f"Неизвестный метод запуска: {self.launch_method}", "❌ ERROR")
        return False

    def _resolve_direct_preset_payload(self) -> tuple[str, str] | None:
        mode_param = self.selected_mode
        if not (isinstance(mode_param, dict) and mode_param.get("is_preset_file")):
            log(
                f"Legacy combined/custom launch больше не поддерживается для {self.launch_method}: {type(mode_param)}",
                "❌ ERROR",
            )
            self._last_error_message = "Для прямого запуска используйте prepared preset файл"
            self.progress.emit("❌ Для прямого запуска используйте prepared preset файл")
            return None

        preset_path = str(mode_param.get("preset_path", "") or "").strip()
        strategy_name = str(mode_param.get("name", "Пресет") or "Пресет")

        log(f"Запуск из preset файла: {preset_path}", "INFO")

        if not preset_path:
            log("Путь к preset файлу не указан", "❌ ERROR")
            self._last_error_message = "Не указан путь к preset файлу"
            self.progress.emit("❌ Ошибка: не указан путь к preset файлу")
            return None

        if not os.path.exists(preset_path):
            log(f"Preset файл не найден: {preset_path}", "❌ ERROR")
            self._last_error_message = f"Preset файл не найден: {preset_path}"
            self.progress.emit("❌ Preset файл не найден")
            return None

        return preset_path, strategy_name

    def _start_direct_preset_with_runner(self, preset_path: str, strategy_name: str) -> bool:
        from launcher_common import get_strategy_runner

        runner = get_strategy_runner(self._get_winws_exe())
        success = runner.start_from_preset_file(preset_path, strategy_name)

        if success:
            log(f"Пресет '{strategy_name}' успешно запущен", "✅ SUCCESS")
            return True

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

    def run(self):
        try:
            self.progress.emit("Подготовка к запуску...")

            is_preset_file, preset_path = self._extract_preset_launch_input()
            process_running = self.dpi_starter.check_process_running_wmi(silent=True)
            skip_stop = process_running and self._can_reuse_running_process(
                is_preset_file=is_preset_file,
                preset_path=preset_path,
            )

            if not self._validate_preset_before_stop(
                is_preset_file=is_preset_file,
                preset_path=preset_path,
                skip_stop=skip_stop,
            ):
                return

            self._stop_previous_process_if_needed(skip_stop=skip_stop)

            self.progress.emit("Запуск DPI...")

            success = self._run_launch_method()
            
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
                        else:
                            fatal_reason = "❌ Для прямого запуска нужен prepared preset файл"
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
        """Запуск через preset-based direct path (StrategyRunner + prepared preset)."""
        try:
            payload = self._resolve_direct_preset_payload()
            if payload is None:
                return False
            preset_path, strategy_name = payload
            return self._start_direct_preset_with_runner(preset_path, strategy_name)
                
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


class DirectPresetSwitchWorker(QObject):
    """Worker для быстрого переключения running direct пресета без общего restart pipeline."""

    finished = pyqtSignal(bool, str, int, str, bool)  # success, error, generation, method, skipped_as_stale
    progress = pyqtSignal(str)

    def __init__(self, app_instance, launch_method: str, generation: int, is_generation_current):
        super().__init__()
        self.app_instance = app_instance
        self.launch_method = str(launch_method or "").strip().lower()
        self.generation = int(generation)
        self._is_generation_current = is_generation_current

    def _get_winws_exe(self) -> str:
        from config.config import get_winws_exe_for_method

        return get_winws_exe_for_method(self.launch_method)

    def run(self):
        try:
            if self.launch_method not in ("direct_zapret1", "direct_zapret2"):
                self.finished.emit(
                    False,
                    f"Неподдерживаемый метод direct switch: {self.launch_method}",
                    self.generation,
                    self.launch_method,
                    False,
                )
                return

            self.progress.emit("Применяем пресет...")

            from core.services import get_direct_flow_coordinator
            from launcher_common import get_strategy_runner

            profile = get_direct_flow_coordinator().ensure_launch_profile(
                self.launch_method,
                require_filters=True,
            )

            if not bool(self._is_generation_current(self.generation)):
                self.finished.emit(True, "", self.generation, self.launch_method, True)
                return

            runner = get_strategy_runner(self._get_winws_exe())
            switch_method = getattr(runner, "switch_preset_file_fast", None)
            if callable(switch_method):
                success = bool(
                    switch_method(
                        str(profile.launch_config_path),
                        profile.display_name,
                    )
                )
            else:
                success = bool(
                    runner.start_from_preset_file(
                        str(profile.launch_config_path),
                        profile.display_name,
                    )
                )

            if not success:
                short_error = str(getattr(runner, "last_error", "") or "").strip()
                if not short_error:
                    short_error = "Не удалось применить выбранный пресет"
                self.finished.emit(False, short_error, self.generation, self.launch_method, False)
                return

            self.finished.emit(True, "", self.generation, self.launch_method, False)
        except Exception as e:
            self.finished.emit(False, str(e), self.generation, self.launch_method, False)


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
        self._direct_preset_switch_thread = None
        self._direct_preset_switch_worker = None
        self._direct_preset_switch_requested_generation = 0
        self._direct_preset_switch_completed_generation = 0
        self._direct_preset_switch_method = ""
        self._pending_launch_warnings: list[str] = []
        self._restart_request_generation = 0
        self._restart_completed_generation = 0
        self._restart_pending_stop_generation = 0
        self._restart_active_start_generation = 0
        # Generation token for async start verification.
        # Prevents stale QTimer checks from previous start attempts.
        self._dpi_start_verify_generation = 0

    def _runtime_service(self):
        return getattr(self.app, "dpi_runtime_service", None)

    def _handle_conflicting_processes_before_start(self) -> bool:
        conflicting = check_conflicting_processes()
        if not conflicting:
            return True

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
            return False

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
                    QMessageBox.StandardButton.No,
                )
                if retry_msg == QMessageBox.StandardButton.No:
                    log("Запуск DPI отменён после неудачного закрытия процессов", "INFO")
                    return False

        if clicked == btn_ignore:
            log("Пользователь продолжил запуск несмотря на конфликтующие процессы", "WARNING")

        return True

    @staticmethod
    def _resolve_launch_method(launch_method=None) -> str:
        return str(launch_method or get_strategy_launch_method() or "").strip().lower()

    @staticmethod
    def _resolve_method_name(launch_method: str) -> str:
        method = str(launch_method or "").strip().lower()
        if method == "orchestra":
            return "оркестр"
        if method == "direct_zapret2":
            return "прямой"
        if method == "direct_zapret2_orchestra":
            return "оркестратор Z2"
        if method == "direct_zapret1":
            return "прямой Z1"
        return "классический"

    @staticmethod
    def _resolve_mode_name(selected_mode) -> str:
        if isinstance(selected_mode, tuple) and len(selected_mode) == 2:
            _, strategy_name = selected_mode
            return str(strategy_name or "Неизвестная стратегия")
        if isinstance(selected_mode, dict):
            return str(selected_mode.get("name", str(selected_mode)) or "Неизвестная стратегия")
        if isinstance(selected_mode, str):
            return str(selected_mode or "Неизвестная стратегия")
        return "Неизвестная стратегия"

    def _fail_start_preparation(self, message: str) -> None:
        text = str(message or "").strip() or "Не удалось подготовить запуск DPI"
        log(f"Ошибка подготовки запуска: {text}", "❌ ERROR")
        self.app.set_status(f"❌ {text}")
        self._show_launch_error_top(text)
        self._mark_runtime_failed(text)

    def _prepare_selected_mode_for_start(self, selected_mode, launch_method: str):
        method = str(launch_method or "").strip().lower()

        if method == "orchestra":
            return {"is_orchestra": True, "name": "Оркестр"}

        if selected_mode is not None and selected_mode != "default":
            return selected_mode

        if method in ("direct_zapret2", "direct_zapret1"):
            from core.services import get_direct_flow_coordinator

            snapshot = get_direct_flow_coordinator().get_startup_snapshot(
                method,
                require_filters=True,
            )
            log(f"Используется выбранный source-пресет: {snapshot.preset_path}", "INFO")
            return snapshot.to_selected_mode()

        if method == "direct_zapret2_orchestra":
            from preset_orchestra_zapret2 import (
                ensure_default_preset_exists,
                get_active_preset_path,
                get_active_preset_name,
            )

            ensure_default_preset_exists()
            preset_path = get_active_preset_path()
            preset_name = get_active_preset_name() or "Default"
            return {
                "is_preset_file": True,
                "name": f"Пресет оркестра: {preset_name}",
                "preset_path": str(preset_path),
            }

        raise RuntimeError("Неизвестный метод запуска")

    @staticmethod
    def _direct_filter_flags(launch_method: str) -> tuple[str, ...]:
        method = str(launch_method or "").strip().lower()
        if method == "direct_zapret1":
            return ("--wf-tcp=", "--wf-udp=")
        return ("--wf-tcp-out", "--wf-udp-out", "--wf-raw-part")

    def _validate_direct_selected_mode(self, selected_mode, launch_method: str) -> None:
        method = str(launch_method or "").strip().lower()
        if method not in ("direct_zapret2", "direct_zapret2_orchestra", "direct_zapret1"):
            return
        if not isinstance(selected_mode, dict) or not bool(selected_mode.get("is_preset_file")):
            return

        preset_path = Path(str(selected_mode.get("preset_path") or "").strip())
        if not preset_path.exists():
            raise RuntimeError("Preset файл не найден. Создайте пресет в настройках")

        try:
            content = preset_path.read_text(encoding="utf-8").strip()

            if method in ("direct_zapret2", "direct_zapret2_orchestra"):
                content_lower = content.lower()
                if ("unknown.txt" in content_lower) or ("ipset-unknown.txt" in content_lower):
                    try:
                        if method == "direct_zapret2_orchestra":
                            from preset_orchestra_zapret2.txt_preset_parser import (
                                parse_preset_file,
                                generate_preset_file,
                            )

                            data = parse_preset_file(preset_path)
                            if generate_preset_file(data, preset_path, atomic=True):
                                content = preset_path.read_text(encoding="utf-8").strip()
                        else:
                            from core.direct_preset_core.service import DirectPresetService
                            from core.services import get_app_paths

                            service = DirectPresetService(get_app_paths(), "winws2")
                            source = service.read_source_preset(preset_path)
                            if service.remove_placeholder_profiles(source):
                                service.write_source_preset(preset_path, source)
                                content = preset_path.read_text(encoding="utf-8").strip()
                    except Exception as e:
                        log(f"Ошибка очистки preset файла от unknown.txt: {e}", "DEBUG")

            if not any(flag in content for flag in self._direct_filter_flags(method)):
                raise RuntimeError("Выберите хотя бы одну категорию для запуска")
        except RuntimeError:
            raise
        except Exception as e:
            raise RuntimeError(f"Ошибка чтения preset: {e}") from e

    def _prepare_start_request(self, selected_mode=None, launch_method=None) -> PreparedDpiStartRequest:
        resolved_method = self._resolve_launch_method(launch_method)
        log(f"Используется метод запуска: {resolved_method}", "INFO")

        prepared_selected_mode = self._prepare_selected_mode_for_start(selected_mode, resolved_method)
        self._validate_direct_selected_mode(prepared_selected_mode, resolved_method)

        prelaunch_warnings, prelaunch_error = self._sanitize_direct_preset_before_launch(
            prepared_selected_mode,
            resolved_method,
        )
        if prelaunch_error:
            raise RuntimeError(prelaunch_error)

        self._pending_launch_warnings = [
            *prelaunch_warnings,
            *self._collect_soft_launch_warnings(prepared_selected_mode, resolved_method),
        ]

        return PreparedDpiStartRequest(
            launch_method=resolved_method,
            selected_mode=prepared_selected_mode,
            mode_name=self._resolve_mode_name(prepared_selected_mode),
            method_name=self._resolve_method_name(resolved_method),
        )

    @staticmethod
    def _expected_preset_path(selected_mode) -> str:
        if isinstance(selected_mode, dict) and bool(selected_mode.get("is_preset_file")):
            return str(selected_mode.get("preset_path") or "").strip()
        return ""

    @staticmethod
    def _expected_process_name(launch_method: str) -> str:
        method = str(launch_method or "").strip().lower()
        if method == "orchestra":
            return ""
        try:
            from config import get_winws_exe_for_method

            return os.path.basename(get_winws_exe_for_method(method)).strip().lower()
        except Exception:
            return ""

    def _begin_runtime_start(self, launch_method: str, selected_mode) -> None:
        runtime_service = self._runtime_service()
        if runtime_service is not None:
            runtime_service.begin_start(
                launch_method=launch_method,
                expected_process=self._expected_process_name(launch_method),
                expected_preset_path=self._expected_preset_path(selected_mode),
            )

    def _mark_runtime_running(self) -> None:
        runtime_service = self._runtime_service()
        if runtime_service is not None:
            runtime_service.mark_running()

    def _mark_runtime_failed(self, error_message: str, *, exit_code: int | None = None) -> None:
        runtime_service = self._runtime_service()
        if runtime_service is not None:
            runtime_service.mark_start_failed(error_message, exit_code=exit_code)

    def _begin_runtime_stop(self) -> None:
        runtime_service = self._runtime_service()
        if runtime_service is not None:
            runtime_service.begin_stop()

    def _mark_runtime_stopped(self) -> None:
        runtime_service = self._runtime_service()
        if runtime_service is not None:
            runtime_service.mark_stopped(clear_error=True)

    def _maybe_restart_discord_after_runtime_apply(self, *, skip_first_start: bool) -> bool:
        """Перезапускает Discord после применения пресета, если это разрешено настройкой."""
        try:
            is_first_start = bool(getattr(self.app, "_first_dpi_start", True))
            if skip_first_start and is_first_start:
                return False

            from discord.discord_restart import get_discord_restart_setting

            if not bool(get_discord_restart_setting(default=True)):
                return False

            discord_manager = getattr(self.app, "discord_manager", None)
            if discord_manager is None:
                return False

            return bool(discord_manager.restart_discord_if_running())
        except Exception as e:
            log(f"Discord restart check error: {e}", "DEBUG")
            return False
        finally:
            if skip_first_start:
                self.app._first_dpi_start = False

    def _process_pending_direct_preset_switch(self) -> None:
        target_generation = int(self._direct_preset_switch_requested_generation or 0)
        if target_generation <= int(self._direct_preset_switch_completed_generation or 0):
            return

        launch_method = str(
            self._direct_preset_switch_method or get_strategy_launch_method() or ""
        ).strip().lower()
        if launch_method not in ("direct_zapret1", "direct_zapret2"):
            return

        try:
            if self._direct_preset_switch_thread and self._direct_preset_switch_thread.isRunning():
                return
        except RuntimeError:
            self._direct_preset_switch_thread = None

        try:
            if self._dpi_start_thread and self._dpi_start_thread.isRunning():
                log(
                    f"Direct preset switch отложен: основной start pipeline ещё идёт, поколение {target_generation}",
                    "DEBUG",
                )
                return
        except RuntimeError:
            self._dpi_start_thread = None

        try:
            if self._dpi_stop_thread and self._dpi_stop_thread.isRunning():
                log(
                    f"Direct preset switch отложен: stop pipeline ещё идёт, поколение {target_generation}",
                    "DEBUG",
                )
                return
        except RuntimeError:
            self._dpi_stop_thread = None

        if not self.is_running():
            log("Direct preset switch пропущен: DPI уже не запущен", "DEBUG")
            self._direct_preset_switch_completed_generation = target_generation
            return

        if hasattr(self.app, 'main_window') and hasattr(self.app.main_window, '_show_active_strategy_page_loading'):
            self.app.main_window._show_active_strategy_page_loading()

        self._direct_preset_switch_thread = QThread()
        self._direct_preset_switch_worker = DirectPresetSwitchWorker(
            self.app,
            launch_method,
            target_generation,
            lambda generation: generation == self._direct_preset_switch_requested_generation,
        )
        self._direct_preset_switch_worker.moveToThread(self._direct_preset_switch_thread)
        self._direct_preset_switch_thread.started.connect(self._direct_preset_switch_worker.run)
        self._direct_preset_switch_worker.progress.connect(self.app.set_status)
        self._direct_preset_switch_worker.finished.connect(self._on_direct_preset_switch_finished)

        def cleanup_switch_thread():
            try:
                if self._direct_preset_switch_thread:
                    self._direct_preset_switch_thread.quit()
                    self._direct_preset_switch_thread.wait(2000)
                    self._direct_preset_switch_thread = None
                if self._direct_preset_switch_worker is not None:
                    self._direct_preset_switch_worker.deleteLater()
                    self._direct_preset_switch_worker = None
            except Exception as e:
                log(f"Ошибка при очистке direct preset switch thread: {e}", "❌ ERROR")

        self._direct_preset_switch_worker.finished.connect(cleanup_switch_thread)
        self._direct_preset_switch_thread.start()

    def switch_direct_preset_async(self, launch_method: str | None = None) -> None:
        method = str(launch_method or get_strategy_launch_method() or "").strip().lower()
        if method not in ("direct_zapret1", "direct_zapret2"):
            self.restart_dpi_async()
            return

        self._direct_preset_switch_method = method
        self._direct_preset_switch_requested_generation += 1
        log(
            f"Direct preset switch запросили, актуальное поколение {self._direct_preset_switch_requested_generation} ({method})",
            "INFO",
        )
        self._process_pending_direct_preset_switch()

    def _process_pending_restart_request(self) -> None:
        target_generation = int(self._restart_request_generation or 0)
        if target_generation <= int(self._restart_completed_generation or 0):
            return

        try:
            if self._dpi_start_thread and self._dpi_start_thread.isRunning():
                log(
                    f"Перезапуск DPI отложен: запуск ещё идёт, актуальное поколение {target_generation}",
                    "DEBUG",
                )
                return
        except RuntimeError:
            self._dpi_start_thread = None

        try:
            if self._dpi_stop_thread and self._dpi_stop_thread.isRunning():
                self._restart_pending_stop_generation = target_generation
                log(
                    f"Перезапуск DPI отложен: остановка ещё идёт, актуальное поколение {target_generation}",
                    "DEBUG",
                )
                return
        except RuntimeError:
            self._dpi_stop_thread = None

        if self.is_running():
            self._restart_pending_stop_generation = target_generation
            log(
                f"Перезапуск DPI: сначала останавливаем текущий процесс, актуальное поколение {target_generation}",
                "INFO",
            )
            self.stop_dpi_async()
            return

        self._restart_active_start_generation = target_generation
        log(
            f"Перезапуск DPI: запускаем актуальный выбранный пресет, поколение {target_generation}",
            "INFO",
        )
        self.start_dpi_async()

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
            controller = getattr(self.app, "window_notification_controller", None)
            if controller is not None:
                auto_fix_action = None
                if text.startswith("[AUTOFIX:"):
                    end_idx = text.find("]")
                    if end_idx > 0:
                        auto_fix_action = text[9:end_idx]
                        text = text[end_idx + 1 :].strip()

                buttons = []
                duration = 10000
                if auto_fix_action:
                    buttons.append(notification_action("autofix", "Исправить", value=auto_fix_action))
                    duration = -1

                controller.notify(
                    advisory_notification(
                        level="error",
                        title="Ошибка",
                        content=text,
                        source="launch.dpi_error",
                        presentation="infobar",
                        queue="immediate",
                        duration=duration,
                        buttons=buttons,
                        dedupe_key=f"launch.dpi_error:{' '.join(text.split()).lower()}",
                    )
                )
        except Exception as e:
            log(f"Не удалось показать InfoBar ошибки запуска: {e}", "DEBUG")

    def _show_launch_warning_top(self, message: str) -> None:
        text = str(message or "").strip()
        if not text:
            return
        try:
            while text.startswith(("⚠️", "⚠")):
                text = text[1:].strip()
        except Exception:
            pass
        if not text:
            return

        try:
            controller = getattr(self.app, "window_notification_controller", None)
            if controller is not None:
                controller.notify(
                    advisory_notification(
                        level="warning",
                        title="Предупреждение",
                        content=text,
                        source="launch.dpi_warning",
                        presentation="infobar",
                        queue="immediate",
                        duration=9000,
                        dedupe_key=f"launch.dpi_warning:{' '.join(text.split()).lower()}",
                    )
                )
        except Exception as e:
            log(f"Не удалось показать InfoBar предупреждения запуска: {e}", "DEBUG")

    def _collect_soft_launch_warnings(self, selected_mode, launch_method: str) -> list[str]:
        method = str(launch_method or "").strip().lower()
        if method != "direct_zapret2":
            return []
        if not isinstance(selected_mode, dict) or not bool(selected_mode.get("is_preset_file")):
            return []

        preset_path = str(selected_mode.get("preset_path") or "").strip()
        if not preset_path or not Path(preset_path).exists():
            return []

        try:
            from core.direct_preset_core.service import DirectPresetService
            from core.services import get_app_paths

            service = DirectPresetService(get_app_paths(), "winws2")
            source = service.read_source_preset(Path(preset_path))
            labels = service.collect_out_range_autofix_warning_labels(source)
        except Exception as e:
            log(f"Не удалось собрать предупреждения out-range для запуска: {e}", "DEBUG")
            return []

        if not labels:
            return []

        max_show = 5
        shown = labels[:max_show]
        hidden = len(labels) - len(shown)
        message = (
            "У некоторых фильтров out-range отсутствует или записан некорректно. "
            f"Перед запуском будет автоматически применён --out-range=-d8 или исправлен формат: {', '.join(shown)}"
        )
        if hidden > 0:
            message += f" (+{hidden} ещё)"
        return [message]

    def _sanitize_direct_preset_before_launch(self, selected_mode, launch_method: str) -> tuple[list[str], str | None]:
        method = str(launch_method or "").strip().lower()
        if method != "direct_zapret2":
            return [], None
        if not isinstance(selected_mode, dict) or not bool(selected_mode.get("is_preset_file")):
            return [], None

        preset_path = Path(str(selected_mode.get("preset_path") or "").strip())
        if not preset_path.exists():
            return [], "Preset файл не найден. Создайте пресет в настройках"

        try:
            from core.direct_preset_core.service import DirectPresetService
            from core.services import get_app_paths

            service = DirectPresetService(get_app_paths(), "winws2")
            source = service.read_source_preset(preset_path)
            changed = False
            warnings: list[str] = []

            if service.remove_placeholder_profiles(source):
                changed = True
                warnings.append("Из launch-пресета автоматически убраны placeholder-фильтры unknown.txt.")

            repaired_labels = service.repair_out_range_profiles(source)
            if repaired_labels:
                changed = True
                max_show = 5
                shown = repaired_labels[:max_show]
                hidden = len(repaired_labels) - len(shown)
                message = (
                    "В source-пресете автоматически исправлен out-range. "
                    f"Для этих фильтров записан канонический формат или подставлен --out-range=-d8: {', '.join(shown)}"
                )
                if hidden > 0:
                    message += f" (+{hidden} ещё)"
                warnings.append(message)

            if changed:
                service.write_source_preset(preset_path, source)

            return warnings, None
        except Exception as e:
            log(f"Не удалось подготовить direct preset перед запуском: {e}", "DEBUG")
            return [], None

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

        self._pending_launch_warnings = []

        if not self._handle_conflicting_processes_before_start():
            return

        # Invalidate any pending verification loop from older starts.
        self._dpi_start_verify_generation += 1

        try:
            request = self._prepare_start_request(selected_mode, launch_method)
        except Exception as e:
            self._fail_start_preparation(str(e))
            return

        if isinstance(request.selected_mode, tuple) and len(request.selected_mode) == 2:
            strategy_id, strategy_name = request.selected_mode
            log(f"Обработка встроенной стратегии: {strategy_name} (ID: {strategy_id})", "DEBUG")
        elif isinstance(request.selected_mode, dict):
            log(f"Обработка стратегии: {request.mode_name}", "DEBUG")
        elif isinstance(request.selected_mode, str):
            log(f"Обработка строковой стратегии: {request.mode_name}", "DEBUG")

        self.app.set_status(f"🚀 Запуск DPI ({request.method_name}): {request.mode_name}")
        
        # Показываем индикатор только на уже загруженной странице стратегий
        # для активного метода запуска, без старого обязательного attr-контракта.
        if hasattr(self.app, 'main_window') and hasattr(self.app.main_window, '_show_active_strategy_page_loading'):
            self.app.main_window._show_active_strategy_page_loading()
        
        store = getattr(self.app, "ui_state_store", None)
        if store is not None:
            store.set_dpi_busy(True, "Запуск Zapret...")

        self._begin_runtime_start(request.launch_method, request.selected_mode)
        
        # Создаем поток и worker
        self._dpi_start_thread = QThread()
        self._dpi_start_worker = DPIStartWorker(self.app, request.selected_mode, request.launch_method)
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
        
        log(f"Запуск асинхронного старта DPI: {request.mode_name} (метод: {request.method_name})", "INFO")

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
        
        if hasattr(self.app, 'main_window') and hasattr(self.app.main_window, '_show_active_strategy_page_loading'):
            self.app.main_window._show_active_strategy_page_loading()
        
        store = getattr(self.app, "ui_state_store", None)
        if store is not None:
            store.set_dpi_busy(True, "Остановка Zapret...")

        self._begin_runtime_stop()
        
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
        completed_restart_generation = int(self._restart_active_start_generation or 0)
        try:
            if hasattr(self.app, 'main_window') and hasattr(self.app.main_window, '_show_active_strategy_page_success'):
                self.app.main_window._show_active_strategy_page_success()
            
            if success:
                # ✅ РЕАЛЬНАЯ ПРОВЕРКА: процесс действительно запущен?
                # Используем QTimer вместо time.sleep чтобы не блокировать main thread.
                self._dpi_start_verify_retry = 0
                verify_gen = self._dpi_start_verify_generation
                self._verify_dpi_process_running(verify_gen)
                    
            else:
                if completed_restart_generation:
                    self._restart_completed_generation = max(
                        self._restart_completed_generation,
                        completed_restart_generation,
                    )
                    self._restart_active_start_generation = 0
                log(f"Ошибка асинхронного запуска DPI: {error_message}", "❌ ERROR")
                self.app.set_status(f"❌ Ошибка запуска: {error_message}")
                self._show_launch_error_top(error_message)
                self._mark_runtime_failed(error_message)

                if self._restart_request_generation > self._restart_completed_generation:
                    QTimer.singleShot(0, self._process_pending_restart_request)
                if self._direct_preset_switch_requested_generation > self._direct_preset_switch_completed_generation:
                    QTimer.singleShot(0, self._process_pending_direct_preset_switch)
                
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

        store = getattr(self.app, "ui_state_store", None)
        if store is not None:
            store.set_dpi_busy(False)

        completed_restart_generation = int(self._restart_active_start_generation or 0)
        if completed_restart_generation:
            self._restart_completed_generation = max(
                self._restart_completed_generation,
                completed_restart_generation,
            )
            self._restart_active_start_generation = 0

        if running:
            log("DPI запущен асинхронно", "INFO")
            self.app.set_status("✅ DPI успешно запущен")
            self._mark_runtime_running()

            # Устанавливаем флаг намеренного запуска
            self.app.intentional_start = True

            # Discord трогаем только после успешного применения runtime,
            # а пропуск первого запуска держим в одном общем месте.
            self._maybe_restart_discord_after_runtime_apply(skip_first_start=True)

            pending_warnings = list(getattr(self, "_pending_launch_warnings", []) or [])
            self._pending_launch_warnings = []
            for warning_text in pending_warnings:
                log(f"Launch warning: {warning_text}", "WARNING")
                QTimer.singleShot(150, lambda text=warning_text: self._show_launch_warning_top(text))
        else:
            # Процесс не запустился или сразу упал
            log("DPI не запустился - процесс не найден после старта", "❌ ERROR")
            self.app.set_status("❌ Процесс не запустился. Проверьте логи")
            self._show_launch_error_top("Процесс не запустился. Проверьте логи")

            self._pending_launch_warnings = []
            self._mark_runtime_failed("Процесс не запустился. Проверьте логи")

        if self._restart_request_generation > self._restart_completed_generation:
            QTimer.singleShot(0, self._process_pending_restart_request)
        if self._direct_preset_switch_requested_generation > self._direct_preset_switch_completed_generation:
            QTimer.singleShot(0, self._process_pending_direct_preset_switch)

    def _on_dpi_stop_finished(self, success, error_message):
        """Обрабатывает завершение асинхронной остановки DPI"""
        restart_generation_after_stop = int(self._restart_pending_stop_generation or 0)
        try:
            store = getattr(self.app, "ui_state_store", None)
            if store is not None:
                store.set_dpi_busy(False)

            if hasattr(self.app, 'main_window') and hasattr(self.app.main_window, '_show_active_strategy_page_success'):
                self.app.main_window._show_active_strategy_page_success()
            
            if success:
                # ✅ РЕАЛЬНАЯ ПРОВЕРКА: процесс действительно остановлен?
                is_still_running = self.app.dpi_starter.check_process_running_wmi(silent=True)
                
                if not is_still_running:
                    log("DPI остановлен асинхронно", "INFO")
                    if error_message:
                        self.app.set_status(f"✅ {error_message}")
                    else:
                        self.app.set_status("✅ DPI успешно остановлен")
                    self._mark_runtime_stopped()

                    if restart_generation_after_stop > self._restart_completed_generation:
                        self._restart_pending_stop_generation = 0
                        self._restart_active_start_generation = max(
                            restart_generation_after_stop,
                            self._restart_request_generation,
                        )
                        self.start_dpi_async()
                        return
                else:
                    # Процесс всё ещё работает
                    log("DPI всё ещё работает после попытки остановки", "⚠ WARNING")
                    self.app.set_status("⚠ Процесс всё ещё работает")
                    self._mark_runtime_running()

                    self._restart_pending_stop_generation = 0
                
            else:
                log(f"Ошибка асинхронной остановки DPI: {error_message}", "❌ ERROR")
                self.app.set_status(f"❌ Ошибка остановки: {error_message}")
                
                # Проверяем реальный статус процесса
                is_running = self.app.dpi_starter.check_process_running_wmi(silent=True)
                if is_running:
                    self._mark_runtime_running()
                else:
                    self._mark_runtime_stopped()

                self._restart_pending_stop_generation = 0
                
        except Exception as e:
            log(f"Ошибка при обработке результата остановки DPI: {e}", "❌ ERROR")
            self.app.set_status(f"Ошибка: {e}")
        finally:
            if self._direct_preset_switch_requested_generation > self._direct_preset_switch_completed_generation:
                QTimer.singleShot(0, self._process_pending_direct_preset_switch)

    def _on_direct_preset_switch_finished(self, success, error_message, generation, launch_method, skipped_as_stale):
        try:
            store = getattr(self.app, "ui_state_store", None)
            if store is not None:
                store.set_dpi_busy(False)

            if hasattr(self.app, 'main_window') and hasattr(self.app.main_window, '_show_active_strategy_page_success'):
                self.app.main_window._show_active_strategy_page_success()

            self._direct_preset_switch_completed_generation = max(
                int(self._direct_preset_switch_completed_generation or 0),
                int(generation or 0),
            )

            if skipped_as_stale:
                log(
                    f"Direct preset switch поколения {generation} пропущен как устаревший ({launch_method})",
                    "DEBUG",
                )
            elif success:
                log(
                    f"Direct preset switch успешно завершён, поколение {generation} ({launch_method})",
                    "INFO",
                )
                self._maybe_restart_discord_after_runtime_apply(skip_first_start=False)
                if int(self._direct_preset_switch_requested_generation or 0) <= int(self._direct_preset_switch_completed_generation or 0):
                    self.app.set_status("✅ Пресет успешно применён")
            else:
                log(
                    f"Ошибка direct preset switch, поколение {generation} ({launch_method}): {error_message}",
                    "❌ ERROR",
                )
                self.app.set_status(f"❌ Ошибка переключения пресета: {error_message}")
                self._show_launch_error_top(error_message)
        finally:
            if self._direct_preset_switch_requested_generation > self._direct_preset_switch_completed_generation:
                QTimer.singleShot(0, self._process_pending_direct_preset_switch)
    
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
        Перезапускает DPI по модели "последний запрос побеждает".

        Старые запросы не исполняются повторно: если пользователь быстро
        переключает пресеты, мы запоминаем только последнее поколение
        запроса и продолжаем pipeline от него.
        """
        self._restart_request_generation += 1
        log(
            f"Перезапуск DPI запросили, актуальное поколение {self._restart_request_generation}",
            "INFO",
        )
        self._process_pending_restart_request()
