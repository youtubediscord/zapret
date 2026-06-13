# winws_runtime/runners/zapret2_runner.py
"""
Strategy runner for Zapret 2 (winws2.exe).

Preset changes are applied by the runtime preset coordinator. The runner only
starts, stops, and switches to the concrete preset file it is given.
"""

import hashlib
import os
import re
import shlex
import subprocess
import time
import threading
from typing import Optional

from log.log import log
from settings.mode import ENGINE_WINWS2, ZAPRET2_MODE

from .runner_base import StrategyRunnerBase, _ERROR_SERVICE_MARKED_FOR_DELETE
from .preset_runner_support import (
    PreparedPresetArtifact,
    PresetRunnerState,
    PresetRunnerStateMachine,
    is_process_alive_with_expected_name,
    launch_args_from_preset_text,
    preset_cache_key,
    prune_at_config_cache,
    remember_cache_entry,
    wait_for_process_exit,
    wait_for_process_stable_start,
)
from .constants import CREATE_NO_WINDOW
from winws_runtime.health.process_health_check import (
    diagnose_startup_error
)
from winws_runtime.runtime.system_ops import (
    find_stale_windivert_delete_pending_services_runtime,
    get_all_winws_process_pids,
    get_process_pids_by_name,
)


_WINDOWS_ABS_RE = re.compile(r"^(?:[A-Za-z]:[\\/]|\\\\)")
_STATUS_DLL_INIT_FAILED = 0xC0000142
_TRANSIENT_DRY_RUN_RETRY_DELAY_SEC = 0.75


def _is_windows_abs(path: str) -> bool:
    try:
        return bool(_WINDOWS_ABS_RE.match(str(path or "")))
    except Exception:
        return False


def _strip_outer_quotes(value: str) -> str:
    v = str(value or "").strip()
    if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
        v = v[1:-1]
    return v.strip()


