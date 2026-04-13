from __future__ import annotations

from log.log import log

from filters.strategy_detail.zapret2.controller import StrategyDetailPageController
from filters.ui.strategy_detail.zapret2.apply import apply_tree_working_state, apply_working_mark_updates
from filters.ui.strategy_detail.zapret2.preview import (
    close_preview_dialog,
    ensure_preview_dialog_instance,
    show_preview_dialog_for_strategy,
)


def refresh_working_marks_for_target(page) -> None:
    if not (page._target_key and page._strategies_tree):
        return
    plan = StrategyDetailPageController.build_working_marks_plan(
        target_key=page._target_key,
        strategy_ids=list(page._strategies_tree.get_strategy_ids() or []),
        custom_strategy_id=page.CUSTOM_STRATEGY_ID,
        mark_getter=lambda strategy_id: page._feedback_store.get_mark(page._target_key, strategy_id),
    )
    apply_working_mark_updates(
        page._strategies_tree,
        plan.updates,
    )


def get_preview_strategy_data(page, strategy_id: str) -> dict:
    plan = StrategyDetailPageController.build_preview_strategy_data(
        strategy_id=strategy_id,
        strategy_data=page._strategies_data_by_id.get(strategy_id, {}),
    )
    return dict(plan.data or {})


def get_preview_rating(page, strategy_id: str, target_key: str):
    return StrategyDetailPageController.get_preview_rating(
        page._feedback_store,
        strategy_id=strategy_id,
        target_key=target_key,
    )


def toggle_preview_rating(page, strategy_id: str, rating: str, target_key: str):
    result = StrategyDetailPageController.toggle_preview_rating(
        page._feedback_store,
        strategy_id=strategy_id,
        rating=rating,
        target_key=target_key,
    )
    apply_tree_working_state(
        page._strategies_tree,
        strategy_id=strategy_id,
        state=result.resulting_mark_state,
        should_update=result.should_update_tree_state,
    )
    return result.resulting_rating


def close_preview_dialog_runtime(page, force: bool = False):
    page._preview_dialog, page._preview_pinned = close_preview_dialog(
        page._preview_dialog,
        preview_pinned=page._preview_pinned,
        force=force,
    )


def close_transient_overlays(page) -> None:
    try:
        close_preview_dialog_runtime(page, force=True)
    except Exception:
        pass
    try:
        page._close_filter_combo_popup()
    except Exception:
        pass


def on_preview_closed(page) -> None:
    page._preview_dialog = None
    page._preview_pinned = False


def ensure_preview_dialog_runtime(page):
    parent_win = page._host_window or page.window() or page
    page._preview_dialog = ensure_preview_dialog_instance(
        page._preview_dialog,
        parent_win=parent_win,
        on_closed=page._on_preview_closed,
        dialog_cls=page._args_preview_dialog_cls,
    )
    return page._preview_dialog


def show_preview_dialog_runtime(page, strategy_id: str, global_pos) -> None:
    if not (page._target_key and strategy_id and strategy_id != "none"):
        return

    data = get_preview_strategy_data(page, strategy_id)

    try:
        dialog = ensure_preview_dialog_runtime(page)
        if dialog is None:
            return

        show_preview_dialog_for_strategy(
            dialog,
            target_key=page._target_key,
            strategy_id=strategy_id,
            global_pos=global_pos,
            strategy_data=data,
            rating_getter=page._get_preview_rating,
            rating_toggler=page._toggle_preview_rating,
        )
    except Exception as e:
        log(f"Preview dialog failed: {e}", "DEBUG")


def on_tree_preview_requested(page, strategy_id: str, global_pos):
    _ = (page, strategy_id, global_pos)
    # Hover preview is intentionally disabled.


def on_tree_preview_pinned_requested(page, strategy_id: str, global_pos):
    show_preview_dialog_runtime(page, strategy_id, global_pos)


def on_tree_preview_hide_requested(page) -> None:
    _ = page
    # No hover preview instance to hide.


def on_tree_working_mark_requested(page, strategy_id: str, is_working):
    result = StrategyDetailPageController.save_strategy_mark(
        page._feedback_store,
        strategy_id=strategy_id,
        is_working=is_working,
        target_key=page._target_key,
    )
    apply_tree_working_state(
        page._strategies_tree,
        strategy_id=strategy_id,
        state=result.resulting_mark_state,
        should_update=result.should_update_tree_state,
    )
    if result.should_emit_signal and page._target_key:
        page.strategy_marked.emit(page._target_key, strategy_id, is_working)


def on_favorite_toggled(page, strategy_id: str, is_favorite: bool) -> None:
    result = StrategyDetailPageController.toggle_favorite(
        page._feedback_store,
        strategy_id=strategy_id,
        is_favorite=is_favorite,
        target_key=page._target_key,
        favorite_ids=page._favorite_strategy_ids,
    )
    if not result.ok:
        return

    page._favorite_strategy_ids = set(result.updated_favorite_ids)


def get_default_strategy(page) -> str:
    for sid in (page._default_strategy_order or []):
        if sid and sid != "none":
            return sid
    return "none"
