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
    check_conflicting_processes, get_conflicting_processes_report, diagnose_startup_error
)
from utils.args_resolver import resolve_args_paths
from utils.service_manager import (
    cleanup_windivert_services, stop_and_delete_service, unload_driver, service_exists
)
from utils.process_killer import kill_process_by_name, kill_winws_force


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
            cleanup_windivert_services()
        except Exception as e:
            log(f"Fast cleanup error: {e}", "DEBUG")

    def _unload_known_windivert_drivers(self) -> None:
        """Best-effort unload of known WinDivert-related drivers before spawn."""
        try:
            for driver in ["WinDivert", "WinDivert14", "WinDivert64", "Monkey"]:
                try:
                    unload_driver(driver)
                except Exception:
                    pass
        except Exception:
            pass

    def _perform_standard_windivert_cleanup(self) -> None:
        """Canonical lightweight cleanup before ordinary preset start."""
        log("Cleaning up previous winws processes...", "DEBUG")
        kill_winws_force()
        self._fast_cleanup_services()
        self._unload_known_windivert_drivers()
        time.sleep(0.3)

    def _force_cleanup_multiple_services(self, service_names: List[str], retry_count: int = 3):
        """Force cleanup multiple services"""
        for service_name in service_names:
            try:
                stop_and_delete_service(service_name, retry_count=retry_count)
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
        log("Performing aggressive WinDivert cleanup via Win API...", "INFO")

        # 1. Kill ALL processes that may hold handles
        self._kill_all_winws_processes()
        time.sleep(0.3)

        # 2. Unload drivers via fltmc (before deleting services!)
        drivers = ["WinDivert", "WinDivert14", "WinDivert64", "Monkey"]
        for driver in drivers:
            try:
                unload_driver(driver)
            except:
                pass

        time.sleep(0.2)

        # 3. Stop and delete services via Win API
        services = ["WinDivert", "WinDivert14", "WinDivert64", "windivert", "Monkey"]
        for service in services:
            try:
                stop_and_delete_service(service, retry_count=3)
            except:
                pass

        time.sleep(0.3)

        # 4. Final process cleanup
        self._kill_all_winws_processes()

        log("Aggressive cleanup completed", "INFO")

    def stop(self) -> bool:
        """Stops running process"""
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
        for service_name in ["WinDivert", "windivert", "WinDivert14", "WinDivert64"]:
            stop_and_delete_service(service_name, retry_count=3)

    def _stop_monkey_service(self):
        """Stops and deletes Monkey service via Win API"""
        stop_and_delete_service("Monkey", retry_count=3)

    def _force_delete_service(self, service_name: str):
        """Force delete a service"""
        try:
            stop_and_delete_service(service_name, retry_count=5)
        except Exception as e:
            log(f"Force delete service {service_name} error: {e}", "DEBUG")

    def _kill_all_winws_processes(self):
        """Forcefully terminates all winws.exe and winws2.exe processes via Win API"""
        try:
            kill_winws_force()
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
