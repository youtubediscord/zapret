from __future__ import annotations

from filters.strategy_detail.zapret1.data_helpers import (
    get_target_details_v1,
    load_current_strategy_id_v1,
    load_target_payload_sync_v1,
)
from filters.strategy_detail.zapret1.payload_workflow import (
    apply_loaded_target_payload_v1,
    apply_missing_payload_v1,
    apply_preset_refresh_v1,
    handle_loaded_payload_v1,
    start_target_payload_request_v1,
)
from filters.ui.strategy_detail.shared_detail_header import (
    apply_detail_breadcrumb,
    build_detail_header_text_state,
)


def rebuild_breadcrumb_v1(
    *,
    breadcrumb,
    tr_fn,
    target_info: dict,
    target_key: str,
) -> None:
    header_state = build_detail_header_text_state(
        target_info=target_info,
        target_key=target_key,
        tr=tr_fn,
        ports_text_key="page.z1_strategy_detail.subtitle.ports",
        ports_text_default="порты: {ports}",
        empty_title=target_key,
        empty_detail="Target",
    )
    apply_detail_breadcrumb(
        breadcrumb,
        control_text=tr_fn("page.z1_strategy_detail.breadcrumb.control", "Управление"),
        strategies_text=tr_fn("page.z1_strategy_detail.breadcrumb.strategies", "Прямой запуск Zapret 1"),
        detail_text=header_state.detail_text,
    )


def handle_breadcrumb_changed_v1(
    *,
    key: str,
    rebuild_breadcrumb_fn,
    emit_back_fn,
    emit_navigate_to_control_fn,
) -> None:
    rebuild_breadcrumb_fn()
    if key == "strategies":
        emit_back_fn()
    elif key == "control":
        emit_navigate_to_control_fn()


def load_target_payload_sync_runtime_v1(page, target_key: str | None = None, *, refresh: bool = False):
    return load_target_payload_sync_v1(
        target_key=target_key,
        current_target_key=page._target_key,
        require_app_context_fn=page._require_app_context,
        set_payload_fn=lambda payload: setattr(page, "_target_payload", payload),
        refresh=refresh,
    )


def request_target_payload_runtime_v1(page, target_key: str, *, refresh: bool, reason: str) -> None:
    request_state = start_target_payload_request_v1(
        cleanup_in_progress=page._cleanup_in_progress,
        target_key=target_key,
        reason=reason,
        refresh=refresh,
        current_request_id=page._target_payload_request_id,
        issue_page_load_token_fn=page.issue_page_load_token,
        require_app_context_fn=page._require_app_context,
        worker_cls=page._target_payload_worker_cls,
        parent=page,
        on_loaded_callback=page._on_target_payload_loaded,
        show_loading_fn=page.show_loading,
    )
    if request_state is None:
        return

    normalized_key, request_id, worker = request_state
    page._target_key = normalized_key
    page._target_payload_request_id = request_id
    page._target_payload_worker = worker
    worker.start()


def on_target_payload_loaded_runtime_v1(page, request_id: int, snapshot, token: int) -> None:
    handle_loaded_payload_v1(
        cleanup_in_progress=page._cleanup_in_progress,
        request_id=request_id,
        snapshot=snapshot,
        token=token,
        current_request_id=page._target_payload_request_id,
        is_page_load_token_current_fn=page.is_page_load_token_current,
        refresh_btn=page._refresh_btn,
        on_missing_payload_fn=page._handle_missing_target_payload,
        set_payload_fn=lambda payload: setattr(page, "_target_payload", payload),
        normalize_target_info_fn=page._normalize_target_info,
        target_key=page._target_key,
        load_current_strategy_id_fn=page._load_current_strategy_id,
        set_current_strategy_id_fn=lambda value: setattr(page, "_current_strategy_id", value),
        set_last_enabled_strategy_id_fn=lambda value: setattr(page, "_last_enabled_strategy_id", value),
        update_header_labels_fn=page._apply_loaded_header_state,
        rebuild_breadcrumb_fn=page._rebuild_breadcrumb,
        apply_loaded_target_payload_fn=page._apply_loaded_target_payload,
    )


def handle_missing_target_payload_runtime_v1(page) -> None:
    apply_missing_payload_v1(
        refresh_btn=page._refresh_btn,
        stop_spinner_fn=page._stop_spinner,
        clear_strategies_and_rebuild_fn=page._clear_strategies_and_rebuild,
        refresh_args_preview_fn=page._refresh_args_preview,
        update_selected_label_fn=page._update_selected_label,
        sync_target_controls_fn=page._sync_target_controls,
        hide_success_fn=page._hide_success,
    )


def apply_loaded_header_state_runtime_v1(page, normalized_info: dict) -> None:
    page._target_info = normalized_info
    page._update_header_labels()


def clear_strategies_and_rebuild_runtime_v1(page) -> None:
    page._strategies = {}
    page._rebuild_tree_rows()


