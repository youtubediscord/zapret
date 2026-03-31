# zapret2_launcher/strategy_runner.py
"""
Strategy runner for Zapret 2 (winws2.exe) with hot-reload support.

This version:
- Supports hot-reload via ConfigFileWatcher
- Monitors the launch preset file for changes
- Automatically restarts process when config changes
- Uses winws2.exe executable
"""

import os
import re
import subprocess
import time
import threading
from typing import Optional

from log import log
from launcher_common.runner_base import StrategyRunnerBase
from launcher_common.preset_runner_support import (
    ConfigFileWatcher,
    PreparedPresetArtifact,
    PresetRunnerState,
    PresetRunnerStateMachine,
    is_process_alive_with_expected_name,
    launch_args_from_preset_text,
    notify_ui_launch_error,
    preset_cache_key,
    remember_cache_entry,
    wait_for_process_exit,
    wait_for_process_stable_start,
)
from utils.circular_strategy_numbering import (
    strip_strategy_tags,
)
from launcher_common.constants import CREATE_NO_WINDOW
from dpi.process_health_check import (
    diagnose_startup_error
)


_WINDOWS_ABS_RE = re.compile(r"^(?:[A-Za-z]:[\\/]|\\\\)")

# Core lua-init files required by any preset that uses --lua-desync.
# Order matters — zapret-lib must come first (defines base primitives).
_CORE_LUA_INITS = [
    "lua/zapret-lib.lua",
    "lua/zapret-antidpi.lua",
    "lua/zapret-auto.lua",
    "lua/custom_funcs.lua",
    "lua/custom_diag.lua",
]

# Extension lua files required only when specific desync functions are used.
# key = lua file (relative to work_dir), value = set of function names it defines.
_EXTENSION_LUA_INITS: dict[str, set[str]] = {
    "lua/zapret-multishake.lua": {
        "hostfakesplit_stealth", "hostfakesplit_chaos",
        "hostfakesplit_multi", "hostfakesplit_gradual",
        "hostfakesplit_decoy",
    },
}

_LUA_DESYNC_FUNC_RE = re.compile(r"--lua-desync=([a-z_]+)")
_LUA_INIT_RE = re.compile(r"--lua-init=@?(.+)")


def _ensure_lua_init_lines(content: str, work_dir: str) -> tuple[str, bool]:
    """Check preset content and add missing --lua-init lines.

    Returns (possibly_modified_content, was_modified).
    """
    lines = content.split("\n")

    # Collect existing lua-init paths (normalized: strip @, lowercase, forward slashes).
    existing_inits: set[str] = set()
    for line in lines:
        m = _LUA_INIT_RE.match(line.strip())
        if m:
            existing_inits.add(m.group(1).strip().replace("\\", "/").lower())

    # Collect desync function names used in this preset.
    used_funcs: set[str] = set()
    for line in lines:
        for m in _LUA_DESYNC_FUNC_RE.finditer(line):
            used_funcs.add(m.group(1))

    if not used_funcs:
        return content, False

    # Determine which lua-init files are needed.
    needed: list[str] = []

    # Core files — always needed when any --lua-desync is present.
    for lua_path in _CORE_LUA_INITS:
        if lua_path.lower() not in existing_inits:
            full = os.path.join(work_dir, lua_path) if work_dir else lua_path
            if not work_dir or os.path.isfile(full):
                needed.append(lua_path)

    # Extension files — needed only when matching functions are used.
    for lua_path, funcs in _EXTENSION_LUA_INITS.items():
        if lua_path.lower() not in existing_inits and used_funcs & funcs:
            full = os.path.join(work_dir, lua_path) if work_dir else lua_path
            if not work_dir or os.path.isfile(full):
                needed.append(lua_path)

    if not needed:
        return content, False

    # Insert missing lines right after the last existing --lua-init line,
    # or after the header comments if no lua-init lines exist.
    insert_idx = 0
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("--lua-init="):
            insert_idx = i + 1
        elif insert_idx == 0 and (stripped.startswith("#") or stripped == ""):
            insert_idx = i + 1

    new_lines = [f"--lua-init=@{p}" for p in needed]
    lines = lines[:insert_idx] + new_lines + lines[insert_idx:]

    log(f"Auto-added missing lua-init lines: {', '.join(needed)}", "WARNING")
    return "\n".join(lines), True


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


