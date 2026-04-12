from __future__ import annotations

from filters.strategy_detail.shared_filter_mode import apply_filter_mode_selector_state as _apply_filter_mode_selector_state


def apply_strategies_summary_label(label, text: str, *, previous_text: str | None = None) -> tuple[bool, str]:
    normalized = str(text or "")
    if normalized == str(previous_text or ""):
        return False, str(previous_text or "")
    label.setText(normalized)
    return True, normalized


def apply_selected_strategy_header_state(label, state, *, set_tooltip_fn) -> None:
    try:
        if not state.visible:
            label.hide()
            return
        label.set_full_text(state.text)
        set_tooltip_fn(label, state.tooltip)
        label.show()
    except Exception:
        pass


def apply_loading_indicator_state(
    spinner,
    success_icon,
    *,
    loading: bool = False,
    success: bool = False,
    success_pixmap=None,
) -> None:
    if loading:
        try:
            success_icon.hide()
        except Exception:
            pass
        try:
            spinner.show()
        except Exception:
            pass
        try:
            spinner.start()
        except Exception:
            pass
        return

    try:
        spinner.stop()
    except Exception:
        pass
    try:
        spinner.hide()
    except Exception:
        pass

    if success:
        try:
            if success_pixmap is not None:
                success_icon.setPixmap(success_pixmap)
        except Exception:
            pass
        try:
            success_icon.show()
        except Exception:
            pass
        return

    try:
        success_icon.hide()
    except Exception:
        pass


def apply_target_payload_shell_state(
    settings_host,
    toolbar_frame,
    *,
    visible: bool = True,
) -> None:
    try:
        settings_host.setVisible(visible)
    except Exception:
        pass
    try:
        toolbar_frame.setVisible(visible)
    except Exception:
        pass


def apply_target_payload_header_state(
    title_label,
    subtitle_label,
    breadcrumb,
    *,
    title_text: str,
    subtitle_text: str,
    detail_text: str,
    control_text: str,
    strategies_text: str,
) -> None:
    title_label.setText(title_text)
    subtitle_label.setText(subtitle_text)

    if breadcrumb is None:
        return

    breadcrumb.blockSignals(True)
    try:
        breadcrumb.clear()
        breadcrumb.addItem("control", control_text)
        breadcrumb.addItem("strategies", strategies_text)
        breadcrumb.addItem("detail", detail_text)
    finally:
        breadcrumb.blockSignals(False)


def apply_target_payload_filter_reset(search_input, active_filters: set[str]) -> None:
    try:
        search_input.clear()
    except Exception:
        pass
    try:
        active_filters.clear()
    except Exception:
        pass


def apply_sort_combo_state(combo, *, target_mode: str) -> None:
    combo.blockSignals(True)
    match_index = 0
    try:
        for i in range(combo.count()):
            if str(combo.itemData(i) or "").strip().lower() == target_mode:
                match_index = i
                break
    except Exception:
        pass
    try:
        combo.setCurrentIndex(match_index)
    except Exception:
        pass
    combo.blockSignals(False)


def apply_sort_button_state(
    btn,
    *,
    is_active: bool,
    icon_color: str,
    tooltip_text: str,
    previous_icon_color,
    icon_builder,
    set_tooltip_fn,
):
    try:
        if icon_color != previous_icon_color:
            btn.setIcon(icon_builder(icon_color))
            previous_icon_color = icon_color
    except Exception:
        pass
    try:
        set_tooltip_fn(btn, tooltip_text)
    except Exception:
        pass
    return previous_icon_color


def apply_technique_filter_combo_state(combo, *, target_index: int) -> None:
    combo.blockSignals(True)
    try:
        combo.setCurrentIndex(target_index)
    except Exception:
        pass
    combo.blockSignals(False)


def apply_args_editor_state(edit_args_btn, *, enabled: bool) -> None:
    try:
        if edit_args_btn is not None:
            edit_args_btn.setEnabled(enabled)
    except Exception:
        pass


def apply_filter_mode_selector_state(selector, *, mode: str) -> None:
    _apply_filter_mode_selector_state(selector, mode=mode)


def apply_tree_selected_strategy_state(tree, *, strategy_id: str) -> None:
    if tree is None:
        return
    normalized_strategy_id = str(strategy_id or "none").strip() or "none"
    if normalized_strategy_id != "none":
        try:
            tree.set_selected_strategy(normalized_strategy_id)
            return
        except Exception:
            pass
    try:
        if tree.has_strategy("none"):
            tree.set_selected_strategy("none")
        else:
            tree.clearSelection()
    except Exception:
        pass


def apply_current_strategy_tree_state(tree, *, current_strategy_id: str) -> None:
    if tree is None:
        return
    normalized_strategy_id = str(current_strategy_id or "none").strip() or "none"
    try:
        if normalized_strategy_id != "none" and tree.has_strategy(normalized_strategy_id):
            tree.set_selected_strategy(normalized_strategy_id)
            return
        if tree.has_strategy("none"):
            tree.set_selected_strategy("none")
        else:
            tree.clearSelection()
    except Exception:
        pass


def apply_loading_plan_action(
    action: str,
    *,
    show_loading_fn,
    stop_loading_fn,
    show_success_fn,
    success_icon,
) -> None:
    normalized_action = str(action or "").strip().lower()
    if normalized_action == "show":
        show_loading_fn()
        return
    if normalized_action == "success":
        show_success_fn()
        return
    if normalized_action in {"stop", "hide"}:
        stop_loading_fn()
        try:
            success_icon.hide()
        except Exception:
            pass


def apply_tree_working_state(tree, *, strategy_id: str, state, should_update: bool = True) -> None:
    if not should_update or tree is None:
        return
    try:
        tree.set_working_state(strategy_id, state)
    except Exception:
        pass


def apply_working_mark_updates(tree, updates) -> None:
    if tree is None:
        return
    for update in list(updates or []):
        try:
            tree.set_working_state(update.strategy_id, update.state)
        except Exception:
            pass
