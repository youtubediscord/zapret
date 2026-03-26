# zapret1_launcher/strategy_runner.py
"""
Strategy runner for Zapret 1 (winws.exe).

Supports hot-reload via ConfigFileWatcher when preset-zapret1.txt changes.
Does NOT support Lua functionality.
Writes args to preset-zapret1.txt and launches winws.exe via @file syntax.
"""

import os
import subprocess
import threading
import time
from typing import Optional, List, Callable
from datetime import datetime
from log import log

from launcher_common.args_filters import apply_all_filters
from launcher_common.constants import SW_HIDE, CREATE_NO_WINDOW, STARTF_USESHOWWINDOW
from dpi.process_health_check import (
    check_process_health,
    check_common_crash_causes,
    check_conflicting_processes,
    get_conflicting_processes_report,
    diagnose_startup_error
)


def log_full_command(cmd_list: List[str], strategy_name: str):
    """
    Writes full command line to a separate file for debugging.

    Args:
        cmd_list: List of command arguments
        strategy_name: Strategy name
    """
    try:
        from config import LOGS_FOLDER

        os.makedirs(LOGS_FOLDER, exist_ok=True)

        cmd_log_file = os.path.join(LOGS_FOLDER, "commands_full.log")

        full_cmd_parts = []
        for i, arg in enumerate(cmd_list):
            if i == 0:
                full_cmd_parts.append(arg)
            else:
                if arg.startswith('"') and arg.endswith('"'):
                    full_cmd_parts.append(arg)
                elif ' ' in arg or '\t' in arg:
                    full_cmd_parts.append(f'"{arg}"')
                else:
                    full_cmd_parts.append(arg)

        full_cmd = ' '.join(full_cmd_parts)

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        separator = "=" * 80

        with open(cmd_log_file, 'a', encoding='utf-8') as f:
            f.write(f"\n{separator}\n")
            f.write(f"Timestamp: {timestamp}\n")
            f.write(f"Strategy: {strategy_name}\n")
            f.write(f"Command length: {len(full_cmd)} characters\n")
            f.write(f"Arguments count: {len(cmd_list) - 1}\n")
            f.write(f"{separator}\n")
            f.write(f"FULL COMMAND:\n")
            f.write(f"{full_cmd}\n")
            f.write(f"{separator}\n")

            f.write(f"ARGUMENTS LIST:\n")
            for i, arg in enumerate(cmd_list):
                f.write(f"[{i:3}]: {arg}\n")
            f.write(f"{separator}\n\n")

        last_cmd_file = os.path.join(LOGS_FOLDER, "last_command.txt")
        with open(last_cmd_file, 'w', encoding='utf-8') as f:
            f.write(f"# Last command executed at {timestamp}\n")
            f.write(f"# Strategy: {strategy_name}\n\n")
            f.write(full_cmd)

        log(f"Command saved to logs/commands_full.log", "DEBUG")

    except Exception as e:
        log(f"Error writing command to log: {e}", "DEBUG")


