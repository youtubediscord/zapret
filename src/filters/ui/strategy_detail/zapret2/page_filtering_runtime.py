from __future__ import annotations

import time as _time

from filters.strategy_detail.zapret2.filtering_logic import (
    build_filter_apply_plan,
    build_phase_selection_plan,
    build_phase_tab_change_plan,
    build_phase_tab_reclick_plan,
    build_sort_apply_plan,
    build_sort_change_plan,
    build_sort_options,
    build_sort_tooltip,
    build_strategies_summary,
    build_technique_filter_plan,
)
from filters.ui.strategy_detail.zapret2.common import STRATEGY_TECHNIQUE_FILTERS, log_z2_detail_metric as _log_z2_detail_metric
from filters.ui.strategy_detail.zapret2.filtering_ui import (
    apply_filter_plan_to_tree,
    apply_sort_plan_to_tree,
    populate_sort_combo,
    update_sort_button_ui,
    update_strategies_summary,
    update_technique_filter_ui,
)
from filters.ui.strategy_detail.zapret2.tcp_phase_ui import sync_tree_selection_to_active_phase


def on_search_changed(page, text: str) -> None:
    _ = text
    page._apply_filters()


def on_filter_toggled(page, technique: str, active: bool) -> None:
    if active:
        page._active_filters.add(technique)
    else:
        page._active_filters.discard(technique)
    page._update_technique_filter_ui()
    page._apply_filters()


def populate_sort_combo_runtime(page) -> None:
    entries = build_sort_options(tr=page._tr)
    populate_sort_combo(getattr(page, "_sort_combo", None), entries)
    page._update_sort_button_ui()


def update_sort_button_ui_runtime(page) -> None:
    page._last_sort_icon_color = update_sort_button_ui(
        combo=getattr(page, "_sort_combo", None),
        button=getattr(page, "_sort_btn", None),
        sort_mode=page._sort_mode,
        tr=page._tr,
        previous_icon_color=page._last_sort_icon_color,
        get_theme_tokens_fn=page._get_theme_tokens_fn,
        build_tooltip_fn=build_sort_tooltip,
        set_tooltip_fn=page._set_tooltip_fn,
        icon_builder=lambda icon_color: page._build_sort_icon(icon_color),
    )


def on_sort_combo_changed(page, index: int) -> None:
    combo = getattr(page, "_sort_combo", None)
    if combo is None:
        return

    requested_mode = "default"
    try:
        requested_mode = str(combo.itemData(index) or "default").strip().lower() or "default"
    except Exception:
        pass

    plan = build_sort_change_plan(
        requested_mode=requested_mode,
        current_mode=page._sort_mode,
        target_key=page._target_key,
    )
    if not plan.should_apply:
        return

    page._sort_mode = plan.normalized_mode
    if plan.should_persist:
        page._save_target_sort(page._target_key, page._sort_mode)
    page._apply_sort()


def on_technique_filter_changed(page, index: int) -> None:
    page._active_filters.clear()
    if index > 0 and index <= len(STRATEGY_TECHNIQUE_FILTERS):
        key = STRATEGY_TECHNIQUE_FILTERS[index - 1][1]
        page._active_filters.add(key)
    page._apply_filters()


def update_technique_filter_ui_runtime(page) -> None:
    update_technique_filter_ui(
        combo=getattr(page, "_filter_combo", None),
        active_filters=page._active_filters,
        technique_filters=STRATEGY_TECHNIQUE_FILTERS,
        build_technique_filter_plan_fn=build_technique_filter_plan,
    )


def update_strategies_summary_runtime(page) -> None:
    search_text = ""
    if getattr(page, "_search_input", None) is not None:
        try:
            search_text = page._search_input.text()
        except Exception:
            search_text = ""

    changed, page._last_strategies_summary_text = update_strategies_summary(
        label=getattr(page, "_strategies_summary_label", None),
        tree=getattr(page, "_strategies_tree", None),
        search_text=search_text,
        tcp_phase_mode=page._tcp_phase_mode,
        active_phase_key=page._active_phase_key,
        active_filters=page._active_filters,
        technique_filters=STRATEGY_TECHNIQUE_FILTERS,
        tr=page._tr,
        previous_text=page._last_strategies_summary_text,
        build_summary_fn=build_strategies_summary,
    )
    if not changed:
        return


