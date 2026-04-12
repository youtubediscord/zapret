from __future__ import annotations

from importlib import import_module

from PyQt6.QtWidgets import QWidget

from log import log
from ui.main_window_display import (
    on_autostart_disabled as on_main_window_autostart_disabled,
    on_autostart_enabled as on_main_window_autostart_enabled,
    on_subscription_updated as on_main_window_subscription_updated,
    open_subscription_dialog as open_main_window_subscription_dialog,
)
from ui.main_window_appearance_flow import (
    on_animations_changed,
    on_background_preset_changed,
    on_background_refresh_needed,
    on_editor_smooth_scroll_changed,
    on_mica_changed,
    on_opacity_changed,
    on_smooth_scroll_changed,
)
from ui.main_window_mode_switch import handle_main_window_launch_method_changed
from ui.main_window_orchestra_flow import on_clear_learned_requested
from ui.main_window_state_flow import on_direct_mode_changed
from ui.main_window_strategy_detail_flow import (
    on_open_target_detail,
    on_strategy_detail_back,
    on_strategy_detail_filter_mode_changed,
    on_strategy_detail_selected,
    on_z1_strategy_detail_selected,
    open_zapret1_target_detail,
)
from ui.main_window_strategy_selection_flow import on_strategy_selected_from_page
from ui.router import (
    get_eager_page_names_for_method,
    get_page_route_key,
    resolve_preset_detail_back_page_for_method,
    resolve_preset_detail_root_page_for_method,
    resolve_strategy_detail_root_page_for_method,
    resolve_zapret1_navigation_pages,
    resolve_zapret2_navigation_pages,
)
from ui.page_performance import log_page_metric
from ui.page_names import PageName
from ui.page_registry import get_page_performance_profile
from ui.window_action_controller import (
    open_connection_test,
    open_folder,
    start_dpi,
    stop_dpi,
)
from ui.main_window_navigation_build import on_ui_language_changed as on_main_window_ui_language_changed


def _show_active_zapret2_control_page(window) -> None:
    from ui.main_window_navigation import show_active_zapret2_control_page

    show_active_zapret2_control_page(window)


def _open_zapret2_preset_detail(window, preset_name: str) -> None:
    from ui.main_window_navigation import open_zapret2_preset_detail

    open_zapret2_preset_detail(window, preset_name)


def _open_zapret1_preset_detail(window, preset_name: str) -> None:
    from ui.main_window_navigation import open_zapret1_preset_detail

    open_zapret1_preset_detail(window, preset_name)


def get_eager_page_names(window) -> tuple[PageName, ...]:
    getter = getattr(window, "_get_launch_method", None)
    if callable(getter):
        try:
            method = getter()
        except Exception:
            method = ""
    else:
        method = ""

    return get_eager_page_names_for_method(method)


def create_pages(window) -> None:
    """Create page registry and initialize only truly eager pages."""
    import time as _time

    _t_pages_total = _time.perf_counter()

    for page_name in get_eager_page_names(window):
        ensure_page(window, page_name)
        window._pump_startup_ui()

    log(
        f"⏱ Startup: _create_pages core {(_time.perf_counter() - _t_pages_total) * 1000:.0f}ms",
        "DEBUG",
    )
    window._pump_startup_ui(force=True)

def get_loaded_page(window, name: PageName) -> QWidget | None:
    """Возвращает уже созданную страницу без lazy-инициализации."""
    pages = getattr(window, "pages", None)
    if not isinstance(pages, dict):
        return None
    return pages.get(name)


def get_strategy_page_name_for_method(method: str | None) -> PageName | None:
    normalized = str(method or "").strip().lower()
    if normalized == "direct_zapret2":
        return resolve_zapret2_navigation_pages(normalized).strategies_page
    if normalized == "direct_zapret1":
        return resolve_zapret1_navigation_pages().strategies_page
    return None


def get_loaded_strategy_page_for_method(window, method: str | None = None) -> QWidget | None:
    if method is None:
        getter = getattr(window, "_get_launch_method", None)
        method = getter() if callable(getter) else ""
    page_name = get_strategy_page_name_for_method(method)
    if page_name is None:
        return None
    return get_loaded_page(window, page_name)


