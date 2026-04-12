from __future__ import annotations

from PyQt6.QtWidgets import QWidget

from direct_launch.runtime import handle_launch_method_changed_runtime
from ui.navigation.navigation_controller import ensure_navigation_controller
from ui.navigation_targets import (
    resolve_preset_detail_back_page_for_method,
    resolve_preset_detail_root_page_for_method,
    resolve_strategy_detail_root_page_for_method,
    resolve_zapret1_navigation_pages,
    resolve_zapret2_navigation_pages,
)
from ui.orchestra_runtime_actions import on_clear_learned_requested
from ui.page_contracts import PageSignalName, get_page_signal
from ui.page_names import PageName
from ui.strategy_detail_workflow import (
    on_open_target_detail,
    on_strategy_detail_back,
    on_strategy_detail_filter_mode_changed,
    on_strategy_detail_selected,
    on_z1_strategy_detail_selected,
    open_zapret1_target_detail,
)
from ui.strategy_selection_workflow import on_strategy_selected_from_page
from ui.window_display_state import on_direct_mode_changed

from .helpers import (
    connect_page_signal_if_present,
    connect_show_page_signal,
    connect_show_page_signal_if_present,
)


def _show_active_zapret2_control_page(window) -> None:
    from ui.ui_workflows import ensure_ui_workflows

    ensure_ui_workflows(window).show_active_zapret2_control_page()


def _open_zapret2_preset_detail(window, preset_name: str) -> None:
    from ui.ui_workflows import ensure_ui_workflows

    ensure_ui_workflows(window).open_zapret2_preset_detail(preset_name)


def _open_zapret1_preset_detail(window, preset_name: str) -> None:
    from ui.ui_workflows import ensure_ui_workflows

    ensure_ui_workflows(window).open_zapret1_preset_detail(preset_name)


def _on_launch_method_changed(window, method: str) -> None:
    from ui.ui_workflows import ensure_ui_workflows

    plan = handle_launch_method_changed_runtime(window, method)

    if plan.dispatch_action == "restart":
        log_text = (
            f"Метод '{method}' сохранён, дальнейший запуск передан в единый runtime pipeline"
        )
    elif plan.dispatch_action == "stop":
        log_text = (
            f"Метод '{method}' сохранён, активный DPI будет остановлен через единый runtime pipeline"
        )
    else:
        log_text = f"Метод '{method}' сохранён без немедленного запуска"

    try:
        from log import log

        log(log_text, "INFO")
    except Exception:
        pass

    try:
        ensure_navigation_controller(window).sync_nav_visibility(method)
    except Exception:
        pass

    try:
        ensure_ui_workflows(window).redirect_to_strategies_page_for_method(method)
    except Exception:
        pass