class StrategyRunnerV2(StrategyRunnerBase):
    """
    Runner for Zapret 2 (winws2.exe) with hot-reload support.

    Features:
    - Hot-reload: automatically restarts when the launch preset file changes
    - Full Lua support
    - Uses winws2.exe executable
    """

    def __init__(self, winws_exe_path: str):
        """
        Initialize V2 strategy runner.

        Args:
            winws_exe_path: Path to winws2.exe
        """
        super().__init__(winws_exe_path)
        self._config_watcher: Optional[ConfigFileWatcher] = None
        self._preset_file_path: Optional[str] = None
        # Human-readable last start error (for UI/status).
        self.last_error: Optional[str] = None
        self._prepared_preset_cache: dict[tuple[str, int, int], PreparedPresetArtifact] = {}
        self._state_lock = threading.RLock()
        self._runner_state = PresetRunnerStateMachine()
        self._last_spawn_exit_code: Optional[int] = None
        self._last_spawn_stderr: str = ""

        log(f"StrategyRunnerV2 initialized with hot-reload support", "INFO")

    def _set_last_error(self, message: Optional[str]) -> None:
        try:
            text = str(message or "").strip()
        except Exception:
            text = ""
        self.last_error = text or None
        if text:
            notify_ui_launch_error(text)

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
            out: list[str] = []
            if default_dir:
                out.append(os.path.normpath(os.path.join(default_dir, v)))
            out.append(os.path.normpath(os.path.join(self.work_dir, v)))
            return out

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

    def _normalize_preset_text(self, source_content: str) -> str:
        normalized, lua_fixed = _ensure_lua_init_lines(source_content, self.work_dir)
        if lua_fixed:
            log("Applying implicit lua-init lines for launch artifact", "DEBUG")

        cleaned = strip_strategy_tags(normalized)
        if cleaned != normalized:
            log("Ignoring legacy :strategy=N tags in launch artifact", "DEBUG")
        return cleaned

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
                if cached is not None:
                    return cached

            try:
                with open(p, "r", encoding="utf-8", errors="replace") as f:
                    source_content = f.read()
            except Exception:
                return PreparedPresetArtifact(p, cache_key, "", tuple(), False, f"Preset файл не найден: {p}")

            normalized_text = self._normalize_preset_text(source_content)
            launch_args = tuple(launch_args_from_preset_text(normalized_text))
            missing = self._collect_missing_preset_references_from_text(normalized_text)
            validation_ok = not missing
            validation_report = "" if validation_ok else self._build_validation_report(missing)
            artifact = PreparedPresetArtifact(
                preset_path=p,
                cache_key=cache_key,
                normalized_text=normalized_text,
                launch_args=launch_args,
                validation_ok=validation_ok,
                validation_report=validation_report,
            )

            final_cache_key = preset_cache_key(p)
            if cache_key is not None and final_cache_key == cache_key:
                with self._state_lock:
                    remember_cache_entry(self._prepared_preset_cache, cache_key, artifact)
                return artifact

        return artifact

    def _on_config_changed(self):
        """
        Called when config file changes.
        Restarts process with new config.
        """
        log("Hot-reload triggered: config file changed", "INFO")

        with self._state_lock:
            preset_path = str(self._preset_file_path or "").strip()
            strategy_name = str(self.current_launch_label or "Preset").strip() or "Preset"

            if not preset_path or not os.path.exists(preset_path):
                log("Preset file not found, cannot hot-reload", "WARNING")
                return

            artifact = self._compile_preset_artifact(preset_path)
            if not artifact.validation_ok:
                self._set_runner_state_locked(
                    PresetRunnerState.FAILED,
                    preset_path=preset_path,
                    strategy_name=strategy_name,
                    error=artifact.validation_report,
                    reason="watcher_compile_failed",
                )
                for line in (artifact.validation_report or "").splitlines():
                    if line.strip():
                        log(line, "ERROR")
                try:
                    self._set_last_error((artifact.validation_report or "").splitlines()[0].strip())
                except Exception:
                    self._set_last_error("Preset содержит ссылки на отсутствующие файлы")
                return

            self._stop_process_only_locked()
            self._spawn_process_locked(
                artifact,
                strategy_name,
                hot_reload=True,
            )

    def _stop_process_only_locked(self) -> None:
        """
        Stops the process without stopping the config watcher.
        Used for hot-reload to keep monitoring the config file.
        """
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

                log(f"Hot-reload: stopping process '{strategy_name}' (PID: {pid})", "INFO")

                # Soft stop
                self.running_process.terminate()

                if wait_for_process_exit(self.running_process, timeout=3.0):
                    log(f"Process stopped for hot-reload (PID: {pid})", "SUCCESS")
                else:
                    log("Soft stop timeout, force killing for hot-reload", "WARNING")
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
                        from utils.process_killer import get_process_pids

                        cleanup_needed = bool(get_process_pids(os.path.basename(self.winws_exe)))
                    except Exception:
                        cleanup_needed = False

            if cleanup_needed:
                log("Hot-reload fallback cleanup: detected lingering winws process", "DEBUG")
                self._kill_all_winws_processes()

        except Exception as e:
            log(f"Error stopping process for hot-reload: {e}", "ERROR")

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

    def _spawn_process_locked(
        self,
        artifact: PreparedPresetArtifact,
        strategy_name: str,
        *,
        hot_reload: bool,
    ) -> bool:
        if not artifact.launch_args:
            message = "Не удалось подготовить аргументы запуска из preset файла"
            self._set_last_error(message)
            if hot_reload:
                log("Cannot start from preset: no launch arguments produced", "ERROR")
            else:
                log(message, "ERROR")
            return False

        cmd = [self.winws_exe, *artifact.launch_args]
        start_label = "Hot-reload" if hot_reload else "Starting"

        log(f"{start_label}: starting from preset {artifact.preset_path}", "INFO")
        if not hot_reload:
            log(f"Strategy: {strategy_name}", "INFO")

        try:
            self._set_runner_state_locked(
                PresetRunnerState.STARTING,
                preset_path=artifact.preset_path,
                strategy_name=strategy_name,
                reason="hot_reload_start" if hot_reload else "start_from_preset",
            )
            self.running_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.DEVNULL,
                startupinfo=self._create_startup_info(),
                creationflags=CREATE_NO_WINDOW,
                cwd=self.work_dir
            )
            self.current_launch_label = strategy_name
            self.current_strategy_args = list(artifact.launch_args)
            self._last_spawn_exit_code = None
            self._last_spawn_stderr = ""

            stable_ok = wait_for_process_stable_start(
                self.running_process,
                readiness_check=lambda: self._spawn_readiness_check_locked(self.running_process),
            )

            if stable_ok:
                self._set_runner_state_locked(
                    PresetRunnerState.RUNNING,
                    preset_path=artifact.preset_path,
                    strategy_name=strategy_name,
                    pid=self.running_process.pid,
                    reason="start_confirmed",
                )
                if hot_reload:
                    log(f"Hot-reload successful (PID: {self.running_process.pid})", "SUCCESS")
                else:
                    log(f"Strategy '{strategy_name}' started from preset (PID: {self.running_process.pid})", "SUCCESS")
                return True

            exit_code = self.running_process.returncode
            if hot_reload:
                log(f"Hot-reload failed: process exited (code: {exit_code})", "ERROR")
            else:
                log(f"Strategy '{strategy_name}' exited immediately (code: {exit_code})", "ERROR")

            stderr_output = ""
            try:
                stderr_output = self.running_process.stderr.read().decode('utf-8', errors='ignore')
                if stderr_output:
                    log(f"Error: {stderr_output[:500]}", "ERROR")
            except Exception:
                stderr_output = ""

            self._last_spawn_exit_code = int(exit_code)
            self._last_spawn_stderr = str(stderr_output or "")
            self._set_runner_state_locked(
                PresetRunnerState.FAILED,
                preset_path=artifact.preset_path,
                strategy_name=strategy_name,
                error=str(stderr_output or ""),
                reason="process_exited_during_start",
            )

            if not hot_reload:
                from dpi.process_health_check import diagnose_winws_exit

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
                        self._set_last_error(f"winws2 завершился сразу (код {exit_code}): {first_line[:200]}")
                    else:
                        self._set_last_error(f"winws2 завершился сразу (код {exit_code})")
            else:
                first_line = ""
                try:
                    first_line = (stderr_output or "").strip().splitlines()[0].strip()
                except Exception:
                    first_line = ""
                if first_line:
                    self._set_last_error(f"Hot-reload failed: {first_line[:200]}")
                else:
                    self._set_last_error(f"Hot-reload failed (код {exit_code})")

            self._clear_process_state_locked()
            if artifact.preset_path:
                self._preset_file_path = None
            return False

        except Exception as e:
            diagnosis = diagnose_startup_error(e, self.winws_exe)
            for line in diagnosis.split('\n'):
                log(line, "ERROR")
            try:
                self._set_last_error(diagnosis.split("\n")[0].strip())
            except Exception:
                self._set_last_error(None)
            self._set_runner_state_locked(
                PresetRunnerState.FAILED,
                preset_path=artifact.preset_path,
                strategy_name=strategy_name,
                error=diagnosis.split("\n")[0].strip(),
                reason="spawn_exception",
            )
            self._last_spawn_exit_code = None
            self._last_spawn_stderr = ""
            import traceback
            log(traceback.format_exc(), "DEBUG")
            self._clear_process_state_locked()
            self._preset_file_path = None
            return False

    def switch_preset_file_fast(self, preset_path: str, strategy_name: str = "Preset") -> bool:
        """Fast path for switching running direct preset using lightweight stop/start."""
        if not os.path.exists(preset_path):
            log(f"Fast switch preset file not found: {preset_path}", "ERROR")
            self._set_last_error(f"Preset файл не найден: {preset_path}")
            return False

        self._set_last_error(None)
        self._stop_config_watcher()

        with self._state_lock:
            artifact = self._compile_preset_artifact(preset_path)
            if not artifact.validation_ok:
                self._set_runner_state_locked(
                    PresetRunnerState.FAILED,
                    preset_path=preset_path,
                    strategy_name=strategy_name,
                    error=artifact.validation_report,
                    reason="manual_switch_compile_failed",
                )
                for line in (artifact.validation_report or "").splitlines():
                    if line.strip():
                        log(line, "ERROR")
                try:
                    self._set_last_error((artifact.validation_report or "").splitlines()[0].strip())
                except Exception:
                    self._set_last_error("Preset содержит ссылки на отсутствующие файлы")
                return False

            if self.running_process and self.is_running():
                self._stop_process_only_locked()

            self._preset_file_path = preset_path
            success = self._spawn_process_locked(
                artifact,
                strategy_name,
                hot_reload=True,
            )
        if success:
            self._start_config_watcher()
        return success

    def start_from_preset_file(
        self,
        preset_path: str,
        strategy_name: str = "Preset",
        _force_cleanup: bool = False,
        _retry_count: int = 0,
    ) -> bool:
        """
        Starts strategy directly from existing preset file.

        This is the primary method for ordinary direct_zapret2 launch - it uses
        an already prepared preset file instead of generating args from
        registry/category selections.

        Features:
        - Hot-reload support (monitors preset file for changes)
        - No registry access needed
        - Preset file already contains all arguments

        Args:
            preset_path: Path to the prepared launch preset file
            strategy_name: Strategy name for logs

        Returns:
            True if strategy started successfully
        """
        from utils.process_killer import kill_winws_force, get_process_pids

        if not os.path.exists(preset_path):
            log(f"Preset file not found: {preset_path}", "ERROR")
            self._set_last_error(f"Preset файл не найден: {preset_path}")
            return False

        self._set_last_error(None)
        self._stop_config_watcher()

        with self._state_lock:
            return self._start_from_preset_file_locked(
                preset_path,
                strategy_name,
                force_cleanup=bool(_force_cleanup),
                retry_count=int(_retry_count),
                kill_winws_force=kill_winws_force,
                get_process_pids=get_process_pids,
            )

    def _start_from_preset_file_locked(
        self,
        preset_path: str,
        strategy_name: str,
        *,
        force_cleanup: bool,
        retry_count: int,
        kill_winws_force,
        get_process_pids,
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

        cleanup_required = bool(force_cleanup)

        if self.running_process and self.is_running():
            log("Stopping previous process before starting new one", "INFO")
            self._stop_process_only_locked()
            cleanup_required = True

        try:
            active_winws_pids = get_process_pids("winws.exe") + get_process_pids("winws2.exe")
        except Exception:
            active_winws_pids = []

        if active_winws_pids:
            cleanup_required = True

        if cleanup_required:
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
        else:
            log("Fast start: cleanup skipped (no active winws processes)", "DEBUG")

        self._preset_file_path = preset_path
        success = self._spawn_process_locked(
            artifact,
            strategy_name,
            hot_reload=False,
        )
        if success:
            self._start_config_watcher()
            return True

        exit_code = int(self._last_spawn_exit_code or -1)
        stderr_output = str(self._last_spawn_stderr or "")

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
                kill_winws_force=kill_winws_force,
                get_process_pids=get_process_pids,
            )

        return False

    def find_running_preset_pid(self, preset_path: str) -> Optional[int]:
        """Returns PID of winws2.exe running with @preset_path, if any."""
        try:
            import psutil

            target_exe = os.path.basename(self.winws_exe).lower()
            target_preset = os.path.normcase(os.path.normpath(os.path.abspath(preset_path)))

            for proc in psutil.process_iter(["pid", "name", "cmdline"]):
                try:
                    name = (proc.info.get("name") or "").lower()
                    if name != target_exe:
                        continue

                    cmdline = proc.info.get("cmdline") or []
                    if not isinstance(cmdline, list):
                        continue

                    for arg in cmdline:
                        if not isinstance(arg, str):
                            continue
                        if not arg.startswith("@"):
                            continue

                        raw = arg[1:].strip().strip('"').strip()
                        if not raw:
                            continue

                        candidate = raw
                        if not os.path.isabs(candidate):
                            candidate = os.path.join(self.work_dir, candidate)

                        candidate_norm = os.path.normcase(os.path.normpath(os.path.abspath(candidate)))
                        if candidate_norm == target_preset:
                            return int(proc.info.get("pid"))
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue
                except Exception:
                    continue

            return None
        except Exception:
            return None

    def _start_config_watcher(self):
        """Start watching the preset file for changes or retarget existing watcher."""
        with self._state_lock:
            preset_path = str(self._preset_file_path or "").strip()
            watcher = self._config_watcher

        if not preset_path or not os.path.exists(preset_path):
            return

        if watcher:
            watcher.update_file_path(preset_path)
            log(f"Config watcher retargeted to: {preset_path}", "DEBUG")
            return

        watcher = ConfigFileWatcher(
            preset_path,
            self._on_config_changed,
            interval=1.0
        )
        with self._state_lock:
            self._config_watcher = watcher
        watcher.start()
        log(f"Config watcher started for: {preset_path}", "DEBUG")

    def _stop_config_watcher(self):
        """Stop watching the preset file"""
        with self._state_lock:
            watcher = self._config_watcher
            self._config_watcher = None
        if watcher:
            watcher.stop()
            log("Config watcher stopped", "DEBUG")

    def stop_background_watchers(self) -> None:
        self._stop_config_watcher()

    def stop(self) -> bool:
        """
        Stops running process and config watcher.

        Overrides base class to also stop the hot-reload watcher.
        """
        # Stop config watcher first
        self._stop_config_watcher()

        # Clear preset file path
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
            success = super().stop()
            self._set_runner_state_locked(
                PresetRunnerState.IDLE,
                reason="public_stop_completed",
                allow_same=True,
            )
            return success