class ConfigFileWatcher:
    """
    Monitors preset file changes for hot-reload.

    Watches a config file and calls callback when modification time changes.
    Runs in a background thread with configurable polling interval.
    """

    def __init__(self, file_path: str, callback: Callable[[], None], interval: float = 1.0):
        self._file_path = file_path
        self._callback = callback
        self._interval = interval
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._last_mtime: Optional[float] = None

        if os.path.exists(self._file_path):
            self._last_mtime = os.path.getmtime(self._file_path)

    def start(self):
        """Start watching the file in background thread"""
        if self._running:
            log("ConfigFileWatcher already running", "DEBUG")
            return
        self._running = True
        self._thread = threading.Thread(target=self._watch_loop, daemon=True, name="ConfigFileWatcherV1")
        self._thread.start()
        log(f"ConfigFileWatcher started for: {self._file_path}", "DEBUG")

    def stop(self):
        """Stop watching the file"""
        if not self._running:
            return
        self._running = False
        watcher_thread = self._thread
        if watcher_thread and watcher_thread.is_alive():
            if watcher_thread is threading.current_thread():
                log("ConfigFileWatcherV1.stop called from watcher thread; skip self-join", "DEBUG")
            else:
                watcher_thread.join(timeout=2.0)
        self._thread = None
        log("ConfigFileWatcher stopped", "DEBUG")

    def _watch_loop(self):
        """Main watch loop - polls file for changes"""
        while self._running:
            try:
                if os.path.exists(self._file_path):
                    current_mtime = os.path.getmtime(self._file_path)
                    if self._last_mtime is not None and current_mtime != self._last_mtime:
                        log(f"Config file changed: {self._file_path}", "INFO")
                        self._last_mtime = current_mtime
                        try:
                            self._callback()
                        except Exception as e:
                            log(f"Error in config change callback: {e}", "ERROR")
                    self._last_mtime = current_mtime
            except Exception as e:
                log(f"Error checking file modification: {e}", "DEBUG")

            sleep_remaining = self._interval
            while sleep_remaining > 0 and self._running:
                time.sleep(min(0.1, sleep_remaining))
                sleep_remaining -= 0.1