def has_nav_item(window, name: PageName) -> bool:
    """Возвращает True только для страниц, реально зарегистрированных в sidebar."""
    nav_items = getattr(window, "_nav_items", None)
    if not isinstance(nav_items, dict):
        return False
    return name in nav_items


def set_stacked_widget_current_page(window, page: QWidget | None, *, animate: bool = True) -> bool:
    """Переключает текущую страницу в stacked widget.

    Для внутренних страниц без sidebar-пункта используем прямое переключение без
    fluent-анимации. Это уменьшает риск побочных переходов при открытии скрытых
    route'ов вроде страниц пресетов и detail-экранов.
    """
    stack = getattr(window, "stackedWidget", None)
    if page is None or stack is None:
        return False

    if animate:
        switch_to = getattr(window, "switchTo", None)
        if callable(switch_to):
            try:
                switch_to(page)
                return True
            except Exception:
                pass

    view = getattr(stack, "view", None)
    set_animation_enabled = getattr(view, "setAnimationEnabled", None)
    previous_animation_enabled = getattr(view, "isAnimationEnabled", None)
    animation_flag_known = isinstance(previous_animation_enabled, bool)

    if callable(set_animation_enabled):
        try:
            set_animation_enabled(False)
        except Exception:
            pass

    try:
        try:
            stack.setCurrentWidget(page, False)
        except TypeError:
            stack.setCurrentWidget(page)
        return True
    except Exception:
        return False
    finally:
        if callable(set_animation_enabled) and animation_flag_known:
            try:
                set_animation_enabled(bool(previous_animation_enabled))
            except Exception:
                pass


def connect_signal_once(window, key: str, signal_obj, slot_obj) -> None:
    if key in window._lazy_signal_connections:
        return
    try:
        signal_obj.connect(slot_obj)
        window._lazy_signal_connections.add(key)
    except Exception:
        pass


def _connect_show_page_signal(window, key: str, signal_obj, target_page: PageName) -> None:
    connect_signal_once(
        window,
        key,
        signal_obj,
        lambda target=target_page: window.show_page(target),
    )

def ensure_page_in_stacked_widget(window, page: QWidget | None) -> None:
    stack = getattr(window, "stackedWidget", None)
    if page is None or stack is None:
        return
    try:
        if stack.indexOf(page) < 0:
            stack.addWidget(page)
    except Exception:
        pass


def bind_page_ui_state(window, page: QWidget | None) -> None:
    store = getattr(window, "ui_state_store", None)
    binder = getattr(page, "bind_ui_state_store", None)
    if store is None or page is None or not callable(binder):
        return

    try:
        binder(store)
    except Exception:
        pass


