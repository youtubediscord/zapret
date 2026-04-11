from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from config import get_zapret_userdata_dir
from core.direct_flow import DirectFlowCoordinator
from core.paths import AppPaths
from core.presets.repository import PresetRepository
from core.presets.selection_service import PresetSelectionService
from core.runtime.direct_ui_snapshot_service import DirectUiSnapshotService
from core.runtime.preset_runtime_coordinator import PresetRuntimeCoordinator
from core.runtime.program_settings_runtime_service import ProgramSettingsRuntimeService
from core.runtime.user_presets_runtime_service import UserPresetsRuntimeService
from managers.app_runtime_state import AppRuntimeState
from managers.dpi_runtime_service import DpiRuntimeService
from ui.main_window_state import AppUiState, MainWindowStateStore


@dataclass(frozen=True, slots=True)
class AppContext:
    app_paths: AppPaths
    ui_state_store: MainWindowStateStore
    app_runtime_state: AppRuntimeState
    dpi_runtime_service: DpiRuntimeService
    direct_flow_coordinator: DirectFlowCoordinator
    preset_selection_service: PresetSelectionService
    preset_repository: PresetRepository
    direct_ui_snapshot_service: DirectUiSnapshotService
    program_settings_runtime_service: ProgramSettingsRuntimeService
    user_presets_runtime_service_factory: Callable[[str], UserPresetsRuntimeService]
    preset_runtime_coordinator_factory: Callable[..., PresetRuntimeCoordinator]


def build_app_context(*, initial_ui_state: AppUiState | None = None) -> AppContext:
    root = Path(get_zapret_userdata_dir()).resolve()
    app_paths = AppPaths(user_root=root, local_root=root)
    ui_state_store = MainWindowStateStore(initial_ui_state or AppUiState())
    preset_repository = PresetRepository(app_paths)
    preset_selection_service = PresetSelectionService(app_paths, preset_repository)
    app_runtime_state = AppRuntimeState(ui_state_store)
    dpi_runtime_service = DpiRuntimeService(ui_state_store)
    direct_flow_coordinator = DirectFlowCoordinator()
    direct_ui_snapshot_service = DirectUiSnapshotService()
    program_settings_runtime_service = ProgramSettingsRuntimeService()

    return AppContext(
        app_paths=app_paths,
        ui_state_store=ui_state_store,
        app_runtime_state=app_runtime_state,
        dpi_runtime_service=dpi_runtime_service,
        direct_flow_coordinator=direct_flow_coordinator,
        preset_selection_service=preset_selection_service,
        preset_repository=preset_repository,
        direct_ui_snapshot_service=direct_ui_snapshot_service,
        program_settings_runtime_service=program_settings_runtime_service,
        user_presets_runtime_service_factory=lambda scope_key: UserPresetsRuntimeService(scope_key=scope_key),
        preset_runtime_coordinator_factory=lambda *args, **kwargs: PresetRuntimeCoordinator(*args, **kwargs),
    )
