"""UI-helper'ы для фильтрации и сортировки на странице деталей стратегии Z2."""

from __future__ import annotations


def populate_sort_combo(combo, entries) -> None:
    if combo is None:
        return

    combo.blockSignals(True)
    try:
        combo.clear()
        for entry in entries:
            mode = entry.mode
            label = entry.label
            combo.addItem(label)
            try:
                combo.setItemData(combo.count() - 1, mode)
            except Exception:
                pass
    finally:
        combo.blockSignals(False)


def update_sort_button_ui(
    *,
    combo,
    button,
    sort_mode: str,
    tr,
    previous_icon_color,
    get_theme_tokens_fn,
    build_tooltip_fn,
    apply_sort_combo_state_fn,
    apply_sort_button_state_fn,
    set_tooltip_fn,
    icon_builder,
):
    target_mode = str(sort_mode or "default").strip().lower() or "default"

    if combo is not None:
        apply_sort_combo_state_fn(
            combo,
            target_mode=target_mode,
        )

    if not button:
        return previous_icon_color

    is_active = target_mode != "default"
    try:
        tokens = get_theme_tokens_fn()
        color = tokens.accent_hex if is_active else tokens.fg_faint
        tooltip_text = build_tooltip_fn(mode=sort_mode, tr=tr)
        return apply_sort_button_state_fn(
            button,
            is_active=is_active,
            icon_color=color,
            tooltip_text=tooltip_text,
            previous_icon_color=previous_icon_color,
            icon_builder=icon_builder,
            set_tooltip_fn=set_tooltip_fn,
        )
    except Exception:
        return previous_icon_color


def update_technique_filter_ui(
    *,
    combo,
    active_filters: set[str],
    technique_filters,
    build_technique_filter_plan_fn,
    apply_technique_filter_combo_state_fn,
) -> None:
    if combo is None:
        return

    plan = build_technique_filter_plan_fn(
        active_filters=active_filters,
        technique_filters=technique_filters,
    )
    apply_technique_filter_combo_state_fn(
        combo,
        target_index=plan.target_index,
    )


def update_strategies_summary(
    *,
    label,
    tree,
    search_text: str,
    tcp_phase_mode: bool,
    active_phase_key: str,
    active_filters: set[str],
    technique_filters,
    tr,
    previous_text: str | None,
    build_summary_fn,
    apply_summary_label_fn,
):
    if label is None:
        return False, str(previous_text or "")

    total = tree.total_strategy_count() if tree is not None else 0
    visible = tree.visible_strategy_count() if tree is not None else 0
    search_active = bool(str(search_text or "").strip())

    plan = build_summary_fn(
        total=total,
        visible=visible,
        tcp_phase_mode=tcp_phase_mode,
        active_phase_key=active_phase_key,
        active_filters=active_filters,
        search_active=search_active,
        technique_filters=technique_filters,
        tr=tr,
    )

    return apply_summary_label_fn(
        label,
        plan.text,
        previous_text=previous_text,
    )


def apply_filter_plan_to_tree(
    *,
    tree,
    filter_plan,
    target_key: str,
    update_summary_fn,
    sync_phase_selection_fn,
    log_metric_fn,
    started_at: float,
) -> bool:
    if tree is None:
        return False

    if filter_plan.use_phase_filter:
        try:
            tree.set_all_strategies_phase(filter_plan.phase_key)
        except Exception:
            pass
        tree.apply_phase_filter(filter_plan.search_text, filter_plan.phase_key)
        if filter_plan.should_sync_phase_selection:
            sync_phase_selection_fn()
        update_summary_fn()
        try:
            log_metric_fn(
                "_apply_filters.phase",
                started_at,
                extra=(
                    f"target={target_key}, visible={tree.visible_strategy_count()}, "
                    f"total={tree.total_strategy_count()}, phase={filter_plan.phase_key or 'none'}, "
                    f"search={'yes' if filter_plan.search_text.strip() else 'no'}"
                ),
            )
        except Exception:
            pass
        return True

    try:
        tree.set_all_strategies_phase(None)
    except Exception:
        pass
    tree.apply_filter(filter_plan.search_text, filter_plan.active_filters)
    if filter_plan.should_restore_selected_strategy:
        tree.set_selected_strategy(filter_plan.selected_strategy_id)
    update_summary_fn()
    try:
        log_metric_fn(
            "_apply_filters.default",
            started_at,
            extra=(
                f"target={target_key}, visible={tree.visible_strategy_count()}, "
                f"total={tree.total_strategy_count()}, active_filters={len(filter_plan.active_filters)}, "
                f"search={'yes' if filter_plan.search_text.strip() else 'no'}"
            ),
        )
    except Exception:
        pass
    return True


def apply_sort_plan_to_tree(
    *,
    tree,
    sort_plan,
    target_key: str,
    set_sort_mode_fn,
    update_sort_button_ui_fn,
    update_summary_fn,
    log_metric_fn,
    started_at: float,
) -> str:
    if tree is None:
        return str(getattr(sort_plan, "normalized_mode", "") or "")

    normalized_mode = str(getattr(sort_plan, "normalized_mode", "") or "")
    set_sort_mode_fn(normalized_mode)
    tree.set_sort_mode(normalized_mode)
    tree.apply_sort()
    update_sort_button_ui_fn()
    update_summary_fn()
    if sort_plan.should_restore_selected_strategy:
        tree.set_selected_strategy(sort_plan.selected_strategy_id)
    try:
        log_metric_fn(
            "_apply_sort.total",
            started_at,
            extra=f"target={target_key}, mode={normalized_mode}, rows={tree.total_strategy_count()}",
        )
    except Exception:
        pass
    return normalized_mode
