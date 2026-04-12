"""Runtime-helper слой для Control page."""

from __future__ import annotations

from ui.compat_widgets import set_tooltip
from direct_control.control_runtime_controller import ControlPageController
from direct_control.ui.control_page_runtime_shared import (
    apply_program_settings_toggles,
    apply_status_plan as apply_status_plan_shared,
    set_toggle_checked,
    show_action_result_plan,
)


def apply_program_settings_snapshot(snapshot, *, auto_dpi_toggle, defender_toggle, max_block_toggle) -> None:
    apply_program_settings_toggles(
        snapshot,
        auto_dpi_toggle=auto_dpi_toggle,
        defender_toggle=defender_toggle,
        max_block_toggle=max_block_toggle,
    )


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
    return apply_status_plan_shared(
        plan,
        status_title=status_title,
        status_desc=status_desc,
        status_dot=status_dot,
        start_btn=start_btn,
        stop_winws_btn=stop_winws_btn,
        stop_and_exit_btn=stop_and_exit_btn,
        update_stop_button_text=update_stop_button_text,
    )


def apply_strategy_display(name: str, *, language: str, window, strategy_label, strategy_desc) -> None:
    plan = ControlPageController.build_strategy_display_plan(
        name=name,
        language=language,
        window=window,
    )
    strategy_label.setText(plan.title)
    strategy_desc.setText(plan.description)
    set_tooltip(strategy_label, plan.tooltip)


__all__ = [
    "apply_program_settings_snapshot",
    "apply_status_plan",
    "apply_strategy_display",
    "set_toggle_checked",
    "show_action_result_plan",
]