class StrategyRunnerV1:
    """
    Runner for Zapret 1 (winws.exe).
    Simple version without hot-reload and Lua functionality.
    """

    def __init__(self, winws_exe_path: str):
        """
        Args:
            winws_exe_path: Path to winws.exe
        """
        self.winws_exe = os.path.abspath(winws_exe_path)
        self.running_process: Optional[subprocess.Popen] = None
        self.current_strategy_name: Optional[str] = None
        self.current_strategy_args: Optional[List[str]] = None
        # Human-readable last start error (for UI/status).
        self.last_error: Optional[str] = None

        # Config file watcher for hot-reload on preset change
        self._config_watcher: Optional[ConfigFileWatcher] = None
        self._preset_file_path: Optional[str] = None

        # Verify exe exists
        if not os.path.exists(self.winws_exe):
            raise FileNotFoundError(f"winws.exe not found: {self.winws_exe}")

        # Determine working directory
        exe_dir = os.path.dirname(self.winws_exe)
        self.work_dir = os.path.dirname(exe_dir)

        self.bin_dir = os.path.join(self.work_dir, "bin")
        self.lists_dir = os.path.join(self.work_dir, "lists")

        log(f"StrategyRunnerV1 initialized. winws.exe: {self.winws_exe}", "INFO")
        log(f"Working directory: {self.work_dir}", "DEBUG")
        log(f"Lists folder: {self.lists_dir}", "DEBUG")
        log(f"Bin folder: {self.bin_dir}", "DEBUG")

    def _set_last_error(self, message: Optional[str]) -> None:
        try:
            text = str(message or "").strip()
        except Exception:
            text = ""
        self.last_error = text or None
        if text:
            self._notify_ui_launch_error(text)

    @staticmethod
    def _notify_ui_launch_error(message: str) -> None:
        """Best-effort UI notification from any thread (queued to main Qt thread)."""
        text = str(message or "").strip()
        if not text:
            return
        try:
            from PyQt6.QtCore import QMetaObject, Qt, Q_ARG
            from PyQt6.QtWidgets import QApplication

            app = QApplication.instance()
            if app is None:
                return

            target = app.activeWindow()
            if target is None or not hasattr(target, "show_dpi_launch_error"):
                for widget in app.topLevelWidgets():
                    if hasattr(widget, "show_dpi_launch_error"):
                        target = widget
                        break

            if target is not None and hasattr(target, "show_dpi_launch_error"):
                QMetaObject.invokeMethod(
                    target,
                    "show_dpi_launch_error",
                    Qt.ConnectionType.QueuedConnection,
                    Q_ARG(str, text),
                )
        except Exception:
            pass

    def _write_preset_file(self, args: List[str], strategy_name: str) -> str:
        """
        Writes arguments to preset file for loading via @file.
        Uses preset-zapret1.txt for winws.exe.

        Args:
            args: List of command line arguments
            strategy_name: Strategy name for comment

        Returns:
            Path to created file
        """
        preset_filename = "preset-zapret1.txt"
        preset_path = os.path.join(self.work_dir, preset_filename)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        with open(preset_path, 'w', encoding='utf-8') as f:
            f.write(f"# Strategy: {strategy_name}\n")
            f.write(f"# Generated: {timestamp}\n")

            first_filter_found = False

            for arg in args:
                if not first_filter_found and (arg.startswith('--filter-tcp') or arg.startswith('--filter-udp')):
                    f.write("\n")
                    first_filter_found = True

                f.write(f"{arg}\n")

                if arg == '--new':
                    f.write("\n")

        return preset_path

    def _create_startup_info(self):
        """Creates STARTUPINFO for hidden process launch"""
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags = STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = SW_HIDE
        return startupinfo

    def _resolve_file_paths(self, args: List[str]) -> List[str]:
        """Resolves relative file paths"""
        from config import WINDIVERT_FILTER
        from utils.args_resolver import resolve_args_paths

        return resolve_args_paths(args, self.lists_dir, self.bin_dir, WINDIVERT_FILTER)

    def _fast_cleanup_services(self):
        """Fast service cleanup via Win API (for normal startup)"""
        try:
            from utils.service_manager import cleanup_windivert_services
            cleanup_windivert_services()
        except Exception as e:
            log(f"Fast cleanup error: {e}", "DEBUG")

    def _is_windivert_conflict_error(self, stderr: str, exit_code: int) -> bool:
        """Checks if error is a retryable WinDivert conflict (GUID/LUID collision).

        This does NOT include system-level errors like service disabled (1058),
        driver blocked (1275), or Secure Boot (577) — those are not fixable
        by cleanup/retry.
        """
        if exit_code == 9:
            return True

        stderr_lower = (stderr or "").lower()
        conflict_signatures = [
            "guid or luid already exists",
            "object with that guid",
        ]
        return any(sig in stderr_lower for sig in conflict_signatures)

    def _is_windivert_system_error(self, stderr: str, exit_code: int) -> bool:
        """Checks if error is a non-retryable WinDivert system error."""
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
        from utils.service_manager import stop_and_delete_service, unload_driver

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

    def _kill_all_winws_processes(self):
        """Forcefully terminates all winws.exe and winws2.exe processes via Win API"""
        try:
            from utils.process_killer import kill_winws_force
            kill_winws_force()
        except Exception as e:
            log(f"Error killing winws processes: {e}", "DEBUG")

    def _stop_windivert_service(self):
        """Stops and deletes WinDivert service via Win API"""
        from utils.service_manager import stop_and_delete_service

        for service_name in ["WinDivert", "windivert", "WinDivert14", "WinDivert64"]:
            stop_and_delete_service(service_name, retry_count=3)

    def _stop_monkey_service(self):
        """Stops and deletes Monkey service via Win API"""
        from utils.service_manager import stop_and_delete_service
        stop_and_delete_service("Monkey", retry_count=3)

    def _on_config_changed(self) -> None:
        """Called when preset-zapret1.txt changes. Performs full restart."""
        log("preset-zapret1.txt changed, restarting winws.exe...", "INFO")
        try:
            if self._preset_file_path and os.path.exists(self._preset_file_path):
                self.start_from_preset_file(
                    self._preset_file_path,
                    strategy_name=self.current_strategy_name or "Preset",
                )
        except Exception as e:
            log(f"Error restarting after config change: {e}", "ERROR")

    def _start_config_watcher(self, preset_file: str) -> None:
        """Starts config file watcher for hot-reload."""
        # Stop existing watcher
        if self._config_watcher:
            self._config_watcher.stop()
            self._config_watcher = None

        self._config_watcher = ConfigFileWatcher(
            file_path=preset_file,
            callback=self._on_config_changed,
            interval=1.0,
        )
        self._config_watcher.start()

    def start_strategy_custom(self, custom_args: List[str], strategy_name: str = "Custom Strategy", _retry_count: int = 0) -> bool:
        """
        Starts strategy with arbitrary arguments.

        Unlike V2:
        - No hot-reload
        - No --lua-* arguments

        Args:
            custom_args: List of command line arguments
            strategy_name: Strategy name for logs
            _retry_count: Internal retry counter (don't pass externally)
        """
        MAX_RETRIES = 2

        conflicting = check_conflicting_processes()
        if conflicting:
            warning_report = get_conflicting_processes_report()
            log(warning_report, "WARNING")

        self._set_last_error(None)

        try:
            # Stop previous process
            if self.running_process and self.is_running():
                log("Stopping previous process before starting new one", "INFO")
                self.stop()

            from utils.process_killer import kill_winws_force

            if _retry_count > 0:
                # Aggressive cleanup only on retry
                self._aggressive_windivert_cleanup()
            else:
                log("Cleaning up previous winws processes...", "DEBUG")
                kill_winws_force()

                self._fast_cleanup_services()

                # Unload WinDivert drivers for complete cleanup
                try:
                    from utils.service_manager import unload_driver
                    for driver in ["WinDivert", "WinDivert14", "WinDivert64", "Monkey"]:
                        try:
                            unload_driver(driver)
                        except:
                            pass
                except:
                    pass

                time.sleep(0.3)

            if not custom_args:
                log("No arguments for startup", "ERROR")
                self._set_last_error("Не заданы аргументы стратегии")
                return False

            # Self-healing: verify winws.exe still exists before launch
            if not os.path.exists(self.winws_exe):
                log(f"winws.exe disappeared: {self.winws_exe}", "ERROR")
                self._set_last_error(f"winws.exe не найден: {self.winws_exe}")
                return False

            # Self-healing: ensure work/lists directories exist
            for d in (self.work_dir, self.lists_dir, self.bin_dir):
                if d and not os.path.isdir(d):
                    try:
                        os.makedirs(d, exist_ok=True)
                        log(f"Auto-created missing directory: {d}", "INFO")
                    except Exception as e:
                        log(f"Cannot create directory {d}: {e}", "WARNING")

            # Resolve paths
            resolved_args = self._resolve_file_paths(custom_args)

            # Apply ALL filters in correct order
            resolved_args = apply_all_filters(resolved_args, self.lists_dir)

            # Write config to file
            preset_file = self._write_preset_file(resolved_args, strategy_name)
            self._preset_file_path = preset_file

            # Build command with @file
            cmd = [self.winws_exe, f"@{preset_file}"]

            log(f"Starting strategy '{strategy_name}'" + (f" (attempt {_retry_count + 1})" if _retry_count > 0 else ""), "INFO")
            log(f"Config written to: {preset_file}", "DEBUG")
            log(f"Arguments count: {len(resolved_args)}", "DEBUG")

            # Save full command line for debugging
            log_full_command([self.winws_exe] + resolved_args, strategy_name)

            # Start process
            self.running_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.DEVNULL,
                startupinfo=self._create_startup_info(),
                creationflags=CREATE_NO_WINDOW,
                cwd=self.work_dir
            )

            # Save info
            self.current_strategy_name = strategy_name
            self.current_strategy_args = resolved_args.copy()

            # Quick startup check
            time.sleep(0.2)

            if self.running_process.poll() is None:
                log(f"Strategy '{strategy_name}' started (PID: {self.running_process.pid})", "SUCCESS")
                # Start config file watcher for hot-reload
                self._start_config_watcher(preset_file)
                self._set_last_error(None)
                return True
            else:
                exit_code = self.running_process.returncode
                log(f"Strategy '{strategy_name}' exited immediately (code: {exit_code})", "ERROR")

                stderr_output = ""
                try:
                    stderr_output = self.running_process.stderr.read().decode('utf-8', errors='ignore')
                    if stderr_output:
                        log(f"Error: {stderr_output[:500]}", "ERROR")
                except:
                    pass

                from dpi.process_health_check import diagnose_winws_exit
                diag = diagnose_winws_exit(exit_code, stderr_output)
                if diag:
                    prefix = f"[AUTOFIX:{diag.auto_fix}]" if diag.auto_fix else ""
                    self._set_last_error(f"{prefix}{diag.cause}. {diag.solution}")
                    log(f"Diagnosis: {diag.cause} | Fix: {diag.solution} | auto_fix={diag.auto_fix}", "INFO")
                else:
                    first_line = ""
                    try:
                        first_line = next((ln.strip() for ln in (stderr_output or "").splitlines() if ln.strip()), "")
                    except Exception:
                        first_line = ""
                    if first_line:
                        self._set_last_error(f"winws завершился сразу (код {exit_code}): {first_line[:200]}")
                    else:
                        self._set_last_error(f"winws завершился сразу (код {exit_code})")

                self.running_process = None
                self.current_strategy_name = None
                self.current_strategy_args = None

                # System-level errors — don't retry
                if self._is_windivert_system_error(stderr_output, exit_code):
                    log("WinDivert system error — retry will not help", "WARNING")
                    return False

                # Retryable conflict
                if self._is_windivert_conflict_error(stderr_output, exit_code) and _retry_count < MAX_RETRIES:
                    log(f"Detected WinDivert conflict, automatic retry ({_retry_count + 1}/{MAX_RETRIES})...", "INFO")
                    return self.start_strategy_custom(custom_args, strategy_name, _retry_count + 1)

                if not diag:
                    causes = check_common_crash_causes()
                    if causes:
                        log("Possible causes:", "INFO")
                        for line in causes.split('\n')[:5]:
                            log(f"  {line}", "INFO")

                return False

        except Exception as e:
            diagnosis = diagnose_startup_error(e, self.winws_exe)
            for line in diagnosis.split('\n'):
                log(line, "ERROR")

            try:
                self._set_last_error(diagnosis.split("\n")[0].strip())
            except Exception:
                self._set_last_error(None)

            import traceback
            log(traceback.format_exc(), "DEBUG")
            self.running_process = None
            self.current_strategy_name = None
            self.current_strategy_args = None
            return False

    def start_from_preset_file(self, preset_path: str, strategy_name: str = "Preset", _retry_count: int = 0) -> bool:
        """
        Starts strategy directly from an existing preset file via @file syntax.

        Unlike the old approach, does NOT re-parse/rewrite the file.
        Preset file must already contain resolved paths (lists/X, bin/X).
        """
        MAX_RETRIES = 2

        if not os.path.exists(preset_path):
            # Self-healing: try to create default preset
            log(f"Preset file not found: {preset_path}, attempting auto-create...", "WARNING")
            try:
                from core.services import get_direct_flow_coordinator

                get_direct_flow_coordinator().ensure_runtime("direct_zapret1")
                if not os.path.exists(preset_path):
                    get_direct_flow_coordinator().select_preset("direct_zapret1", "Default")
                if os.path.exists(preset_path):
                    log(f"Auto-created preset file: {preset_path}", "INFO")
            except Exception as e:
                log(f"Auto-create failed: {e}", "WARNING")

        if not os.path.exists(preset_path):
            log(f"Preset file not found: {preset_path}", "ERROR")
            self._set_last_error(f"Preset файл не найден: {preset_path}")
            return False

        self._set_last_error(None)

        try:
            # Stop previous process
            if self.running_process and self.is_running():
                log("Stopping previous process before starting new one", "INFO")
                self.stop()

            from utils.process_killer import kill_winws_force

            if _retry_count > 0:
                self._aggressive_windivert_cleanup()
            else:
                log("Cleaning up previous winws processes...", "DEBUG")
                kill_winws_force()
                self._fast_cleanup_services()

                try:
                    from utils.service_manager import unload_driver
                    for driver in ["WinDivert", "WinDivert14", "WinDivert64", "Monkey"]:
                        try:
                            unload_driver(driver)
                        except Exception:
                            pass
                except Exception:
                    pass

                time.sleep(0.3)

            # Self-healing: verify winws.exe still exists
            if not os.path.exists(self.winws_exe):
                log(f"winws.exe disappeared: {self.winws_exe}", "ERROR")
                self._set_last_error(f"winws.exe не найден: {self.winws_exe}")
                return False

            # Store preset file path for hot-reload
            self._preset_file_path = preset_path

            # Build command with @file
            cmd = [self.winws_exe, f"@{preset_path}"]

            log(f"Starting from preset file: {preset_path}", "INFO")
            log(f"Strategy: {strategy_name}" + (f" (attempt {_retry_count + 1})" if _retry_count > 0 else ""), "INFO")

            # Start process
            self.running_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.DEVNULL,
                startupinfo=self._create_startup_info(),
                creationflags=CREATE_NO_WINDOW,
                cwd=self.work_dir
            )

            # Save info
            self.current_strategy_name = strategy_name
            self.current_strategy_args = [f"@{preset_path}"]

            # Quick startup check
            time.sleep(0.2)

            if self.running_process.poll() is None:
                log(f"Strategy '{strategy_name}' started from preset (PID: {self.running_process.pid})", "SUCCESS")
                self._start_config_watcher(preset_path)
                self._set_last_error(None)
                return True
            else:
                exit_code = self.running_process.returncode
                log(f"Strategy '{strategy_name}' exited immediately (code: {exit_code})", "ERROR")

                stderr_output = ""
                try:
                    stderr_output = self.running_process.stderr.read().decode('utf-8', errors='ignore')
                    if stderr_output:
                        log(f"Error: {stderr_output[:500]}", "ERROR")
                except Exception:
                    pass

                from dpi.process_health_check import diagnose_winws_exit
                diag = diagnose_winws_exit(exit_code, stderr_output)
                if diag:
                    prefix = f"[AUTOFIX:{diag.auto_fix}]" if diag.auto_fix else ""
                    self._set_last_error(f"{prefix}{diag.cause}. {diag.solution}")
                    log(f"Diagnosis: {diag.cause} | Fix: {diag.solution} | auto_fix={diag.auto_fix}", "INFO")
                else:
                    first_line = ""
                    try:
                        first_line = next((ln.strip() for ln in (stderr_output or "").splitlines() if ln.strip()), "")
                    except Exception:
                        first_line = ""
                    if first_line:
                        self._set_last_error(f"winws завершился сразу (код {exit_code}): {first_line[:200]}")
                    else:
                        self._set_last_error(f"winws завершился сразу (код {exit_code})")

                self.running_process = None
                self.current_strategy_name = None
                self.current_strategy_args = None

                # System-level errors — don't retry
                if self._is_windivert_system_error(stderr_output, exit_code):
                    log("WinDivert system error — retry will not help", "WARNING")
                    return False

                # Retryable conflict
                if self._is_windivert_conflict_error(stderr_output, exit_code) and _retry_count < MAX_RETRIES:
                    log(f"Detected WinDivert conflict, automatic retry ({_retry_count + 1}/{MAX_RETRIES})...", "INFO")
                    return self.start_from_preset_file(preset_path, strategy_name, _retry_count + 1)

                if not diag:
                    causes = check_common_crash_causes()
                    if causes:
                        log("Possible causes:", "INFO")
                        for line in causes.split('\n')[:5]:
                            log(f"  {line}", "INFO")

                return False

        except Exception as e:
            diagnosis = diagnose_startup_error(e, self.winws_exe)
            for line in diagnosis.split('\n'):
                log(line, "ERROR")

            try:
                self._set_last_error(diagnosis.split("\n")[0].strip())
            except Exception:
                self._set_last_error(None)

            import traceback
            log(traceback.format_exc(), "DEBUG")
            self.running_process = None
            self.current_strategy_name = None
            self.current_strategy_args = None
            return False

    def stop(self) -> bool:
        """Stops running process"""
        try:
            # Stop config file watcher
            if self._config_watcher:
                self._config_watcher.stop()
                self._config_watcher = None

            success = True

            if self.running_process and self.is_running():
                pid = self.running_process.pid
                strategy_name = self.current_strategy_name or "unknown"

                log(f"Stopping strategy '{strategy_name}' (PID: {pid})", "INFO")

                # Soft stop
                self.running_process.terminate()

                try:
                    self.running_process.wait(timeout=5)
                    log(f"Process stopped (PID: {pid})", "SUCCESS")
                except subprocess.TimeoutExpired:
                    log("Soft stop failed, using force kill", "WARNING")
                    self.running_process.kill()
                    self.running_process.wait()
                    log(f"Process forcefully terminated (PID: {pid})", "SUCCESS")
            else:
                log("No running process to stop", "INFO")

            # Additional cleanup
            self._stop_windivert_service()
            self._stop_monkey_service()
            self._kill_all_winws_processes()

            # Clear state
            self.running_process = None
            self.current_strategy_name = None
            self.current_strategy_args = None

            return success

        except Exception as e:
            log(f"Error stopping process: {e}", "ERROR")
            return False

    def is_running(self) -> bool:
        """Checks if process is running"""
        if not self.running_process:
            return False

        poll_result = self.running_process.poll()
        is_running = poll_result is None

        if not is_running and self.current_strategy_name:
            log(f"Strategy process exited (code: {poll_result})", "WARNING")

        return is_running

    def get_current_strategy_info(self) -> dict:
        """Returns information about current running strategy"""
        if not self.is_running():
            return {}

        return {
            'name': self.current_strategy_name,
            'pid': self.running_process.pid if self.running_process else None,
            'args_count': len(self.current_strategy_args) if self.current_strategy_args else 0
        }

    def get_process(self) -> Optional[subprocess.Popen]:
        """Returns current running process for output reading"""
        if self.is_running():
            return self.running_process
        return None


