from __future__ import annotations

from log.log import log

from filters.ui.strategy_detail.shared_interactions import (
    build_preview_strategy_data,
    close_preview_dialog,
    ensure_preview_dialog_instance,
    get_preview_rating,
    save_strategy_mark,
    show_preview_dialog_for_strategy,
    toggle_favorite,
    toggle_preview_rating,
)
from filters.ui.strategy_detail.zapret1.args_workflow import open_args_editor_dialog_v1
from filters.strategy_detail.zapret1.args_workflow import save_custom_args_v1


def open_args_editor_runtime_v1(page) -> None:
    open_args_editor_dialog_v1(
        has_fluent=page._HAS_FLUENT,
        current_strategy_id=page._current_strategy_id,
        get_current_args_fn=page._get_current_args,
        parent=page.window(),
        language=page._ui_language,
        run_args_editor_dialog_fn=page._run_args_editor_dialog_fn,
        apply_args_fn=page._save_custom_args,
        log_fn=log,
    )


def save_custom_args_runtime_v1(page, args_text: str) -> None:
    save_custom_args_v1(
        direct_facade=page._direct_facade,
        target_key=page._target_key,
        args_text=args_text,
        load_target_payload_sync_fn=page._load_target_payload_sync,
        set_current_strategy_id_fn=lambda value: setattr(page, "_current_strategy_id", value),
        set_last_enabled_strategy_id_fn=lambda value: setattr(page, "_last_enabled_strategy_id", value),
        emit_strategy_selected_fn=page.strategy_selected.emit,
        sync_target_controls_fn=page._sync_target_controls,
        has_fluent=page._HAS_FLUENT,
        info_bar_cls=page._info_bar_cls,
        tr_fn=page._tr,
        parent_window=page.window(),
        request_target_payload_fn=page._request_target_payload,
        log_fn=log,
    )


def get_preview_strategy_data_runtime_v1(page, strategy_id: str) -> dict:
    strategy = dict(page._strategies.get(str(strategy_id or "").strip(), {}) or {})
    return build_preview_strategy_data(
        strategy_id=strategy_id,
        strategy_data={
            "name": strategy.get("name", strategy_id),
            "args": strategy.get("args", ""),
        },
    )


def get_preview_rating_runtime_v1(page, strategy_id: str, target_key: str):
    if page._feedback_store is None:
        return None
    return get_preview_rating(
        page._feedback_store,
        strategy_id=strategy_id,
        target_key=target_key,
    )


def toggle_preview_rating_runtime_v1(page, strategy_id: str, rating: str, target_key: str):
    if page._feedback_store is None:
        return None
    ok, resulting_state, resulting_rating = toggle_preview_rating(
        page._feedback_store,
        strategy_id=strategy_id,
        rating=rating,
        target_key=target_key,
    )
    if ok and page._tree is not None:
        page._tree.set_working_state(strategy_id, resulting_state)
    return resulting_rating


def close_preview_dialog_runtime_v1(page, force: bool = False):
    page._preview_dialog, page._preview_pinned = close_preview_dialog(
        page._preview_dialog,
        preview_pinned=page._preview_pinned,
        force=force,
    )


def close_transient_overlays_runtime_v1(page) -> None:
    try:
        close_preview_dialog_runtime_v1(page, force=True)
    except Exception:
        pass


def on_preview_closed_runtime_v1(page) -> None:
    page._preview_dialog = None
    page._preview_pinned = False


def ensure_preview_dialog_runtime_v1(page):
    parent_win = page.window() or page
    page._preview_dialog = ensure_preview_dialog_instance(
        page._preview_dialog,
        parent_win=parent_win,
        on_closed=page._on_preview_closed,
        dialog_cls=page._args_preview_dialog_cls,
    )
    return page._preview_dialog


def show_preview_dialog_runtime_v1(page, strategy_id: str, global_pos) -> None:
    if not (page._target_key and strategy_id and strategy_id != "none"):
        return
    dialog = ensure_preview_dialog_runtime_v1(page)
    if dialog is None:
        return
    show_preview_dialog_for_strategy(
        dialog,
        target_key=page._target_key,
        strategy_id=strategy_id,
        global_pos=global_pos,
        strategy_data=page._get_preview_strategy_data(strategy_id),
        rating_getter=page._get_preview_rating,
        rating_toggler=page._toggle_preview_rating,
    )


def on_tree_preview_requested_runtime_v1(page, strategy_id: str, global_pos):
    _ = (page, strategy_id, global_pos)


def on_tree_preview_pinned_requested_runtime_v1(page, strategy_id: str, global_pos):
    show_preview_dialog_runtime_v1(page, strategy_id, global_pos)


def on_tree_preview_hide_requested_runtime_v1(page) -> None:
    _ = page


def on_tree_working_mark_requested_runtime_v1(page, strategy_id: str, is_working):
    if page._feedback_store is None or page._tree is None:
        return
    ok, resulting_state, _ = save_strategy_mark(
        page._feedback_store,
        strategy_id=strategy_id,
        is_working=is_working,
        target_key=page._target_key,
    )
    if ok:
        page._tree.set_working_state(strategy_id, resulting_state)


def on_favorite_toggled_runtime_v1(page, strategy_id: str, is_favorite: bool) -> None:
    if page._feedback_store is None:
        return
    ok, updated_ids = toggle_favorite(
        page._feedback_store,
        strategy_id=strategy_id,
        is_favorite=is_favorite,
        target_key=page._target_key,
        favorite_ids=page._favorite_strategy_ids,
    )
    if ok:
        page._favorite_strategy_ids = set(updated_ids)
