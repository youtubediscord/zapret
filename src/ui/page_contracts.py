from __future__ import annotations


class PageMethodName:
    SHOW_LOADING = "show_loading"
    SHOW_SUCCESS = "show_success"
    SWITCH_TO_TAB = "switch_to_tab"
    REQUEST_DIAGNOSTICS_START_FOCUS = "request_diagnostics_start_focus"
    CLOSE_TRANSIENT_OVERLAYS = "close_transient_overlays"
    SHOW_TARGET = "show_target"
    SET_PRESET_FILE_NAME = "set_preset_file_name"
    REFRESH_PRESETS_VIEW = "refresh_presets_view_if_possible"
    APPLY_STRATEGY_SELECTION = "apply_strategy_selection"
    APPLY_FILTER_MODE_CHANGE = "apply_filter_mode_change"
    REFRESH_STRATEGY_LIST_STATE = "refresh_strategy_list_state"


class PageSignalName:
    OPEN_TARGET_DETAIL = "open_target_detail"
    BACK_CLICKED = "back_clicked"
    PRESET_OPEN_REQUESTED = "preset_open_requested"
    NAVIGATE_TO_ROOT = "navigate_to_root"
    NAVIGATE_TO_PRESETS = "navigate_to_presets"
    NAVIGATE_TO_DIRECT_LAUNCH = "navigate_to_direct_launch"
    NAVIGATE_TO_BLOBS = "navigate_to_blobs"
    DIRECT_MODE_CHANGED = "direct_mode_changed"
    STRATEGY_SELECTED = "strategy_selected"
    FILTER_MODE_CHANGED = "filter_mode_changed"
    TARGET_CLICKED = "target_clicked"
    NAVIGATE_TO_CONTROL = "navigate_to_control"
    NAVIGATE_TO_STRATEGIES = "navigate_to_strategies"
    AUTOSTART_ENABLED = "autostart_enabled"
    AUTOSTART_DISABLED = "autostart_disabled"
    NAVIGATE_TO_DPI_SETTINGS = "navigate_to_dpi_settings"
    DISPLAY_MODE_CHANGED = "display_mode_changed"
    THEME_CHANGED = "theme_changed"
    GARLAND_CHANGED = "garland_changed"
    SNOWFLAKES_CHANGED = "snowflakes_changed"
    BACKGROUND_REFRESH_NEEDED = "background_refresh_needed"
    BACKGROUND_PRESET_CHANGED = "background_preset_changed"
    OPACITY_CHANGED = "opacity_changed"
    MICA_CHANGED = "mica_changed"
    ANIMATIONS_CHANGED = "animations_changed"
    SMOOTH_SCROLL_CHANGED = "smooth_scroll_changed"
    EDITOR_SMOOTH_SCROLL_CHANGED = "editor_smooth_scroll_changed"
    UI_LANGUAGE_CHANGED = "ui_language_changed"
    OPEN_PREMIUM_REQUESTED = "open_premium_requested"
    OPEN_UPDATES_REQUESTED = "open_updates_requested"
    SUBSCRIPTION_UPDATED = "subscription_updated"
    LAUNCH_METHOD_CHANGED = "launch_method_changed"
    CLEAR_LEARNED_REQUESTED = "clear_learned_requested"


def get_page_method(page, method_name: str):
    handler = getattr(page, str(method_name or ""), None)
    return handler if callable(handler) else None


def get_page_signal(page, signal_name: str):
    signal = getattr(page, str(signal_name or ""), None)
    return signal if signal is not None else None


__all__ = [
    "PageMethodName",
    "PageSignalName",
    "get_page_method",
    "get_page_signal",
]
