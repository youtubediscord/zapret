from __future__ import annotations

from ui.accessibility import set_accessible_description, set_state_text


def _current_widget_text(widget) -> str | None:
    try:
        getter = getattr(widget, "text", None)
        if callable(getter):
            return str(getter())
        if getter is not None:
            return str(getter)
    except Exception:
        return None
    return None


def set_text_if_changed(widget, text: str) -> bool:
    next_text = str(text or "")
    current = _current_widget_text(widget)
    if current is not None and current == next_text:
        return False
    widget.setText(next_text)
    return True


def _current_widget_visible(widget) -> bool | None:
    try:
        return not bool(widget.isHidden())
    except Exception:
        pass
    try:
        return bool(widget.isVisible())
    except Exception:
        return None


def set_visible_if_changed(widget, visible: bool) -> bool:
    next_visible = bool(visible)
    current = _current_widget_visible(widget)
    if current is not None and current == next_visible:
        return False
    widget.setVisible(next_visible)
    return True


def set_enabled_if_changed(widget, enabled: bool) -> bool:
    next_enabled = bool(enabled)
    try:
        if bool(widget.isEnabled()) == next_enabled:
            return False
    except Exception:
        pass
    widget.setEnabled(next_enabled)
    return True


def set_progress_active_if_changed(progress, active: bool) -> bool:
    next_active = bool(active)
    if getattr(progress, "_last_control_progress_active", None) == next_active:
        return False
    setattr(progress, "_last_control_progress_active", next_active)
    if next_active:
        progress.start()
    else:
        progress.stop()
    return True


def set_toggle_checked(toggle, checked: bool) -> None:
    """Устанавливает состояние toggle по каноническому контракту Win11ToggleRow."""
    next_checked = bool(checked)
    try:
        if bool(toggle.isChecked()) == next_checked:
            return
    except Exception:
        pass
    toggle.setChecked(next_checked, block_signals=True)


def apply_program_settings_toggles(
    snapshot,
    *,
    auto_dpi_toggle=None,
    gui_autostart_toggle=None,
    hide_to_tray_toggle=None,
    defender_toggle=None,
    max_block_toggle=None,
) -> None:
    if auto_dpi_toggle is not None:
        set_toggle_checked(auto_dpi_toggle, getattr(snapshot, "auto_dpi_enabled", False))
    if gui_autostart_toggle is not None:
        set_toggle_checked(gui_autostart_toggle, getattr(snapshot, "gui_autostart_enabled", False))
    if hide_to_tray_toggle is not None:
        set_toggle_checked(hide_to_tray_toggle, getattr(snapshot, "hide_to_tray_on_minimize_close", False))
    if defender_toggle is not None:
        set_toggle_checked(defender_toggle, getattr(snapshot, "defender_disabled", False))
    if max_block_toggle is not None:
        set_toggle_checked(max_block_toggle, getattr(snapshot, "max_blocked", False))


def show_action_result_plan(plan, *, parent_widget, set_status, info_bar_cls, toggle=None) -> None:
    if plan.revert_checked is not None and toggle is not None:
        set_toggle_checked(toggle, plan.revert_checked)

    if plan.final_status:
        set_status(plan.final_status)

    if plan.level == "success":
        info_bar_cls.success(title=plan.title, content=plan.content, parent=parent_widget)
    elif plan.level == "warning":
        info_bar_cls.warning(title=plan.title, content=plan.content, parent=parent_widget)
    else:
        info_bar_cls.error(title=plan.title, content=plan.content, parent=parent_widget)


def apply_status_plan(
    plan,
    *,
    status_title,
    status_desc,
    status_dot,
    start_btn,
    stop_winws_btn,
    stop_and_exit_btn,
    update_stop_button_text,
) -> bool:
    plan_key = (
        str(getattr(plan, "phase", "") or ""),
        str(getattr(plan, "title", "") or ""),
        str(getattr(plan, "description", "") or ""),
        str(getattr(plan, "dot_color", "") or ""),
        bool(getattr(plan, "pulsing", False)),
        bool(getattr(plan, "show_start", False)),
        bool(getattr(plan, "show_stop_only", False)),
        bool(getattr(plan, "show_stop_and_exit", False)),
    )
    if getattr(status_dot, "_last_control_status_plan_key", None) == plan_key:
        return plan.phase == "running"
    setattr(status_dot, "_last_control_status_plan_key", plan_key)
    set_text_if_changed(status_title, plan.title)
    set_text_if_changed(status_desc, plan.description)
    set_state_text(status_title, plan.title)
    set_accessible_description(status_title, plan.description)
    set_state_text(status_dot, f"Индикатор состояния Zapret: {plan.title}")
    status_dot.set_color(plan.dot_color)
    if plan.pulsing:
        status_dot.start_pulse()
    else:
        status_dot.stop_pulse()
    set_visible_if_changed(start_btn, plan.show_start)
    update_stop_button_text()
    set_visible_if_changed(stop_winws_btn, plan.show_stop_only)
    set_visible_if_changed(stop_and_exit_btn, plan.show_stop_and_exit)
    return plan.phase == "running"


def status_message_dot_color(message: str) -> str:
    text = str(message or "").lower()
    if any(marker in text for marker in ("ошибка", "не удалось", "выключен", "останов")):
        return "#f5c04d"
    if any(marker in text for marker in ("успешно", "включена", "включен", "запущен", "готово")):
        return "#4cc38a"
    return "#8ab4f8"


def apply_last_status_message(
    message: str,
    *,
    message_label,
    message_dot,
    empty_text: str,
) -> None:
    text = str(message or "").strip() or str(empty_text or "")
    color = status_message_dot_color(text)
    message_key = (text, color)
    if getattr(message_dot, "_last_control_status_message_key", None) == message_key:
        return
    setattr(message_dot, "_last_control_status_message_key", message_key)
    message_label.setText(text)
    set_state_text(message_label, text)
    message_dot.set_color(color)
    message_dot.stop_pulse()


def run_confirmation_dialog(dialog_plan, *, message_box_cls, parent_widget, toggle=None) -> bool:
    box = message_box_cls(dialog_plan.title, dialog_plan.content, parent_widget)
    if box.exec():
        return True

    if dialog_plan.revert_checked is not None and toggle is not None:
        set_toggle_checked(toggle, dialog_plan.revert_checked)
    return False
