"""TCP phase workflow helper'ы для страницы деталей стратегии Z2."""

from __future__ import annotations


def build_strategy_args_lookup(*, strategies_data_by_id, load_args_text_fn) -> dict[str, str]:
    return {
        str(strategy_id): load_args_text_fn(str(strategy_id))
        for strategy_id in (strategies_data_by_id or {}).keys()
        if str(strategy_id or "").strip()
    }


def load_tcp_phase_state(
    *,
    tcp_phase_mode: bool,
    target_key: str,
    args_text: str,
    strategies_data_by_id,
    phase_order,
    embedded_fake_techniques,
    fake_disabled_strategy_id: str,
    custom_strategy_id: str,
    normalize_args_text_fn,
    extract_desync_technique_fn,
    map_phase_fn,
    infer_phase_key_fn,
    build_state_plan_fn,
):
    if not (tcp_phase_mode and target_key):
        return {}, {}, False

    hide_fake_phase = False
    args_norm = normalize_args_text_fn(args_text)
    phase_lines: dict[str, list[str]] = {key: [] for key in phase_order}
    if args_norm:
        for raw in args_norm.splitlines():
            line = raw.strip()
            if not line or line == "--new":
                continue
            technique = extract_desync_technique_fn(line)
            if not technique:
                continue
            if technique in embedded_fake_techniques:
                hide_fake_phase = True
            phase = map_phase_fn(technique)
            if not phase:
                continue
            phase_lines.setdefault(phase, []).append(line)

    phase_chunks = {
        key: normalize_args_text_fn("\n".join(lines))
        for key, lines in phase_lines.items()
        if lines
    }

    lookup: dict[str, dict[str, str]] = {key: {} for key in phase_order}
    for strategy_id, data in (strategies_data_by_id or {}).items():
        if not strategy_id or strategy_id == fake_disabled_strategy_id:
            continue
        args_val = (data or {}).get("args") if isinstance(data, dict) else ""
        if isinstance(args_val, (list, tuple)):
            args_val = "\n".join([str(arg) for arg in args_val if arg is not None])
        normalized_args = normalize_args_text_fn(str(args_val or ""))
        if not normalized_args:
            continue
        phase_key = infer_phase_key_fn(normalized_args)
        if not phase_key:
            continue
        if normalized_args not in lookup.get(phase_key, {}):
            lookup.setdefault(phase_key, {})[normalized_args] = strategy_id

    plan = build_state_plan_fn(
        phase_chunks=phase_chunks,
        phase_lookup=lookup,
        phase_order=phase_order,
        hide_fake_phase=hide_fake_phase,
        fake_disabled_strategy_id=fake_disabled_strategy_id,
        custom_strategy_id=custom_strategy_id,
    )
    return dict(plan.selected_ids or {}), dict(plan.custom_args or {}), bool(plan.hide_fake_phase)


def apply_tcp_phase_save_result(
    plan,
    *,
    target_key: str,
    set_selected_state_fn,
    set_target_enabled_ui_fn,
    refresh_args_editor_fn,
    show_loading_fn,
    stop_loading_fn,
    hide_success_icon_fn,
    update_header_fn,
    update_markers_fn,
    emit_selection_fn,
) -> None:
    set_selected_state_fn(plan.selected_strategy_id, plan.current_strategy_id)
    set_target_enabled_ui_fn(plan.target_enabled)
    if plan.should_refresh_args_editor:
        refresh_args_editor_fn()

    if plan.should_show_loading:
        show_loading_fn()
    elif plan.should_hide_loading:
        stop_loading_fn()
        hide_success_icon_fn()

    if plan.should_update_header:
        update_header_fn(plan.selected_strategy_id)
    if plan.should_update_markers:
        update_markers_fn()

    if plan.should_emit_selection:
        emit_selection_fn(target_key, plan.selected_strategy_id)


def apply_tcp_phase_row_click_result(
    plan,
    *,
    set_phase_state_fn,
    strategies_tree,
    apply_tabs_visibility_fn,
    save_state_fn,
) -> None:
    if not plan.should_apply:
        return

    set_phase_state_fn(
        dict(plan.selected_ids or {}),
        dict(plan.custom_args or {}),
        bool(plan.hide_fake_phase),
    )

    if plan.should_clear_active_strategy:
        try:
            strategies_tree.clear_active_strategy()
        except Exception:
            pass
    elif plan.should_select_strategy and plan.selected_strategy_id:
        strategies_tree.set_selected_strategy(plan.selected_strategy_id)

    apply_tabs_visibility_fn()
    if plan.should_save:
        save_state_fn(show_loading=True)
