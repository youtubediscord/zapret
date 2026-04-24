from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


@dataclass(frozen=True)
class EnginePaths:
    engine: str
    presets_root_dir: Path
    user_presets_dir: Path
    builtin_presets_dir: Path

    def ensure_directories(self) -> "EnginePaths":
        self.presets_root_dir.mkdir(parents=True, exist_ok=True)
        self.user_presets_dir.mkdir(parents=True, exist_ok=True)
        self.builtin_presets_dir.mkdir(parents=True, exist_ok=True)
        return self


@dataclass(frozen=True)
class AppPaths:
    user_root: Path
    local_root: Path

    @lru_cache(maxsize=None)
    def engine_paths(self, engine: str) -> EnginePaths:
        engine_key = str(engine or "").strip().lower()
        presets_root_dir = self.user_root / "presets"

        if engine_key == "winws2":
            user_presets_dir = presets_root_dir / "presets_v2"
            builtin_presets_dir = presets_root_dir / "presets_v2_builtin"
        elif engine_key == "winws1":
            user_presets_dir = presets_root_dir / "presets_v1"
            builtin_presets_dir = presets_root_dir / "presets_v1_builtin"
        else:
            user_presets_dir = presets_root_dir / engine_key
            builtin_presets_dir = presets_root_dir / f"{engine_key}_builtin"

        return EnginePaths(
            engine=engine_key,
            presets_root_dir=presets_root_dir,
            user_presets_dir=user_presets_dir,
            builtin_presets_dir=builtin_presets_dir,
        )