def stop_spinner_runtime_v1(page) -> None:
    if page._spinner is not None:
        try:
            if hasattr(page._spinner, "stop"):
                page._spinner.stop()
        except Exception:
            pass
        page._spinner.hide()


def apply_loaded_target_payload_runtime_v1(page) -> None:
    page._ensure_interaction_stores()
    apply_loaded_target_payload_v1(
        payload=getattr(page, "_target_payload", None),
        set_strategies_fn=lambda value: setattr(page, "_strategies", value),
        rebuild_tree_rows_fn=page._rebuild_tree_rows,
        refresh_args_preview_fn=page._refresh_args_preview,
        update_selected_label_fn=page._update_selected_label,
        sync_target_controls_fn=page._sync_target_controls,
        show_success_fn=page.show_success,
    )
    page._refresh_marks_and_favorites_for_target()


def show_target_runtime_v1(page, target_key: str, direct_facade=None) -> None:
    if page._cleanup_in_progress:
        return

    normalized_target_key = str(target_key or "").strip().lower()
    if not normalized_target_key:
        return

    if direct_facade is not None:
        page._direct_facade = direct_facade
    elif page._direct_facade is None:
        try:
            from direct_preset.facade import DirectPresetFacade

            page._direct_facade = DirectPresetFacade.from_launch_method(
                "direct_zapret1",
                app_context=page._require_app_context(),
            )
        except Exception:
            page._direct_facade = None

    page._request_target_payload(normalized_target_key, refresh=False, reason="show_target")


def activate_page_runtime_v1(page) -> None:
    if page._cleanup_in_progress:
        return

    page._rebuild_breadcrumb()
    if page._target_key and page._preset_refresh_pending:
        page._preset_refresh_pending = False
        page._single_shot_fn(0, lambda: (not page._cleanup_in_progress) and page.refresh_from_preset_switch())


def bind_ui_state_store_v1(
    *,
    current_store,
    store,
    current_unsubscribe,
    set_store_fn,
    set_unsubscribe_fn,
    on_ui_state_changed,
) -> None:
    if current_store is store:
        return

    if callable(current_unsubscribe):
        try:
            current_unsubscribe()
        except Exception:
            pass

    set_store_fn(store)
    unsubscribe = store.subscribe(
        on_ui_state_changed,
        fields={"active_preset_revision", "preset_content_revision"},
        emit_initial=False,
    )
    set_unsubscribe_fn(unsubscribe)


def handle_ui_state_changed_v1(
    *,
    cleanup_in_progress: bool,
    changed_fields: frozenset[str],
    refresh_from_preset_switch_fn,
) -> None:
    if cleanup_in_progress:
        return
    if "active_preset_revision" in changed_fields or "preset_content_revision" in changed_fields:
        refresh_from_preset_switch_fn()


def cleanup_page_v1(
    *,
    set_cleanup_in_progress_fn,
    clear_preset_refresh_pending_fn,
    increment_request_id_fn,
    success_timer,
    current_unsubscribe,
    set_unsubscribe_fn,
    set_store_fn,
) -> None:
    set_cleanup_in_progress_fn(True)
    clear_preset_refresh_pending_fn()
    increment_request_id_fn()
    success_timer.stop()

    if callable(current_unsubscribe):
        try:
            current_unsubscribe()
        except Exception:
            pass
    set_unsubscribe_fn(None)
    set_store_fn(None)


def load_current_strategy_id_runtime_v1(page) -> str:
    return load_current_strategy_id_v1(
        direct_facade=page._direct_facade,
        target_key=page._target_key,
        get_target_details_fn=page._get_target_details,
    )


def get_target_details_runtime_v1(page, target_key: str | None = None):
    return get_target_details_v1(
        target_key=target_key,
        current_target_key=page._target_key,
        direct_facade=page._direct_facade,
        current_payload=getattr(page, "_target_payload", None),
        load_target_payload_sync_fn=page._load_target_payload_sync,
    )


def reload_target_runtime_v1(page, *_args) -> None:
    if not page._target_key:
        return

    if page._refresh_btn:
        page._refresh_btn.set_loading(True)

    try:
        page._request_target_payload(page._target_key, refresh=True, reason="reload")
    except Exception as exc:
        page._log_fn(f"Zapret1StrategyDetailPage: cannot load strategies: {exc}", "ERROR")
        page._reload_target_error_fallback()


def reload_target_error_fallback_runtime_v1(page) -> None:
    page._strategies = {}
    page._rebuild_tree_rows()
    page._favorite_strategy_ids = set()
    page._refresh_args_preview()
    page._update_selected_label()
    page._sync_target_controls()
    page._hide_success()


def refresh_from_preset_switch_runtime_v1(page) -> None:
    page._preset_refresh_pending = False
    apply_preset_refresh_v1(
        cleanup_in_progress=page._cleanup_in_progress,
        is_visible=page.isVisible(),
        target_key=page._target_key,
        mark_pending_fn=lambda: setattr(page, "_preset_refresh_pending", True),
        request_payload_fn=page._request_target_payload,
    )