def _connect_z2_navigation_signals(window, page_name: PageName, page: QWidget, z2_direct) -> None:
    if page_name == PageName.ZAPRET2_DIRECT and hasattr(page, "open_target_detail"):
        connect_signal_once(
            window,
            "z2_direct.open_target_detail",
            page.open_target_detail,
            lambda target_key, current_strategy_id, w=window: on_open_target_detail(w, target_key, current_strategy_id),
        )

    if page_name in (z2_direct.strategies_page, z2_direct.user_presets_page, PageName.BLOBS) and hasattr(page, "back_clicked"):
        connect_signal_once(
            window,
            f"back_to_control.{page_name.name}",
            page.back_clicked,
            lambda w=window: _show_active_zapret2_control_page(w),
        )

    if page_name == z2_direct.user_presets_page and hasattr(page, "preset_open_requested"):
        connect_signal_once(
            window,
            f"{page_name.name}.preset_open_requested",
            page.preset_open_requested,
            lambda preset_name, w=window: _open_zapret2_preset_detail(w, preset_name),
        )

    if page_name == z2_direct.preset_detail_page and hasattr(page, "back_clicked"):
        connect_signal_once(
            window,
            "z2_preset_detail.back_clicked",
            page.back_clicked,
            lambda target=resolve_preset_detail_back_page_for_method("direct_zapret2"): window.show_page(target),
        )
        if hasattr(page, "navigate_to_root"):
            connect_signal_once(
                window,
                "z2_preset_detail.navigate_to_root",
                page.navigate_to_root,
                lambda target=resolve_preset_detail_root_page_for_method("direct_zapret2"): window.show_page(target),
            )

    if page_name == z2_direct.control_page:
        if hasattr(page, "navigate_to_presets"):
            _connect_show_page_signal(
                window,
                f"{page_name.name}.navigate_to_presets",
                page.navigate_to_presets,
                z2_direct.user_presets_page,
            )

        if hasattr(page, "navigate_to_direct_launch"):
            _connect_show_page_signal(
                window,
                f"{page_name.name}.navigate_to_direct_launch",
                page.navigate_to_direct_launch,
                z2_direct.strategies_page,
            )

        if hasattr(page, "navigate_to_blobs"):
            _connect_show_page_signal(
                window,
                f"{page_name.name}.navigate_to_blobs",
                page.navigate_to_blobs,
                PageName.BLOBS,
            )

        if page_name == z2_direct.control_page and hasattr(page, "direct_mode_changed"):
            connect_signal_once(
                window,
                f"{page_name.name}.direct_mode_changed",
                page.direct_mode_changed,
                lambda mode, w=window: on_direct_mode_changed(w, mode),
            )

    if page_name == z2_direct.strategy_detail_page:
        if hasattr(page, "back_clicked"):
            connect_signal_once(
                window,
                "strategy_detail.back_clicked",
                page.back_clicked,
                lambda w=window: on_strategy_detail_back(w),
            )
        if hasattr(page, "navigate_to_root"):
            connect_signal_once(
                window,
                "strategy_detail.navigate_to_root",
                page.navigate_to_root,
                lambda target=resolve_strategy_detail_root_page_for_method("direct_zapret2"): window.show_page(target),
            )
        if hasattr(page, "strategy_selected"):
            connect_signal_once(
                window,
                "strategy_detail.strategy_selected",
                page.strategy_selected,
                lambda target_key, strategy_id, w=window: on_strategy_detail_selected(w, target_key, strategy_id),
            )
        if hasattr(page, "filter_mode_changed"):
            connect_signal_once(
                window,
                "strategy_detail.filter_mode_changed",
                page.filter_mode_changed,
                lambda target_key, filter_mode, w=window: on_strategy_detail_filter_mode_changed(w, target_key, filter_mode),
            )

def _connect_z1_navigation_signals(window, page_name: PageName, page: QWidget, z1_pages) -> None:
    if page_name in (z1_pages.strategies_page, z1_pages.user_presets_page) and hasattr(page, "back_clicked"):
        _connect_show_page_signal(
            window,
            f"back_to_z1_control.{page_name.name}",
            page.back_clicked,
            z1_pages.control_page,
        )

    if page_name == z1_pages.user_presets_page and hasattr(page, "preset_open_requested"):
        connect_signal_once(
            window,
            "z1_user_presets.preset_open_requested",
            page.preset_open_requested,
            lambda preset_name, w=window: _open_zapret1_preset_detail(w, preset_name),
        )

    if page_name == z1_pages.preset_detail_page and hasattr(page, "back_clicked"):
        _connect_show_page_signal(
            window,
            "z1_preset_detail.back_clicked",
            page.back_clicked,
            resolve_preset_detail_back_page_for_method("direct_zapret1"),
        )
        if hasattr(page, "navigate_to_root"):
            _connect_show_page_signal(
                window,
                "z1_preset_detail.navigate_to_root",
                page.navigate_to_root,
                resolve_preset_detail_root_page_for_method("direct_zapret1"),
            )

    if page_name == z1_pages.strategies_page and hasattr(page, "target_clicked"):
        connect_signal_once(
            window,
            "z1_direct.target_clicked",
            page.target_clicked,
            lambda target_key, target_info, w=window: open_zapret1_target_detail(w, target_key, target_info),
        )

    if page_name == z1_pages.strategy_detail_page:
        if hasattr(page, "back_clicked"):
            _connect_show_page_signal(
                window,
                "z1_strategy_detail.back_clicked",
                page.back_clicked,
                z1_pages.strategies_page,
            )
        if hasattr(page, "navigate_to_control"):
            _connect_show_page_signal(
                window,
                "z1_strategy_detail.navigate_to_control",
                page.navigate_to_control,
                resolve_strategy_detail_root_page_for_method("direct_zapret1"),
            )
        if hasattr(page, "strategy_selected"):
            connect_signal_once(
                window,
                "z1_strategy_detail.strategy_selected",
                page.strategy_selected,
                lambda target_key, strategy_id, w=window: on_z1_strategy_detail_selected(w, target_key, strategy_id),
            )

    if page_name == z1_pages.control_page:
        if hasattr(page, "navigate_to_strategies"):
            _connect_show_page_signal(
                window,
                "z1_control.navigate_to_strategies",
                page.navigate_to_strategies,
                z1_pages.strategies_page,
            )
        if hasattr(page, "navigate_to_presets"):
            _connect_show_page_signal(
                window,
                "z1_control.navigate_to_presets",
                page.navigate_to_presets,
                z1_pages.user_presets_page,
            )
        if hasattr(page, "navigate_to_blobs"):
            _connect_show_page_signal(
                window,
                "z1_control.navigate_to_blobs",
                page.navigate_to_blobs,
                PageName.BLOBS,
            )


