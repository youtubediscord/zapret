from __future__ import annotations

from direct_preset.common.out_range import (
    is_simple_out_range,
    is_valuefree_out_range_mode,
    normalize_simple_out_range_mode,
)

from dataclasses import dataclass


@dataclass(slots=True)
class StrategyDetailSyndataTimerPlan:
    should_schedule: bool
    pending_target_key: str | None
    delay_ms: int


@dataclass(slots=True)
class StrategyDetailSyndataPersistPlan:
    should_save: bool
    normalized_target_key: str
    payload: dict[str, object]


@dataclass(slots=True)
class StrategyDetailArgsEditorStatePlan:
    enabled: bool
    should_hide_editor: bool


@dataclass(slots=True)
class StrategyDetailArgsEditorOpenPlan:
    should_open: bool
    initial_text: str


@dataclass(slots=True)
class StrategyDetailArgsApplyPlan:
    should_apply: bool
    normalized_text: str
    args_lines: list[str]


@dataclass(slots=True)
class StrategyDetailArgsApplyResultPlan:
    selected_strategy_id: str
    current_strategy_id: str
    should_show_loading: bool
    should_emit_args_changed: bool


def build_syndata_timer_plan(
    *,
    target_key: str,
    delay_ms: int,
) -> StrategyDetailSyndataTimerPlan:
    normalized_target = str(target_key or "").strip().lower()
    return StrategyDetailSyndataTimerPlan(
        should_schedule=bool(normalized_target),
        pending_target_key=normalized_target or None,
        delay_ms=max(0, int(delay_ms)),
    )


def build_syndata_persist_plan(
    *,
    target_key: str,
    pending_target_key: str | None,
    payload: dict[str, object],
) -> StrategyDetailSyndataPersistPlan:
    normalized_target = str(target_key or "").strip().lower()
    normalized_pending = str(pending_target_key or "").strip().lower()
    should_save = bool(normalized_target) and (not normalized_pending or normalized_pending == normalized_target)
    return StrategyDetailSyndataPersistPlan(
        should_save=should_save,
        normalized_target_key=normalized_target,
        payload=dict(payload or {}),
    )


def build_target_settings_payload(*, details, protocol: str | None) -> dict[str, object]:
    if details is None:
        fallback = {
            "enabled": False,
            "blob": "tls_google",
            "tls_mod": "none",
            "autottl_delta": 0,
            "autottl_min": 3,
            "autottl_max": 20,
            "out_range": 8,
            "out_range_mode": "d",
            "out_range_expression": "-d8",
            "out_range_is_simple": True,
            "tcp_flags_unset": "none",
            "send_enabled": False,
            "send_repeats": 2,
            "send_ip_ttl": 0,
            "send_ip6_ttl": 0,
            "send_ip_id": "none",
            "send_badsum": False,
        }
        from filters.strategy_detail.zapret2.mode_policy import is_udp_like_protocol

        if is_udp_like_protocol(protocol):
            fallback["enabled"] = False
            fallback["send_enabled"] = False
        return fallback

    out_range = details.out_range_settings
    send = details.send_settings
    syndata = details.syndata_settings
    out_range_expression = str(out_range.expression or "").strip()
    out_range_mode = normalize_simple_out_range_mode(out_range.mode or "d")
    out_range_enabled = bool(
        out_range.enabled and (is_valuefree_out_range_mode(out_range_mode) or int(out_range.value or 0) > 0)
    )
    out_range_is_simple = bool(is_simple_out_range(out_range))
    return {
        "enabled": bool(syndata.enabled),
        "blob": str(syndata.blob or "tls_google"),
        "tls_mod": str(syndata.tls_mod or "none"),
        "autottl_delta": int(syndata.autottl_delta or 0),
        "autottl_min": int(syndata.autottl_min or 3),
        "autottl_max": int(syndata.autottl_max or 20),
        "out_range": (
            int(out_range.value or 8)
            if out_range_enabled and not is_valuefree_out_range_mode(out_range_mode)
            else 8
        ),
        "out_range_mode": out_range_mode if out_range_enabled else "d",
        "out_range_expression": out_range_expression,
        "out_range_is_simple": out_range_is_simple,
        "tcp_flags_unset": str(syndata.tcp_flags_unset or "none"),
        "send_enabled": bool(send.enabled),
        "send_repeats": int(send.repeats or 0),
        "send_ip_ttl": int(send.ip_ttl or 0),
        "send_ip6_ttl": int(send.ip6_ttl or 0),
        "send_ip_id": str(send.ip_id or "none"),
        "send_badsum": bool(send.badsum),
    }


def build_args_editor_state_plan(
    *,
    target_key: str,
    selected_strategy_id: str,
) -> StrategyDetailArgsEditorStatePlan:
    enabled = bool(str(target_key or "").strip()) and (str(selected_strategy_id or "none").strip() or "none") != "none"
    return StrategyDetailArgsEditorStatePlan(
        enabled=enabled,
        should_hide_editor=not enabled,
    )


def build_args_editor_open_plan(
    facade,
    *,
    payload,
    target_key: str,
    selected_strategy_id: str,
) -> StrategyDetailArgsEditorOpenPlan:
    state_plan = build_args_editor_state_plan(
        target_key=target_key,
        selected_strategy_id=selected_strategy_id,
    )
    if not state_plan.enabled:
        return StrategyDetailArgsEditorOpenPlan(
            should_open=False,
            initial_text="",
        )

    normalized_target = str(target_key or "").strip().lower()
    if payload is not None and str(getattr(payload, "target_key", "") or "").strip().lower() == normalized_target:
        return StrategyDetailArgsEditorOpenPlan(
            should_open=True,
            initial_text=str(getattr(payload, "raw_args_text", "") or ""),
        )
    try:
        return StrategyDetailArgsEditorOpenPlan(
            should_open=True,
            initial_text=str(facade.get_target_raw_args_text(normalized_target) or ""),
        )
    except Exception:
        return StrategyDetailArgsEditorOpenPlan(
            should_open=True,
            initial_text="",
        )


def build_args_apply_plan(
    *,
    target_key: str,
    selected_strategy_id: str,
    raw_text: str,
) -> StrategyDetailArgsApplyPlan:
    state_plan = build_args_editor_state_plan(
        target_key=target_key,
        selected_strategy_id=selected_strategy_id,
    )
    lines = [line.strip() for line in str(raw_text or "").splitlines() if line.strip()]
    return StrategyDetailArgsApplyPlan(
        should_apply=state_plan.enabled,
        normalized_text="\n".join(lines),
        args_lines=lines,
    )


def build_args_apply_result_plan(*, payload) -> StrategyDetailArgsApplyResultPlan:
    current_strategy_id = (
        str(getattr(getattr(payload, "details", None), "current_strategy", "none") or "none").strip() or "none"
    )
    return StrategyDetailArgsApplyResultPlan(
        selected_strategy_id=current_strategy_id,
        current_strategy_id=current_strategy_id,
        should_show_loading=current_strategy_id != "none",
        should_emit_args_changed=True,
    )
