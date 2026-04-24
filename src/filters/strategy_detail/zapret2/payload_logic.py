from __future__ import annotations

from dataclasses import dataclass

from filters.ui.strategy_detail.shared_detail_header import build_detail_header_text_state


@dataclass(slots=True)
class StrategyDetailRowClickPlan:
    selected_strategy_id: str
    remembered_last_enabled_strategy_id: str | None
    should_hide_args_editor: bool
    loading_state: str
    target_enabled: bool
    should_emit_strategy_selected: bool
    suppress_next_preset_refresh: bool


@dataclass(slots=True)
class StrategyDetailLoadingStatePlan:
    action: str


@dataclass(slots=True)
class StrategyDetailTargetRequestPlan:
    should_request: bool
    normalized_target_key: str
    token_reason: str


@dataclass(slots=True)
class StrategyDetailPayloadLoadedPlan:
    action: str
    normalized_target_key: str
    log_level: str | None = None
    log_message: str = ""


@dataclass(slots=True)
class StrategyDetailPayloadApplyPlan:
    policy: object
    current_strategy_id: str
    selected_strategy_id: str
    target_enabled: bool
    should_reuse_list: bool
    title_text: str
    subtitle_text: str


@dataclass(slots=True)
class StrategyDetailPresetRefreshPlan:
    should_mark_pending: bool
    should_request_refresh: bool


def build_row_click_plan(
    *,
    strategy_id: str,
    prev_strategy_id: str,
    has_target_key: bool,
) -> StrategyDetailRowClickPlan:
    normalized_id = str(strategy_id or "none").strip() or "none"
    normalized_prev = str(prev_strategy_id or "").strip()
    remembered_last_enabled = None
    if normalized_id == "none" and normalized_prev and normalized_prev != "none":
        remembered_last_enabled = normalized_prev

    return StrategyDetailRowClickPlan(
        selected_strategy_id=normalized_id,
        remembered_last_enabled_strategy_id=remembered_last_enabled,
        should_hide_args_editor=normalized_prev != normalized_id,
        loading_state="show" if normalized_id != "none" else "stop",
        target_enabled=normalized_id != "none",
        should_emit_strategy_selected=bool(has_target_key),
        suppress_next_preset_refresh=bool(has_target_key),
    )


def build_status_icon_plan(*, active: bool) -> StrategyDetailLoadingStatePlan:
    return StrategyDetailLoadingStatePlan(action="success" if active else "hide")


def build_apply_feedback_timeout_plan(
    *,
    waiting_for_process_start: bool,
    selected_strategy_id: str,
) -> StrategyDetailLoadingStatePlan:
    if not waiting_for_process_start:
        return StrategyDetailLoadingStatePlan(action="noop")
    if (selected_strategy_id or "none") != "none":
        return StrategyDetailLoadingStatePlan(action="success")
    return StrategyDetailLoadingStatePlan(action="hide")


def build_target_payload_request_plan(
    *,
    target_key: str,
    reason: str,
) -> StrategyDetailTargetRequestPlan:
    normalized_key = str(target_key or "").strip().lower()
    should_request = bool(normalized_key)
    token_reason = f"{reason}:{normalized_key}" if should_request else str(reason or "").strip()
    return StrategyDetailTargetRequestPlan(
        should_request=should_request,
        normalized_target_key=normalized_key,
        token_reason=token_reason,
    )


def build_payload_loaded_plan(
    *,
    request_id: int,
    current_request_id: int,
    token_is_current: bool,
    snapshot,
    fallback_target_key: str,
) -> StrategyDetailPayloadLoadedPlan:
    if request_id != current_request_id:
        return StrategyDetailPayloadLoadedPlan(action="ignore", normalized_target_key="")
    if not token_is_current:
        return StrategyDetailPayloadLoadedPlan(action="ignore", normalized_target_key="")

    normalized_key = str(
        getattr(snapshot, "target_key", "") or fallback_target_key or ""
    ).strip().lower()
    payload = getattr(snapshot, "payload", None)
    if payload is None or getattr(payload, "target_item", None) is None:
        return StrategyDetailPayloadLoadedPlan(
            action="missing",
            normalized_target_key=normalized_key,
            log_level="WARNING",
            log_message=f"StrategyDetailPage.show_target: target '{normalized_key}' не найден",
        )

    return StrategyDetailPayloadLoadedPlan(
        action="apply",
        normalized_target_key=normalized_key,
    )


def build_target_payload_apply_plan(
    *,
    payload,
    has_strategy_rows: bool,
    loaded_strategy_type: str | None,
    loaded_direct_mode: str | None,
    loaded_tcp_phase_mode: bool,
    direct_mode_override: str | None,
    tr,
) -> StrategyDetailPayloadApplyPlan:
    from filters.strategy_detail.zapret2.mode_policy import build_strategy_detail_mode_policy

    target_info = getattr(payload, "target_item", None)
    policy = build_strategy_detail_mode_policy(
        target_info,
        direct_mode=direct_mode_override,
        is_circular_preset=bool(getattr(payload, "is_circular_preset", False)),
    )
    details = getattr(payload, "details", None)
    current_strategy_id = str(getattr(details, "current_strategy", "none") or "none").strip() or "none"
    header_state = build_detail_header_text_state(
        target_info=target_info,
        target_key="",
        tr=tr,
        ports_text_key="page.z2_strategy_detail.subtitle.ports",
        ports_text_default="порты: {ports}",
        empty_title="",
        empty_detail=tr("page.z2_strategy_detail.header.category_fallback", "Target"),
    )

    return StrategyDetailPayloadApplyPlan(
        policy=policy,
        current_strategy_id=current_strategy_id,
        selected_strategy_id=current_strategy_id,
        target_enabled=current_strategy_id != "none",
        should_reuse_list=(
            bool(has_strategy_rows)
            and loaded_strategy_type == policy.strategy_type
            and loaded_direct_mode == policy.direct_mode
            and bool(loaded_tcp_phase_mode) == bool(policy.tcp_phase_mode)
        ),
        title_text=header_state.title_text,
        subtitle_text=header_state.subtitle_text,
    )


def build_preset_refresh_plan(
    *,
    is_visible: bool,
    target_key: str,
) -> StrategyDetailPresetRefreshPlan:
    if not is_visible:
        return StrategyDetailPresetRefreshPlan(
            should_mark_pending=True,
            should_request_refresh=False,
        )
    if not str(target_key or "").strip():
        return StrategyDetailPresetRefreshPlan(
            should_mark_pending=False,
            should_request_refresh=False,
        )
    return StrategyDetailPresetRefreshPlan(
        should_mark_pending=False,
        should_request_refresh=True,
    )
