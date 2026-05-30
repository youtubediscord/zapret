from __future__ import annotations

from app.state_store import AppUiState


def build_initial_ui_state() -> AppUiState:
    """Собирает честное стартовое состояние UI до создания окна и AppRuntime."""
    try:
        from settings.mode import ALL_LAUNCH_METHODS, normalize_launch_method
        from settings.store import read_settings
        from winws_runtime.state import LaunchRuntimeService

        settings = read_settings()
        appearance = settings.get("appearance") if isinstance(settings, dict) else {}
        if not isinstance(appearance, dict):
            appearance = {}
        window = settings.get("window") if isinstance(settings, dict) else {}
        if not isinstance(window, dict):
            window = {}
        ui_state = settings.get("ui_state") if isinstance(settings, dict) else {}
        if not isinstance(ui_state, dict):
            ui_state = {}
        from settings.appearance import (
            store_warmed_accent_color,
            store_warmed_animations_enabled,
            store_warmed_background_preset,
            store_warmed_editor_smooth_scroll_enabled,
            store_warmed_mica_enabled,
            store_warmed_premium_effects,
            store_warmed_rkn_background,
            store_warmed_sidebar_icon_style,
            store_warmed_smooth_scroll_enabled,
            store_warmed_tinted_settings,
            store_warmed_ui_language,
            store_warmed_window_opacity,
        )

        store_warmed_ui_language(appearance.get("ui_language"))
        store_warmed_background_preset(appearance.get("background_preset"))
        store_warmed_mica_enabled(appearance.get("mica_enabled"))
        store_warmed_window_opacity(window.get("opacity"))
        store_warmed_accent_color(appearance.get("accent_color"))
        store_warmed_tinted_settings(
            appearance.get("follow_windows_accent"),
            appearance.get("tinted_background"),
            appearance.get("tinted_background_intensity"),
        )
        store_warmed_rkn_background(appearance.get("rkn_background"))
        store_warmed_animations_enabled(appearance.get("animations_enabled"))
        store_warmed_smooth_scroll_enabled(appearance.get("smooth_scroll_enabled"))
        store_warmed_editor_smooth_scroll_enabled(appearance.get("editor_smooth_scroll_enabled"))
        store_warmed_sidebar_icon_style(appearance.get("sidebar_icon_style"))
        store_warmed_premium_effects(appearance.get("garland_enabled"), appearance.get("snowflakes_enabled"))
        from core.runtime.program_settings_runtime_service import store_warmed_hide_to_tray_on_minimize_close

        store_warmed_hide_to_tray_on_minimize_close(window.get("hide_to_tray_on_minimize_close"))
        from ui.navigation.sidebar_state import store_warmed_sidebar_expanded

        store_warmed_sidebar_expanded(ui_state.get("sidebar_expanded"))
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
