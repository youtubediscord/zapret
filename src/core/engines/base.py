from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class ValidationPlan:
    name: str
    args: list[str]
    config_path: Path


class EngineAdapter(Protocol):
    engine_id: str

    def get_executable_path(self) -> Path: ...

    def get_bundle_root(self) -> Path: ...

    def build_managed_preamble(self, engine_paths) -> list[str]: ...

    def build_validation_plans(self, compiled, engine_paths) -> list[ValidationPlan]: ...

    def start(self, compiled, engine_paths): ...

    def stop(self, session, engine_paths) -> None: ...
