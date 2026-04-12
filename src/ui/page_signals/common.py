from __future__ import annotations

from PyQt6.QtWidgets import QWidget

from ui.navigation.navigation_controller import ensure_navigation_controller
from ui.page_contracts import PageSignalName, get_page_signal
from ui.page_names import PageName
from ui.window_appearance_state import (
    on_animations_changed,
    on_background_preset_changed,
    on_background_refresh_needed,
    on_editor_smooth_scroll_changed,
    on_mica_changed,
    on_opacity_changed,
    on_smooth_scroll_changed,
)
from ui.window_display_state import (
    update_autostart_display,
    update_subscription_display,
)

from .helpers import connect_page_signal_if_present, connect_show_page_signal_if_present


def connect_common_page_signals(window, page_name: PageName, page: QWidget) -> None:
    if page_name == PageName.AUTOSTART:
        connect_page_signal_if_present(
            window,
            "autostart.autostart_enabled",
            page,
            PageSignalName.AUTOSTART_ENABLED,
            lambda w=window: update_autostart_display(w, True),
        )
        connect_page_signal_if_present(
            window,
            "autostart.autostart_disabled",
            page,
            PageSignalName.AUTOSTART_DISABLED,
            lambda w=window: update_autostart_display(w, False),
        )
        connect_show_page_signal_if_present(
            window,
            "autostart.navigate_to_dpi_settings",
            page,
            PageSignalName.NAVIGATE_TO_DPI_SETTINGS,
            PageName.DPI_SETTINGS,
        )

    if page_name == PageName.APPEARANCE:
        signal_obj = get_page_signal(page, PageSignalName.DISPLAY_MODE_CHANGED)
        if signal_obj is not None:
            window.display_mode_changed = signal_obj
        else:
            signal_obj = get_page_signal(page, PageSignalName.THEME_CHANGED)
            if signal_obj is not None:
                window.display_mode_changed = signal_obj

        connect_page_signal_if_present(window, "appearance.garland_changed", page, PageSignalName.GARLAND_CHANGED, window.set_garland_enabled)
        connect_page_signal_if_present(window, "appearance.snowflakes_changed", page, PageSignalName.SNOWFLAKES_CHANGED, window.set_snowflakes_enabled)
        connect_page_signal_if_present(window, "appearance.background_refresh_needed", page, PageSignalName.BACKGROUND_REFRESH_NEEDED, lambda w=window: on_background_refresh_needed(w))
        connect_page_signal_if_present(window, "appearance.background_preset_changed", page, PageSignalName.BACKGROUND_PRESET_CHANGED, lambda preset, w=window: on_background_preset_changed(w, preset))
        connect_page_signal_if_present(window, "appearance.opacity_changed", page, PageSignalName.OPACITY_CHANGED, lambda value, w=window: on_opacity_changed(w, value))
        connect_page_signal_if_present(window, "appearance.mica_changed", page, PageSignalName.MICA_CHANGED, lambda enabled, w=window: on_mica_changed(w, enabled))
        connect_page_signal_if_present(window, "appearance.animations_changed", page, PageSignalName.ANIMATIONS_CHANGED, lambda enabled, w=window: on_animations_changed(w, enabled))
        connect_page_signal_if_present(window, "appearance.smooth_scroll_changed", page, PageSignalName.SMOOTH_SCROLL_CHANGED, lambda enabled, w=window: on_smooth_scroll_changed(w, enabled))
        connect_page_signal_if_present(window, "appearance.editor_smooth_scroll_changed", page, PageSignalName.EDITOR_SMOOTH_SCROLL_CHANGED, lambda enabled, w=window: on_editor_smooth_scroll_changed(w, enabled))
        connect_page_signal_if_present(
            window,
            "appearance.ui_language_changed",
            page,
            PageSignalName.UI_LANGUAGE_CHANGED,
            lambda language, w=window: ensure_navigation_controller(w).on_ui_language_changed(language),
        )

    if page_name == PageName.ABOUT:
        connect_show_page_signal_if_present(window, "about.open_premium_requested", page, PageSignalName.OPEN_PREMIUM_REQUESTED, PageName.PREMIUM)
        connect_show_page_signal_if_present(window, "about.open_updates_requested", page, PageSignalName.OPEN_UPDATES_REQUESTED, PageName.SERVERS, allow_internal=True)

    if page_name == PageName.PREMIUM:
        connect_page_signal_if_present(
            window,
            "premium.subscription_updated",
            page,
            PageSignalName.SUBSCRIPTION_UPDATED,
            lambda is_premium, days_remaining, w=window: update_subscription_display(w, is_premium, days_remaining),
        )


__all__ = ["connect_common_page_signals"]
