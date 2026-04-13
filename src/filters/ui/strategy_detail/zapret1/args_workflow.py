"""UI-driven args workflow для страницы деталей стратегии Zapret 1."""

from __future__ import annotations


def open_args_editor_dialog_v1(
    *,
    has_fluent: bool,
    current_strategy_id: str,
    get_current_args_fn,
    parent,
    language: str,
    run_args_editor_dialog_fn,
    apply_args_fn,
    log_fn,
) -> None:
    if not has_fluent or (current_strategy_id or "none") == "none":
        return
    try:
        edited_text = run_args_editor_dialog_fn(
            initial_text=get_current_args_fn(),
            parent=parent,
            language=language,
        )
        if edited_text is not None:
            apply_args_fn(edited_text.strip())
    except Exception as exc:
        log_fn(f"Zapret1StrategyDetailPage: args editor error: {exc}", "ERROR")
