from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from app_state.app_runtime_state import AppRuntimeState
    from app_state.launch_runtime_service import LaunchRuntimeService
    from app_state.main_window_state import AppUiState, MainWindowStateStore
    from winws_runtime.flow.direct_flow import DirectFlowCoordinator
    from core.paths import AppPaths
    from core.presets.preset_file_store import PresetFileStore
    from core.presets.runtime_store import DirectRuntimePresetStore
    from core.presets.selection_service import PresetSelectionService
    from direct_preset.runtime import DirectUiSnapshotService
    from core.runtime.orchestra_whitelist_runtime_service import OrchestraWhitelistRuntimeService
    from core.runtime.preset_runtime_coordinator import PresetRuntimeCoordinator
    from core.runtime.program_settings_runtime_service import ProgramSettingsRuntimeService
    from core.runtime.user_presets_runtime_service import UserPresetsRuntimeService
    from direct_preset.facade import DirectPresetFacade
    from app_state.strategy_feedback_store import StrategyFeedbackStore


_APP_CONTEXT: "AppContext | None" = None


@dataclass(frozen=True, slots=True)
class AppContext:
    app_paths: AppPaths
    ui_state_store: MainWindowStateStore
    app_runtime_state: AppRuntimeState
    launch_runtime_service: LaunchRuntimeService
    direct_flow_coordinator: DirectFlowCoordinator
    preset_selection_service: PresetSelectionService
    preset_file_store: PresetFileStore
    preset_store: DirectRuntimePresetStore
    preset_store_v1: DirectRuntimePresetStore
    strategy_feedback_store: StrategyFeedbackStore
    direct_ui_snapshot_service: DirectUiSnapshotService
    orchestra_whitelist_runtime_service: OrchestraWhitelistRuntimeService
    program_settings_runtime_service: ProgramSettingsRuntimeService
    user_presets_runtime_service_factory: Callable[[str], UserPresetsRuntimeService]
    preset_runtime_coordinator_factory: Callable[..., PresetRuntimeCoordinator]


def build_app_context(*, initial_ui_state: AppUiState | None = None) -> AppContext:
    from app_state.app_runtime_state import AppRuntimeState
    from app_state.launch_runtime_service import LaunchRuntimeService
    from app_state.main_window_state import AppUiState, MainWindowStateStore
    from config.config import get_zapret_userdata_dir

    from winws_runtime.flow.direct_flow import DirectFlowCoordinator
    from core.paths import AppPaths
    from core.presets.preset_file_store import PresetFileStore
    from core.presets.runtime_store import DirectRuntimePresetStore
    from core.presets.selection_service import PresetSelectionService
    from direct_preset.runtime import DirectUiSnapshotService
    from core.runtime.orchestra_whitelist_runtime_service import OrchestraWhitelistRuntimeService
    from core.runtime.preset_runtime_coordinator import PresetRuntimeCoordinator
    from core.runtime.program_settings_runtime_service import ProgramSettingsRuntimeService
    from core.runtime.user_presets_runtime_service import UserPresetsRuntimeService
    from app_state.strategy_feedback_store import StrategyFeedbackStore

    root = Path(get_zapret_userdata_dir()).resolve()
    app_paths = AppPaths(user_root=root, local_root=root)
    ui_state_store = MainWindowStateStore(initial_ui_state or AppUiState())
    preset_file_store = PresetFileStore(app_paths)
    preset_selection_service = PresetSelectionService(app_paths, preset_file_store)
    preset_store = DirectRuntimePresetStore("winws2", preset_file_store, preset_selection_service)
    preset_store_v1 = DirectRuntimePresetStore("winws1", preset_file_store, preset_selection_service)
    strategy_feedback_store = StrategyFeedbackStore.default()
    app_runtime_state = AppRuntimeState(ui_state_store)
    launch_runtime_service = LaunchRuntimeService(ui_state_store)
    direct_flow_coordinator = DirectFlowCoordinator(app_paths, preset_selection_service, preset_file_store)

    def _direct_facade_factory(launch_method: str) -> DirectPresetFacade:
        method = str(launch_method or "").strip().lower()
        if method == "direct_zapret2":
            engine = "winws2"
        elif method == "direct_zapret1":
            engine = "winws1"
        else:
            raise ValueError(f"Unsupported launch method for direct facade: {launch_method}")

        return DirectPresetFacade(
            engine=engine,
            launch_method=method,
            app_paths=app_paths,
            direct_flow_coordinator=direct_flow_coordinator,
            preset_file_store=preset_file_store,
            preset_selection_service=preset_selection_service,
            preset_store=preset_store,
            preset_store_v1=preset_store_v1,
        )

    direct_ui_snapshot_service = DirectUiSnapshotService(
        _direct_facade_factory
    )
    orchestra_whitelist_runtime_service = OrchestraWhitelistRuntimeService()
    program_settings_runtime_service = ProgramSettingsRuntimeService()

    return AppContext(
        app_paths=app_paths,
        ui_state_store=ui_state_store,
        app_runtime_state=app_runtime_state,
        launch_runtime_service=launch_runtime_service,
        direct_flow_coordinator=direct_flow_coordinator,
        preset_selection_service=preset_selection_service,
        preset_file_store=preset_file_store,
        preset_store=preset_store,
        preset_store_v1=preset_store_v1,
        strategy_feedback_store=strategy_feedback_store,
        direct_ui_snapshot_service=direct_ui_snapshot_service,
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
