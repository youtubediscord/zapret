from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from app_state.app_runtime_state import AppRuntimeState
    from app_state.main_window_state import AppUiState, MainWindowStateStore
    from winws_runtime.flow.preset_mode import PresetModeCoordinator
    from winws_runtime.state import LaunchRuntimeService
    from core.paths import AppPaths
    from core.presets.preset_file_store import PresetFileStore
    from core.presets.ui_store import PresetUiStore
    from core.presets.selection_service import PresetSelectionService
    from core.runtime.orchestra_whitelist_runtime_service import OrchestraWhitelistRuntimeService
    from core.runtime.preset_runtime_coordinator import PresetRuntimeCoordinator
    from core.runtime.program_settings_runtime_service import ProgramSettingsRuntimeService
    from core.runtime.user_presets_runtime_service import UserPresetsRuntimeService


_APP_CONTEXT: "AppContext | None" = None


@dataclass(frozen=True, slots=True)
class AppContext:
    app_paths: AppPaths
    ui_state_store: MainWindowStateStore
    app_runtime_state: AppRuntimeState
    launch_runtime_service: LaunchRuntimeService
    preset_mode_coordinator: PresetModeCoordinator
    preset_selection_service: PresetSelectionService
    preset_file_store: PresetFileStore
    preset_store: PresetUiStore
    preset_store_v1: PresetUiStore
    orchestra_whitelist_runtime_service: OrchestraWhitelistRuntimeService
    program_settings_runtime_service: ProgramSettingsRuntimeService
    user_presets_runtime_service_factory: Callable[[str], UserPresetsRuntimeService]
    preset_runtime_coordinator_factory: Callable[..., PresetRuntimeCoordinator]


def build_app_context(*, initial_ui_state: AppUiState | None = None) -> AppContext:
    from app_state.app_runtime_state import AppRuntimeState
    from app_state.main_window_state import AppUiState, MainWindowStateStore
    from config.config import MAIN_DIRECTORY

    from winws_runtime.flow.preset_mode import PresetModeCoordinator
    from winws_runtime.state import LaunchRuntimeService
    from core.paths import AppPaths
    from core.presets.preset_file_store import PresetFileStore
    from core.presets.ui_store import PresetUiStore
    from core.presets.selection_service import PresetSelectionService
    from core.runtime.orchestra_whitelist_runtime_service import OrchestraWhitelistRuntimeService
    from core.runtime.preset_runtime_coordinator import PresetRuntimeCoordinator
    from core.runtime.program_settings_runtime_service import ProgramSettingsRuntimeService
    from core.runtime.user_presets_runtime_service import UserPresetsRuntimeService

    root = Path(MAIN_DIRECTORY).resolve()
    app_paths = AppPaths(user_root=root, local_root=root)
    ui_state_store = MainWindowStateStore(initial_ui_state or AppUiState())
    preset_file_store = PresetFileStore(app_paths)
    preset_selection_service = PresetSelectionService(preset_file_store)
    preset_store = PresetUiStore("winws2", preset_file_store, preset_selection_service)
    preset_store_v1 = PresetUiStore("winws1", preset_file_store, preset_selection_service)
    app_runtime_state = AppRuntimeState(ui_state_store)
    launch_runtime_service = LaunchRuntimeService(ui_state_store)
    preset_mode_coordinator = PresetModeCoordinator(app_paths, preset_selection_service, preset_file_store)

    orchestra_whitelist_runtime_service = OrchestraWhitelistRuntimeService()
    program_settings_runtime_service = ProgramSettingsRuntimeService()

    return AppContext(
        app_paths=app_paths,
        ui_state_store=ui_state_store,
        app_runtime_state=app_runtime_state,
        launch_runtime_service=launch_runtime_service,
        preset_mode_coordinator=preset_mode_coordinator,
        preset_selection_service=preset_selection_service,
        preset_file_store=preset_file_store,
        preset_store=preset_store,
        preset_store_v1=preset_store_v1,
        orchestra_whitelist_runtime_service=orchestra_whitelist_runtime_service,
        program_settings_runtime_service=program_settings_runtime_service,
        user_presets_runtime_service_factory=lambda scope_key: UserPresetsRuntimeService(scope_key=scope_key),
        preset_runtime_coordinator_factory=lambda *args, **kwargs: PresetRuntimeCoordinator(*args, **kwargs),
    )


def install_app_context(app_context: AppContext | None) -> None:
    global _APP_CONTEXT
    _APP_CONTEXT = app_context


def require_app_context() -> AppContext:
    context = _APP_CONTEXT
    if context is None:
        raise RuntimeError("AppContext is not installed")
    return context
