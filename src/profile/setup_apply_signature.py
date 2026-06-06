from __future__ import annotations


def profile_setup_payload_apply_signature(payload) -> tuple[object, ...]:
    if payload is None:
        return (None,)

    strategy_entries = getattr(payload, "strategy_entries", {}) or {}
    strategy_states = getattr(payload, "strategy_states", {}) or {}

    return (
        getattr(payload, "item", None),
        tuple(sorted(strategy_entries.items())),
        tuple(sorted(strategy_states.items())),
        str(getattr(payload, "raw_profile_text", "") or ""),
        str(getattr(payload, "raw_strategy_text", "") or ""),
        str(getattr(payload, "match_summary", "") or ""),
        tuple(getattr(payload, "strategy_branches", ()) or ()),
        str(getattr(payload, "current_strategy_branch_id", "") or ""),
        str(getattr(payload, "editable_filter_kind", "") or ""),
        str(getattr(payload, "editable_filter_value", "") or ""),
        bool(getattr(payload, "editable_filter_enabled", True)),
        str(getattr(payload, "editable_filter_role", "") or ""),
        tuple(getattr(payload, "editable_filter_kinds", ()) or ()),
        str(getattr(payload, "in_range", "") or "x"),
        str(getattr(payload, "out_range", "") or "a"),
        getattr(payload, "current_strategy_state", None),
    )


__all__ = ["profile_setup_payload_apply_signature"]