class Winws2StrategyRunner(StrategyRunnerBase):
    """
    Runner for Zapret 2 (winws2.exe).

    Features:
    - Full Lua support
    - Uses winws2.exe executable
    """

    def __init__(self, winws_exe_path: str):
        """
        Initialize winws2 strategy runner.

        Args:
            winws_exe_path: Path to winws2.exe
        """
        super().__init__(winws_exe_path)
        self._preset_file_path: Optional[str] = None
        # Human-readable last start error (for UI/status).
        self.last_error: Optional[str] = None
        self._prepared_preset_cache: dict[tuple[str, int, int], PreparedPresetArtifact] = {}
        self._state_lock = threading.RLock()
        self._runner_state = PresetRunnerStateMachine()
        self._last_spawn_exit_code: Optional[int] = None
        self._last_spawn_stderr: str = ""

        log("Winws2StrategyRunner initialized", "INFO")

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
                launch_method=ZAPRET2_MODE,
                error=error,
            )
        return snapshot

    def validate_preset_file(self, preset_path: str) -> tuple[bool, str]:
        artifact = self._compile_preset_artifact(preset_path)
        return artifact.validation_ok, artifact.validation_report

    def _collect_missing_preset_references_from_text(self, content: str) -> list[tuple[str, str]]:
        """Returns list of (ref, expected_abs_path) for missing referenced files."""

        def _norm_slashes(s: str) -> str:
            return str(s or "").replace("\\", "/")

        def _resolve_candidates(raw_value: str, default_dir: Optional[str] = None) -> list[str]:
            v = str(raw_value or "").strip()
            if not v:
                return []

            # Some options allow @file values.
            if v.startswith("@"):
                v = v[1:].strip()

            v = _strip_outer_quotes(v)
            if not v:
                return []

            # Windows absolute should be detected even in non-Windows dev.
            if os.path.isabs(v) or _is_windows_abs(v):
                return [os.path.normpath(v)]

            # Relative with folders.
            if "/" in v or "\\" in v:
                return [os.path.normpath(os.path.join(self.work_dir, v))]

            # Bare filename: try default_dir first (lists/bin/lua), then work_dir.
            return [os.path.normpath(os.path.join(self.work_dir, v))]

        def _exists_any(paths: list[str]) -> bool:
            for p in paths:
                try:
                    if p and os.path.exists(p):
                        return True
                except Exception:
                    continue
            return False

        missing: list[tuple[str, str]] = []
        seen: set[str] = set()

        lists_dir = self.lists_dir
        bin_dir = self.bin_dir
        lua_dir = os.path.join(self.work_dir, "lua")
        filter_dir = os.path.join(self.work_dir, "windivert.filter")

        try:
            for raw in str(content or "").splitlines():
                line = (raw or "").strip()
                if not line or line.startswith("#"):
                    continue
                if "=" not in line:
                    continue

                key, _sep, value = line.partition("=")
                key_l = key.strip().lower()
                value_s = value.strip()

                # lists/*.txt
                if key_l in ("--hostlist", "--ipset", "--hostlist-exclude", "--ipset-exclude"):
                    candidates = _resolve_candidates(value_s, default_dir=lists_dir)
                    if candidates and (not _exists_any(candidates)):
                        ref = f"{key.strip()}={_norm_slashes(_strip_outer_quotes(value_s).lstrip('@'))}"
                        expected = candidates[0] if candidates else ""
                        k = ref.lower()
                        if k not in seen:
                            seen.add(k)
                            missing.append((ref, expected))
                    continue

                # lua/*.lua
                if key_l == "--lua-init":
                    candidates = _resolve_candidates(value_s, default_dir=lua_dir)
                    if candidates and (not _exists_any(candidates)):
                        ref = f"{key.strip()}={_norm_slashes(_strip_outer_quotes(value_s).lstrip('@'))}"
                        expected = candidates[0] if candidates else ""
                        k = ref.lower()
                        if k not in seen:
                            seen.add(k)
                            missing.append((ref, expected))
                    continue

                # windivert.filter/*
                if key_l == "--wf-raw-part":
                    candidates = _resolve_candidates(value_s, default_dir=filter_dir)
                    if candidates and (not _exists_any(candidates)):
                        ref = f"{key.strip()}={_norm_slashes(_strip_outer_quotes(value_s).lstrip('@'))}"
                        expected = candidates[0] if candidates else ""
                        k = ref.lower()
                        if k not in seen:
                            seen.add(k)
                            missing.append((ref, expected))
                    continue

                # Various bin-backed fake payload args (winws/winws2).
                if key_l in (
                    "--dpi-desync-fake-syndata",
                    "--dpi-desync-fake-tls",
                    "--dpi-desync-fake-quic",
                    "--dpi-desync-fake-unknown-udp",
                    "--dpi-desync-split-seqovl-pattern",
                    "--dpi-desync-fake-http",
                    "--dpi-desync-fake-unknown",
                    "--dpi-desync-fakedsplit-pattern",
                    "--dpi-desync-fake-discord",
                    "--dpi-desync-fake-stun",
                    "--dpi-desync-fake-dht",
                    "--dpi-desync-fake-wireguard",
                ):
                    special = _strip_outer_quotes(value_s.strip())
                    if special.startswith("@"):
                        special = special[1:].strip()
                    special = special.lower()
                    if special.startswith("0x") or special.startswith("!") or special.startswith("^"):
                        continue

                    # Only *.bin values are treated as file references here.
                    if not special.endswith(".bin"):
                        continue

                    candidates = _resolve_candidates(value_s, default_dir=bin_dir)
                    if candidates and (not _exists_any(candidates)):
                        ref = f"{key.strip()}={_norm_slashes(_strip_outer_quotes(value_s).lstrip('@'))}"
                        expected = candidates[0] if candidates else ""
                        k = ref.lower()
                        if k not in seen:
                            seen.add(k)
                            missing.append((ref, expected))
                    continue

                # --blob=name:@path or --blob=name:+offset@path
                if key_l == "--blob":
                    blob_value = _strip_outer_quotes(value_s)
                    if not blob_value or ":" not in blob_value:
                        continue

                    _name, _colon, tail = blob_value.partition(":")
                    tail = tail.strip()
                    if not tail:
                        continue

                    # Hex blobs / inline values.
                    if tail.lower().startswith("0x"):
                        continue

                    file_part = ""
                    if tail.startswith("@"):
                        file_part = tail[1:].strip()
                    elif tail.startswith("+"):
                        at_idx = tail.find("@")
                        if at_idx > 0 and at_idx < len(tail) - 1:
                            file_part = tail[at_idx + 1 :].strip()

                    if not file_part:
                        continue

                    candidates = _resolve_candidates(file_part, default_dir=bin_dir)
                    if candidates and (not _exists_any(candidates)):
                        ref = f"{key.strip()}={_norm_slashes(blob_value)}"
                        expected = candidates[0] if candidates else ""
                        k = ref.lower()
                        if k not in seen:
                            seen.add(k)
                            missing.append((ref, expected))
                    continue
        except Exception:
            return []

        return missing

    @staticmethod
    def _build_validation_report(missing: list[tuple[str, str]]) -> str:
        if not missing:
            return ""

        max_show = 15
        shown = missing[:max_show]
        hidden = len(missing) - len(shown)

        example = shown[0][0] if shown else ""
        if example:
            header = f"Preset содержит ссылки на отсутствующие файлы ({len(missing)}), например: {example}"
        else:
            header = f"Preset содержит ссылки на отсутствующие файлы ({len(missing)}):"

        lines: list[str] = [header]
        for ref, expected in shown:
            if expected:
                lines.append(f"- {ref}  (ожидается: {expected})")
            else:
                lines.append(f"- {ref}")
        if hidden > 0:
            lines.append(f"... и еще {hidden} файл(ов)")
        return "\n".join(lines)

    def _prepare_preset_text_for_launch(self, source_content: str) -> str:
        from winws_runtime.preset_launch_text import prepare_winws2_preset_text_for_launch

        source_is_circular = self._is_circular_preset_text(source_content)
        prepared = prepare_winws2_preset_text_for_launch(
            source_content,
            source_is_circular=source_is_circular,
        )
        return prepared.text

    def _build_winws2_at_config_text(self, prepared_text: str) -> str:
        args = launch_args_from_preset_text(prepared_text)
        if not args:
            return ""
        return "\n".join(shlex.quote(arg) for arg in args) + "\n"

    def _winws2_at_config_dir(self) -> str:
        return os.path.join(str(self.work_dir or ""), "tmp", "winws2_at_config")

    def _winws2_startup_output_dir(self) -> str:
        return os.path.join(str(self.work_dir or ""), "tmp", "winws2_startup_output")

    def _write_winws2_at_config(self, preset_path: str, prepared_text: str) -> str:
        config_text = self._build_winws2_at_config_text(prepared_text)
        digest_source = f"{os.path.abspath(str(preset_path or ''))}\0{config_text}".encode("utf-8", "surrogatepass")
        digest = hashlib.sha1(digest_source).hexdigest()[:20]
        config_dir = self._winws2_at_config_dir()
        os.makedirs(config_dir, exist_ok=True)
        config_path = os.path.join(config_dir, f"winws2_at_{digest}.txt")

        try:
            with open(config_path, "r", encoding="utf-8", errors="replace") as f:
                if f.read() == config_text:
                    prune_at_config_cache(config_dir, config_path, filename_prefix="winws2_at_")
                    return config_path
        except FileNotFoundError:
            pass
        except Exception:
            pass

        with open(config_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(config_text)
        prune_at_config_cache(config_dir, config_path, filename_prefix="winws2_at_")
        return config_path

    def _startup_output_path_for_artifact(self, artifact: PreparedPresetArtifact) -> str:
        digest_source = (
            f"{os.path.abspath(str(artifact.preset_path or ''))}\0"
            f"{' '.join(str(arg or '') for arg in artifact.launch_args)}"
        ).encode("utf-8", "surrogatepass")
        digest = hashlib.sha1(digest_source).hexdigest()[:20]
        return os.path.join(self._winws2_startup_output_dir(), f"winws2_startup_{digest}.log")

    @staticmethod
    def _read_startup_output_file(path: str) -> str:
        try:
            with open(path, "rb") as f:
                data = f.read(64 * 1024)
            return data.decode("utf-8", errors="replace").strip()
        except Exception:
            return ""

    @staticmethod
    def _summarize_startup_output(output: str) -> str:
        lines = [line.strip() for line in str(output or "").splitlines() if line.strip()]
        for line in reversed(lines):
            lower = line.lower()
            if "windivert:" in lower or "error opening filter" in lower:
                return line
        for line in reversed(lines):
            lower = line.lower()
            if "error" in lower or "ошибка" in lower:
                return line
        return lines[0] if lines else ""

    @staticmethod
    def _launch_args_files_exist(launch_args: tuple[str, ...]) -> bool:
        if not launch_args:
            return False
        for arg in launch_args:
            value = str(arg or "")
            if value.startswith("@") and len(value) > 1 and not os.path.exists(value[1:]):
                return False
        return True

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
                    source_content = f.read()
            except Exception:
                return PreparedPresetArtifact(p, cache_key, "", tuple(), False, f"Preset файл не найден: {p}")

            try:
                normalized_text = self._prepare_preset_text_for_launch(source_content)
                missing = self._collect_missing_preset_references_from_text(normalized_text)
                validation_ok = not missing
                validation_report = "" if validation_ok else self._build_validation_report(missing)
                at_config_path = self._write_winws2_at_config(p, normalized_text)
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
                normalized_text=normalized_text,
                launch_args=(f"@{at_config_path}",),
                validation_ok=validation_ok,
                validation_report=validation_report,
            )

            final_cache_key = preset_cache_key(p)
            if cache_key is not None and final_cache_key == cache_key:
                with self._state_lock:
                    remember_cache_entry(self._prepared_preset_cache, cache_key, artifact)
                return artifact

        return artifact

    def _is_circular_preset_path(self, preset_path: str) -> bool:
        p = str(preset_path or "").strip()
        if not p or not os.path.exists(p):
            return False

        try:
            with open(p, "r", encoding="utf-8", errors="replace") as f:
                source_content = f.read()
        except Exception:
            return False

        return self._is_circular_preset_text(source_content)

    @staticmethod
    def _is_circular_preset_text(source_content: str) -> bool:
        from winws_runtime.preset_launch_text import is_winws2_circular_preset_text

        return is_winws2_circular_preset_text(source_content)

    def _stop_process_only_locked(self) -> bool:
        """
        Stops only the running winws2 process.
        """
        try:
            cleanup_needed = False
            had_running_process = False
            if self.running_process and self.is_running():
                had_running_process = True
                pid = self.running_process.pid
                strategy_name = self.current_launch_label or "unknown"
                self._set_runner_state_locked(
                    PresetRunnerState.STOPPING,
                    preset_path=str(self._preset_file_path or ""),
                    strategy_name=str(strategy_name),
                    pid=pid,
                    reason="stop_process_only",
                )

                log(f"Preset switch: stopping process '{strategy_name}' (PID: {pid})", "INFO")

                # Soft stop
                self.running_process.terminate()

                if wait_for_process_exit(self.running_process, timeout=3.0):
                    log(f"Process stopped for preset switch (PID: {pid})", "SUCCESS")
                else:
                    log("Soft stop timeout, force killing for preset switch", "WARNING")
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
                log("Preset switch fallback cleanup: detected lingering winws process", "DEBUG")
                self._kill_all_winws_processes()
            return had_running_process or cleanup_needed
        except Exception as e:
            log(f"Error stopping process for preset switch: {e}", "ERROR")
            return False

    def _clear_process_state_locked(self) -> None:
        self.running_process = None
        self.current_launch_label = None
        self.current_strategy_args = None

    def _prepare_state_for_spawn_locked(self, preset_path: str, strategy_name: str) -> None:
        """Normalize stale runner state before a new spawn attempt."""
        snapshot = self._runner_state.snapshot()
        has_live_process = bool(self.running_process and self.is_running())
        if has_live_process:
            return
        if snapshot.state in (PresetRunnerState.RUNNING, PresetRunnerState.STARTING, PresetRunnerState.STOPPING):
            self._clear_process_state_locked()
            self._set_runner_state_locked(
                PresetRunnerState.IDLE,
                preset_path=preset_path,
                strategy_name=strategy_name,
                reason="stale_state_recovered_before_spawn",
            )

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
            f"Preset changed before winws2 spawn, rebuilding @config: {artifact.preset_path}",
            "INFO",
        )
        return self._compile_preset_artifact(artifact.preset_path)

    def _artifact_for_handoff_locked(self, artifact: PreparedPresetArtifact) -> PreparedPresetArtifact:
        """Build a temporary @config that can coexist with the old winws2 briefly."""
        text = str(getattr(artifact, "normalized_text", "") or "").rstrip()
        if not text:
            return artifact
        handoff_text = f"{text}\n--wf-dup-check=0\n"
        at_config_path = self._write_winws2_at_config(artifact.preset_path, handoff_text)
        return PreparedPresetArtifact(
            preset_path=artifact.preset_path,
            cache_key=None,
            normalized_text=handoff_text,
            launch_args=(f"@{at_config_path}",),
            validation_ok=artifact.validation_ok,
            validation_report=artifact.validation_report,
        )

    def _artifact_for_dry_run_locked(self, artifact: PreparedPresetArtifact) -> PreparedPresetArtifact:
        text = str(getattr(artifact, "normalized_text", "") or "").rstrip()
        if not text:
            return artifact
        dry_run_text = f"{text}\n--wf-dup-check=0\n--dry-run\n"
        at_config_path = self._write_winws2_at_config(artifact.preset_path, dry_run_text)
        return PreparedPresetArtifact(
            preset_path=artifact.preset_path,
            cache_key=None,
            normalized_text=dry_run_text,
            launch_args=(f"@{at_config_path}",),
            validation_ok=artifact.validation_ok,
            validation_report=artifact.validation_report,
        )

    @staticmethod
    def _decode_process_output(data) -> str:
        if isinstance(data, bytes):
            return data.decode("utf-8", errors="replace")
        return str(data or "")

    @staticmethod
    def _should_retry_dry_run_exit_code(exit_code: int) -> bool:
        return int(exit_code) == _STATUS_DLL_INIT_FAILED

    def _run_preset_dry_run_locked(
        self,
        artifact: PreparedPresetArtifact,
        strategy_name: str,
        *,
        preset_switch: bool,
        notify_failure: bool,
    ) -> bool:
        dry_run_artifact = self._artifact_for_dry_run_locked(artifact)
        if not dry_run_artifact.launch_args:
            return True

        cmd = [self.winws_exe, *dry_run_artifact.launch_args]
        for attempt in range(2):
            try:
                result = subprocess.run(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    stdin=subprocess.DEVNULL,
                    startupinfo=self._create_startup_info(),
                    creationflags=CREATE_NO_WINDOW,
                    cwd=self.work_dir,
                    timeout=6.0,
                    check=False,
                )
            except subprocess.TimeoutExpired:
                message = "Preset dry-run timeout"
                self._last_spawn_exit_code = 124
                self._last_spawn_stderr = message
                log(message, "WARNING" if not notify_failure else "ERROR")
                self._set_last_error(message, notify=notify_failure)
                return False
            except Exception as exc:
                message = f"Preset dry-run failed: {exc}"
                self._last_spawn_exit_code = None
                self._last_spawn_stderr = message
                log(message, "WARNING" if not notify_failure else "ERROR")
                self._set_last_error(message, notify=notify_failure)
                return False

            output = "\n".join(
                part.strip()
                for part in (
                    self._decode_process_output(getattr(result, "stdout", b"")),
                    self._decode_process_output(getattr(result, "stderr", b"")),
                )
                if part and part.strip()
            )
            self._last_spawn_exit_code = int(getattr(result, "returncode", -1))
            self._last_spawn_stderr = output
            if self._last_spawn_exit_code == 0:
                return True
            if attempt == 0 and self._should_retry_dry_run_exit_code(self._last_spawn_exit_code):
                log(
                    "Preset dry-run hit transient Windows process init error "
                    f"(code: {self._last_spawn_exit_code}), retrying once",
                    "WARNING",
                )
                time.sleep(_TRANSIENT_DRY_RUN_RETRY_DELAY_SEC)
                continue
            break

        failure_log_level = "ERROR" if notify_failure else "WARNING"
        first_line = next((line.strip() for line in output.splitlines() if line.strip()), "")
        log(
            f"Preset dry-run failed before winws2 start (code: {self._last_spawn_exit_code})"
            + (f": {first_line[:300]}" if first_line else ""),
            failure_log_level,
        )
        self._set_runner_state_locked(
            PresetRunnerState.FAILED,
            preset_path=artifact.preset_path,
            strategy_name=strategy_name,
            error=output,
            reason="dry_run_failed_before_spawn",
            publish_failure=notify_failure,
        )
        if first_line:
            self._set_last_error(f"Preset dry-run failed: {first_line[:200]}", notify=notify_failure)
        else:
            self._set_last_error(
                f"Preset dry-run failed (код {self._last_spawn_exit_code})",
                notify=notify_failure,
            )
        return False

    def _restore_process_state_locked(
        self,
        *,
        process,
        preset_path: str,
        strategy_name: str | None,
        strategy_args,
    ) -> None:
        self.running_process = process
        self._preset_file_path = preset_path
        self.current_launch_label = strategy_name
        self.current_strategy_args = list(strategy_args or ())

    def _stop_previous_process_after_handoff_locked(self, process, strategy_name: str, preset_path: str) -> None:
        """Stop the old process after the replacement has already started."""
        if process is None:
            return
        try:
            pid = int(getattr(process, "pid", 0) or 0)
        except Exception:
            pid = 0
        try:
            if process.poll() is not None:
                return
        except Exception:
            pass

        label = str(strategy_name or "previous")
        log(f"Preset switch handoff: stopping previous process '{label}' (PID: {pid})", "INFO")
        try:
            process.terminate()
            if wait_for_process_exit(process, timeout=3.0):
                log(f"Previous preset process stopped after handoff (PID: {pid})", "SUCCESS")
                return

            log("Previous preset process soft stop timeout after handoff, force killing", "WARNING")
            process.kill()
            if not wait_for_process_exit(process, timeout=1.0):
                log(
                    f"Previous preset process did not exit after handoff kill (PID: {pid}, preset={preset_path})",
                    "WARNING",
                )
        except Exception as exc:
            log(f"Error stopping previous process after preset handoff: {exc}", "WARNING")

    @staticmethod
    def _safe_file_sha1(path: str) -> str:
        try:
            h = hashlib.sha1()
            with open(path, "rb") as f:
                for chunk in iter(lambda: f.read(1024 * 1024), b""):
                    h.update(chunk)
            return h.hexdigest()
        except Exception:
            return ""

    def _log_winws2_launch_command(self, *, cmd: list[str], artifact: PreparedPresetArtifact) -> None:
        try:
            command_line = subprocess.list2cmdline([str(part) for part in cmd])
        except Exception:
            command_line = " ".join(str(part) for part in cmd)

        log(f"Winws2 launch command: {command_line}", "INFO")
        log(f"Winws2 launch cwd: {self.work_dir}", "INFO")

        for arg in artifact.launch_args:
            value = str(arg or "")
            if not value.startswith("@") or len(value) <= 1:
                continue

            config_path = value[1:]
            try:
                size = os.path.getsize(config_path)
            except Exception:
                size = -1
            digest = self._safe_file_sha1(config_path)
            digest_part = f", sha1={digest}" if digest else ""
            log(
                "Winws2 launch @config: "
                f"path={config_path}, bytes={size}{digest_part}, source={artifact.preset_path}",
                "INFO",
            )
        try:
            log(f"Winws2 startup output: {self._startup_output_path_for_artifact(artifact)}", "DEBUG")
        except Exception:
            pass

    def _spawn_process_locked(
        self,
        artifact: PreparedPresetArtifact,
        strategy_name: str,
        *,
        preset_switch: bool,
        notify_failure: bool = True,
        stable_start_window_seconds: float = 1.0,
    ) -> bool:
        if not artifact.launch_args:
            message = "Не удалось подготовить аргументы запуска из preset файла"
            self._set_last_error(message, notify=notify_failure)
            if preset_switch:
                log("Cannot start from preset: no launch arguments produced", "ERROR")
            else:
                log(message, "ERROR")
            return False

        cmd = [self.winws_exe, *artifact.launch_args]
        start_label = "Preset switch" if preset_switch else "Starting"

        log(f"{start_label}: starting from preset {artifact.preset_path}", "INFO")
        self._log_winws2_launch_command(cmd=cmd, artifact=artifact)
        if not preset_switch:
            log(f"Strategy: {strategy_name}", "INFO")

        if not self._run_preset_dry_run_locked(
            artifact,
            strategy_name,
            preset_switch=preset_switch,
            notify_failure=notify_failure,
        ):
            return False

        try:
            startup_output_path = self._startup_output_path_for_artifact(artifact)
            startup_output_file = None
            startup_stdout = subprocess.DEVNULL
            startup_stderr = subprocess.DEVNULL
            try:
                os.makedirs(os.path.dirname(startup_output_path), exist_ok=True)
                startup_output_file = open(startup_output_path, "wb")
                startup_stdout = startup_output_file
                startup_stderr = startup_output_file
            except Exception as exc:
                log(f"Не удалось открыть файл стартового вывода winws2: {exc}", "DEBUG")

            self._prepare_state_for_spawn_locked(artifact.preset_path, strategy_name)
            self._set_runner_state_locked(
                PresetRunnerState.STARTING,
                preset_path=artifact.preset_path,
                strategy_name=strategy_name,
                reason="preset_switch_start" if preset_switch else "start_from_preset",
            )
            try:
                self.running_process = subprocess.Popen(
                    cmd,
                    stdout=startup_stdout,
                    stderr=startup_stderr,
                    stdin=subprocess.DEVNULL,
                    startupinfo=self._create_startup_info(),
                    creationflags=CREATE_NO_WINDOW,
                    cwd=self.work_dir
                )
            finally:
                if startup_output_file is not None:
                    try:
                        startup_output_file.close()
                    except Exception:
                        pass
            self.current_launch_label = strategy_name
            self.current_strategy_args = list(artifact.launch_args)
            self._last_spawn_exit_code = None
            self._last_spawn_stderr = ""

            stable_ok = wait_for_process_stable_start(
                self.running_process,
                readiness_check=lambda: self._spawn_readiness_check_locked(self.running_process),
                stable_window=stable_start_window_seconds,
            )

            if stable_ok:
                self._set_runner_state_locked(
                    PresetRunnerState.RUNNING,
                    preset_path=artifact.preset_path,
                    strategy_name=strategy_name,
                    pid=self.running_process.pid,
                    reason="start_confirmed",
                )
                if preset_switch:
                    log(f"Preset switch successful (PID: {self.running_process.pid})", "SUCCESS")
                else:
                    log(f"Strategy '{strategy_name}' started from preset (PID: {self.running_process.pid})", "SUCCESS")
                return True

            exit_code = self.running_process.returncode
            failure_log_level = "ERROR" if notify_failure else "WARNING"
            if preset_switch:
                log(f"Preset switch failed: process exited (code: {exit_code})", failure_log_level)
            else:
                log(f"Strategy '{strategy_name}' exited immediately (code: {exit_code})", failure_log_level)

            stderr_output = self._read_startup_output_file(startup_output_path)
            if not stderr_output:
                stderr_output = self._read_process_startup_output(self.running_process)
            if stderr_output:
                startup_summary = self._summarize_startup_output(stderr_output)
                log(f"Error: {(startup_summary or stderr_output)[:500]}", failure_log_level)

            self._last_spawn_exit_code = int(exit_code)
            self._last_spawn_stderr = str(stderr_output or "")
            self._set_runner_state_locked(
                PresetRunnerState.FAILED,
                preset_path=artifact.preset_path,
                strategy_name=strategy_name,
                error=str(stderr_output or ""),
                reason="process_exited_during_start",
                publish_failure=notify_failure,
            )

            if not preset_switch:
                from winws_runtime.health.process_health_check import diagnose_winws_exit

                diag = diagnose_winws_exit(exit_code, stderr_output)
                if diag:
                    prefix = f"[AUTOFIX:{diag.auto_fix}]" if diag.auto_fix else ""
                    self._set_last_error(f"{prefix}{diag.cause}. {diag.solution}")
                    log(f"Diagnosis: {diag.cause} | Fix: {diag.solution} | auto_fix={diag.auto_fix}", "INFO")
                else:
                    first_line = ""
                    try:
                        first_line = (stderr_output or "").strip().splitlines()[0].strip()
                    except Exception:
                        first_line = ""
                    if first_line:
                        self._set_last_error(f"{ENGINE_WINWS2} завершился сразу (код {exit_code}): {first_line[:200]}")
                    else:
                        self._set_last_error(f"{ENGINE_WINWS2} завершился сразу (код {exit_code})")
            else:
                first_line = ""
                try:
                    first_line = (stderr_output or "").strip().splitlines()[0].strip()
                except Exception:
                    first_line = ""
                if first_line:
                    self._set_last_error(f"Preset switch failed: {first_line[:200]}", notify=notify_failure)
                else:
                    self._set_last_error(f"Preset switch failed (код {exit_code})", notify=notify_failure)

            self._clear_process_state_locked()
            if artifact.preset_path and not preset_switch:
                self._preset_file_path = None
            return False

        except Exception as e:
            diagnosis = diagnose_startup_error(e, self.winws_exe)
            failure_log_level = "ERROR" if notify_failure else "WARNING"
            for line in diagnosis.split('\n'):
                log(line, failure_log_level)
            try:
                self._set_last_error(diagnosis.split("\n")[0].strip(), notify=notify_failure)
            except Exception:
                self._set_last_error(None, notify=notify_failure)
            self._set_runner_state_locked(
                PresetRunnerState.FAILED,
                preset_path=artifact.preset_path,
                strategy_name=strategy_name,
                error=diagnosis.split("\n")[0].strip(),
                reason="spawn_exception",
                publish_failure=notify_failure,
            )
            self._last_spawn_exit_code = None
            self._last_spawn_stderr = ""
            import traceback
            log(traceback.format_exc(), "DEBUG")
            self._clear_process_state_locked()
            if not preset_switch:
                self._preset_file_path = None
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
                for line in (artifact.validation_report or "").splitlines():
                    if line.strip():
                        log(line, "ERROR")
                try:
                    self._set_last_error((artifact.validation_report or "").splitlines()[0].strip(), notify=False)
                except Exception:
                    self._set_last_error("Preset содержит ссылки на отсутствующие файлы", notify=False)
                return False

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
                for line in (artifact.validation_report or "").splitlines():
                    if line.strip():
                        log(line, "ERROR")
                try:
                    self._set_last_error((artifact.validation_report or "").splitlines()[0].strip(), notify=False)
                except Exception:
                    self._set_last_error("Preset содержит ссылки на отсутствующие файлы", notify=False)
                return False

            if callable(is_current) and not bool(is_current()):
                log("Fast preset switch skipped before spawn: request is stale", "DEBUG")
                return True

            old_process = self.running_process if self.running_process and self.is_running() else None
            old_preset_path = str(self._preset_file_path or "")
            old_strategy_name = getattr(self, "current_launch_label", None)
            old_strategy_args = tuple(getattr(self, "current_strategy_args", None) or ())

            self._preset_file_path = preset_path
            spawn_artifact = self._artifact_for_handoff_locked(artifact) if old_process is not None else artifact
            success = self._spawn_process_locked(
                spawn_artifact,
                strategy_name,
                preset_switch=True,
                notify_failure=False,
            )
            if old_process is not None:
                if success:
                    self._stop_previous_process_after_handoff_locked(
                        old_process,
                        str(old_strategy_name or "unknown"),
                        old_preset_path,
                    )
                else:
                    self._restore_process_state_locked(
                        process=old_process,
                        preset_path=old_preset_path,
                        strategy_name=old_strategy_name,
                        strategy_args=old_strategy_args,
                    )
                    return False
            if not success:
                success = self._retry_fast_switch_after_failed_spawn_locked(
                    artifact,
                    strategy_name,
                )
        return success

    def _retry_fast_switch_after_failed_spawn_locked(self, artifact: PreparedPresetArtifact, strategy_name: str) -> bool:
        exit_code = int(self._last_spawn_exit_code or -1)
        stderr_output = str(self._last_spawn_stderr or "")

        retry_allowed = self._is_windivert_conflict_error(stderr_output, exit_code)
        retry_allowed = retry_allowed or self._should_retry_transient_windivert_service_error(
            stderr_output,
            exit_code,
            retry_count=0,
            max_retry_count=1,
        )
        if not retry_allowed:
            return False
        if self._is_windivert_system_error(stderr_output, exit_code):
            log("Fast preset switch hit WinDivert system error; retry will not help", "WARNING")
            return False

        log(
            "Fast preset switch hit WinDivert conflict, retrying inside switch after cleanup",
            "WARNING",
        )
        self._aggressive_windivert_cleanup()
        self._wait_after_aggressive_windivert_cleanup()
        if not self._ensure_windivert_ready_before_spawn():
            self._last_spawn_exit_code = 34
            self._last_spawn_stderr = "windivert: readiness probe failed before fast switch retry"
            self._set_last_error("WinDivert ещё не готов к открытию фильтра", notify=False)
            return False

        return bool(
            self._spawn_process_locked(
                artifact,
                strategy_name,
                preset_switch=True,
                notify_failure=False,
            )
        )

    def start_from_preset_file(
        self,
        preset_path: str,
        strategy_name: str = "Preset",
        _force_cleanup: bool = False,
        _retry_count: int = 0,
        _stable_start_window_seconds: float = 1.0,
    ) -> bool:
        """
        Запускает движок Zapret 2 из выбранного preset-файла.

        Это основной путь для обычного запуска zapret2_mode: берём готовый
        preset-файл, а не собираем аргументы из старых категорий.

        Важно: изменения preset-файла применяет runtime preset coordinator.
        Runner не следит за файлом сам, чтобы не было двух перезапусков подряд.

        Args:
            preset_path: путь к preset-файлу
            strategy_name: имя для логов

        Returns:
            True, если запуск прошёл успешно
        """
        if not os.path.exists(preset_path):
            log(f"Preset file not found: {preset_path}", "ERROR")
            self._set_last_error(f"Preset файл не найден: {preset_path}")
            return False

        self._set_last_error(None)

        with self._state_lock:
            return self._start_from_preset_file_locked(
                preset_path,
                strategy_name,
                force_cleanup=bool(_force_cleanup),
                retry_count=int(_retry_count),
                stable_start_window_seconds=float(_stable_start_window_seconds),
            )

    def _resolve_cleanup_required_before_spawn(
        self,
        *,
        force_cleanup: bool,
    ) -> bool:
        cleanup_required = bool(force_cleanup)

        if self.running_process and self.is_running():
            log("Stopping previous process before starting new one", "INFO")
            self._stop_process_only_locked()
            cleanup_required = True

        try:
            active_winws_pids = get_all_winws_process_pids()
        except Exception:
            active_winws_pids = []

        if active_winws_pids:
            cleanup_required = True

        return cleanup_required

    def _perform_cleanup_before_spawn_locked(self, *, cleanup_required: bool) -> None:
        if cleanup_required:
            self._perform_standard_windivert_cleanup()
        else:
            log("Fast start: cleanup skipped (no active winws processes)", "DEBUG")

    def _maybe_retry_after_failed_spawn_locked(
        self,
        preset_path: str,
        strategy_name: str,
        *,
        cleanup_required: bool,
        retry_count: int,
        stable_start_window_seconds: float = 1.0,
    ) -> bool:
        exit_code = int(self._last_spawn_exit_code or -1)
        stderr_output = str(self._last_spawn_stderr or "")
        transient_service_retry = self._should_retry_transient_windivert_service_error(
            stderr_output,
            exit_code,
            retry_count=retry_count,
            max_retry_count=1,
        )

        stale_services: list[str] = []
        if retry_count == 0:
            try:
                stale_services = find_stale_windivert_delete_pending_services_runtime()
            except Exception:
                stale_services = []
        delete_pending_codes = {_ERROR_SERVICE_MARKED_FOR_DELETE, _ERROR_SERVICE_MARKED_FOR_DELETE & 0xFF}
        if stale_services and (transient_service_retry or exit_code in delete_pending_codes):
            log(
                "WinDivert service stayed stale after failed winws2 start; "
                f"retrying with aggressive cleanup: {','.join(stale_services)}",
                "WARNING",
            )
            return self._start_from_preset_file_locked(
                preset_path,
                strategy_name,
                force_cleanup=True,
                retry_count=retry_count + 1,
                stable_start_window_seconds=stable_start_window_seconds,
            )

        if stale_services:
            log(
                "WinDivert service stayed stale after failed winws2 start; "
                f"cleaning without retry: {','.join(stale_services)}",
                "WARNING",
            )
            self._aggressive_windivert_cleanup()

        if transient_service_retry:
            log(
                "Transient WinDivert service error detected, retrying with aggressive cleanup",
                "WARNING",
            )
            return self._start_from_preset_file_locked(
                preset_path,
                strategy_name,
                force_cleanup=True,
                retry_count=retry_count + 1,
                stable_start_window_seconds=stable_start_window_seconds,
            )

        if self._is_windivert_system_error(stderr_output, exit_code):
            log("WinDivert system error detected — retry will not help", "WARNING")
            return False

        if (
            (not cleanup_required)
            and retry_count == 0
            and self._is_windivert_conflict_error(stderr_output, exit_code)
        ):
            log("WinDivert conflict detected, retrying with full cleanup", "WARNING")
            return self._start_from_preset_file_locked(
                preset_path,
                strategy_name,
                force_cleanup=True,
                retry_count=1,
                stable_start_window_seconds=stable_start_window_seconds,
            )

        return False

    def _start_from_preset_file_locked(
        self,
        preset_path: str,
        strategy_name: str,
        *,
        force_cleanup: bool,
        retry_count: int,
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
            )
            for line in (artifact.validation_report or "").splitlines():
                if line.strip():
                    log(line, "ERROR")
            try:
                self._set_last_error((artifact.validation_report or "").splitlines()[0].strip())
            except Exception:
                self._set_last_error("Preset содержит ссылки на отсутствующие файлы")
            return False

        cleanup_required = self._resolve_cleanup_required_before_spawn(
            force_cleanup=force_cleanup,
        )
        self._perform_cleanup_before_spawn_locked(cleanup_required=cleanup_required)
        if retry_count > 0:
            self._wait_after_aggressive_windivert_cleanup()
        if not self._ensure_windivert_ready_before_spawn():
            self._last_spawn_exit_code = 34
            self._last_spawn_stderr = "windivert: readiness probe failed before spawn"
            self._set_last_error("WinDivert ещё не готов к открытию фильтра")
            return False

        self._preset_file_path = preset_path
        success = self._spawn_process_locked(
            artifact,
            strategy_name,
            preset_switch=False,
            stable_start_window_seconds=stable_start_window_seconds,
        )
        if success:
            return True

        return self._maybe_retry_after_failed_spawn_locked(
            preset_path,
            strategy_name,
            cleanup_required=cleanup_required,
            retry_count=retry_count,
            stable_start_window_seconds=stable_start_window_seconds,
        )

    def stop_background_watchers(self) -> None:
        return None

    def stop(self, *, cleanup_services: bool = True) -> bool:
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
