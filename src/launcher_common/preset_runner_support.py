from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import os
import subprocess
import threading
import time
from typing import Callable, Optional

from app_notifications import advisory_notification
from log import log

try:
    import psutil  # type: ignore[import-not-found]
except Exception:  # pragma: no cover - local test environments may not ship psutil
    class _PsutilStub:
        class NoSuchProcess(Exception):
            pass

        class AccessDenied(Exception):
            pass

        class ZombieProcess(Exception):
            pass

        class Process:
            def __init__(self, *_args, **_kwargs):
                raise _PsutilStub.NoSuchProcess()

    psutil = _PsutilStub()


def launch_args_from_preset_text(content: str) -> list[str]:
    """Build argv directly from a source preset file."""
    args: list[str] = []
    for raw in str(content or "").splitlines():
        stripped = raw.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            continue
        args.append(stripped)
    return args


class ConfigFileWatcher:
    """
    Monitors preset file changes for hot-reload.

    Watches a config file and calls callback when modification time changes.
    Runs in a background thread with configurable polling interval.
    """

    def __init__(
        self,
        file_path: str,
        callback: Callable[[], None],
        interval: float = 1.0,
        *,
        thread_name: str = "ConfigFileWatcher",
    ):
        self._file_path = file_path
        self._callback = callback
        self._interval = interval
        self._thread_name = str(thread_name or "ConfigFileWatcher")
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._last_mtime: Optional[float] = None

        if os.path.exists(self._file_path):
            self._last_mtime = os.path.getmtime(self._file_path)

    def start(self):
        """Start watching the file in background thread."""
        if self._running:
            log("ConfigFileWatcher already running", "DEBUG")
            return

        self._running = True
        self._thread = threading.Thread(target=self._watch_loop, daemon=True, name=self._thread_name)
        self._thread.start()
        log(f"ConfigFileWatcher started for: {self._file_path}", "DEBUG")

    def update_file_path(self, file_path: str) -> None:
        """Switch watched file without restarting watcher thread."""
        self._file_path = str(file_path or "")
        self._last_mtime = None
        try:
            if self._file_path and os.path.exists(self._file_path):
                self._last_mtime = os.path.getmtime(self._file_path)
        except Exception:
            self._last_mtime = None

    def stop(self):
        """Stop watching the file."""
        if not self._running:
            return

        self._running = False
        watcher_thread = self._thread
        if watcher_thread and watcher_thread.is_alive():
            if watcher_thread is threading.current_thread():
                log(f"{self._thread_name}.stop called from watcher thread; skip self-join", "DEBUG")
            else:
                watcher_thread.join(timeout=2.0)
        self._thread = None
        log("ConfigFileWatcher stopped", "DEBUG")

    def _watch_loop(self):
        """Main watch loop - polls file for changes."""
        while self._running:
            try:
                if os.path.exists(self._file_path):
                    current_mtime = os.path.getmtime(self._file_path)
                    if self._last_mtime is not None and current_mtime != self._last_mtime:
                        log(f"Config file changed: {self._file_path}", "INFO")
                        self._last_mtime = current_mtime
                        try:
                            publish_active_preset_content_changed(self._file_path)
                        except Exception:
                            pass
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


@dataclass(frozen=True)
class PreparedPresetArtifact:
    preset_path: str
    cache_key: tuple[str, int, int] | None
    normalized_text: str
    launch_args: tuple[str, ...]
    validation_ok: bool
    validation_report: str


class PresetRunnerState(str, Enum):
    IDLE = "idle"
    STOPPING = "stopping"
    STARTING = "starting"
    RUNNING = "running"
    FAILED = "failed"


@dataclass(frozen=True)
class PresetRunnerStateSnapshot:
    state: PresetRunnerState
    generation: int
    preset_path: str
    strategy_name: str
    pid: int | None
    error: str
    reason: str


class PresetRunnerStateMachine:
    _ALLOWED: dict[PresetRunnerState, set[PresetRunnerState]] = {
        PresetRunnerState.IDLE: {PresetRunnerState.STARTING, PresetRunnerState.FAILED},
        PresetRunnerState.STOPPING: {PresetRunnerState.IDLE, PresetRunnerState.STARTING, PresetRunnerState.FAILED},
        PresetRunnerState.STARTING: {PresetRunnerState.RUNNING, PresetRunnerState.FAILED, PresetRunnerState.IDLE},
        PresetRunnerState.RUNNING: {PresetRunnerState.STOPPING, PresetRunnerState.FAILED, PresetRunnerState.IDLE},
        PresetRunnerState.FAILED: {PresetRunnerState.IDLE, PresetRunnerState.STARTING},
    }

    def __init__(self) -> None:
        self._generation = 0
        self._snapshot = PresetRunnerStateSnapshot(
            state=PresetRunnerState.IDLE,
            generation=0,
            preset_path="",
            strategy_name="",
            pid=None,
            error="",
            reason="initialized",
        )

    def snapshot(self) -> PresetRunnerStateSnapshot:
        return self._snapshot

    def transition(
        self,
        target: PresetRunnerState,
        *,
        preset_path: str = "",
        strategy_name: str = "",
        pid: int | None = None,
        error: str = "",
        reason: str = "",
        allow_same: bool = False,
    ) -> PresetRunnerStateSnapshot:
        current = self._snapshot.state
        if target == current and not allow_same:
            return self._snapshot

        allowed = self._ALLOWED.get(current, set())
        if target != current and target not in allowed:
            raise RuntimeError(f"Invalid preset runner state transition: {current.value} -> {target.value}")

        self._generation += 1
        self._snapshot = PresetRunnerStateSnapshot(
            state=target,
            generation=self._generation,
            preset_path=str(preset_path or ""),
            strategy_name=str(strategy_name or ""),
            pid=pid,
            error=str(error or ""),
            reason=str(reason or ""),
        )
        return self._snapshot


