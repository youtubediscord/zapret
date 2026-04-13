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
from .preset_runner_support import wait_for_process_exit
from winws_runtime.health.process_health_check import (
    check_process_health, get_last_crash_info, check_common_crash_causes,
    check_conflicting_processes, get_conflicting_processes_report, diagnose_startup_error,
    diagnose_winws_exit,
)
from winws_runtime.runtime.system_ops import (
    aggressive_windivert_cleanup_runtime,
    cleanup_windivert_services_runtime,
    force_kill_all_winws_processes,
    standard_windivert_cleanup_runtime,
    stop_and_delete_named_service,
    unload_known_windivert_drivers_runtime,
    WinDivertRuntimeProbeResult,
    wait_for_windivert_spawn_ready_runtime,
)
from utils.args_resolver import resolve_args_paths


_AGGRESSIVE_WINDIVERT_RETRY_COOLDOWN_SECONDS = 1.8
_WINDIVERT_PRESPAWN_WAIT_SECONDS = 3.0


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

        # Verify exe exists
        if not os.path.exists(self.winws_exe):
            raise FileNotFoundError(f"Executable not found: {self.winws_exe}")

        # Determine working directories
        exe_dir = os.path.dirname(self.winws_exe)
        self.work_dir = os.path.dirname(exe_dir)
        self.bin_dir = os.path.join(self.work_dir, "bin")
        self.lists_dir = os.path.join(self.work_dir, "lists")

        log(f"{self.__class__.__name__} initialized. exe: {self.winws_exe}", "INFO")
        log(f"Working directory: {self.work_dir}", "DEBUG")
        log(f"Lists folder: {self.lists_dir}", "DEBUG")
        log(f"Bin folder: {self.bin_dir}", "DEBUG")

    @abstractmethod
    def start_from_preset_file(self, preset_path: str, strategy_name: str = "Preset") -> bool:
        """
        Starts strategy directly from existing preset file.

        This is the preferred method for launching DPI in the current
        preset-based direct architecture.

        Concrete runners must implement this explicitly. Preset launch is the
        only supported direct-start contract in the current architecture.

        Args:
            preset_path: Path to the preset file
            strategy_name: Strategy name for logs

        Returns:
            True if strategy started successfully
        """
        pass

    def _create_startup_info(self):
        """Creates STARTUPINFO for hidden process launch"""
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags = STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = SW_HIDE
        return startupinfo

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
        from config.config import WINDIVERT_FILTER

        return resolve_args_paths(args, self.lists_dir, self.bin_dir, WINDIVERT_FILTER)

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
        # Exit code 9 = ERROR_INVALID_BLOCK — stale WinDivert state
        if exit_code == 9:
            return True

        stderr_lower = (stderr or "").lower()
        conflict_signatures = [
            "guid or luid already exists",
            "object with that guid",
        ]
        return any(sig in stderr_lower for sig in conflict_signatures)

    def _is_windivert_system_error(self, stderr: str, exit_code: int) -> bool:
        """Checks if error is a non-retryable WinDivert system error.

        These errors require user action (Secure Boot, AV, adapter, etc.)
        and should NOT be retried.
        """
        non_retryable_codes = {577, 1058, 1060, 1068, 1275, 654}
        if exit_code in non_retryable_codes:
            return True

        stderr_lower = (stderr or "").lower()
        system_signatures = [
            "the service cannot be started",
            "service is disabled",
            "invalid image hash",
            "driver blocked",
            "disable secure boot",
            "driver failed prior unload",
        ]
        return any(sig in stderr_lower for sig in system_signatures)

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

    def _ensure_windivert_ready_before_spawn(self, *, max_wait_seconds: float = _WINDIVERT_PRESPAWN_WAIT_SECONDS) -> bool:
        """Проверяет готовность WinDivert прямо перед новым spawn."""
        try:
            probe = wait_for_windivert_spawn_ready_runtime(
                max_wait_seconds=max_wait_seconds,
                poll_interval=0.25,
            )
        except Exception:
            return True

        if probe.ready:
            return True

        recovery_probe = self._retry_windivert_spawn_readiness_after_recovery(probe)
        if recovery_probe.ready:
            return True

        log(
            "WinDivert pre-spawn readiness check failed: "
            f"installed={recovery_probe.installed}, error={recovery_probe.error_code}, stage={recovery_probe.stage}",
            "WARNING",
        )
        return False

    def _retry_windivert_spawn_readiness_after_recovery(
        self,
        probe: WinDivertRuntimeProbeResult,
    ) -> WinDivertRuntimeProbeResult:
        """Один recovery-цикл для pre-spawn readiness.

        Нужен для плавающих случаев, когда stop/cleanup уже завершён, но
        WinDivert ещё не готов открыть NETWORK layer. Не бесконечный retry:
        делаем один контролируемый цикл и возвращаем итоговый probe.
        """
        transient_codes = {1058, 1060, 1753}
        if probe.ready or int(probe.error_code or 0) not in transient_codes:
            return probe

        log(
            "WinDivert pre-spawn readiness transient failure, performing one recovery cycle",
            "WARNING",
        )
        try:
            self._aggressive_windivert_cleanup()
            self._wait_after_aggressive_windivert_cleanup()
            return wait_for_windivert_spawn_ready_runtime(
                max_wait_seconds=_WINDIVERT_PRESPAWN_WAIT_SECONDS,
                poll_interval=0.25,
            )
        except Exception:
            return probe

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

        try:
            diag = diagnose_winws_exit(exit_code, stderr)
        except Exception:
            diag = None

        win32_error = int(getattr(diag, "win32_error", exit_code) or exit_code)
        if win32_error != 1058:
            return False

        cause = str(getattr(diag, "cause", "") or "").strip().lower()
        hard_no_retry_markers = (
            "base filtering engine",
            "служба windivert отключена",
            "отсутствуют файлы windivert",
            "secure boot",
            "подпись драйвера",
            "политика безопасности",
        )
        if any(marker in cause for marker in hard_no_retry_markers):
            return False

        return True

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

            # Additional cleanup
            if cleanup_services:
                self._stop_windivert_service()
                self._stop_monkey_service()
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
            'pid': self.running_process.pid if self.running_process else None,
            'args_count': len(self.current_strategy_args) if self.current_strategy_args else 0
        }

    def get_process(self) -> Optional[subprocess.Popen]:
        """Returns current running process for output reading"""
        if self.is_running():
            return self.running_process
        return None
