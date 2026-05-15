from __future__ import annotations

from ui.navigation.text_sync import resolve_ui_language
from ui.startup_ui_metrics import log_startup_page_init_summary
from ui.page_factory import UiPageFactory
from ui.page_host import WindowPageHost
from ui.page_registry import PAGE_CLASS_SPECS
from ui.runtime_ui_bridge import ensure_runtime_ui_bridge
from ui.window_appearance_bindings import initialize_window_appearance_bindings
from ui.window_ui_session import WindowUiSession, get_window_ui_session
from presets.ui_bindings import bind_preset_stores_to_runtime


def initialize_build_ui_state(
    window,
    *,
    nav_icons,
    nav_labels,
    has_fluent: bool,
    default_nav_icon,
    nav_scroll_position,
    sidebar_search_widget_cls,
) -> None:
    page_factory = UiPageFactory(window, PAGE_CLASS_SPECS)
    page_host = WindowPageHost(window, page_factory)
    window.ui_session = WindowUiSession(
        page_factory=page_factory,
        page_host=page_host,
        pages=page_host.pages,
        page_class_specs=page_factory.page_class_specs,
        nav_icons=nav_icons,
        nav_labels=nav_labels,
        default_nav_icon=default_nav_icon,
        has_fluent_nav=bool(has_fluent),
        nav_scroll_position=nav_scroll_position,
        sidebar_search_widget_cls=sidebar_search_widget_cls,
        ui_language=resolve_ui_language(window),
    )
    window.ui_session.runtime_ui_bridge = ensure_runtime_ui_bridge(
        window,
        notify=window.window_notification_center.notify,
        set_status=window.set_status,
        mark_content_changed=window.app_runtime.state.ui.bump_preset_content_revision,
    )
    window.app_runtime.features.runtime.configure_runtime_ui_bridge(window.ui_session.runtime_ui_bridge)


def create_preset_runtime_coordinator(window):
    state = window.app_runtime.state
    runtime_feature = window.app_runtime.features.runtime
    presets_feature = window.app_runtime.features.presets
    profile_feature = window.app_runtime.features.profile
    return runtime_feature.create_preset_runtime_coordinator(
        ui_state_store=state.ui,
        get_launch_method=get_current_launch_method_for_preset_runtime,
        get_active_preset_path=lambda: resolve_active_preset_watch_path(
            presets_feature=presets_feature,
        ),
        refresh_after_switch=lambda: presets_feature.refresh_profile_strategy_summary_in_store(
            method=get_current_launch_method_for_preset_runtime(),
            profile_feature=profile_feature,
            ui_state_store=state.ui,
        ),
    )


def finalize_page_stack_bootstrap(window) -> None:
    session = get_window_ui_session(window)
    if session is None:
        return
    session.page_host.finalize_stack_bootstrap()


def ensure_session_memory_defaults(window) -> None:
    session = get_window_ui_session(window)
    if session is not None:
        session.ui_bootstrap_bindings_connected = False


def finish_ui_bootstrap(window) -> None:
    session = get_window_ui_session(window)
    if session is None:
        return
    if bool(session.ui_bootstrap_bindings_connected):
        return

    bind_preset_stores_to_runtime(
        presets_feature=window.app_runtime.features.presets,
        preset_runtime=session.preset_runtime_coordinator,
    )
    initialize_window_appearance_bindings(window)
    session.ui_bootstrap_bindings_connected = True
    log_startup_page_init_summary(window)


def get_current_launch_method_for_preset_runtime() -> str:
    from ui.workflows.common import get_current_launch_method

    return get_current_launch_method(default="")


def resolve_active_preset_watch_path(*, presets_feature) -> str:
    from settings.mode import is_preset_launch_method

    method = get_current_launch_method_for_preset_runtime()
    if not is_preset_launch_method(method):
        return ""

    preset_path = presets_feature.get_selected_source_path(method)
    return str(preset_path or "")
