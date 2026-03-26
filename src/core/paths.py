from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


@dataclass(frozen=True)
class EnginePaths:
    engine: str
    presets_dir: Path
    state_dir: Path
    runtime_dir: Path
    runtime_low_dir: Path
    index_path: Path
    selected_state_path: Path
    effective_config_path: Path
    validate_dry_run_config_path: Path
    validate_lua_config_path: Path
    worker_pid_path: Path
    worker_log_path: Path
    session_path: Path
    last_validation_path: Path

    def ensure_directories(self) -> "EnginePaths":
        self.presets_dir.mkdir(parents=True, exist_ok=True)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        self.runtime_low_dir.mkdir(parents=True, exist_ok=True)
        return self


@dataclass(frozen=True)
class AppPaths:
    user_root: Path
    local_root: Path

    @lru_cache(maxsize=None)
    def engine_paths(self, engine: str) -> EnginePaths:
        engine_key = str(engine or "").strip().lower()
        state_dir = self.user_root / "core" / engine_key
        runtime_dir = self.local_root / "runtime" / engine_key
        runtime_low_dir = runtime_dir / "low"

        if engine_key == "winws2":
            presets_dir = self.user_root / "presets_v2"
        elif engine_key == "winws1":
            presets_dir = self.user_root / "presets_v1"
        else:
            presets_dir = self.user_root / "presets" / engine_key

        return EnginePaths(
            engine=engine_key,
            presets_dir=presets_dir,
            state_dir=state_dir,
            runtime_dir=runtime_dir,
            runtime_low_dir=runtime_low_dir,
            index_path=state_dir / "index.json",
            selected_state_path=state_dir / "selection.json",
            effective_config_path=runtime_dir / "effective.txt",
            validate_dry_run_config_path=runtime_dir / "validate_dry_run.txt",
            validate_lua_config_path=runtime_dir / "validate_lua.txt",
            worker_pid_path=runtime_dir / "worker.pid",
            worker_log_path=runtime_dir / "worker.log",
            session_path=state_dir / "session.json",
            last_validation_path=state_dir / "last_validation.json",
        )
