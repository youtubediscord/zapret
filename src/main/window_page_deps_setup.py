from __future__ import annotations

from ui.page_deps.common import PageDepsSources
from ui.ui_root import WindowUiRoot
from ui.window_bootstrap_runtime import WindowRuntimeBootstrapDeps


def build_window_page_deps_sources(*, features, state, page_actions) -> PageDepsSources:
    return PageDepsSources(
        feature_deps={
            "autostart": features.autostart,
            "blobs": features.blobs,
            "blockcheck": features.blockcheck,
            "diagnostics": features.diagnostics,
            "dns": features.dns,
            "dpi_settings": features.dpi_settings,
            "external_actions": features.external_actions,
            "hosts": features.hosts,
            "logs": features.logs,
            "orchestra": features.orchestra,
            "premium": features.premium,
            "presets": features.presets,
            "profile": features.profile,
            "program_settings": features.program_settings,
            "runtime": features.runtime,
            "telegram_proxy": features.telegram_proxy,
            "updater": features.updater,
        },
        ui_state_store=state.ui,
        actions={
            "after_launch_method_changed": page_actions.after_launch_method_changed,
            "notify": page_actions.notify,
            "on_animations_changed": page_actions.on_animations_changed,
            "on_background_preset_changed": page_actions.on_background_preset_changed,
            "on_background_refresh_needed": page_actions.on_background_refresh_needed,
            "on_editor_smooth_scroll_changed": page_actions.on_editor_smooth_scroll_changed,
            "on_mica_changed": page_actions.on_mica_changed,
            "on_opacity_changed": page_actions.on_opacity_changed,
            "on_profile_setup_changed": page_actions.on_profile_setup_changed,
            "on_smooth_scroll_changed": page_actions.on_smooth_scroll_changed,
            "on_ui_language_changed": page_actions.on_ui_language_changed,
            "open_connection_test": page_actions.open_connection_test,
            "open_folder": page_actions.open_folder,
            "open_preset_raw_editor": page_actions.open_preset_raw_editor,
            "open_profile_setup": page_actions.open_profile_setup,
            "request_exit": page_actions.request_exit,
            "set_garland_enabled": page_actions.set_garland_enabled,
            "set_snowflakes_enabled": page_actions.set_snowflakes_enabled,
            "set_status": page_actions.set_status,
            "show_active_mode_control_page": page_actions.show_active_mode_control_page,
            "show_page": page_actions.show_page,
        },
    )


def attach_window_ui_root(window, *, features, state, page_actions) -> None:
    runtime_bootstrap_deps = WindowRuntimeBootstrapDeps(
        runtime_feature=features.runtime,
        presets_feature=features.presets,
        profile_feature=features.profile,
        ui_state_store=state.ui,
        notify=page_actions.notify,
        set_status=page_actions.set_status,
    )
    window._ui_root = WindowUiRoot(
        window,
        build_window_page_deps_sources(
            features=features,
            state=state,
            page_actions=page_actions,
        ),
        runtime_bootstrap_deps,
    )


__all__ = ["attach_window_ui_root", "build_window_page_deps_sources"]
