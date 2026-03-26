from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from .direct_flow import DirectFlowCoordinator
from .paths import AppPaths
from .presets.compiler import PresetCompiler
from .presets.repository import PresetRepository
from .presets.selection_service import PresetSelectionService
from .presets.validator import PresetValidator
from .runtime.launcher import EngineLauncher
from .runtime.session_registry import SessionRegistry
from .runtime.status_service import StatusService


@lru_cache(maxsize=1)
def get_app_paths() -> AppPaths:
    from config import get_zapret_userdata_dir

    root = Path(get_zapret_userdata_dir()).resolve()
    return AppPaths(user_root=root, local_root=root)


@lru_cache(maxsize=1)
def get_preset_repository() -> PresetRepository:
    return PresetRepository(get_app_paths())


@lru_cache(maxsize=1)
def get_selection_service() -> PresetSelectionService:
    return PresetSelectionService(get_app_paths(), get_preset_repository())


@lru_cache(maxsize=1)
def get_preset_compiler() -> PresetCompiler:
    return PresetCompiler(get_app_paths())


@lru_cache(maxsize=1)
def get_preset_validator() -> PresetValidator:
    return PresetValidator(get_app_paths())


@lru_cache(maxsize=1)
def get_session_registry() -> SessionRegistry:
    return SessionRegistry(get_app_paths())


@lru_cache(maxsize=1)
def get_status_service() -> StatusService:
    return StatusService(
        get_app_paths(),
        get_preset_repository(),
        get_selection_service(),
        get_session_registry(),
    )


@lru_cache(maxsize=1)
def get_engine_launcher(adapters: tuple[tuple[str, object], ...] = ()) -> EngineLauncher:
    return EngineLauncher(
        get_app_paths(),
        get_preset_repository(),
        get_selection_service(),
        get_preset_compiler(),
        get_preset_validator(),
        get_session_registry(),
        get_status_service(),
        dict(adapters),
    )


@lru_cache(maxsize=1)
def get_direct_flow_coordinator() -> DirectFlowCoordinator:
    return DirectFlowCoordinator()
