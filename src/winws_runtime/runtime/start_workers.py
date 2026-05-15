from __future__ import annotations

from dataclasses import dataclass
import os
import time

from PyQt6.QtCore import QObject, pyqtSignal

from log.log import log
from settings.mode import ENGINE_WINWS2, is_orchestra_launch_method, is_preset_launch_method, is_zapret2_launch_method
from winws_runtime.health.process_health_check import diagnose_startup_error
from winws_runtime.runtime.sync_shutdown import shutdown_runtime_sync
from winws_runtime.runtime.system_ops import force_kill_all_winws_processes


@dataclass(frozen=True)
class PreparedDpiStartRequest:
    launch_method: str
    selected_mode: object
    mode_name: str
    method_name: str


class PresetLaunchStartWorker(QObject):
    """Worker для асинхронного запуска прямого launch-runtime."""

    finished = pyqtSignal(bool, str)  # success, error_message
    progress = pyqtSignal(str)        # status_message

    def __init__(self, selected_mode, launch_method, *, runtime_feature, runtime_api):
        super().__init__()
        self.selected_mode = selected_mode
        self.launch_method = launch_method
        self._runtime_feature = runtime_feature
        self.launch_runtime_api = runtime_api
        self._last_error_message: str = ""

    def _get_winws_exe(self) -> str:
        from settings.mode import exe_path_for_launch_method

        return exe_path_for_launch_method(self.launch_method)

    def _configure_runner_runtime_callbacks(self, runner) -> None:
        configurator = getattr(runner, "configure_runtime_callbacks", None)
        if not callable(configurator):
            return

        def _publish_runner_failure(*, launch_method: str, error: str = "") -> None:
            try:
                self._runtime_feature.events.publish_runner_failure(
                    launch_method=launch_method,
                    error=error,
                )
            except Exception:
                return

        def _notify_launch_error(message: str) -> None:
            try:
                self._runtime_feature.events.publish_launch_error(str(message or ""))
            except Exception:
                return

        def _publish_active_preset_content_changed(path: str) -> None:
            normalized_path = str(path or "").strip()
            if not normalized_path:
                return
            try:
                self._runtime_feature.events.publish_active_preset_content_changed(normalized_path)
            except Exception:
                return

        configurator(
            transition_in_progress=self._runtime_feature.objects.transition_pipeline_in_progress,
            runner_failure=_publish_runner_failure,
            launch_error=_notify_launch_error,
            active_preset_content_changed=_publish_active_preset_content_changed,
        )

    def _extract_preset_launch_input(self) -> tuple[bool, str]:
        mode_param = self.selected_mode
        if (
            isinstance(mode_param, dict)
            and mode_param.get("is_preset_file")
            and is_preset_launch_method(self.launch_method)
        ):
            return True, str(mode_param.get("preset_path") or "").strip()
        return False, ""

    def _can_reuse_running_process(self, *, is_preset_file: bool, preset_path: str) -> bool:
        if not is_preset_file or not preset_path:
            return False
        if not is_zapret2_launch_method(self.launch_method):
            return False
        try:
            from winws_runtime.runners.runner_factory import get_strategy_runner

            runner = get_strategy_runner(self._get_winws_exe())
            self._configure_runner_runtime_callbacks(runner)
            if hasattr(runner, "find_running_preset_pid"):
                pid = runner.find_running_preset_pid(preset_path)
                if pid:
                    log(
                        f"Preset уже запущен (PID: {pid}), пропускаем остановку",
                        "INFO",
                    )
                    return True
        except Exception as e:
            log(f"Не удалось проверить уже запущенный preset: {e}", "DEBUG")
        return False

    def _validate_preset_before_stop(self, *, is_preset_file: bool, preset_path: str, skip_stop: bool) -> bool:
        if not is_preset_file or not preset_path or skip_stop:
            return True
        try:
            from winws_runtime.runners.runner_factory import get_strategy_runner

            runner = get_strategy_runner(self._get_winws_exe())
            self._configure_runner_runtime_callbacks(runner)
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
        except Exception as e:
            log(f"Не удалось проверить preset перед остановкой предыдущего процесса: {e}", "DEBUG")
        return True

    def _stop_previous_process_if_needed(self, *, skip_stop: bool) -> None:
        process_running = self.launch_runtime_api.has_residual_processes(silent=True)
        if (not process_running) or skip_stop:
            return

        self.progress.emit("Останавливаем предыдущий процесс...")
        shutdown_result = shutdown_runtime_sync(
            runtime_feature=self._runtime_feature,
            reason=f"start_worker_prelaunch:{self.launch_method}",
            include_cleanup=False,
            cleanup_services=False,
            update_runtime_state=False,
        )
        if not shutdown_result.still_running:
            time.sleep(0.5)
            return

        max_wait = 10
        for attempt in range(max_wait):
            time.sleep(0.5)
            if not self.launch_runtime_api.has_residual_processes(silent=True):
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
        if is_orchestra_launch_method(self.launch_method):
            return self._start_orchestra()
        if is_preset_launch_method(self.launch_method):
            return self._start_preset_mode()
        log(f"Неизвестный метод запуска: {self.launch_method}", "❌ ERROR")
        return False

    def _resolve_presets_payload(self) -> tuple[str, str] | None:
        mode_param = self.selected_mode
        if not (isinstance(mode_param, dict) and mode_param.get("is_preset_file")):
            log(f"Ожидался preset файл для {self.launch_method}: {type(mode_param)}", "❌ ERROR")
            self._last_error_message = "Для режима профилей нужен preset файл"
            self.progress.emit("❌ Для режима профилей нужен preset файл")
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

    def _start_presets_with_runner(self, preset_path: str, strategy_name: str) -> bool:
        from winws_runtime.runners.runner_factory import get_strategy_runner

        runner = get_strategy_runner(self._get_winws_exe())
        self._configure_runner_runtime_callbacks(runner)
        success = runner.start_from_preset_file(preset_path, strategy_name)

        if success:
            log(f"Пресет '{strategy_name}' успешно запущен", "✅ SUCCESS")
            return True

        details = str(getattr(runner, "last_error", "") or "").strip()
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
            process_running = self.launch_runtime_api.has_residual_processes(silent=True)
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
                mode_param = self.selected_mode
                if isinstance(mode_param, dict) and is_preset_launch_method(self.launch_method):
                    if mode_param.get("is_preset_file"):
                        preset_path = str(mode_param.get("preset_path") or "").strip()
                        if not preset_path:
                            fatal_reason = "❌ Ошибка: не указан путь к preset файлу"
                    else:
                        fatal_reason = "❌ Для режима профилей нужен preset файл"

                error_msg = fatal_reason or (self._last_error_message or "Не удалось запустить DPI. Проверьте логи")
                self.progress.emit(error_msg)
                self.finished.emit(False, error_msg)

        except Exception as e:
            exe_path = self.launch_runtime_api.expected_exe_path
            diagnosis = diagnose_startup_error(e, exe_path)
            for line in diagnosis.split("\n"):
                log(line, "❌ ERROR")
            self.finished.emit(False, diagnosis.split("\n")[0])

    def _start_preset_mode(self):
        """Запуск preset-режима через существующий preset файл."""
        try:
            payload = self._resolve_presets_payload()
            if payload is None:
                return False
            preset_path, strategy_name = payload
            return self._start_presets_with_runner(preset_path, strategy_name)

        except Exception as e:
            exe_path = self._get_winws_exe()
            diagnosis = diagnose_startup_error(e, exe_path)
            for line in diagnosis.split("\n"):
                log(line, "❌ ERROR")
            self.progress.emit(diagnosis.split("\n")[0])
            return False

    def _start_orchestra(self):
        """Запуск через оркестратор автоматического обучения."""
        try:
            log("Запуск оркестратора...", "INFO")

            runner = self._runtime_feature.dependencies.orchestra_feature.ensure_runner()

            attempts = 2
            for attempt in range(1, attempts + 1):
                if runner.start():
                    log("Оркестратор успешно запущен", "✅ SUCCESS")
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
                        log(f"Диагностика старта: последние строки {ENGINE_WINWS2}:", "INFO")
                        for line in recent_output[-6:]:
                            clean = str(line or "").strip()
                            if clean:
                                if len(clean) > 300:
                                    clean = clean[:300] + " ..."
                                log(f"  {clean}", "INFO")
                except Exception as e:
                    log(f"Не удалось записать диагностику старта оркестратора: {e}", "DEBUG")

                return False

        except Exception as e:
            exe_path = self._get_winws_exe()
            diagnosis = diagnose_startup_error(e, exe_path)
            for line in diagnosis.split("\n"):
                log(line, "❌ ERROR")
            import traceback

            log(traceback.format_exc(), "DEBUG")
            return False
