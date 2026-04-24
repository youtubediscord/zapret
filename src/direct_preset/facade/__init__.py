from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable, Optional

if TYPE_CHECKING:
    from app_context import AppContext
    from .backend import DirectPresetFacadeBackend
    from winws_runtime.flow.direct_flow import DirectFlowCoordinator
    from core.paths import AppPaths
    from core.presets.preset_file_store import PresetFileStore
    from core.presets.runtime_store import DirectRuntimePresetStore
    from core.presets.selection_service import PresetSelectionService


@dataclass(frozen=True)
class DirectPresetFacade:
    engine: str
    launch_method: str
    app_paths: "AppPaths"
    direct_flow_coordinator: "DirectFlowCoordinator"
    preset_file_store: "PresetFileStore"
    preset_selection_service: "PresetSelectionService"
    preset_store: "DirectRuntimePresetStore"
    preset_store_v1: "DirectRuntimePresetStore"
    direct_mode_override: str | None = None
    on_dpi_reload_needed: Optional[Callable[[], None]] = None

    @classmethod
    def from_launch_method(
        cls,
        launch_method: str,
        *,
        app_context: "AppContext",
        direct_mode_override: str | None = None,
        on_dpi_reload_needed: Optional[Callable[[], None]] = None,
    ) -> "DirectPresetFacade":
        method = str(launch_method or "").strip().lower()
        if method == "direct_zapret2":
            return cls(
                engine="winws2",
                launch_method=method,
                app_paths=app_context.app_paths,
                direct_flow_coordinator=app_context.direct_flow_coordinator,
                preset_file_store=app_context.preset_file_store,
                preset_selection_service=app_context.preset_selection_service,
                preset_store=app_context.preset_store,
                preset_store_v1=app_context.preset_store_v1,
                direct_mode_override=direct_mode_override,
                on_dpi_reload_needed=on_dpi_reload_needed,
            )
        if method == "direct_zapret1":
            return cls(
                engine="winws1",
                launch_method=method,
                app_paths=app_context.app_paths,
                direct_flow_coordinator=app_context.direct_flow_coordinator,
                preset_file_store=app_context.preset_file_store,
                preset_selection_service=app_context.preset_selection_service,
                preset_store=app_context.preset_store,
                preset_store_v1=app_context.preset_store_v1,
                direct_mode_override=direct_mode_override,
                on_dpi_reload_needed=on_dpi_reload_needed,
            )
        raise ValueError(f"Unsupported launch method for direct preset facade: {launch_method}")

    def _backend(self) -> DirectPresetFacadeBackend:
        from .backend import DirectPresetFacadeBackend

        return DirectPresetFacadeBackend(
            engine=self.engine,
            launch_method=self.launch_method,
            app_paths=self.app_paths,
            direct_flow_coordinator=self.direct_flow_coordinator,
            preset_file_store=self.preset_file_store,
            preset_selection_service=self.preset_selection_service,
            preset_store=self.preset_store,
            preset_store_v1=self.preset_store_v1,
            direct_mode_override=self.direct_mode_override,
            on_dpi_reload_needed=self.on_dpi_reload_needed,
        )

    def __getattr__(self, name: str):
        if name.startswith("__"):
            raise AttributeError(name)
        return getattr(self._backend(), name)
