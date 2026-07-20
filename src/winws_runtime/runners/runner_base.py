# winws_runtime/runners/runner_base.py
"""Base class for strategy runners with shared functionality"""

import os
import subprocess
import time
from abc import ABC, abstractmethod
from typing import Optional, List, Dict

from log.log import log

from .args_filters import apply_all_filters
from .constants import SW_HIDE, CREATE_NO_WINDOW, STARTF_USESHOWWINDOW
from .preset_runner_support import launch_args_from_preset_text, wait_for_process_exit
from .spawn_failure import classify_spawn_failure
from winws_runtime.health.process_health_check import (
    check_process_health, get_last_crash_info, check_common_crash_causes,
    diagnose_startup_error, diagnose_winws_exit, execute_windivert_auto_fix,
)
from winws_runtime.health.windivert_diagnostics import (
    _ERROR_SERVICE_MARKED_FOR_DELETE,
    _WINDIVERT_PRESPAWN_WAIT_SECONDS,
    WinDivertReadinessResult,
    describe_windivert_readiness_failure,
    ensure_windivert_ready_before_spawn,
)
from winws_runtime.health.windows_system_dependencies import (
    mark_windows_server_wlanapi_message,
    should_offer_windows_server_wlanapi_install,
)
from winws_runtime.runtime.system_ops import (
    aggressive_windivert_cleanup_runtime,
    cleanup_windivert_services_runtime,
    force_kill_all_winws_processes,
    standard_windivert_cleanup_runtime,
    stop_and_delete_named_service,
    unload_known_windivert_drivers_runtime,
    WinDivertRuntimeProbeResult,
)
from utils.args_resolver import resolve_args_paths


_AGGRESSIVE_WINDIVERT_RETRY_COOLDOWN_SECONDS = 1.8
_WINDOWS_SYSTEM_DLLS_REQUIRED_BY_WINWS = ("wlanapi.dll",)
_SAFE_WINDIVERT_AUTOFIX_ACTIONS = {
    "cleanup_driver",
    "enable_bfe",
    "enable_driver",
    "enable_adapters",
}