def _connect_common_page_signals(window, page_name: PageName, page: QWidget) -> None:
    if page_name == PageName.AUTOSTART:
        if hasattr(page, "autostart_enabled"):
            connect_signal_once(
                window,
                "autostart.autostart_enabled",
                page.autostart_enabled,
                lambda w=window: on_main_window_autostart_enabled(w),
            )
        if hasattr(page, "autostart_disabled"):
            connect_signal_once(
                window,
                "autostart.autostart_disabled",
                page.autostart_disabled,
                lambda w=window: on_main_window_autostart_disabled(w),
            )
        if hasattr(page, "navigate_to_dpi_settings"):
            connect_signal_once(
                window,
                "autostart.navigate_to_dpi_settings",
                page.navigate_to_dpi_settings,
                window._navigate_to_dpi_settings,
            )

    if page_name == PageName.APPEARANCE:
        if hasattr(page, "display_mode_changed"):
            window.display_mode_changed = page.display_mode_changed
        elif hasattr(page, "theme_changed"):
            window.display_mode_changed = page.theme_changed

        if hasattr(page, "garland_changed"):
            connect_signal_once(
                window,
                "appearance.garland_changed",
                page.garland_changed,
                window.set_garland_enabled,
            )
        if hasattr(page, "snowflakes_changed"):
            connect_signal_once(
                window,
                "appearance.snowflakes_changed",
                page.snowflakes_changed,
                window.set_snowflakes_enabled,
            )
        if hasattr(page, "background_refresh_needed"):
            connect_signal_once(
                window,
                "appearance.background_refresh_needed",
                page.background_refresh_needed,
                lambda w=window: on_background_refresh_needed(w),
            )
        if hasattr(page, "background_preset_changed"):
            connect_signal_once(
                window,
                "appearance.background_preset_changed",
                page.background_preset_changed,
                lambda preset, w=window: on_background_preset_changed(w, preset),
            )
        if hasattr(page, "opacity_changed"):
            connect_signal_once(
                window,
                "appearance.opacity_changed",
                page.opacity_changed,
                lambda value, w=window: on_opacity_changed(w, value),
            )
        if hasattr(page, "mica_changed"):
            connect_signal_once(
                window,
                "appearance.mica_changed",
                page.mica_changed,
                lambda enabled, w=window: on_mica_changed(w, enabled),
            )
        if hasattr(page, "animations_changed"):
            connect_signal_once(
                window,
                "appearance.animations_changed",
                page.animations_changed,
                lambda enabled, w=window: on_animations_changed(w, enabled),
            )
        if hasattr(page, "smooth_scroll_changed"):
            connect_signal_once(
                window,
                "appearance.smooth_scroll_changed",
                page.smooth_scroll_changed,
                lambda enabled, w=window: on_smooth_scroll_changed(w, enabled),
            )
        if hasattr(page, "editor_smooth_scroll_changed"):
            connect_signal_once(
                window,
                "appearance.editor_smooth_scroll_changed",
                page.editor_smooth_scroll_changed,
                lambda enabled, w=window: on_editor_smooth_scroll_changed(w, enabled),
            )
        if hasattr(page, "ui_language_changed"):
            connect_signal_once(
                window,
                "appearance.ui_language_changed",
                page.ui_language_changed,
                lambda language, w=window: on_main_window_ui_language_changed(w, language),
            )

    if page_name == PageName.ABOUT:
        if hasattr(page, "open_premium_requested"):
            connect_signal_once(
                window,
                "about.open_premium_requested",
                page.open_premium_requested,
                lambda w=window: open_main_window_subscription_dialog(w),
            )
        if hasattr(page, "open_updates_requested"):
            _connect_show_page_signal(
                window,
                "about.open_updates_requested",
                page.open_updates_requested,
                PageName.SERVERS,
            )

    if page_name == PageName.PREMIUM and hasattr(page, "subscription_updated"):
        connect_signal_once(
            window,
            "premium.subscription_updated",
            page.subscription_updated,
            lambda is_premium, days_remaining, w=window: on_main_window_subscription_updated(w, is_premium, days_remaining),
        )

    if page_name == PageName.DPI_SETTINGS and hasattr(page, "launch_method_changed"):
        connect_signal_once(
            window,
            "dpi_settings.launch_method_changed",
            page.launch_method_changed,
            lambda method, w=window: handle_main_window_launch_method_changed(w, method),
        )

    if page_name in (
        PageName.ZAPRET1_DIRECT,
        PageName.ZAPRET2_DIRECT,
    ) and hasattr(page, "strategy_selected"):
        connect_signal_once(
            window,
            f"strategy_selected.{page_name.name}",
            page.strategy_selected,
            lambda strategy_id, strategy_name, w=window: on_strategy_selected_from_page(w, strategy_id, strategy_name),
        )


