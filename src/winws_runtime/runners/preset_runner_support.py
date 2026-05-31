from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import os
import re
import subprocess
import time
from typing import Callable

from log.log import log


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


_INLINE_ARG_SPLIT_RE = re.compile(r"(?<=\S)\s+(?=--)")


def _split_launch_line(raw_line: str) -> list[str]:
    """Split a preset line into one or more CLI arguments.

    Circular/source presets may store several `--...` arguments on one line to
    keep a single logical strategy together. `subprocess.Popen()` still expects
    every CLI argument as a separate list item, so we split only on whitespace
    that introduces the next `--` argument.
    """
    stripped = str(raw_line or "").strip()
    if not stripped:
        return []
    if not stripped.startswith("--"):
        return [stripped]
    return [part.strip() for part in _INLINE_ARG_SPLIT_RE.split(stripped) if part.strip()]


def launch_args_from_preset_text(content: str) -> list[str]:
    """Собирает argv из текста выбранного preset-файла."""
    args: list[str] = []
    for raw in str(content or "").splitlines():
        stripped = raw.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            continue
        args.extend(_split_launch_line(stripped))
    return args

@dataclass(frozen=True)
class PreparedPresetArtifact:
    preset_path: str
    cache_key: tuple[object, ...] | None
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
        PresetRunnerState.RUNNING: {
            PresetRunnerState.STARTING,
            PresetRunnerState.STOPPING,
            PresetRunnerState.FAILED,
            PresetRunnerState.IDLE,
        },
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


def preset_cache_key(path: str) -> tuple[object, ...] | None:
    p = str(path or "").strip()
    if not p:
        return None
    try:
        stat = os.stat(p)
    except Exception:
        return None

    digest = ""
    try:
        h = hashlib.blake2b(digest_size=16)
        with open(p, "rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        digest = h.hexdigest()
    except Exception:
        digest = ""

    return (os.path.normcase(p), int(stat.st_mtime_ns), int(stat.st_size), digest)


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


AT_CONFIG_MAX_FILES = 64


def prune_at_config_cache(
    config_dir: str,
    keep_path: str,
    *,
    filename_prefix: str,
    max_files: int = AT_CONFIG_MAX_FILES,
) -> None:
    try:
        limit = max(1, int(max_files))
    except Exception:
        limit = AT_CONFIG_MAX_FILES

    keep_norm = os.path.normcase(os.path.abspath(str(keep_path or "")))
    entries: list[tuple[bool, int, str, str]] = []

    try:
        with os.scandir(config_dir) as scan:
            for entry in scan:
                if not entry.is_file():
                    continue
                if not entry.name.startswith(filename_prefix) or not entry.name.endswith(".txt"):
                    continue
                try:
                    stat = entry.stat()
                except OSError:
                    continue
                path = os.path.abspath(entry.path)
                norm = os.path.normcase(path)
                entries.append((norm == keep_norm, int(stat.st_mtime_ns), entry.name, path))
    except OSError:
        return

    if len(entries) <= limit:
        return

    has_keep = any(is_keep for is_keep, _mtime, _name, _path in entries)
    keep_count = limit - 1 if has_keep else limit
    newest = sorted(
        (item for item in entries if not item[0]),
        key=lambda item: (item[1], item[2]),
        reverse=True,
    )[:keep_count]
    allowed = {os.path.normcase(os.path.abspath(path)) for _is_keep, _mtime, _name, path in newest}
    if has_keep:
        allowed.add(keep_norm)

    for _is_keep, _mtime, _name, path in entries:
        norm = os.path.normcase(os.path.abspath(path))
        if norm in allowed:
            continue
        try:
            os.remove(path)
        except OSError:
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
    *,
    stable_window: float = 1.0,
) -> bool:
    startup_timeout = 2.5
    stable_window = max(0.05, float(stable_window))
    probe_interval = 0.05

    start_time = time.perf_counter()
    ready_since: float | None = None

    while (time.perf_counter() - start_time) < startup_timeout:
        if process.poll() is not None:
            return False

        is_ready = False
        if readiness_check is not None:
            try:
                is_ready = bool(readiness_check())
            except Exception:
                is_ready = False
        else:
            is_ready = True

        if is_ready:
            if ready_since is None:
                ready_since = time.perf_counter()
            elif (time.perf_counter() - ready_since) >= stable_window:
                return True
        else:
            ready_since = None

        time.sleep(probe_interval)

    return False


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