class StrategyRunnerBase(ABC):
    """Abstract base class for strategy runners"""

    def __init__(self, winws_exe_path: str):
        """
        Initialize base strategy runner.

        Args:
            winws_exe_path: Path to winws.exe or winws2.exe
        """
        self.winws_exe = os.path.abspath(winws_exe_path)
        self.running_process: Optional[subprocess.Popen] = None
        self.current_launch_label: Optional[str] = None
        self.current_strategy_args: Optional[List[str]] = None
        self._transition_in_progress_callback = None
        self._runner_failure_callback = None
        self._launch_error_callback = None
        self._active_preset_content_changed_callback = None
        self._unexpected_process_exit_callback = None
        self._last_windivert_readiness_probe: Optional[WinDivertRuntimeProbeResult] = None
        self._last_windivert_readiness_result: Optional[WinDivertReadinessResult] = None

        # Verify exe exists
        if not os.path.exists(self.winws_exe):
            raise FileNotFoundError(f"Executable not found: {self.winws_exe}")

        # Determine working directories
        exe_dir = os.path.dirname(self.winws_exe)
        self.work_dir = os.path.dirname(exe_dir)
        self.bin_dir = os.path.join(self.work_dir, "bin")
        self.lists_dir = os.path.join(self.work_dir, "lists")

        try:
            from winws_runtime.health.launch_conflicts import register_own_windivert_dirs

            register_own_windivert_dirs(self.work_dir)
        except Exception:
            pass

        log(f"{self.__class__.__name__} initialized. exe: {self.winws_exe}", "INFO")
        log(f"Working directory: {self.work_dir}", "DEBUG")
        log(f"Lists folder: {self.lists_dir}", "DEBUG")
        log(f"Bin folder: {self.bin_dir}", "DEBUG")

    def configure_runtime_callbacks(
        self,
        *,
        transition_in_progress=None,
        runner_failure=None,
        launch_error=None,
        active_preset_content_changed=None,
        unexpected_process_exit=None,
    ) -> None:
        self._transition_in_progress_callback = transition_in_progress
        self._runner_failure_callback = runner_failure
        self._launch_error_callback = launch_error
        self._active_preset_content_changed_callback = active_preset_content_changed
        self._unexpected_process_exit_callback = unexpected_process_exit

    def launch_transition_in_progress(self, launch_method: str) -> bool:
        callback = self._transition_in_progress_callback
        if not callable(callback):
            return False
        try:
            return bool(callback(launch_method))
        except Exception:
            return False

    def publish_runner_failure(self, *, launch_method: str, error: str) -> None:
        callback = self._runner_failure_callback
        if not callable(callback):
            return
        try:
            callback(launch_method=launch_method, error=error)
        except Exception:
            return

    def notify_launch_error(self, message: str) -> None:
        callback = self._launch_error_callback
        if not callable(callback):
            return
        try:
            callback(message)
        except Exception:
            return

    def publish_active_preset_content_changed(self, path: str) -> None:
        callback = self._active_preset_content_changed_callback
        if not callable(callback):
            return
        try:
            callback(str(path or ""))
        except Exception:
            return

    def notify_unexpected_process_exit(self) -> None:
        callback = self._unexpected_process_exit_callback
        if not callable(callback):
            return
        try:
            callback()
        except Exception:
            return

    def _start_process_exit_watcher(self, process) -> None:
        """Instant exit detection for OUR spawned process.

        A daemon thread parked in `process.wait()` (WaitForSingleObject under
        the hood: zero CPU) fires the moment the process dies — no waiting for
        the 2s PID poll. The poll monitor stays as the fallback and as the only
        watcher for processes we did not spawn.
        """
        import threading

        def _watch() -> None:
            try:
                process.wait()
            except Exception:
                return
            self._on_watched_process_exit(process)

        threading.Thread(target=_watch, name="winws-exit-watcher", daemon=True).start()

    def _on_watched_process_exit(self, process) -> None:
        # Identity first (lock-free): fast switch replaces running_process
        # before stopping the old one; stop() clears it after termination.
        if process is not self.running_process:
            return
        try:
            snapshot = self.get_runner_state_snapshot()
        except Exception:
            snapshot = None
        state_value = str(getattr(getattr(snapshot, "state", None), "value", "") or "")
        if state_value in ("stopping", "idle"):
            return
        try:
            exit_code = process.poll()
        except Exception:
            exit_code = None
        log(
            f"Watched winws process exited unexpectedly (code: {exit_code}); notifying runtime",
            "WARNING",
        )
        self.notify_unexpected_process_exit()

    @abstractmethod
    def start_from_preset_file(self, preset_path: str, strategy_name: str = "Preset") -> bool:
        """
        Запускает движок из выбранного preset-файла.

        Это основной способ запуска DPI в текущей preset-архитектуре.

        Конкретные runner-ы должны явно реализовать этот метод. Запуск preset —
        единственный поддерживаемый контракт запуска для режима preset.

        Args:
            preset_path: путь к preset-файлу
            strategy_name: имя для логов

        Returns:
            True, если запуск прошёл успешно
        """
        pass

    @abstractmethod
    def switch_preset_file_fast(self, preset_path: str, strategy_name: str = "Preset", *, is_current=None) -> bool:
        """
        Быстро применяет другой preset для уже работающего режима preset.

        У этого контракта нет fallback на полный запуск: конкретный runner
        обязан сам решить, как остановить старый процесс и запустить новый.
        is_current нужен для быстрых кликов: если запрос уже устарел,
        runner должен выйти до запуска нового процесса.
        """
        pass

    def read_post_mortem_output(self) -> str:
        """Process output available after an unexpected death; "" when the runner keeps none."""
        return ""

    def build_post_mortem_snapshot(self) -> dict | None:
        """Exit facts for a tracked process that died unexpectedly.

        Returns None when there is nothing to diagnose: no tracked Popen
        (e.g. an adopted external process) or the process is still alive.
        """
        process = self.running_process
        if process is None:
            return None
        try:
            exit_code = process.poll()
        except Exception:
            return None
        if exit_code is None:
            return None
        return {
            "exit_code": int(exit_code),
            "output": self.read_post_mortem_output(),
            "strategy_name": str(self.current_launch_label or ""),
        }

    def _publish_final_launch_failure(self, *, launch_method: str, fallback_message: str) -> None:
        """Single user-facing publication point for a failed launch operation.

        Individual spawn attempts and retries stay quiet (WARNING logs only);
        this is called exactly once, after the whole operation — including all
        retries — has failed. The ERROR log line doubles as the UI toast via
        the global error notifier.
        """
        message = str(getattr(self, "last_error", "") or "").strip() or str(fallback_message or "").strip()
        if not message:
            message = "Не удалось запустить DPI"
        self.last_error = message
        log(message, "ERROR")
        self.notify_launch_error(message)
        # Runtime state и UI получают то же человеко-понятное сообщение. Сырой
        # вывод winws остаётся в журнале и в _last_spawn_stderr, но больше не
        # создаёт второе уведомление со строкой версии вместо причины ошибки.
        self.publish_runner_failure(launch_method=launch_method, error=message)

    def _create_startup_info(self):
        """Creates STARTUPINFO for hidden process launch"""
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags = STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = SW_HIDE
        return startupinfo

    def _get_missing_windows_system_dependencies(self) -> tuple[str, ...]:
        if os.name != "nt":
            return ()

        windows_dir = os.environ.get("SystemRoot") or os.environ.get("WINDIR")
        if not windows_dir:
            return ()

        search_dirs = (
            os.path.join(windows_dir, "System32"),
            os.path.join(windows_dir, "SysWOW64"),
        )
        missing: list[str] = []
        for dll_name in _WINDOWS_SYSTEM_DLLS_REQUIRED_BY_WINWS:
            if not any(os.path.exists(os.path.join(folder, dll_name)) for folder in search_dirs):
                missing.append(dll_name)
        return tuple(missing)

    def _format_missing_windows_system_dependency_error(self, missing_dlls: tuple[str, ...]) -> str:
        dll_text = ", ".join(str(name) for name in missing_dlls if str(name).strip())
        if not dll_text:
            dll_text = "системная DLL"
        exe_name = os.path.basename(str(self.winws_exe or "")) or "winws"
        message = (
            f"Windows урезана: не найден системный файл {dll_text}. "
            f"Из-за этого {exe_name} не может запуститься. "
            "Нужна обычная Windows или сборка, где есть компонент автонастройки WLAN "
            "(беспроводная сеть)."
        )
        if should_offer_windows_server_wlanapi_install(missing_dlls):
            return mark_windows_server_wlanapi_message(message)
        return message

    def get_runner_state_snapshot(self):
        """Optional public state snapshot hook for newer preset runners."""
        return None

    def stop_background_watchers(self) -> None:
        """Public lifecycle hook for stopping background watchers before invalidation."""
        return None

    def _clear_process_runtime_state(self) -> None:
        """Clear shared process-related runtime fields."""
        self.running_process = None
        self.current_launch_label = None
        self.current_strategy_args = None

    def _resolve_file_paths(self, args: List[str]) -> List[str]:
        """Resolves relative file paths"""
        filter_dir = os.path.join(self.work_dir, "windivert.filter")
        return resolve_args_paths(args, self.lists_dir, self.bin_dir, filter_dir)

    def _build_launch_args_from_preset_text(self, content: str) -> tuple[str, ...]:
        """Собирает аргументы запуска и приводит пути к файлам к рабочим путям."""
        return tuple(self._resolve_file_paths(launch_args_from_preset_text(content)))

    def _read_process_startup_output(self, process: subprocess.Popen) -> str:
        """Read winws output after an immediate startup failure."""
        try:
            stdout_data, stderr_data = process.communicate(timeout=1.0)
        except Exception:
            chunks = []
            for stream_name in ("stdout", "stderr"):
                stream = getattr(process, stream_name, None)
                if stream is None:
                    continue
                try:
                    chunks.append(stream.read())
                except Exception:
                    pass
            stdout_data = b""
            stderr_data = b"".join(chunk for chunk in chunks if isinstance(chunk, bytes))

        data = b""
        for chunk in (stdout_data, stderr_data):
            if isinstance(chunk, bytes):
                data += chunk
            elif chunk:
                data += str(chunk).encode("utf-8", errors="replace")
        return data.decode("utf-8", errors="replace").strip()

    def _fast_cleanup_services(self):
        """Fast service cleanup via Win API (for normal startup)"""
        try:
            cleanup_windivert_services_runtime()
        except Exception as e:
            log(f"Fast cleanup error: {e}", "DEBUG")

    def _unload_known_windivert_drivers(self) -> None:
        """Best-effort unload of known WinDivert-related drivers before spawn."""
        try:
            unload_known_windivert_drivers_runtime()
        except Exception:
            pass

    def _perform_standard_windivert_cleanup(self) -> None:
        """Canonical lightweight cleanup before ordinary preset start."""
        standard_windivert_cleanup_runtime()

    def _force_cleanup_multiple_services(self, service_names: List[str], retry_count: int = 3):
        """Force cleanup multiple services"""
        for service_name in service_names:
            try:
                stop_and_delete_named_service(service_name, retry_count=retry_count)
            except Exception as e:
                log(f"Error cleaning up service {service_name}: {e}", "DEBUG")

    def _is_windivert_conflict_error(self, stderr: str, exit_code: int) -> bool:
        """Checks if error is a retryable WinDivert conflict (GUID/LUID collision).

        This does NOT include system-level errors like service disabled (1058),
        driver blocked (1275), or Secure Boot (577) — those are not fixable
        by cleanup/retry.
        """
        return classify_spawn_failure(exit_code, stderr).is_conflict

    def _is_windivert_system_error(self, stderr: str, exit_code: int) -> bool:
        """Checks if error is a non-retryable WinDivert system error.

        These errors require user action (Secure Boot, AV, adapter, etc.)
        and should NOT be retried.
        """
        return classify_spawn_failure(exit_code, stderr).is_system

    def _aggressive_windivert_cleanup(self):
        """Aggressive WinDivert cleanup via Win API - for cases when normal cleanup doesn't help"""
        aggressive_windivert_cleanup_runtime()

    def _wait_after_aggressive_windivert_cleanup(self, *, seconds: float = _AGGRESSIVE_WINDIVERT_RETRY_COOLDOWN_SECONDS) -> None:
        """Даём Windows время после тяжёлой очистки WinDivert.

        Практически это нужно именно для плавающих 1058/34 случаев: сразу после
        aggressive cleanup драйвер/SCM ещё могут не успеть полностью освободить
        filter handle, и мгновенный повторный spawn просто ловит ту же ошибку.
        """
        cooldown = max(0.0, float(seconds))
        if cooldown <= 0:
            return
        log(f"Waiting {cooldown:.1f}s for WinDivert cleanup to settle", "DEBUG")
        time.sleep(cooldown)

    def _maybe_run_windivert_auto_fix_after_failed_spawn(
        self,
        stderr: str,
        exit_code: int,
        *,
        retry_count: int,
        max_retry_count: int = 1,
    ) -> bool:
        """Выполняет безопасное автолечение WinDivert перед одним повтором запуска."""
        if retry_count >= max_retry_count:
            return False

        try:
            diag = diagnose_winws_exit(exit_code, stderr)
        except Exception as exc:
            log(f"WinDivert auto-fix diagnosis failed: {exc}", "DEBUG")
            return False

        action = str(getattr(diag, "auto_fix", "") or "").strip()
        if action not in _SAFE_WINDIVERT_AUTOFIX_ACTIONS:
            return False

        cause = str(getattr(diag, "cause", "") or "").strip()
        log(
            f"WinDivert auto-fix '{action}' selected"
            + (f" after failure: {cause}" if cause else ""),
            "WARNING",
        )
        try:
            ok, message = execute_windivert_auto_fix(action)
        except Exception as exc:
            log(f"WinDivert auto-fix '{action}' failed: {exc}", "WARNING")
            return False

        if message:
            log(f"WinDivert auto-fix '{action}': {message}", "SUCCESS" if ok else "WARNING")
        if not ok:
            return False

        if action in {"cleanup_driver", "enable_driver"}:
            self._wait_after_aggressive_windivert_cleanup()
        return True

    def _ensure_windivert_ready_before_spawn(self, *, max_wait_seconds: float = _WINDIVERT_PRESPAWN_WAIT_SECONDS) -> bool:
        """Проверяет готовность WinDivert прямо перед новым spawn.

        Probe-оркестрация и recovery-цикл живут в центре диагностики
        (`winws_runtime.health.windivert_diagnostics`); runner передаёт туда
        только свои cleanup-колбэки.
        """
        self._last_windivert_readiness_probe = None
        self._last_windivert_readiness_result = None
        result = ensure_windivert_ready_before_spawn(
            max_wait_seconds=max_wait_seconds,
            aggressive_cleanup=self._aggressive_windivert_cleanup,
            wait_after_cleanup=self._wait_after_aggressive_windivert_cleanup,
        )
        if result.ready:
            return True

        self._last_windivert_readiness_probe = result.probe
        self._last_windivert_readiness_result = result
        return False

    def _fail_spawn_for_windivert_readiness(self, *, context: str = "spawn") -> bool:
        """Единственная точка провала spawn из-за pre-spawn readiness WinDivert.

        Сохраняет прежний контракт всех раннеров: exit code 34, stderr вида
        "windivert: readiness probe failed before ...", last_error с
        человеко-читаемым описанием. Всегда возвращает False.
        """
        result: Optional[WinDivertReadinessResult] = getattr(
            self, "_last_windivert_readiness_result", None
        )
        if result is not None and result.description:
            readiness_error = result.description
        else:
            readiness_error = describe_windivert_readiness_failure(
                getattr(self, "_last_windivert_readiness_probe", None)
            )
        self._last_spawn_exit_code = 34
        self._last_spawn_stderr = (
            f"windivert: readiness probe failed before {context}: {readiness_error}"
        )
        self._set_last_error(readiness_error, notify=False)
        return False

    def _should_retry_transient_windivert_service_error(
        self,
        stderr: str,
        exit_code: int,
        *,
        retry_count: int,
        max_retry_count: int = 1,
    ) -> bool:
        """Разрешает один retry для плавающего WinDivert service error.

        WinDivert code 1058/34 у нас иногда всплывает как остаточная гонка
        после stop/start, а не как реальное отключение BFE/службы/драйвера.
        Для таких случаев разрешаем один повтор через более тяжёлый cleanup.

        При явных системных причинах retry запрещён:
        - BFE реально выключен
        - служба WinDivert реально disabled
        - файлов драйвера нет
        - Secure Boot / подпись / политика безопасности
        """
        if retry_count >= max_retry_count:
            return False
        return classify_spawn_failure(exit_code, stderr).is_service_transient

    # ------------------------------------------------------------------
    #  Общая retry-оркестрация после неудачного spawn (zapret1/zapret2)
    # ------------------------------------------------------------------

    # Текст лога для системной ошибки WinDivert без ретрая; zapret2 исторически
    # использует чуть другую формулировку и переопределяет атрибут.
    _WINDIVERT_SYSTEM_ERROR_NO_RETRY_LOG_MESSAGE = "WinDivert system error — retry will not help"

    def _retry_fast_switch_after_failed_spawn_locked(self, artifact, strategy_name: str) -> bool:
        """Единый retry-путь после неудачного spawn при быстром переключении preset.

        Порядок проверок, лимиты и коды сохранены байт-в-байт с прежними
        реализациями zapret1/zapret2; различия вынесены в hook-методы.
        """
        exit_code = int(self._last_spawn_exit_code or -1)
        stderr_output = str(self._last_spawn_stderr or "")

        retry_allowed = self._is_windivert_conflict_error(stderr_output, exit_code)
        retry_allowed = retry_allowed or self._should_retry_transient_windivert_service_error(
            stderr_output,
            exit_code,
            retry_count=0,
            max_retry_count=1,
        )
        retry_allowed = retry_allowed or self._fast_switch_process_init_retry_allowed(exit_code)
        if not retry_allowed:
            return False
        if self._is_windivert_system_error(stderr_output, exit_code):
            log("Fast preset switch hit WinDivert system error; retry will not help", "WARNING")
            return False

        self._log_fast_switch_retry_reason(exit_code)
        self._cleanup_before_fast_switch_retry_locked()
        if not self._ensure_windivert_ready_before_spawn():
            return self._fail_spawn_for_windivert_readiness(context="fast switch retry")

        return bool(self._spawn_fast_switch_retry_locked(artifact, strategy_name))

    def _fast_switch_process_init_retry_allowed(self, exit_code: int) -> bool:
        """Hook: дополнительное условие ретрая fast switch (zapret2 — DLL init)."""
        return False

    def _cleanup_before_fast_switch_retry_locked(self) -> None:
        """Hook: тяжёлая очистка WinDivert перед retry fast switch."""
        self._aggressive_windivert_cleanup()
        self._wait_after_aggressive_windivert_cleanup()

    def _log_fast_switch_retry_reason(self, exit_code: int) -> None:
        """Hook: сообщение лога перед retry fast switch."""
        log(
            "Fast preset switch hit WinDivert conflict, retrying inside switch after cleanup",
            "WARNING",
        )

    def _spawn_fast_switch_retry_locked(self, artifact, strategy_name: str) -> bool:
        """Hook: как именно конкретный runner повторяет spawn при fast switch."""
        raise NotImplementedError

    def _maybe_retry_after_failed_spawn_locked(
        self,
        preset_path: str,
        strategy_name: str,
        *,
        retry_count: int,
        stable_start_window_seconds: float = 1.0,
        **launch_flags,
    ) -> bool:
        """Единая retry-оркестрация после неудачного spawn при обычном запуске.

        Каркас общий; различия раннеров (stale-службы zapret2, retry кода 1 у
        zapret1, условия conflict-ретрая) вынесены в hook-методы. Порядок
        проверок и лимиты соответствуют прежним реализациям.

        launch_flags: сквозные параметры конкретного runner-а
        (zapret1 — max_retries, zapret2 — cleanup_required).
        """
        exit_code = int(self._last_spawn_exit_code or -1)
        stderr_output = str(self._last_spawn_stderr or "")

        transient_service_retry = self._should_retry_transient_windivert_service_error(
            stderr_output,
            exit_code,
            retry_count=retry_count,
            max_retry_count=1,
        )

        decided = self._retry_hook_before_transient_locked(
            preset_path,
            strategy_name,
            exit_code=exit_code,
            transient_service_retry=transient_service_retry,
            retry_count=retry_count,
            stable_start_window_seconds=stable_start_window_seconds,
            **launch_flags,
        )
        if decided is not None:
            return decided

        if transient_service_retry:
            log(
                "Transient WinDivert service error detected, retrying with aggressive cleanup",
                "WARNING",
            )
            return self._relaunch_after_failed_spawn_locked(
                preset_path,
                strategy_name,
                retry_count=retry_count,
                stable_start_window_seconds=stable_start_window_seconds,
                **launch_flags,
            )

        decided = self._retry_hook_after_transient_locked(
            preset_path,
            strategy_name,
            exit_code=exit_code,
            stderr_output=stderr_output,
            retry_count=retry_count,
            stable_start_window_seconds=stable_start_window_seconds,
            **launch_flags,
        )
        if decided is not None:
            return decided

        if self._maybe_run_windivert_auto_fix_after_failed_spawn(
            stderr_output,
            exit_code,
            retry_count=retry_count,
        ):
            log("WinDivert auto-fix succeeded, retrying preset start once", "WARNING")
            return self._relaunch_after_failed_spawn_locked(
                preset_path,
                strategy_name,
                retry_count=retry_count,
                stable_start_window_seconds=stable_start_window_seconds,
                **launch_flags,
            )

        if self._is_windivert_system_error(stderr_output, exit_code):
            log(self._WINDIVERT_SYSTEM_ERROR_NO_RETRY_LOG_MESSAGE, "WARNING")
            return False

        return self._retry_hook_conflict_and_tail_locked(
            preset_path,
            strategy_name,
            exit_code=exit_code,
            stderr_output=stderr_output,
            retry_count=retry_count,
            stable_start_window_seconds=stable_start_window_seconds,
            **launch_flags,
        )

    def _retry_hook_before_transient_locked(
        self,
        preset_path: str,
        strategy_name: str,
        *,
        exit_code: int,
        transient_service_retry: bool,
        retry_count: int,
        stable_start_window_seconds: float,
        **launch_flags,
    ) -> Optional[bool]:
        """Hook перед transient-ретраем (zapret2 — stale delete-pending службы).

        None — продолжить общий каркас; bool — итог всей операции.
        """
        return None

    def _retry_hook_after_transient_locked(
        self,
        preset_path: str,
        strategy_name: str,
        *,
        exit_code: int,
        stderr_output: str,
        retry_count: int,
        stable_start_window_seconds: float,
        **launch_flags,
    ) -> Optional[bool]:
        """Hook после transient-ретрая (zapret1 — код 1 без вывода, zapret2 — DLL init)."""
        return None

    def _retry_hook_conflict_and_tail_locked(
        self,
        preset_path: str,
        strategy_name: str,
        *,
        exit_code: int,
        stderr_output: str,
        retry_count: int,
        stable_start_window_seconds: float,
        **launch_flags,
    ) -> bool:
        """Hook: обработка WinDivert-конфликта и финал без ретрая."""
        return False

    def _relaunch_after_failed_spawn_locked(
        self,
        preset_path: str,
        strategy_name: str,
        *,
        retry_count: int,
        stable_start_window_seconds: float,
        **launch_flags,
    ) -> bool:
        """Hook: повторный запуск конкретного runner-а с retry_count + 1."""
        raise NotImplementedError

    def stop(self, *, cleanup_services: bool = True) -> bool:
        """Stops running process.

        `cleanup_services=False` используется для сценариев stop->start внутри
        одного runtime pipeline. В таких переходах удаление WinDivert service
        здесь слишком агрессивно: следующий start сам выполняет свою штатную
        pre-cleanup стадию и должен оставаться единственной точкой этой очистки.
        """
        try:
            success = True

            if self.running_process and self.is_running():
                pid = self.running_process.pid
                strategy_name = self.current_launch_label or "unknown"

                log(f"Stopping strategy '{strategy_name}' (PID: {pid})", "INFO")

                # Soft stop
                self.running_process.terminate()

                if wait_for_process_exit(self.running_process, timeout=5.0):
                    log(f"Process stopped (PID: {pid})", "SUCCESS")
                else:
                    log("Soft stop failed, using force kill", "WARNING")
                    self.running_process.kill()
                    wait_for_process_exit(self.running_process, timeout=1.0)
                    log(f"Process forcefully terminated (PID: {pid})", "SUCCESS")
            else:
                log("No running process to stop", "INFO")

            if cleanup_services:
                self._perform_standard_windivert_cleanup()
            else:
                self._kill_all_winws_processes()

            # Clear state
            self._clear_process_runtime_state()

            return success

        except Exception as e:
            log(f"Error stopping process: {e}", "ERROR")
            return False

    def _stop_windivert_service(self):
        """Stops and deletes WinDivert service via Win API"""
        try:
            for service_name in ["WinDivert", "windivert", "WinDivert14", "WinDivert64"]:
                stop_and_delete_named_service(service_name, retry_count=3)
        except Exception as e:
            log(f"Ошибка остановки WinDivert service: {e}", "DEBUG")

    def _stop_monkey_service(self):
        """Stops and deletes Monkey service via Win API"""
        try:
            stop_and_delete_named_service("Monkey", retry_count=3)
        except Exception as e:
            log(f"Ошибка остановки Monkey service: {e}", "DEBUG")

    def _force_delete_service(self, service_name: str):
        """Force delete a service"""
        try:
            stop_and_delete_named_service(service_name, retry_count=5)
        except Exception as e:
            log(f"Force delete service {service_name} error: {e}", "DEBUG")

    def _kill_all_winws_processes(self):
        """Forcefully terminates all winws.exe and winws2.exe processes via Win API"""
        try:
            force_kill_all_winws_processes()
        except Exception as e:
            log(f"Error killing winws processes: {e}", "DEBUG")

    def is_running(self) -> bool:
        """Checks if process is running"""
        if not self.running_process:
            return False

        poll_result = self.running_process.poll()
        is_running = poll_result is None

        if not is_running and self.current_launch_label:
            log(f"Strategy process exited (code: {poll_result})", "WARNING")

        return is_running

    def get_current_strategy_info(self) -> Dict:
        """Returns information about current running strategy"""
        if not self.is_running():
            return {}

        return {
            'name': self.current_launch_label,
            'args_count': len(self.current_strategy_args) if self.current_strategy_args else 0
        }

    def get_process(self) -> Optional[subprocess.Popen]:
        """Returns current running process for output reading"""
        if self.is_running():
            return self.running_process
        return None
