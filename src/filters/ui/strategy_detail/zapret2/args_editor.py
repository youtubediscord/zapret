"""Args-editor workflow helper'ы для страницы деталей стратегии Z2."""

from __future__ import annotations


def refresh_args_editor_state(
    *,
    edit_args_btn,
    target_key: str,
    selected_strategy_id: str,
    build_state_plan_fn,
    hide_editor_fn,
) -> None:
    plan = build_state_plan_fn(
        target_key=target_key,
        selected_strategy_id=selected_strategy_id,
    )
    try:
        if edit_args_btn is not None:
            edit_args_btn.setEnabled(plan.enabled)
    except Exception:
        pass

    if plan.should_hide_editor:
        hide_editor_fn(clear_text=True)


def open_args_editor_dialog(
    *,
    build_open_plan_fn,
    parent,
    language: str,
    run_args_editor_dialog_fn,
    apply_args_fn,
) -> None:
    plan = build_open_plan_fn()
    if not plan.should_open:
        return

    edited_text = run_args_editor_dialog_fn(
        initial_text=plan.initial_text,
        parent=parent,
        language=language,
    )
    if edited_text is not None:
        apply_args_fn(edited_text)


def hide_args_editor_state(*, clear_text: bool = False) -> bool:
    _ = clear_text
    return False