def on_phase_tab_changed(page, route_key: str) -> None:
    plan = build_phase_tab_change_plan(
        tcp_phase_mode=bool(page._tcp_phase_mode),
        phase_key=route_key,
        target_key=page._target_key,
    )
    if not plan.should_apply:
        return

    page._active_phase_key = plan.normalized_phase_key
    try:
        if plan.should_persist:
            page._last_active_phase_key_by_target[page._target_key] = plan.normalized_phase_key
            page._save_target_last_tcp_phase_tab(page._target_key, plan.normalized_phase_key)
    except Exception:
        pass

    page._apply_filters()
    if plan.should_sync_phase_selection:
        page._sync_tree_selection_to_active_phase()


def on_phase_pivot_item_clicked(page, key: str) -> None:
    plan = build_phase_tab_reclick_plan(
        tcp_phase_mode=bool(page._tcp_phase_mode),
        clicked_key=key,
        active_phase_key=page._active_phase_key,
    )
    if plan.should_apply:
        page._apply_filters()
        if plan.should_sync_phase_selection:
            page._sync_tree_selection_to_active_phase()


def apply_filters_runtime(page) -> None:
    if not page._strategies_tree:
        return
    started_at = _time.perf_counter()
    search_text = page._search_input.text() if page._search_input else ""
    selected_sid = page._selected_strategy_id or page._current_strategy_id or "none"
    filter_plan = build_filter_apply_plan(
        tcp_phase_mode=bool(page._tcp_phase_mode),
        active_phase_key=page._active_phase_key,
        search_text=search_text,
        active_filters=page._active_filters,
        selected_strategy_id=page._selected_strategy_id,
        current_strategy_id=page._current_strategy_id,
        has_selected_strategy=bool(page._strategies_tree.has_strategy(selected_sid)),
        is_selected_visible=bool(page._strategies_tree.is_strategy_visible(selected_sid)) if selected_sid else False,
    )
    apply_filter_plan_to_tree(
        tree=page._strategies_tree,
        filter_plan=filter_plan,
        target_key=page._target_key,
        update_summary_fn=page._update_strategies_summary,
        sync_phase_selection_fn=page._sync_tree_selection_to_active_phase,
        log_metric_fn=lambda marker, metric_started_at, extra: _log_z2_detail_metric(
            marker,
            (_time.perf_counter() - metric_started_at) * 1000,
            extra=extra,
        ),
        started_at=started_at,
    )


def sync_tree_selection_to_active_phase_runtime(page) -> None:
    sync_tree_selection_to_active_phase(
        strategies_tree=page._strategies_tree,
        tcp_phase_mode=bool(page._tcp_phase_mode),
        active_phase_key=page._active_phase_key,
        tcp_phase_selected_ids=page._tcp_phase_selected_ids,
        custom_strategy_id=page.CUSTOM_STRATEGY_ID,
        build_phase_selection_plan_fn=build_phase_selection_plan,
    )


def show_sort_menu_runtime(page) -> None:
    def _set_sort(mode: str):
        plan = build_sort_change_plan(
            requested_mode=mode,
            current_mode=page._sort_mode,
            target_key=page._target_key,
        )
        if not plan.should_apply:
            return
        page._sort_mode = plan.normalized_mode
        if plan.should_persist:
            page._save_target_sort(page._target_key, page._sort_mode)
        page._apply_sort()

    if getattr(page, "_sort_btn", None) is None:
        return
    page._show_sort_menu_impl(
        parent=page,
        sort_button=page._sort_btn,
        current_mode=page._sort_mode,
        has_fluent=page._HAS_FLUENT,
        round_menu_cls=page._round_menu_cls,
        action_cls=page._action_cls,
        fluent_icon=page._fluent_icon_cls,
        build_sort_options_fn=build_sort_options,
        tr=page._tr,
        on_select=_set_sort,
        exec_popup_menu_fn=page._exec_popup_menu_fn,
    )


def apply_sort_runtime(page) -> None:
    if not page._strategies_tree:
        return
    started_at = _time.perf_counter()
    selected_sid = page._selected_strategy_id or page._current_strategy_id or "none"
    plan = build_sort_apply_plan(
        sort_mode=page._sort_mode,
        selected_strategy_id=page._selected_strategy_id,
        current_strategy_id=page._current_strategy_id,
        has_selected_strategy=bool(page._strategies_tree.has_strategy(selected_sid)),
    )
    page._sort_mode = apply_sort_plan_to_tree(
        tree=page._strategies_tree,
        sort_plan=plan,
        target_key=page._target_key,
        set_sort_mode_fn=lambda mode: setattr(page, "_sort_mode", mode),
        update_sort_button_ui_fn=page._update_sort_button_ui,
        update_summary_fn=page._update_strategies_summary,
        log_metric_fn=lambda marker, metric_started_at, extra: _log_z2_detail_metric(
            marker,
            (_time.perf_counter() - metric_started_at) * 1000,
            extra=extra,
        ),
        started_at=started_at,
    )
