"""Payload workflow helper'ы для страницы деталей стратегии Zapret 1."""

from __future__ import annotations


def start_target_payload_request_v1(
    *,
    cleanup_in_progress: bool,
    target_key: str,
    reason: str,
    refresh: bool,
    current_request_id: int,
    issue_page_load_token_fn,
    require_app_context_fn,
    worker_cls,
    parent,
    on_loaded_callback,
    show_loading_fn,
):
    if cleanup_in_progress:
        return None

    normalized_key = str(target_key or "").strip().lower()
    if not normalized_key:
        return None

    token = issue_page_load_token_fn(reason=f"{reason}:{normalized_key}")
    request_id = int(current_request_id) + 1
    show_loading_fn()

    worker = worker_cls(
        request_id,
        snapshot_service=require_app_context_fn().direct_ui_snapshot_service,
        launch_method="direct_zapret1",
        target_key=normalized_key,
        refresh=refresh,
        parent=parent,
    )
    worker.loaded.connect(
        lambda loaded_request_id, snapshot, load_token=token: on_loaded_callback(
            loaded_request_id,
            snapshot,
            load_token,
        )
    )
    return normalized_key, request_id, worker


def apply_missing_payload_v1(
    *,
    refresh_btn,
    stop_spinner_fn,
    clear_strategies_and_rebuild_fn,
    refresh_args_preview_fn,
    update_selected_label_fn,
    sync_target_controls_fn,
    hide_success_fn,
) -> None:
    if refresh_btn:
        refresh_btn.set_loading(False)
    clear_strategies_and_rebuild_fn()
    refresh_args_preview_fn()
    update_selected_label_fn()
    sync_target_controls_fn()
    stop_spinner_fn()
    hide_success_fn()


def handle_loaded_payload_v1(
    *,
    cleanup_in_progress: bool,
    request_id: int,
    snapshot,
    token: int,
    current_request_id: int,
    is_page_load_token_current_fn,
    refresh_btn,
    on_missing_payload_fn,
    set_payload_fn,
    normalize_target_info_fn,
    target_key: str,
    load_current_strategy_id_fn,
    set_current_strategy_id_fn,
    set_last_enabled_strategy_id_fn,
    update_header_labels_fn,
    rebuild_breadcrumb_fn,
    apply_loaded_target_payload_fn,
) -> bool:
    if cleanup_in_progress:
        return False
    if request_id != current_request_id:
        return False
    if not is_page_load_token_current_fn(token):
        return False

    if refresh_btn:
        refresh_btn.set_loading(False)

    payload = getattr(snapshot, "payload", None)
    if payload is None:
        on_missing_payload_fn()
        return False

    set_payload_fn(payload)
    target_info = getattr(payload, "target_item", None)
    normalized_info = normalize_target_info_fn(target_key, target_info)

    current_strategy_id = load_current_strategy_id_fn()
    set_current_strategy_id_fn(current_strategy_id)
    if current_strategy_id and current_strategy_id != "none":
        set_last_enabled_strategy_id_fn(current_strategy_id)

    update_header_labels_fn(normalized_info)
    rebuild_breadcrumb_fn()
    apply_loaded_target_payload_fn()
    return True


def apply_loaded_target_payload_v1(
    *,
    payload,
    set_strategies_fn,
    rebuild_tree_rows_fn,
    refresh_args_preview_fn,
    update_selected_label_fn,
    sync_target_controls_fn,
    show_success_fn,
) -> None:
    if payload is not None:
        set_strategies_fn(dict(getattr(payload, "strategy_entries", {}) or {}))
    else:
        set_strategies_fn({})

    rebuild_tree_rows_fn()
    refresh_args_preview_fn()
    update_selected_label_fn()
    sync_target_controls_fn()
    show_success_fn()


def apply_preset_refresh_v1(
    *,
    cleanup_in_progress: bool,
    is_visible: bool,
    target_key: str,
    mark_pending_fn,
    request_payload_fn,
) -> None:
    if cleanup_in_progress:
        return
    if not is_visible:
        mark_pending_fn()
        return
    if not target_key:
        return
    request_payload_fn(target_key, refresh=True, reason="preset_switch")
