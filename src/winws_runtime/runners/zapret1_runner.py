# winws_runtime/runners/zapret1_runner.py
"""
Strategy runner for Zapret 1 (winws.exe).

Preset changes are applied by the runtime preset coordinator. The runner only
starts, stops, and switches to the concrete preset file it is given.
"""

import os
import hashlib
import shlex
import subprocess
import threading
import time
from typing import Optional
from log.log import log

from settings.mode import EXE_NAME_WINWS1, ZAPRET1_MODE

from .constants import CREATE_NO_WINDOW
from .runner_base import StrategyRunnerBase
from .preset_runner_support import (
    PreparedPresetArtifact,
    PresetRunnerState,
    PresetRunnerStateMachine,
    launch_args_from_preset_text,
    is_process_alive_with_expected_name,
    preset_cache_key,
    prune_at_config_cache,
    remember_cache_entry,
    wait_for_process_exit,
    wait_for_process_stable_start,
)
from winws_runtime.health.process_health_check import (
    check_common_crash_causes,
    diagnose_startup_error
)
from winws_runtime.runtime.system_ops import get_process_pids_by_name


class Winws1StrategyRunner(StrategyRunnerBase):
    """
    Runner for Zapret 1 (winws.exe).
    Simple version without Lua functionality.
    """

    def __init__(self, winws_exe_path: str):
        """
        Args:
            winws_exe_path: Path to winws.exe
        """
        super().__init__(winws_exe_path)
        # Human-readable last start error (for UI/status).
        self.last_error: Optional[str] = None
        self._preset_file_path: Optional[str] = None
        self._prepared_preset_cache: dict[tuple[str, int, int], PreparedPresetArtifact] = {}
        self._state_lock = threading.RLock()
        self._runner_state = PresetRunnerStateMachine()
        self._last_spawn_exit_code: Optional[int] = None
        self._last_spawn_stderr: str = ""

    def _set_last_error(self, message: Optional[str], *, notify: bool = True) -> None:
        try:
            text = str(message or "").strip()
        except Exception:
            text = ""
        self.last_error = text or None
        if text and notify:
            self.notify_launch_error(text)

    def get_runner_state_snapshot(self):
        with self._state_lock:
            return self._runner_state.snapshot()

    def _set_runner_state_locked(
        self,
        state: PresetRunnerState,
        *,
        preset_path: str = "",
        strategy_name: str = "",
        pid: int | None = None,
        error: str = "",
        reason: str = "",
        allow_same: bool = False,
        publish_failure: bool = True,
    ):
        snapshot = self._runner_state.transition(
            state,
            preset_path=preset_path,
            strategy_name=strategy_name,
            pid=pid,
            error=error,
            reason=reason,
            allow_same=allow_same,
        )
        log(
            f"Runner state: {snapshot.state.value} "
            f"(gen={snapshot.generation}, reason={snapshot.reason}, preset={snapshot.preset_path})",
            "DEBUG",
        )
        if state == PresetRunnerState.FAILED and publish_failure:
            self.publish_runner_failure(
                launch_method=ZAPRET1_MODE,
                error=error,
            )
        return snapshot

    def _compile_preset_artifact(self, preset_path: str) -> PreparedPresetArtifact:
        p = str(preset_path or "").strip()
        if not p:
            return PreparedPresetArtifact("", None, "", tuple(), False, "Не указан путь к preset файлу")
        if not os.path.exists(p):
            return PreparedPresetArtifact(p, None, "", tuple(), False, f"Preset файл не найден: {p}")

        for _attempt in range(2):
            cache_key = preset_cache_key(p)
            if cache_key is not None:
                with self._state_lock:
                    cached = self._prepared_preset_cache.get(cache_key)
                if cached is not None and self._launch_args_files_exist(cached.launch_args):
                    return cached

            try:
                with open(p, "r", encoding="utf-8", errors="replace") as f:
                    source_text = f.read()
            except Exception as e:
                return PreparedPresetArtifact(p, None, "", tuple(), False, f"Не удалось прочитать preset файл: {e}")

            try:
                at_config_path = self._write_winws1_at_config(p, source_text)
            except Exception as e:
                return PreparedPresetArtifact(
                    preset_path=p,
                    cache_key=cache_key,
                    normalized_text="",
                    launch_args=tuple(),
                    validation_ok=False,
                    validation_report=f"Не удалось подготовить preset файл: {e}",
                )

            artifact = PreparedPresetArtifact(
                preset_path=p,
                cache_key=cache_key,
                normalized_text=source_text,
                launch_args=(f"@{at_config_path}",),
                validation_ok=True,
                validation_report="",
            )

            final_cache_key = preset_cache_key(p)
            if cache_key is not None and final_cache_key == cache_key:
                with self._state_lock:
                    remember_cache_entry(self._prepared_preset_cache, cache_key, artifact)
                return artifact

        return artifact

    def stop_background_watchers(self) -> None:
        return None

    def _stop_process_only_locked(self) -> None:
        """Stops only the current winws.exe process without heavy driver/service cleanup."""
        try:
            cleanup_needed = False
            if self.running_process and self.is_running():
                pid = self.running_process.pid
                strategy_name = self.current_launch_label or "unknown"
                self._set_runner_state_locked(
                    PresetRunnerState.STOPPING,
                    preset_path=str(self._preset_file_path or ""),
                    strategy_name=str(strategy_name),
                    pid=pid,
                    reason="stop_process_only",
                )
                log(f"Fast switch: stopping '{strategy_name}' (PID: {pid})", "INFO")

                self.running_process.terminate()
                if not wait_for_process_exit(self.running_process, timeout=3.0):
                    log("Fast switch: soft stop timeout, force killing", "WARNING")
                    self.running_process.kill()
                    cleanup_needed = not wait_for_process_exit(self.running_process, timeout=1.0)

                self.running_process = None
                self._set_runner_state_locked(
                    PresetRunnerState.IDLE,
                    preset_path=str(self._preset_file_path or ""),
                    strategy_name=str(strategy_name),
                    reason="stop_completed",
                )

                if not cleanup_needed:
                    try:
                        cleanup_needed = bool(get_process_pids_by_name(os.path.basename(self.winws_exe)))
                    except Exception:
                        cleanup_needed = False

            if cleanup_needed:
                log("Fast switch fallback cleanup: detected lingering winws process", "DEBUG")
                self._kill_all_winws_processes()
        except Exception as e:
            log(f"Fast switch: error stopping process: {e}", "ERROR")

    def _clear_process_state_locked(self) -> None:
        self.running_process = None
        self.current_launch_label = None
        self.current_strategy_args = None

    def _spawn_readiness_check_locked(self, process: subprocess.Popen) -> bool:
        try:
            pid = int(process.pid)
        except Exception:
            return False
        return is_process_alive_with_expected_name(pid, self.winws_exe)

    def _refresh_artifact_if_source_changed_locked(
        self,
        artifact: PreparedPresetArtifact,
    ) -> PreparedPresetArtifact:
        artifact_key = getattr(artifact, "cache_key", None)
        if artifact_key is None:
            return artifact

        current_key = preset_cache_key(artifact.preset_path)
        if current_key == artifact_key:
            return artifact

        log(
            f"Preset changed before winws spawn, rebuilding launch args: {artifact.preset_path}",
            "INFO",
        )
        return self._compile_preset_artifact(artifact.preset_path)

    def _build_winws1_at_config_text(self, source_text: str) -> str:
        args = self._resolve_file_paths(launch_args_from_preset_text(source_text))
        if not args:
            return ""
        return "\n".join(shlex.quote(arg) for arg in args) + "\n"

    def _winws1_at_config_dir(self) -> str:
        return os.path.join(str(self.work_dir or ""), "tmp", "winws1_at_config")

    def _write_winws1_at_config(self, preset_path: str, source_text: str) -> str:
        config_text = self._build_winws1_at_config_text(source_text)
        digest_source = f"{os.path.abspath(str(preset_path or ''))}\0{config_text}".encode("utf-8", "surrogatepass")
        digest = hashlib.sha1(digest_source).hexdigest()[:20]
        config_dir = self._winws1_at_config_dir()
        os.makedirs(config_dir, exist_ok=True)
        config_path = os.path.join(config_dir, f"winws1_at_{digest}.txt")

        try:
            with open(config_path, "r", encoding="utf-8", errors="replace") as f:
                if f.read() == config_text:
                    prune_at_config_cache(config_dir, config_path, filename_prefix="winws1_")
                    return config_path
        except FileNotFoundError:
            pass
        except Exception:
            pass

        with open(config_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(config_text)
        prune_at_config_cache(config_dir, config_path, filename_prefix="winws1_")
        return config_path

    def _write_winws1_dry_run_at_config(self, artifact: PreparedPresetArtifact) -> str:
        launch_arg = str((artifact.launch_args or ("",))[0] or "")
        if not launch_arg.startswith("@") or len(launch_arg) <= 1:
            raise ValueError("Zapret 1 dry-run requires an @config launch artifact")

        source_config_path = launch_arg[1:]
        with open(source_config_path, "r", encoding="utf-8", errors="replace") as f:
            config_text = f.read()
        if "--dry-run" not in {line.strip() for line in config_text.splitlines()}:
            config_text = config_text.rstrip("\r\n") + "\n--dry-run\n"

        digest_source = f"{os.path.abspath(source_config_path)}\0{config_text}".encode(
            "utf-8",
            "surrogatepass",
        )
        digest = hashlib.sha1(digest_source).hexdigest()[:20]
        config_dir = self._winws1_at_config_dir()
        os.makedirs(config_dir, exist_ok=True)
        config_path = os.path.join(config_dir, f"winws1_dry_run_{digest}.txt")

        try:
            with open(config_path, "r", encoding="utf-8", errors="replace") as f:
                if f.read() == config_text:
                    prune_at_config_cache(config_dir, config_path, filename_prefix="winws1_")
                    return config_path
        except FileNotFoundError:
            pass
        except Exception:
            pass

        with open(config_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(config_text)
        prune_at_config_cache(config_dir, config_path, filename_prefix="winws1_")
        return config_path

    def _run_preset_dry_run_locked(
        self,
        artifact: PreparedPresetArtifact,
        *,
        notify_failure: bool = True,
    ) -> bool:
        missing_dlls = self._get_missing_windows_system_dependencies()
        if missing_dlls:
            message = self._format_missing_windows_system_dependency_error(missing_dlls)
            self._last_spawn_exit_code = -1
            self._last_spawn_stderr = message
            self._set_last_error(message, notify=False)
            log(message, "WARNING")
            return False

        try:
            dry_run_config_path = self._write_winws1_dry_run_at_config(artifact)
            completed = subprocess.run(
                [self.winws_exe, f"@{dry_run_config_path}"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.DEVNULL,
                startupinfo=self._create_startup_info(),
                creationflags=CREATE_NO_WINDOW,
                cwd=self.work_dir,
                timeout=8.0,
            )
        except subprocess.TimeoutExpired:
            message = "Проверка preset для winws зависла"
            self._last_spawn_exit_code = -1
            self._last_spawn_stderr = message
            self._set_last_error(message, notify=False)
            log(message, "WARNING")
            return False
        except Exception as e:
            message = f"Не удалось проверить preset перед запуском: {e}"
            self._last_spawn_exit_code = -1
            self._last_spawn_stderr = message
            self._set_last_error(message, notify=False)
            log(message, "WARNING")
            return False

        output = self._decode_dry_run_output(completed.stdout, completed.stderr)
        self._last_spawn_exit_code = int(completed.returncode)
        self._last_spawn_stderr = output
        if completed.returncode == 0:
            return True

        first_line = next((line.strip() for line in output.splitlines() if line.strip()), "")
        detail = f": {first_line[:200]}" if first_line else ""
        message = f"Проверка preset для winws не прошла (код {completed.returncode}){detail}"
        self._set_last_error(message, notify=False)
        if output:
            log(f"Winws1 dry-run error: {output[:500]}", "WARNING")
        else:
            log(message, "WARNING")
        return False

    @staticmethod
    def _decode_dry_run_output(stdout_data, stderr_data) -> str:
        data = b""
        for chunk in (stdout_data, stderr_data):
            if isinstance(chunk, bytes):
                data += chunk
            elif chunk:
                data += str(chunk).encode("utf-8", errors="replace")
        return data.decode("utf-8", errors="replace").strip()

    @staticmethod
    def _launch_args_files_exist(launch_args: tuple[str, ...]) -> bool:
        if not launch_args:
            return False
        for arg in launch_args:
            value = str(arg or "")
            if value.startswith("@") and len(value) > 1 and not os.path.exists(value[1:]):
                return False
        return True

    def _spawn_process_locked(
        self,
        artifact: PreparedPresetArtifact,
        strategy_name: str,
        *,
        notify_failure: bool = True,
        stable_start_window_seconds: float = 1.0,
    ) -> bool:
        """One quiet spawn attempt (see Winws2StrategyRunner._spawn_process_locked).

        Failure details go to `_last_spawn_exit_code` / `_last_spawn_stderr` and
        `last_error`; user-facing publication happens once at the operation level.
        `notify_failure` is kept for signature compatibility only.
        """
        if not artifact.launch_args:
            self._set_last_error(
                "Не удалось подготовить аргументы запуска из preset файла",
                notify=False,
            )
            return False

        try:
            cmd = [self.winws_exe, *artifact.launch_args]
            self._set_runner_state_locked(
                PresetRunnerState.STARTING,
                preset_path=artifact.preset_path,
                strategy_name=strategy_name,
                reason="start_from_preset",
            )
            self.running_process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                startupinfo=self._create_startup_info(),
                creationflags=CREATE_NO_WINDOW,
                cwd=self.work_dir
            )

            self.current_launch_label = strategy_name
            self.current_strategy_args = list(artifact.launch_args)
            self._last_spawn_exit_code = None
            self._last_spawn_stderr = ""

            if wait_for_process_stable_start(
                self.running_process,
                readiness_check=lambda: self._spawn_readiness_check_locked(self.running_process),
                stable_window=stable_start_window_seconds,
            ):
                self._set_runner_state_locked(
                    PresetRunnerState.RUNNING,
                    preset_path=artifact.preset_path,
                    strategy_name=strategy_name,
                    pid=self.running_process.pid,
                    reason="start_confirmed",
                )
                log(
                    f"Strategy '{strategy_name}' started from preset (PID: {self.running_process.pid})",
                    "SUCCESS",
                )
                self._set_last_error(None)
                self._start_process_exit_watcher(self.running_process)
                return True

            exit_code = self.running_process.returncode
            # A single failed attempt is not yet a failed operation: retries may
            # follow, so log at WARNING and defer user-facing publication to
            # _publish_final_launch_failure at the end of the whole operation.
            stderr_output = self._read_process_startup_output(self.running_process)
            if stderr_output:
                log(f"Error: {stderr_output[:500]}", "WARNING")

            self._last_spawn_exit_code = int(exit_code)
            self._last_spawn_stderr = str(stderr_output or "")
            log(f"Strategy '{strategy_name}' exited immediately (code: {exit_code})", "WARNING")
            self._set_runner_state_locked(
                PresetRunnerState.FAILED,
                preset_path=artifact.preset_path,
                strategy_name=strategy_name,
                error=str(stderr_output or ""),
                reason="process_exited_during_start",
                publish_failure=False,
            )

            from winws_runtime.health.process_health_check import diagnose_winws_exit

            diag = diagnose_winws_exit(exit_code, stderr_output)
            if diag:
                prefix = f"[AUTOFIX:{diag.auto_fix}]" if diag.auto_fix else ""
                self._set_last_error(f"{prefix}{diag.cause}. {diag.solution}", notify=False)
                log(f"Diagnosis: {diag.cause} | Fix: {diag.solution} | auto_fix={diag.auto_fix}", "INFO")
            else:
                first_line = ""
                try:
                    first_line = next((ln.strip() for ln in (stderr_output or "").splitlines() if ln.strip()), "")
                except Exception:
                    first_line = ""
                if first_line:
                    self._set_last_error(
                        f"winws завершился сразу (код {exit_code}): {first_line[:200]}",
                        notify=False,
                    )
                else:
                    self._set_last_error(f"winws завершился сразу (код {exit_code})", notify=False)

            self._clear_process_state_locked()
            return False
        except Exception as e:
            diagnosis = diagnose_startup_error(e, self.winws_exe)
            for line in diagnosis.split('\n'):
                log(line, "WARNING")
            try:
                self._set_last_error(diagnosis.split("\n")[0].strip(), notify=False)
            except Exception:
                self._set_last_error(None, notify=False)
            self._set_runner_state_locked(
                PresetRunnerState.FAILED,
                preset_path=artifact.preset_path,
                strategy_name=strategy_name,
                error=diagnosis.split("\n")[0].strip(),
                reason="spawn_exception",
                publish_failure=False,
            )
            import traceback
            log(traceback.format_exc(), "DEBUG")
            self._clear_process_state_locked()
            return False

    def switch_preset_file_fast(self, preset_path: str, strategy_name: str = "Preset", *, is_current=None) -> bool:
        """Fast path for switching running preset mode without full start pipeline."""
        if not os.path.exists(preset_path):
            log(f"Fast switch preset file not found: {preset_path}", "ERROR")
            self._set_last_error(f"Preset файл не найден: {preset_path}", notify=False)
            return False

        self._set_last_error(None)

        with self._state_lock:
            artifact = self._compile_preset_artifact(preset_path)
            if not artifact.validation_ok:
                self._set_runner_state_locked(
                    PresetRunnerState.FAILED,
                    preset_path=preset_path,
                    strategy_name=strategy_name,
                    error=artifact.validation_report,
                    reason="manual_switch_compile_failed",
                    publish_failure=False,
                )
                self._set_last_error(artifact.validation_report, notify=False)
                return False

            if callable(is_current) and not bool(is_current()):
                log("Fast preset switch skipped before stop: request is stale", "DEBUG")
                return True

            if self.running_process and self.is_running():
                self._stop_process_only_locked()

            artifact = self._refresh_artifact_if_source_changed_locked(artifact)
            if not artifact.validation_ok:
                self._set_runner_state_locked(
                    PresetRunnerState.FAILED,
                    preset_path=preset_path,
                    strategy_name=strategy_name,
                    error=artifact.validation_report,
                    reason="manual_switch_recompile_failed",
                    publish_failure=False,
                )
                self._set_last_error(artifact.validation_report, notify=False)
                return False

            if callable(is_current) and not bool(is_current()):
                log("Fast preset switch skipped before spawn: request is stale", "DEBUG")
                return True

            self._preset_file_path = preset_path
            success = self._spawn_process_locked(artifact, strategy_name, notify_failure=False)
            if not success:
                success = self._retry_fast_switch_after_failed_spawn_locked(
                    artifact,
                    strategy_name,
                )
        return success

    def _cleanup_before_fast_switch_retry_locked(self) -> None:
        """Hook: winws1 исторически чистит через _prepare_cleanup_before_spawn_locked."""
        self._prepare_cleanup_before_spawn_locked(retry_count=1)

    def _spawn_fast_switch_retry_locked(self, artifact: PreparedPresetArtifact, strategy_name: str) -> bool:
        """Hook общего fast-switch retry: обычный spawn winws."""
        return bool(self._spawn_process_locked(artifact, strategy_name, notify_failure=False))

    def start_from_preset_file(
        self,
        preset_path: str,
        strategy_name: str = "Preset",
        _retry_count: int = 0,
        _stable_start_window_seconds: float = 1.0,
    ) -> bool:
        """
        Запускает движок Zapret 1 из выбранного preset-файла.

        Это основной путь для обычного запуска zapret1_mode.
        """
        max_retries = 2

        if not os.path.exists(preset_path):
            log(f"Preset file not found: {preset_path}", "WARNING")
            self._set_last_error(f"Preset файл не найден: {preset_path}", notify=False)
            self._publish_final_launch_failure(
                launch_method=ZAPRET1_MODE,
                fallback_message=f"{EXE_NAME_WINWS1} не запустился",
            )
            return False

        self._set_last_error(None)

        with self._state_lock:
            success = self._start_from_preset_file_locked(
                preset_path,
                strategy_name,
                retry_count=int(_retry_count),
                max_retries=int(max_retries),
                stable_start_window_seconds=float(_stable_start_window_seconds),
            )

        if not success:
            # Single user-facing publication for the whole operation,
            # after every retry inside the locked flow has been exhausted.
            self._publish_final_launch_failure(
                launch_method=ZAPRET1_MODE,
                fallback_message=f"{EXE_NAME_WINWS1} не запустился",
            )
        return success

    def _prepare_cleanup_before_spawn_locked(self, *, retry_count: int) -> None:
        if retry_count > 0:
            self._aggressive_windivert_cleanup()
            self._wait_after_aggressive_windivert_cleanup()
        else:
            self._perform_standard_windivert_cleanup()

    def _relaunch_after_failed_spawn_locked(
        self,
        preset_path: str,
        strategy_name: str,
        *,
        retry_count: int,
        stable_start_window_seconds: float,
        max_retries: int,
    ) -> bool:
        """Hook общей retry-оркестрации: повторный запуск winws1."""
        return self._start_from_preset_file_locked(
            preset_path,
            strategy_name,
            retry_count=retry_count + 1,
            max_retries=max_retries,
            stable_start_window_seconds=stable_start_window_seconds,
        )

    def _retry_hook_after_transient_locked(
        self,
        preset_path: str,
        strategy_name: str,
        *,
        exit_code: int,
        stderr_output: str,
        retry_count: int,
        stable_start_window_seconds: float,
        max_retries: int,
    ):
        """Hook: winws1 повторяет неклассифицированный код 1 без вывода один раз."""
        if self._should_retry_unclassified_code_one(exit_code, stderr_output, retry_count=retry_count):
            log(
                "Winws1 exited with code 1 without diagnostic output after dry-run passed; retrying once",
                "WARNING",
            )
            return self._relaunch_after_failed_spawn_locked(
                preset_path,
                strategy_name,
                retry_count=retry_count,
                stable_start_window_seconds=stable_start_window_seconds,
                max_retries=max_retries,
            )
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
        max_retries: int,
    ) -> bool:
        """Hook: conflict-ретрай winws1 ограничен max_retries; в конце — подсказки."""
        if self._is_windivert_conflict_error(stderr_output, exit_code) and retry_count < max_retries:
            log(f"Detected WinDivert conflict, automatic retry ({retry_count + 1}/{max_retries})...", "INFO")
            return self._relaunch_after_failed_spawn_locked(
                preset_path,
                strategy_name,
                retry_count=retry_count,
                stable_start_window_seconds=stable_start_window_seconds,
                max_retries=max_retries,
            )

        causes = check_common_crash_causes()
        if causes:
            log("Possible causes:", "INFO")
            for line in causes.split('\n')[:5]:
                log(f"  {line}", "INFO")

        return False

    @staticmethod
    def _should_retry_unclassified_code_one(exit_code: int, stderr_output: str, *, retry_count: int) -> bool:
        if retry_count >= 1:
            return False
        if int(exit_code) != 1:
            return False
        return not str(stderr_output or "").strip()

    def _start_from_preset_file_locked(
        self,
        preset_path: str,
        strategy_name: str,
        *,
        retry_count: int,
        max_retries: int,
        stable_start_window_seconds: float = 1.0,
    ) -> bool:
        artifact = self._compile_preset_artifact(preset_path)
        if not artifact.validation_ok:
            self._set_runner_state_locked(
                PresetRunnerState.FAILED,
                preset_path=preset_path,
                strategy_name=strategy_name,
                error=artifact.validation_report,
                reason="launch_compile_failed",
                publish_failure=False,
            )
            self._set_last_error(artifact.validation_report, notify=False)
            return False

        if self.running_process and self.is_running():
            log("Stopping previous process before starting new one", "INFO")
            self._stop_process_only_locked()

        self._prepare_cleanup_before_spawn_locked(retry_count=retry_count)
        if not self._ensure_windivert_ready_before_spawn():
            return self._fail_spawn_for_windivert_readiness(context="spawn")

        if not os.path.exists(self.winws_exe):
            log(f"{EXE_NAME_WINWS1} disappeared: {self.winws_exe}", "WARNING")
            self._set_last_error(f"{EXE_NAME_WINWS1} не найден: {self.winws_exe}", notify=False)
            return False

        if not self._run_preset_dry_run_locked(artifact):
            return False

        self._preset_file_path = preset_path
        success = self._spawn_process_locked(
            artifact,
            strategy_name,
            stable_start_window_seconds=stable_start_window_seconds,
        )
        if success:
            return True

        return self._maybe_retry_after_failed_spawn_locked(
            preset_path,
            strategy_name,
            retry_count=retry_count,
            max_retries=max_retries,
            stable_start_window_seconds=stable_start_window_seconds,
        )

    def stop(self, *, cleanup_services: bool = True) -> bool:
        """Stops the running winws.exe process."""
        with self._state_lock:
            if self.running_process and self.is_running():
                self._set_runner_state_locked(
                    PresetRunnerState.STOPPING,
                    preset_path=str(self._preset_file_path or ""),
                    strategy_name=str(self.current_launch_label or ""),
                    pid=self.running_process.pid,
                    reason="public_stop",
                )
            self._preset_file_path = None
            success = super().stop(cleanup_services=cleanup_services)
            self._set_runner_state_locked(
                PresetRunnerState.IDLE,
                reason="public_stop_completed",
                allow_same=True,
            )
            return success
