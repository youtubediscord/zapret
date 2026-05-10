from __future__ import annotations

from ui.navigation.text_sync import resolve_ui_language
from ui.page_signals.registry import connect_lazy_page_signals
from ui.startup_ui_metrics import log_startup_page_init_summary
from ui.window_signal_bindings import connect_window_page_signals
from ui.page_factory import UiPageFactory
from ui.page_host import WindowPageHost
from ui.page_registry import PAGE_CLASS_SPECS
from ui.runtime_ui_bridge import ensure_runtime_ui_bridge
from ui.window_display_state import refresh_pages_after_preset_switch_state
from ui.window_ui_session import WindowUiSession, get_window_ui_session
from presets.public import get_selected_source_path
from winws_runtime.public import (
    create_preset_runtime_coordinator as build_preset_runtime_coordinator,
)


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
    page_host = WindowPageHost(
        window,
        page_factory,
        connect_page_signals=connect_lazy_page_signals,
    )
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
    window.runtime_ui_bridge = ensure_runtime_ui_bridge(window)


def create_preset_runtime_coordinator(window):
    return build_preset_runtime_coordinator(
        window,
        app_context=window.app_context,
        ui_state_store=window.ui_state_store,
        get_launch_method=get_current_launch_method_for_preset_runtime,
        get_active_preset_path=lambda: resolve_active_preset_watch_path(window.app_context),
        refresh_after_switch=lambda: refresh_pages_after_preset_switch_state(window.app_context, window.ui_state_store),
    )


def finalize_page_signal_bootstrap(window) -> None:
    window._page_signal_bootstrap_complete = True
    session = get_window_ui_session(window)
    if session is None:
        return
    for page_name, page in list(session.pages.items()):
        connect_lazy_page_signals(window, page_name, page)
        session.page_host.ensure_page_in_stacked_widget(page)


def ensure_session_memory_defaults(window) -> None:
    if not hasattr(window, "_window_page_signals_connected"):
        window._window_page_signals_connected = False


def finish_ui_bootstrap(window) -> None:
    if bool(getattr(window, "_window_page_signals_connected", False)):
        return

    connect_window_page_signals(window)
    window._window_page_signals_connected = True
    log_startup_page_init_summary(window)


def get_current_launch_method_for_preset_runtime() -> str:
    try:
        from settings.dpi.strategy_settings import get_strategy_launch_method

        return str(get_strategy_launch_method() or "").strip().lower()
    except Exception:
        return ""


def resolve_active_preset_watch_path(app_context) -> str:
    try:
        from settings.mode import is_preset_launch_method

        method = get_current_launch_method_for_preset_runtime()
        if not is_preset_launch_method(method):
            return ""

        if app_context is None:
            return ""

        preset_path = get_selected_source_path(method, app_context=app_context)
        return str(preset_path or "")
    except Exception:
        return ""