def connect_lazy_page_signals(window, page_name: PageName, page: QWidget) -> None:
    z1_pages = resolve_zapret1_navigation_pages()
    _connect_common_page_signals(window, page_name, page)

    if page_name == PageName.ZAPRET2_DIRECT and hasattr(page, "open_target_detail"):
        connect_signal_once(
            window,
            "z2_direct.open_target_detail",
            page.open_target_detail,
            lambda target_key, current_strategy_id, w=window: on_open_target_detail(w, target_key, current_strategy_id),
        )
    _connect_z2_navigation_signals(window, page_name, page, resolve_zapret2_navigation_pages("direct_zapret2"))
    _connect_z1_navigation_signals(window, page_name, page, z1_pages)

    if page_name == PageName.ORCHESTRA and hasattr(page, "clear_learned_requested"):
        connect_signal_once(
            window,
            "orchestra.clear_learned_requested",
            page.clear_learned_requested,
            lambda w=window: on_clear_learned_requested(w),
        )


def ensure_page(window, name: PageName) -> QWidget | None:
    page = window.pages.get(name)
    if page is not None:
        window._apply_ui_language_to_page(page)
        bind_page_ui_state(window, page)
        if bool(getattr(window, "_page_signal_bootstrap_complete", False)):
            ensure_page_in_stacked_widget(window, page)
        return page

    page_class_specs = getattr(window, "_page_class_specs", {}) or {}
    spec = page_class_specs.get(name)
    if spec is None:
        return None

    attr_name, module_name, class_name = spec
    import time as _time
    _t_page = _time.perf_counter()
    try:
        module = import_module(module_name)
        page_cls = getattr(module, class_name)
        page = page_cls(window)
    except Exception as e:
        log(f"Ошибка lazy-инициализации страницы {name}: {e}", "ERROR")
        return None

    route_key = get_page_route_key(name)
    if route_key:
        page.setObjectName(route_key)
    elif not page.objectName():
        page.setObjectName(page.__class__.__name__)

    setter = getattr(page, "_set_page_registry_name", None)
    if callable(setter):
        setter(name)
    else:
        setattr(page, "_page_registry_name", name)

    window.pages[name] = page
    setattr(window, attr_name, page)
    window._apply_ui_language_to_page(page)
    bind_page_ui_state(window, page)

    if bool(getattr(window, "_page_signal_bootstrap_complete", False)):
        connect_lazy_page_signals(window, name, page)
        ensure_page_in_stacked_widget(window, page)

    elapsed_ms = int((_time.perf_counter() - _t_page) * 1000)
    window._record_startup_page_init_metric(name, elapsed_ms)
    log_page_metric(name, "constructor", elapsed_ms, budget_ms=get_page_performance_profile(name).first_show_budget_ms)

    return page
