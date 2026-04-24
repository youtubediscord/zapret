"""UI/apply helper'ы для применения target payload на странице деталей стратегии Z2."""

from __future__ import annotations

from filters.ui.strategy_detail.filter_mode_ui import apply_filter_mode_selector_state


def prepare_target_payload_apply_ui(
    *,
    normalized_key: str,
    feedback_store,
    close_preview_fn,
    settings_host,
    toolbar_frame,
    title_label,
    subtitle_label,
    breadcrumb,
    apply_plan,
    detail_text: str,
    control_text: str,
    strategies_text: str,
    apply_header_state_fn,
):
    close_preview_fn(force=True)
    try:
        settings_host.setVisible(True)
    except Exception:
        pass
    try:
        toolbar_frame.setVisible(True)
    except Exception:
        pass
    try:
        favorite_ids = feedback_store.get_favorites(normalized_key)
    except Exception:
        favorite_ids = set()

    apply_header_state_fn(
        title_label,
        subtitle_label,
        breadcrumb,
        title_text=apply_plan.title_text,
        subtitle_text=apply_plan.subtitle_text,
        detail_text=detail_text,
        control_text=control_text,
        strategies_text=strategies_text,
    )
    return favorite_ids


def apply_payload_reuse_plan(
    *,
    reuse_list: bool,
    clear_strategies_fn,
    load_strategies_fn,
    policy,
    strategies_tree,
    favorite_ids: set[str],
    refresh_working_marks_fn,
    current_strategy_id: str,
    restore_scroll_state_fn,
    normalized_key: str,
) -> None:
    if not reuse_list:
        clear_strategies_fn()
        load_strategies_fn(policy)
        return

    for strategy_id in (strategies_tree.get_strategy_ids() if strategies_tree else []):
        want_favorite = strategy_id in favorite_ids
        strategies_tree.set_favorite_state(strategy_id, want_favorite)

    refresh_working_marks_fn()
    normalized_strategy_id = str(current_strategy_id or "none").strip() or "none"
    try:
        if normalized_strategy_id != "none" and strategies_tree.has_strategy(normalized_strategy_id):
            strategies_tree.set_selected_strategy(normalized_strategy_id)
        elif strategies_tree.has_strategy("none"):
            strategies_tree.set_selected_strategy("none")
        else:
            strategies_tree.clearSelection()
    except Exception:
        pass
    restore_scroll_state_fn(normalized_key, defer=True)


def finalize_target_payload_apply_ui(
    *,
    policy,
    normalized_key: str,
    load_target_filter_mode_fn,
    filter_mode_selector,
    apply_target_mode_visibility_fn,
    search_input,
    active_filters: set[str],
    load_target_sort_fn,
    set_sort_mode_fn,
    update_technique_filter_ui_fn,
    apply_sort_fn,
    apply_filters_fn,
    load_syndata_settings_fn,
    apply_syndata_settings_fn,
    refresh_args_editor_state_fn,
    set_target_enabled_ui_fn,
    target_enabled: bool,
    stop_loading_fn,
    hide_success_icon_fn,
    log_metric_fn,
    started_at: float,
    reason: str,
    tcp_phase_mode: bool,
) -> None:
    if policy.show_filter_mode_frame:
        saved_filter_mode = load_target_filter_mode_fn(normalized_key)
        apply_filter_mode_selector_state(filter_mode_selector, mode=saved_filter_mode)
    apply_target_mode_visibility_fn(policy)

    try:
        search_input.clear()
    except Exception:
        pass
    try:
        active_filters.clear()
    except Exception:
        pass
    set_sort_mode_fn(load_target_sort_fn(normalized_key))
    update_technique_filter_ui_fn()

    # TCP phase restoration intentionally stays in the page for now; this helper
    # only handles the common tail shared by all target payload applies.
    _ = tcp_phase_mode

    apply_sort_fn()
    apply_filters_fn()

    syndata_settings = load_syndata_settings_fn(normalized_key)
    apply_syndata_settings_fn(syndata_settings)
    apply_target_mode_visibility_fn(policy)
    refresh_args_editor_state_fn()
    set_target_enabled_ui_fn(target_enabled)
    stop_loading_fn()
    hide_success_icon_fn()

    log_metric_fn(
        "show_target.total",
        started_at,
        extra=(
            f"target={normalized_key}, reason={reason}, "
            f"tcp_phase={'yes' if tcp_phase_mode else 'no'}"
        ),
    )
