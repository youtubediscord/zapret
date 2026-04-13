from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import time

from PyQt6.QtCore import QObject, QMetaObject, Qt, pyqtSignal

from winws_runtime.health.process_health_check import diagnose_startup_error
from log.log import log
from winws_runtime.runtime.system_ops import force_kill_all_winws_processes
from winws_runtime.runtime.sync_shutdown import shutdown_runtime_sync

from settings.dpi.strategy_settings import get_strategy_launch_method


@dataclass(frozen=True)
class PreparedDpiStartRequest:
    launch_method: str
    selected_mode: object
    mode_name: str
    method_name: str


class DirectLaunchStartWorker(QObject):
    """Worker для асинхронного запуска прямого launch-runtime."""

    finished = pyqtSignal(bool, str)  # success, error_message
    progress = pyqtSignal(str)        # status_message

    def __init__(self, app_instance, selected_mode, launch_method):
        super().__init__()
        self.app_instance = app_instance
        self.selected_mode = selected_mode
        self.launch_method = launch_method
        self.launch_runtime_api = app_instance.launch_runtime_api
        self._last_error_message: str = ""

    def _get_winws_exe(self) -> str:
        from config.config import get_winws_exe_for_method

        return get_winws_exe_for_method(self.launch_method)

    def _extract_preset_launch_input(self) -> tuple[bool, str]:
        mode_param = self.selected_mode
        try:
            if (
                isinstance(mode_param, dict)
                and mode_param.get("is_preset_file")
                and self.launch_method in ("direct_zapret2", "direct_zapret1")
            ):
                return True, str(mode_param.get("preset_path") or "").strip()
        except Exception:
            pass
        return False, ""

    def _can_reuse_running_process(self, *, is_preset_file: bool, preset_path: str) -> bool:
        if not is_preset_file or not preset_path:
            return False
        if self.launch_method not in ("direct_zapret2",):
            return False
        try:
            from winws_runtime.runners.runner_factory import get_strategy_runner

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
            from winws_runtime.runners.runner_factory import get_strategy_runner

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
        process_running = self.launch_runtime_api.is_any_running(silent=True)
        if (not process_running) or skip_stop:
            return

        self.progress.emit("Останавливаем предыдущий процесс...")
        shutdown_result = shutdown_runtime_sync(
            window=self.app_instance,
            reason=f"start_worker_prelaunch:{self.launch_method}",
            include_cleanup=True,
            update_runtime_state=False,
        )
        if not shutdown_result.still_running:
            time.sleep(0.5)
            return

        max_wait = 10
        for attempt in range(max_wait):
            time.sleep(0.5)
            if not self.launch_runtime_api.is_any_running(silent=True):
                log(f"✅ Предыдущий процесс остановлен (попытка {attempt + 1})", "DEBUG")
                break
        else:
            log("⚠️ Процесс не остановился за 5 секунд, принудительное завершение...", "WARNING")
            try:
                force_kill_all_winws_processes()
                time.sleep(1)
            except Exception as e:
                log(f"Ошибка kill_winws_force: {e}", "DEBUG")

        time.sleep(0.5)

    def _run_launch_method(self) -> bool:
        if self.launch_method == "orchestra":
            return self._start_orchestra()
        if self.launch_method in ("direct_zapret2", "direct_zapret1"):
            return self._start_direct()
        log(f"Неизвестный метод запуска: {self.launch_method}", "❌ ERROR")
        return False

    def _resolve_direct_preset_payload(self) -> tuple[str, str] | None:
        mode_param = self.selected_mode
        if not (isinstance(mode_param, dict) and mode_param.get("is_preset_file")):
            log(f"Ожидался preset файл для {self.launch_method}: {type(mode_param)}", "❌ ERROR")
            self._last_error_message = "Для прямого запуска нужен preset файл"
            self.progress.emit("❌ Для прямого запуска нужен preset файл")
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
        from winws_runtime.runners.runner_factory import get_strategy_runner

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
            process_running = self.launch_runtime_api.is_any_running(silent=True)
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
                self.finished.emit(True, "")
            else:
                fatal_reason = ""
                try:
                    mode_param = self.selected_mode
                    if isinstance(mode_param, dict) and self.launch_method in ("direct_zapret2", "direct_zapret1"):
                        if mode_param.get("is_preset_file"):
                            preset_path = (mode_param.get("preset_path") or "").strip()
                            if not preset_path:
                                fatal_reason = "❌ Ошибка: не указан путь к preset файлу"
                        else:
                            fatal_reason = "❌ Для прямого запуска нужен preset файл"
                except Exception:
                    fatal_reason = ""

                error_msg = fatal_reason or (self._last_error_message or "Не удалось запустить DPI. Проверьте логи")
                self.progress.emit(error_msg)
                self.finished.emit(False, error_msg)

        except Exception as e:
            exe_path = getattr(self.launch_runtime_api, "expected_exe_path", None)
            diagnosis = diagnose_startup_error(e, exe_path)
            for line in diagnosis.split("\n"):
                log(line, "❌ ERROR")
            self.finished.emit(False, diagnosis.split("\n")[0])

    def _start_direct(self):
        """Запуск direct-режима через существующий preset файл."""
        try:
            payload = self._resolve_direct_preset_payload()
            if payload is None:
                return False
            preset_path, strategy_name = payload
            return self._start_direct_preset_with_runner(preset_path, strategy_name)

        except Exception as e:
            exe_path = self._get_winws_exe() if hasattr(self.app_instance, "launch_runtime_api") else None
            diagnosis = diagnose_startup_error(e, exe_path)
            for line in diagnosis.split("\n"):
                log(line, "❌ ERROR")
            self.progress.emit(diagnosis.split("\n")[0])
            return False

    def _start_orchestra(self):
        """Запуск через оркестратор автоматического обучения."""
        try:
            from orchestra.orchestra_runner import OrchestraRunner

            log("Запуск оркестратора...", "INFO")

            if not hasattr(self.app_instance, "orchestra_runner") or self.app_instance.orchestra_runner is None:
                self.app_instance.orchestra_runner = OrchestraRunner()

            runner = self.app_instance.orchestra_runner

            has_attr = hasattr(self.app_instance, "orchestra_page")
            page_exists = self.app_instance.orchestra_page if has_attr else None
            if has_attr and page_exists:
                runner.set_output_callback(self.app_instance.orchestra_page.emit_log)
            else:
                log("orchestra_page не существует при старте, callback будет установлен позже", "WARNING")

            attempts = 2
            for attempt in range(1, attempts + 1):
                if runner.start():
                    log("Оркестратор успешно запущен", "✅ SUCCESS")

                    if hasattr(self.app_instance, "orchestra_page") and self.app_instance.orchestra_page:
                        QMetaObject.invokeMethod(
                            self.app_instance.orchestra_page,
                            "start_monitoring",
                            Qt.ConnectionType.QueuedConnection,
                        )

                    return True

                start_reason = str(getattr(runner, "last_start_error", "") or "").strip()
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
                    exit_info = getattr(runner, "last_exit_info", None) or {}
                    config_path = str(exit_info.get("config_path") or "").strip()
                    command = exit_info.get("command") or []
                    recent_output = exit_info.get("recent_output") or []

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
                            clean = str(line or "").strip()
                            if clean:
                                if len(clean) > 300:
                                    clean = clean[:300] + " ..."
                                log(f"  {clean}", "INFO")
                except Exception:
                    pass

                return False

        except Exception as e:
            exe_path = self._get_winws_exe() if hasattr(self.app_instance, "launch_runtime_api") else None
            diagnosis = diagnose_startup_error(e, exe_path)
            for line in diagnosis.split("\n"):
                log(line, "❌ ERROR")
            import traceback

            log(traceback.format_exc(), "DEBUG")
            return False


