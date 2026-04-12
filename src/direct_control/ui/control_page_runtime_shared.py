from __future__ import annotations


def set_toggle_checked(toggle, checked: bool) -> None:
    """Устанавливает состояние toggle без лишних сигналов."""
    try:
        toggle.setChecked(bool(checked), block_signals=True)
        return
    except TypeError:
        pass
    except Exception:
        pass

    try:
        toggle.blockSignals(True)
    except Exception:
        pass

    try:
        if hasattr(toggle, "setChecked"):
            toggle.setChecked(bool(checked))
    except Exception:
        pass

    try:
        toggle._circle_position = (toggle.width() - 18) if checked else 4.0  # type: ignore[attr-defined]
        toggle.update()
    except Exception:
        pass

    try:
        toggle.blockSignals(False)
    except Exception:
        pass


def apply_program_settings_toggles(
    snapshot,
    *,
    auto_dpi_toggle=None,
    defender_toggle=None,
    max_block_toggle=None,
) -> None:
    if auto_dpi_toggle is not None:
        set_toggle_checked(auto_dpi_toggle, getattr(snapshot, "auto_dpi_enabled", False))
    if defender_toggle is not None:
        set_toggle_checked(defender_toggle, getattr(snapshot, "defender_disabled", False))
    if max_block_toggle is not None:
        set_toggle_checked(max_block_toggle, getattr(snapshot, "max_blocked", False))


def show_action_result_plan(plan, *, window, set_status, info_bar_cls, toggle=None) -> None:
    if plan.revert_checked is not None and toggle is not None:
        set_toggle_checked(toggle, plan.revert_checked)

    if plan.final_status:
        set_status(plan.final_status)

    if info_bar_cls is None:
        return

    if plan.level == "success":
        info_bar_cls.success(title=plan.title, content=plan.content, parent=window)
    elif plan.level == "warning":
        info_bar_cls.warning(title=plan.title, content=plan.content, parent=window)
    else:
        info_bar_cls.error(title=plan.title, content=plan.content, parent=window)


def apply_status_plan(
    plan,
    *,
    status_title,
    status_desc,
    status_dot,
    start_btn,
    stop_winws_btn,
    stop_and_exit_btn,
    update_stop_button_text=None,
) -> bool:
    status_title.setText(plan.title)
    status_desc.setText(plan.description)
    status_dot.set_color(plan.dot_color)
    if plan.pulsing:
        status_dot.start_pulse()
    else:
        status_dot.stop_pulse()
    start_btn.setVisible(plan.show_start)
    if callable(update_stop_button_text):
        update_stop_button_text()
    stop_winws_btn.setVisible(plan.show_stop_only)
    stop_and_exit_btn.setVisible(plan.show_stop_and_exit)
    return plan.phase == "running"


def run_confirmation_dialog(dialog_plan, *, message_box_cls, window, toggle=None) -> bool:
    box = message_box_cls(dialog_plan.title, dialog_plan.content, window)
    if box.exec():
        return True

    if dialog_plan.revert_checked is not None and toggle is not None:
        set_toggle_checked(toggle, dialog_plan.revert_checked)
    return False