# Global instance
_strategy_runner_v1_instance: Optional[StrategyRunnerV1] = None


def get_strategy_runner_v1(winws_exe_path: str) -> StrategyRunnerV1:
    """Gets or creates global StrategyRunnerV1 instance.

    IMPORTANT: Recreates runner if different exe requested (mode switch).
    """
    global _strategy_runner_v1_instance

    # Recreate runner if exe changed (mode switch)
    if _strategy_runner_v1_instance is not None:
        if _strategy_runner_v1_instance.winws_exe != winws_exe_path:
            log(f"Exe change: {_strategy_runner_v1_instance.winws_exe} -> {winws_exe_path}", "INFO")
            _strategy_runner_v1_instance = None

    if _strategy_runner_v1_instance is None:
        _strategy_runner_v1_instance = StrategyRunnerV1(winws_exe_path)
    return _strategy_runner_v1_instance


def reset_strategy_runner_v1():
    """Resets global instance (synchronously stops process)"""
    global _strategy_runner_v1_instance
    if _strategy_runner_v1_instance:
        _strategy_runner_v1_instance.stop()
    _strategy_runner_v1_instance = None


def invalidate_strategy_runner_v1():
    """Marks runner for recreation without synchronous stop.
    Used when switching launch method - UI updates instantly,
    old process will be stopped on next DPI start."""
    global _strategy_runner_v1_instance
    _strategy_runner_v1_instance = None


def get_current_runner_v1() -> Optional[StrategyRunnerV1]:
    """Returns current runner instance without creating new one"""
    return _strategy_runner_v1_instance
