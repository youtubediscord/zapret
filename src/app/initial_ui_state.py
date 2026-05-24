from __future__ import annotations

from app.state_store import AppUiState


def build_initial_ui_state() -> AppUiState:
    """Собирает честное стартовое состояние UI до создания окна и AppRuntime."""
    try:
        from settings.mode import ALL_LAUNCH_METHODS, normalize_launch_method
        from settings.store import read_settings
        from winws_runtime.state import LaunchRuntimeService

        settings = read_settings()
        program = settings.get("program") if isinstance(settings, dict) else {}
        if not isinstance(program, dict):
            program = {}

        dpi_autostart_enabled = bool(program.get("dpi_autostart", True))
        gui_autostart_enabled = bool(program.get("gui_autostart_enabled", False))
        launch_method = normalize_launch_method(program.get("strategy_launch_method"), default="")

        return LaunchRuntimeService.build_initial_ui_state(
            launch_method=launch_method,
            dpi_autostart_enabled=dpi_autostart_enabled,
            gui_autostart_enabled=gui_autostart_enabled,
            launch_supported=launch_method in ALL_LAUNCH_METHODS,
        )
    except Exception:
        return AppUiState()