def connect_direct_page_signals(window, page_name: PageName, page: QWidget) -> None:
    z1_pages = resolve_zapret1_navigation_pages()
    z2_direct = resolve_zapret2_navigation_pages("direct_zapret2")

    if page_name == PageName.ZAPRET2_DIRECT:
        connect_page_signal_if_present(
            window,
            "z2_direct.open_target_detail",
            page,
            PageSignalName.OPEN_TARGET_DETAIL,
            lambda target_key, current_strategy_id, w=window: on_open_target_detail(w, target_key, current_strategy_id),
        )

    if page_name in (z2_direct.strategies_page, z2_direct.user_presets_page, PageName.BLOBS):
        connect_page_signal_if_present(
            window,
            f"back_to_control.{page_name.name}",
            page,
            PageSignalName.BACK_CLICKED,
            lambda w=window: _show_active_zapret2_control_page(w),
        )

    if page_name == z2_direct.user_presets_page:
        connect_page_signal_if_present(
            window,
            f"{page_name.name}.preset_open_requested",
            page,
            PageSignalName.PRESET_OPEN_REQUESTED,
            lambda preset_name, w=window: _open_zapret2_preset_detail(w, preset_name),
        )

    if page_name == z2_direct.preset_detail_page:
        connect_show_page_signal_if_present(
            window,
            "z2_preset_detail.back_clicked",
            page,
            PageSignalName.BACK_CLICKED,
            resolve_preset_detail_back_page_for_method("direct_zapret2"),
            allow_internal=True,
        )
        connect_show_page_signal_if_present(
            window,
            "z2_preset_detail.navigate_to_root",
            page,
            PageSignalName.NAVIGATE_TO_ROOT,
            resolve_preset_detail_root_page_for_method("direct_zapret2"),
        )

    if page_name == z2_direct.control_page:
        signal_obj = get_page_signal(page, PageSignalName.NAVIGATE_TO_PRESETS)
        if signal_obj is not None:
            connect_show_page_signal(window, f"{page_name.name}.navigate_to_presets", signal_obj, z2_direct.user_presets_page, allow_internal=True)

        signal_obj = get_page_signal(page, PageSignalName.NAVIGATE_TO_DIRECT_LAUNCH)
        if signal_obj is not None:
            connect_show_page_signal(window, f"{page_name.name}.navigate_to_direct_launch", signal_obj, z2_direct.strategies_page, allow_internal=True)

        signal_obj = get_page_signal(page, PageSignalName.NAVIGATE_TO_BLOBS)
        if signal_obj is not None:
            connect_show_page_signal(window, f"{page_name.name}.navigate_to_blobs", signal_obj, PageName.BLOBS, allow_internal=True)

        connect_page_signal_if_present(
            window,
            f"{page_name.name}.direct_mode_changed",
            page,
            PageSignalName.DIRECT_MODE_CHANGED,
            lambda mode, w=window: on_direct_mode_changed(w, mode),
        )

    if page_name == z2_direct.strategy_detail_page:
        connect_page_signal_if_present(window, "strategy_detail.back_clicked", page, PageSignalName.BACK_CLICKED, lambda w=window: on_strategy_detail_back(w))
        connect_show_page_signal_if_present(
            window,
            "strategy_detail.navigate_to_root",
            page,
            PageSignalName.NAVIGATE_TO_ROOT,
            resolve_strategy_detail_root_page_for_method("direct_zapret2"),
        )
        connect_page_signal_if_present(
            window,
            "strategy_detail.strategy_selected",
            page,
            PageSignalName.STRATEGY_SELECTED,
            lambda target_key, strategy_id, w=window: on_strategy_detail_selected(w, target_key, strategy_id),
        )
        connect_page_signal_if_present(
            window,
            "strategy_detail.filter_mode_changed",
            page,
            PageSignalName.FILTER_MODE_CHANGED,
            lambda target_key, filter_mode, w=window: on_strategy_detail_filter_mode_changed(w, target_key, filter_mode),
        )

    if page_name in (z1_pages.strategies_page, z1_pages.user_presets_page):
        connect_show_page_signal_if_present(window, f"back_to_z1_control.{page_name.name}", page, PageSignalName.BACK_CLICKED, z1_pages.control_page)

    if page_name == z1_pages.user_presets_page:
        connect_page_signal_if_present(
            window,
            "z1_user_presets.preset_open_requested",
            page,
            PageSignalName.PRESET_OPEN_REQUESTED,
            lambda preset_name, w=window: _open_zapret1_preset_detail(w, preset_name),
        )

    if page_name == z1_pages.preset_detail_page:
        connect_show_page_signal_if_present(window, "z1_preset_detail.back_clicked", page, PageSignalName.BACK_CLICKED, resolve_preset_detail_back_page_for_method("direct_zapret1"), allow_internal=True)
        connect_show_page_signal_if_present(window, "z1_preset_detail.navigate_to_root", page, PageSignalName.NAVIGATE_TO_ROOT, resolve_preset_detail_root_page_for_method("direct_zapret1"))

    if page_name == z1_pages.strategies_page:
        connect_page_signal_if_present(
            window,
            "z1_direct.target_clicked",
            page,
            PageSignalName.TARGET_CLICKED,
            lambda target_key, target_info, w=window: open_zapret1_target_detail(w, target_key, target_info),
        )

    if page_name == z1_pages.strategy_detail_page:
        connect_show_page_signal_if_present(window, "z1_strategy_detail.back_clicked", page, PageSignalName.BACK_CLICKED, z1_pages.strategies_page, allow_internal=True)
        connect_show_page_signal_if_present(window, "z1_strategy_detail.navigate_to_control", page, PageSignalName.NAVIGATE_TO_CONTROL, resolve_strategy_detail_root_page_for_method("direct_zapret1"))
        connect_page_signal_if_present(
            window,
            "z1_strategy_detail.strategy_selected",
            page,
            PageSignalName.STRATEGY_SELECTED,
            lambda target_key, strategy_id, w=window: on_z1_strategy_detail_selected(w, target_key, strategy_id),
        )

    if page_name == z1_pages.control_page:
        connect_show_page_signal_if_present(window, "z1_control.navigate_to_strategies", page, PageSignalName.NAVIGATE_TO_STRATEGIES, z1_pages.strategies_page, allow_internal=True)
        connect_show_page_signal_if_present(window, "z1_control.navigate_to_presets", page, PageSignalName.NAVIGATE_TO_PRESETS, z1_pages.user_presets_page, allow_internal=True)
        connect_show_page_signal_if_present(window, "z1_control.navigate_to_blobs", page, PageSignalName.NAVIGATE_TO_BLOBS, PageName.BLOBS, allow_internal=True)

    if page_name == PageName.DPI_SETTINGS:
        connect_page_signal_if_present(window, "dpi_settings.launch_method_changed", page, PageSignalName.LAUNCH_METHOD_CHANGED, lambda method, w=window: _on_launch_method_changed(w, method))

    if page_name in (PageName.ZAPRET1_DIRECT, PageName.ZAPRET2_DIRECT):
        connect_page_signal_if_present(
            window,
            f"strategy_selected.{page_name.name}",
            page,
            PageSignalName.STRATEGY_SELECTED,
            lambda strategy_id, strategy_name, w=window: on_strategy_selected_from_page(w, strategy_id, strategy_name),
        )

    if page_name == PageName.ORCHESTRA:
        connect_page_signal_if_present(
            window,
            "orchestra.clear_learned_requested",
            page,
            PageSignalName.CLEAR_LEARNED_REQUESTED,
            lambda w=window: on_clear_learned_requested(w),
        )


__all__ = ["connect_direct_page_signals"]