class DirectLaunchStopWorker(QObject):
    """Worker для асинхронной остановки прямого launch-runtime."""

    finished = pyqtSignal(bool, str)
    progress = pyqtSignal(str)

    def __init__(self, app_instance, launch_method):
        super().__init__()
        self.app_instance = app_instance
        self.launch_method = launch_method

    def _get_winws_exe(self) -> str:
        from config.config import get_winws_exe_for_method

        return get_winws_exe_for_method(self.launch_method)

    def run(self):
        try:
            self.progress.emit("Остановка DPI...")

            if not self.app_instance.launch_runtime_api.is_any_running(silent=True):
                self.progress.emit("DPI уже остановлен")
                self.finished.emit(True, "DPI уже был остановлен")
                return

            self.progress.emit("Завершение процессов...")

            if self.launch_method == "orchestra":
                success = self._stop_orchestra()
            elif self.launch_method in ("direct_zapret2", "direct_zapret1"):
                success = self._stop_direct()
            else:
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
        try:
            return self._shutdown_runtime(reason=f"direct_stop_worker:{self.launch_method}")

        except Exception as e:
            log(f"Ошибка прямой остановки: {e}", "❌ ERROR")
            return False

    def _stop_orchestra(self):
        try:
            return self._shutdown_runtime(reason="orchestra_stop_worker")

        except Exception as e:
            log(f"Ошибка остановки оркестратора: {e}", "❌ ERROR")
            return False

    def _shutdown_runtime(self, *, reason: str) -> bool:
        result = shutdown_runtime_sync(
            window=self.app_instance,
            reason=reason,
            include_cleanup=True,
            update_runtime_state=False,
        )
        return not result.still_running


class DirectPresetSwitchWorker(QObject):
    """Worker для быстрого переключения running direct пресета без общего restart pipeline."""

    finished = pyqtSignal(bool, str, int, str, bool)
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

            from winws_runtime.runners.runner_factory import get_strategy_runner

            profile = self.app_instance.app_context.direct_flow_coordinator.ensure_launch_profile(
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
                        str(profile.preset_path),
                        profile.display_name,
                    )
                )
            else:
                success = bool(
                    runner.start_from_preset_file(
                        str(profile.preset_path),
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
        from config.config import get_winws_exe_for_method

        return get_winws_exe_for_method(self.launch_method)

    def run(self):
        try:
            self.progress.emit("Остановка DPI перед закрытием...")
            shutdown_runtime_sync(
                window=self.app_instance,
                reason=f"stop_and_exit_worker:{self.launch_method}",
                include_cleanup=True,
                update_runtime_state=True,
            )

            self.progress.emit("Завершение работы...")
            self.finished.emit()

        except Exception as e:
            log(f"Ошибка при остановке перед закрытием: {e}", "❌ ERROR")
            self.finished.emit()