def publish_runner_runtime_state(
    *,
    launch_method: str,
    state: PresetRunnerState,
    preset_path: str = "",
    pid: int | None = None,
    error: str = "",
) -> None:
    """Best-effort bridge from runner state machine to GUI runtime state."""
    if state not in {PresetRunnerState.STARTING, PresetRunnerState.RUNNING, PresetRunnerState.FAILED}:
        return

    method = str(launch_method or "").strip().lower()
    if method not in {"direct_zapret1", "direct_zapret2"}:
        return

    payload = {
        "launch_method": method,
        "phase": state.value,
        "preset_path": str(preset_path or "").strip(),
        "pid": int(pid) if isinstance(pid, int) else None,
        "error": str(error or "").strip(),
    }

    try:
        from PyQt6.QtWidgets import QApplication

        app = QApplication.instance()
        if app is None:
            return

        target = app.activeWindow()
        if target is None or not hasattr(target, "runner_runtime_state_requested"):
            for widget in app.topLevelWidgets():
                if hasattr(widget, "runner_runtime_state_requested"):
                    target = widget
                    break

        if target is not None and hasattr(target, "runner_runtime_state_requested"):
            signal = getattr(target, "runner_runtime_state_requested", None)
            if signal is not None:
                signal.emit(dict(payload))
    except Exception:
        pass


def publish_active_preset_content_changed(path: str) -> None:
    """Best-effort bridge that reports active preset file content changes to the app."""
    normalized_path = str(path or "").strip()
    if not normalized_path:
        return

    try:
        from PyQt6.QtWidgets import QApplication

        app = QApplication.instance()
        if app is None:
            return

        target = app.activeWindow()
        if target is None or not hasattr(target, "active_preset_content_changed_requested"):
            for widget in app.topLevelWidgets():
                if hasattr(widget, "active_preset_content_changed_requested"):
                    target = widget
                    break

        if target is not None and hasattr(target, "active_preset_content_changed_requested"):
            signal = getattr(target, "active_preset_content_changed_requested", None)
            if signal is not None:
                signal.emit(normalized_path)
    except Exception:
        pass


def controller_transition_in_progress(launch_method: str) -> bool:
    """Checks whether the main DPI controller is already applying a runtime transition."""
    method = str(launch_method or "").strip().lower()
    if method not in {"direct_zapret1", "direct_zapret2", "orchestra"}:
        return False

    try:
        from PyQt6.QtWidgets import QApplication

        app = QApplication.instance()
        if app is None:
            return False

        target = app.activeWindow()
        if target is None or not hasattr(target, "dpi_controller"):
            for widget in app.topLevelWidgets():
                if hasattr(widget, "dpi_controller"):
                    target = widget
                    break

        if target is None:
            return False

        controller = getattr(target, "dpi_controller", None)
        checker = getattr(controller, "transition_pipeline_in_progress", None)
        if callable(checker):
            return bool(checker(method))
    except Exception:
        return False

    return False


def preset_cache_key(path: str) -> tuple[str, int, int] | None:
    p = str(path or "").strip()
    if not p:
        return None
    try:
        stat = os.stat(p)
    except Exception:
        return None
    return (os.path.normcase(p), int(stat.st_mtime_ns), int(stat.st_size))


def remember_cache_entry(cache: dict, key, value, max_entries: int = 128) -> None:
    if key is None:
        return
    cache[key] = value
    if len(cache) <= max_entries:
        return
    try:
        oldest_key = next(iter(cache))
        cache.pop(oldest_key, None)
    except Exception:
        pass


def wait_for_process_exit(process: subprocess.Popen, timeout: float = 3.0, probe_interval: float = 0.02) -> bool:
    deadline = time.perf_counter() + max(0.05, float(timeout))
    while time.perf_counter() < deadline:
        if process.poll() is not None:
            return True
        time.sleep(max(0.005, float(probe_interval)))
    return process.poll() is not None


def wait_for_process_stable_start(
    process: subprocess.Popen,
    readiness_check: Callable[[], bool] | None = None,
) -> bool:
    if process.poll() is not None:
        return False
    if readiness_check is not None:
        try:
            if readiness_check():
                return True
        except Exception:
            pass
    return process.poll() is None


def is_process_alive_with_expected_name(pid: int, exe_path: str) -> bool:
    try:
        process = psutil.Process(int(pid))
        name = str(process.name() or "").lower()
        expected = os.path.basename(str(exe_path or "")).lower()
        if expected and name != expected:
            return False
        return process.is_running()
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        return False
    except Exception:
        return False


def notify_ui_launch_error(message: str) -> None:
    """Best-effort UI notification from any thread (queued to main Qt thread)."""
    text = str(message or "").strip()
    if not text:
        return
    try:
        from PyQt6.QtWidgets import QApplication

        app = QApplication.instance()
        if app is None:
            return

        target = app.activeWindow()
        if target is None or not hasattr(target, "window_notification_controller"):
            for widget in app.topLevelWidgets():
                if hasattr(widget, "window_notification_controller"):
                    target = widget
                    break

        if target is not None and hasattr(target, "window_notification_controller"):
            controller = getattr(target, "window_notification_controller", None)
            if controller is None:
                return
            controller.notify_threadsafe(
                advisory_notification(
                    level="error",
                    title="Ошибка",
                    content=text,
                    source="launch.runner_error",
                    presentation="infobar",
                    queue="immediate",
                    duration=10000,
                    dedupe_key=f"launch.runner_error:{' '.join(text.split()).lower()}",
                )
            )
    except Exception:
        pass
