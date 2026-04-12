from __future__ import annotations

from core.runtime.preset_runtime_coordinator import PresetRuntimeCoordinator
from ui.page_signals import connect_lazy_page_signals
from ui.startup_ui_metrics import log_startup_page_init_summary
from ui.window_signal_bindings import connect_window_page_signals
from ui.navigation.navigation_controller import (
    WindowNavigationController,
    resolve_window_ui_language,
)
from ui.page_factory import UiPageFactory
from ui.page_host import WindowPageHost
from ui.page_registry import PAGE_CLASS_SPECS
from ui.runtime_ui_bridge import ensure_runtime_ui_bridge
from ui.ui_workflows import WindowUiWorkflows
from ui.window_adapter import WindowUiAdapter
from ui.window_state_refresh import refresh_pages_after_preset_switch


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
    window._navigation_controller = WindowNavigationController(window)
    window._ui_workflows = WindowUiWorkflows(window)
    window._page_factory = UiPageFactory(window, PAGE_CLASS_SPECS)
    window._page_host = WindowPageHost(
        window,
        window._page_factory,
        connect_page_signals=connect_lazy_page_signals,
    )
    window.runtime_ui_bridge = ensure_runtime_ui_bridge(window)
    window._window_ui_adapter = WindowUiAdapter(window)
    window.pages = window._page_host.pages
    window._page_class_specs = window._page_factory.page_class_specs
    window._nav_icons = nav_icons
    window._nav_labels = nav_labels
    window._default_nav_icon = default_nav_icon
    window._has_fluent_nav = bool(has_fluent)
    window._nav_scroll_position = nav_scroll_position
    window._sidebar_search_widget_cls = sidebar_search_widget_cls
    window._lazy_signal_connections = set()
    window._startup_ui_pump_counter = 0
    window._nav_search_query = ""
    window._nav_mode_visibility = {}
    window._nav_headers = []
    window._sidebar_search_nav_widget = None
    window._sidebar_search_model = None
    window._sidebar_search_completer = None
    window._sidebar_search_titlebar_attached = False
    window._ui_language = resolve_window_ui_language(window)
    window._startup_page_init_metrics = []


def create_preset_runtime_coordinator(window) -> PresetRuntimeCoordinator:
    return PresetRuntimeCoordinator(
        window,
        get_launch_method=get_current_launch_method_for_preset_runtime,
        get_active_preset_path=lambda: resolve_active_preset_watch_path(window),
        is_dpi_running=lambda: bool(
            hasattr(window, "launch_controller")
            and window.launch_controller
            and window.launch_controller.is_running()
        ),
        restart_dpi_async=lambda: window.launch_controller.restart_dpi_async(),
        switch_direct_preset_async=lambda method: window.launch_controller.switch_direct_preset_async(method),
        refresh_after_switch=lambda: refresh_pages_after_preset_switch(window),
    )


def finalize_page_signal_bootstrap(window) -> None:
    window._page_signal_bootstrap_complete = True
    for page_name, page in list(window.pages.items()):
        connect_lazy_page_signals(window, page_name, page)
        window._page_host.ensure_page_in_stacked_widget(page)


def ensure_session_memory_defaults(window) -> None:
    if not hasattr(window, "_direct_zapret2_last_opened_target_key"):
        window._direct_zapret2_last_opened_target_key = None
    if not hasattr(window, "_direct_zapret2_restore_detail_on_open"):
        window._direct_zapret2_restore_detail_on_open = False
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


def resolve_active_preset_watch_path(window) -> str:
    try:
        method = get_current_launch_method_for_preset_runtime()
        if method not in {"direct_zapret2", "direct_zapret1"}:
            return ""

        app_context = getattr(window, "app_context", None)
        if app_context is None:
            return ""

        preset_path = app_context.direct_flow_coordinator.get_selected_source_path(method)
        return str(preset_path or "")
    except Exception:
        return ""
