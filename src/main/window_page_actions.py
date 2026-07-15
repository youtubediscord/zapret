from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True, slots=True)
class WindowPageActions:
    set_status: Callable[..., Any]
    notify: Callable[..., Any]
    request_exit: Callable[..., Any]
    open_connection_test: Callable[..., Any]
    open_folder: Callable[..., Any]
    show_page: Callable[..., Any]
    show_active_mode_control_page: Callable[..., Any]
    open_profile_setup: Callable[..., Any]
    on_profile_setup_changed: Callable[..., Any]
    open_preset_raw_editor: Callable[..., Any]
    after_launch_method_changed: Callable[..., Any]
    set_garland_enabled: Callable[..., Any]
    set_snowflakes_enabled: Callable[..., Any]
    on_background_refresh_needed: Callable[..., Any]
    on_background_preset_changed: Callable[..., Any]
    on_opacity_changed: Callable[..., Any]
    on_mica_changed: Callable[..., Any]
    on_animations_changed: Callable[..., Any]
    on_smooth_scroll_changed: Callable[..., Any]
    on_editor_smooth_scroll_changed: Callable[..., Any]
    on_ui_language_changed: Callable[..., Any]
    on_sidebar_icon_style_changed: Callable[..., Any]


def show_page(window, page_name, *, allow_internal: bool = False) -> bool:
    from ui.window_adapter import show_page as _show_page

    return bool(_show_page(window, page_name, allow_internal=allow_internal))


def show_active_mode_control_page(window, *, allow_internal: bool = False) -> bool:
    from ui.workflows.mode import show_active_mode_control_page as _show_active_mode_control_page

    return bool(_show_active_mode_control_page(window, allow_internal=allow_internal))


def open_profile_setup_for_method(window, method, profile_key, *, allow_internal: bool = True) -> bool:
    from main.window_page_presenters import open_profile_setup_for_method as _open_profile_setup_for_method

    return bool(_open_profile_setup_for_method(window, method, profile_key, allow_internal=allow_internal))


def apply_profile_setup_change_for_method(
    window,
    method,
    profile_key,
    change_kind,
    *,
    profile_item=None,
    old_profile_key=None,
) -> bool:
    from main.window_page_presenters import apply_profile_setup_change_for_method as _apply_profile_setup_change_for_method

    return bool(
        _apply_profile_setup_change_for_method(
            window,
            method,
            profile_key,
            change_kind,
            profile_item=profile_item,
            old_profile_key=old_profile_key,
        )
    )


def open_preset_raw_editor_for_method(window, method, preset_name, *, allow_internal: bool = True) -> bool:
    from main.window_page_presenters import open_preset_raw_editor_for_method as _open_preset_raw_editor_for_method

    return bool(_open_preset_raw_editor_for_method(window, method, preset_name, allow_internal=allow_internal))


def apply_launch_method_changed_ui(window, method) -> None:
    from ui.workflows.mode import apply_launch_method_changed_ui as _apply_launch_method_changed_ui

    _apply_launch_method_changed_ui(window, method)


def on_background_refresh_needed(window) -> None:
    from ui.window_appearance_state import on_background_refresh_needed as _on_background_refresh_needed

    _on_background_refresh_needed(window)


def on_background_preset_changed(window, preset) -> None:
    from ui.window_appearance_state import on_background_preset_changed as _on_background_preset_changed

    _on_background_preset_changed(window, preset)


def on_mica_changed(window, enabled) -> None:
    from ui.window_appearance_state import on_mica_changed as _on_mica_changed

    _on_mica_changed(window, enabled)


def on_animations_changed(window, enabled) -> None:
    from ui.window_appearance_state import on_animations_changed as _on_animations_changed

    _on_animations_changed(window, enabled)


def on_smooth_scroll_changed(window, enabled) -> None:
    from ui.window_appearance_state import on_smooth_scroll_changed as _on_smooth_scroll_changed

    _on_smooth_scroll_changed(window, enabled)


def on_editor_smooth_scroll_changed(window, enabled) -> None:
    from ui.window_appearance_state import on_editor_smooth_scroll_changed as _on_editor_smooth_scroll_changed

    _on_editor_smooth_scroll_changed(window, enabled)


def on_ui_language_changed(window, language) -> None:
    from ui.navigation.text_sync import on_ui_language_changed as _on_ui_language_changed

    _on_ui_language_changed(window, language)


def on_sidebar_icon_style_changed(window, style) -> None:
    from ui.navigation.icons import apply_sidebar_icon_style

    apply_sidebar_icon_style(window, style)


def build_window_page_actions(*, window, appearance_actions) -> WindowPageActions:
    return WindowPageActions(
        set_status=window.set_status,
        notify=window.window_notification_center.notify,
        request_exit=window.request_exit,
        open_connection_test=window.open_connection_test,
        open_folder=window.open_folder,
        show_page=lambda page_name, *, allow_internal=False: show_page(
            window,
            page_name,
            allow_internal=allow_internal,
        ),
        show_active_mode_control_page=lambda *, allow_internal=False: show_active_mode_control_page(
            window,
            allow_internal=allow_internal,
        ),
        open_profile_setup=lambda method, profile_key: open_profile_setup_for_method(
            window,
            method,
            profile_key,
            allow_internal=True,
        ),
        on_profile_setup_changed=lambda method, profile_key, change_kind, profile_item=None, old_profile_key=None: apply_profile_setup_change_for_method(
            window,
            method,
            profile_key,
            change_kind,
            profile_item=profile_item,
            old_profile_key=old_profile_key,
        ),
        open_preset_raw_editor=lambda method, preset_name, *, allow_internal=True: open_preset_raw_editor_for_method(
            window,
            method,
            preset_name,
            allow_internal=allow_internal,
        ),
        after_launch_method_changed=lambda method: apply_launch_method_changed_ui(window, method),
        set_garland_enabled=appearance_actions.set_garland_enabled,
        set_snowflakes_enabled=appearance_actions.set_snowflakes_enabled,
        on_background_refresh_needed=lambda: on_background_refresh_needed(window),
        on_background_preset_changed=lambda preset: on_background_preset_changed(window, preset),
        on_opacity_changed=appearance_actions.set_window_opacity,
        on_mica_changed=lambda enabled: on_mica_changed(window, enabled),
        on_animations_changed=lambda enabled: on_animations_changed(window, enabled),
        on_smooth_scroll_changed=lambda enabled: on_smooth_scroll_changed(window, enabled),
        on_editor_smooth_scroll_changed=lambda enabled: on_editor_smooth_scroll_changed(window, enabled),
        on_ui_language_changed=lambda language: on_ui_language_changed(window, language),
        on_sidebar_icon_style_changed=lambda style: on_sidebar_icon_style_changed(window, style),
    )


__all__ = ["WindowPageActions", "build_window_page_actions"]
