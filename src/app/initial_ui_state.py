from __future__ import annotations

from app.state_store import AppUiState


def build_initial_ui_state() -> AppUiState:
    """Собирает честное стартовое состояние UI до создания окна и AppRuntime."""
    try:
        from program_settings.public import is_auto_dpi_enabled
        from settings.dpi.strategy_settings import get_strategy_launch_method
        from settings.mode import ALL_LAUNCH_METHODS, normalize_launch_method
        from settings.store import get_gui_autostart_enabled
        from winws_runtime.public import LaunchRuntimeService

        dpi_autostart_enabled = bool(is_auto_dpi_enabled())
        gui_autostart_enabled = bool(get_gui_autostart_enabled())
        launch_method = normalize_launch_method(get_strategy_launch_method(), default="")

        return LaunchRuntimeService.build_initial_ui_state(
            launch_method=launch_method,
            dpi_autostart_enabled=dpi_autostart_enabled,
            gui_autostart_enabled=gui_autostart_enabled,
            launch_supported=launch_method in ALL_LAUNCH_METHODS,
        )
    except Exception:
        return AppUiState()
