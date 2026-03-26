from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SessionInfo:
    engine: str
    preset_id: str
    preset_name: str
    pid: int
    started_at: str
    effective_config_path: str
    log_path: str


@dataclass(frozen=True)
class EngineStatus:
    state: str
    pid: int | None
    selected_preset_id: str | None
    selected_preset_name: str | None
    running_preset_id: str | None
    running_preset_name: str | None
    effective_config_path: str | None
    log_path: str | None
