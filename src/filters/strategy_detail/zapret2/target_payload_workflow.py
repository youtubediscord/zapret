"""Target payload workflow helper'ы для страницы деталей стратегии Z2."""

from __future__ import annotations


def start_target_payload_request(
    *,
    target_key: str,
    reason: str,
    refresh: bool,
    current_request_id: int,
    build_request_plan_fn,
    issue_page_load_token_fn,
    snapshot_service,
    prepare_request_fn,
    now_fn,
    worker_cls,
    worker_kwargs=None,
    parent,
    on_loaded_callback,
):
    plan = build_request_plan_fn(target_key=target_key, reason=reason)
    if not plan.should_request:
        return None

    token = issue_page_load_token_fn(reason=plan.token_reason)
    request_id = int(current_request_id) + 1
    started_at = now_fn()
    prepare_request_fn(plan.normalized_target_key)

    worker = worker_cls(
        request_id,
        snapshot_service=snapshot_service,
        launch_method="direct_zapret2",
        target_key=plan.normalized_target_key,
        refresh=refresh,
        **dict(worker_kwargs or {}),
        parent=parent,
    )
    worker.loaded.connect(
        lambda loaded_request_id, snapshot, load_token=token, request_reason=reason: on_loaded_callback(
            loaded_request_id,
            snapshot,
            load_token,
            reason=request_reason,
        )
    )
    return request_id, started_at, worker


def handle_loaded_payload(
    *,
    request_id: int,
    snapshot,
    token: int,
    reason: str,
    current_request_id: int,
    fallback_target_key: str,
    token_is_current_fn,
    build_loaded_plan_fn,
    stop_loading_fn,
    hide_success_icon_fn,
    log_fn,
    apply_payload_fn,
    started_at,
) -> None:
    plan = build_loaded_plan_fn(
        request_id=request_id,
        current_request_id=current_request_id,
        token_is_current=token_is_current_fn(token),
        snapshot=snapshot,
        fallback_target_key=fallback_target_key,
    )
    if plan.action == "ignore":
        return

    payload = getattr(snapshot, "payload", None)
    if plan.action == "missing":
        stop_loading_fn()
        hide_success_icon_fn()
        if plan.log_message:
            log_fn(plan.log_message, plan.log_level or "WARNING")
        return

    apply_payload_fn(
        plan.normalized_target_key,
        payload,
        reason=reason,
        started_at=started_at,
    )


def apply_preset_refresh(
    *,
    is_visible: bool,
    target_key: str,
    build_preset_refresh_plan_fn,
    mark_pending_fn,
    request_payload_fn,
) -> None:
    plan = build_preset_refresh_plan_fn(
        is_visible=is_visible,
        target_key=target_key,
    )
    if plan.should_mark_pending:
        mark_pending_fn()
        return
    if not plan.should_request_refresh:
        return

    try:
        request_payload_fn(target_key, refresh=True, reason="preset_switch")
    except Exception:
        return
