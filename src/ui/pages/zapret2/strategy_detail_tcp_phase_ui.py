"""TCP phase UI-helper'ы для страницы деталей стратегии Z2."""

from __future__ import annotations


def update_tcp_phase_chip_markers(
    *,
    tcp_phase_mode: bool,
    tabbar,
    phase_tab_index_by_key: dict[str, int],
    tcp_phase_tab_order,
    selected_ids: dict[str, str],
    custom_args: dict[str, str],
    fake_disabled_strategy_id: str,
    custom_strategy_id: str,
    build_marker_plan_fn,
) -> None:
    if not tcp_phase_mode or not tabbar:
        return

    label_map = {phase_key: label for phase_key, label in tcp_phase_tab_order}
    plan = build_marker_plan_fn(
        phase_label_map=label_map,
        selected_ids=selected_ids,
        custom_args=custom_args,
        fake_disabled_strategy_id=fake_disabled_strategy_id,
        custom_strategy_id=custom_strategy_id,
    )

    for key in (phase_tab_index_by_key or {}).keys():
        try:
            item = (tabbar.items or {}).get(key)
            if item is None:
                continue
            fallback_label = label_map.get(key, str(key).upper())
            new_text = str(plan.labels_by_phase.get(key, fallback_label) or fallback_label)
            if item.text() != new_text:
                item.setText(new_text)
                item.adjustSize()
        except Exception:
            pass


def apply_tcp_phase_tabs_visibility(
    *,
    tcp_phase_mode: bool,
    phase_tabbar,
    hide_fake_phase: bool,
    active_phase_key: str | None,
    build_tabs_visibility_plan_fn,
    set_active_phase_chip_fn,
    reapply_filters_fn,
) -> None:
    if not tcp_phase_mode:
        return

    plan = build_tabs_visibility_plan_fn(
        hide_fake_phase=bool(hide_fake_phase),
        active_phase_key=active_phase_key,
    )
    try:
        if phase_tabbar is not None:
            fake_item = (phase_tabbar.items or {}).get("fake")
            if fake_item is not None:
                fake_item.setVisible(not plan.hide_fake_phase)
    except Exception:
        pass

    if plan.fallback_phase_key:
        set_active_phase_chip_fn(plan.fallback_phase_key)
        if plan.should_reapply_filters:
            try:
                reapply_filters_fn()
            except Exception:
                pass


def set_active_phase_chip(
    *,
    tcp_phase_mode: bool,
    phase_tabbar,
    phase_tab_index_by_key: dict[str, int],
    requested_phase_key: str,
    build_active_phase_chip_plan_fn,
) -> str | None:
    if not tcp_phase_mode or not phase_tabbar:
        return None

    available_keys = set((phase_tab_index_by_key or {}).keys())
    visible_keys: set[str] = set()
    try:
        for key, item in (getattr(phase_tabbar, "items", {}) or {}).items():
            if item is not None and item.isVisible():
                visible_keys.add(str(key))
    except Exception:
        visible_keys = set(available_keys)

    plan = build_active_phase_chip_plan_fn(
        requested_phase_key=requested_phase_key,
        available_phase_keys=available_keys,
        visible_phase_keys=visible_keys,
    )
    if not plan.should_apply or not plan.final_phase_key:
        return None

    try:
        phase_tabbar.blockSignals(True)
        phase_tabbar.setCurrentItem(plan.final_phase_key)
    except Exception:
        pass
    finally:
        try:
            phase_tabbar.blockSignals(False)
        except Exception:
            pass

    return plan.final_phase_key


def select_default_tcp_phase_tab(
    *,
    tcp_phase_mode: bool,
    selected_ids: dict[str, str],
    hide_fake_phase: bool,
    phase_priority: list[str],
    build_default_tab_plan_fn,
    set_active_phase_chip_fn,
) -> None:
    if not tcp_phase_mode:
        return

    plan = build_default_tab_plan_fn(
        selected_ids=selected_ids,
        hide_fake_phase=bool(hide_fake_phase),
        phase_priority=phase_priority,
    )
    set_active_phase_chip_fn(plan.preferred_phase_key)


def sync_tree_selection_to_active_phase(
    *,
    strategies_tree,
    tcp_phase_mode: bool,
    active_phase_key: str | None,
    tcp_phase_selected_ids: dict[str, str],
    custom_strategy_id: str,
    build_phase_selection_plan_fn,
) -> None:
    if not strategies_tree:
        return

    phase = (active_phase_key or "").strip().lower()
    strategy_id = (tcp_phase_selected_ids.get(phase) or "").strip() if phase else ""
    plan = build_phase_selection_plan_fn(
        tcp_phase_mode=bool(tcp_phase_mode),
        active_phase_key=phase,
        phase_selected_strategy_id=strategy_id,
        custom_strategy_id=custom_strategy_id,
        has_strategy=bool(strategies_tree.has_strategy(strategy_id)) if strategy_id else False,
        is_visible=bool(strategies_tree.is_strategy_visible(strategy_id)) if strategy_id else False,
    )
    if plan.should_select_strategy:
        strategies_tree.set_selected_strategy(plan.selected_strategy_id)
        return
    if plan.should_clear_active:
        try:
            strategies_tree.clear_active_strategy()
        except Exception:
            pass
