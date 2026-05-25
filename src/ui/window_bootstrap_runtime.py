from __future__ import annotations

from dataclasses import dataclass
from functools import partial
from typing import Any

from ui.navigation.text_sync import resolve_ui_language
from ui.startup_ui_metrics import log_startup_page_init_summary
from ui.page_factory import UiPageFactory
from ui.page_host import WindowPageHost
from ui.page_registry import PAGE_CLASS_SPECS
from ui.runtime_ui_bridge import RuntimeUiBridge
from ui.window_appearance_bindings import initialize_window_appearance_bindings
from ui.window_ui_session import WindowUiSession, get_window_ui_session
from presets.ui_bindings import bind_preset_stores_to_runtime


@dataclass(frozen=True, slots=True)
class WindowRuntimeBootstrapDeps:
    runtime_feature: Any
    presets_feature: Any
    profile_feature: Any
    ui_state_store: Any
    notify: Any
    set_status: Any


def initialize_build_ui_state(
    window,
    *,
    runtime_deps: WindowRuntimeBootstrapDeps,
    page_deps_sources,
    nav_icons,
    nav_labels,
    default_nav_icon,
    nav_scroll_position,
    sidebar_search_widget_cls,
) -> None:
    page_factory = UiPageFactory(window, PAGE_CLASS_SPECS, page_deps_sources)
    page_host = WindowPageHost(window, page_factory)
    window.ui_session = WindowUiSession(
        page_factory=page_factory,
        page_host=page_host,
        pages=page_host.pages,
        page_class_specs=page_factory.page_class_specs,
        nav_icons=nav_icons,
        nav_labels=nav_labels,
        default_nav_icon=default_nav_icon,
        nav_scroll_position=nav_scroll_position,
        sidebar_search_widget_cls=sidebar_search_widget_cls,
        ui_language=resolve_ui_language(window),
        sidebar_search_profile_loader=partial(
            load_sidebar_search_profile_items,
            runtime_deps.profile_feature,
        ),
        sidebar_search_preset_loader=partial(
            load_sidebar_search_preset_manifests,
            runtime_deps.presets_feature,
        ),
    )
    window.ui_session.runtime_ui_bridge = RuntimeUiBridge(
        notify=runtime_deps.notify,
        set_status=runtime_deps.set_status,
        mark_content_changed=runtime_deps.ui_state_store.bump_preset_content_revision,
    )
    runtime_deps.runtime_feature.configure_runtime_ui_bridge(window.ui_session.runtime_ui_bridge)


def create_preset_runtime_coordinator(window, runtime_deps: WindowRuntimeBootstrapDeps):
    return runtime_deps.runtime_feature.create_preset_runtime_coordinator(
        ui_state_store=runtime_deps.ui_state_store,
        get_launch_method=get_current_launch_method_for_preset_runtime,
        get_active_preset_path=lambda: resolve_active_preset_watch_path(
            presets_feature=runtime_deps.presets_feature,
        ),
        refresh_after_switch=lambda: runtime_deps.presets_feature.refresh_profile_strategy_summary_in_store(
            method=get_current_launch_method_for_preset_runtime(),
            profile_feature=runtime_deps.profile_feature,
            ui_state_store=runtime_deps.ui_state_store,
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


def finish_ui_bootstrap(window, runtime_deps: WindowRuntimeBootstrapDeps) -> None:
    session = get_window_ui_session(window)
    if session is None:
        return
    if bool(session.ui_bootstrap_bindings_connected):
        return

    bind_preset_stores_to_runtime(
        presets_feature=runtime_deps.presets_feature,
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


def load_sidebar_search_profile_items(profile_feature, launch_method: str) -> tuple[object, ...]:
    payload = None
    try:
        payload = profile_feature.get_cached_profile_list(launch_method)
    except Exception:
        payload = None
    if payload is None:
        try:
            payload = profile_feature.list_profiles(launch_method)
        except Exception:
            payload = None
    return tuple(getattr(payload, "items", ()) or ())


def load_sidebar_search_preset_manifests(presets_feature, launch_method: str) -> tuple[object, ...]:
    try:
        return tuple(presets_feature.list_preset_manifests(launch_method) or ())
    except Exception:
        return ()
