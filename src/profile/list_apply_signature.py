from __future__ import annotations


def profile_payload_apply_signature_base(payload, *, view_state=None) -> tuple[object, ...]:
    return (
        tuple(_profile_item_signature(item) for item in tuple(getattr(payload, "items", ()) or ())),
        str(getattr(payload, "selected_preset_file_name", "") or ""),
        str(getattr(payload, "selected_preset_name", "") or ""),
        int(getattr(payload, "normalized_split_profiles", 0) or 0),
        int(getattr(payload, "normalized_created_profiles", 0) or 0),
        _freeze_signature_value(view_state),
    )


def profile_payload_apply_signature(
    payload,
    *,
    view_state=None,
    search_query: str = "",
    apply_signature_base: tuple[object, ...] | None = None,
) -> tuple[object, ...]:
    base = (
        tuple(apply_signature_base)
        if apply_signature_base is not None
        else profile_payload_apply_signature_base(payload, view_state=view_state)
    )
    return (*base, str(search_query or ""))


def _profile_item_signature(item) -> object:
    if isinstance(item, (str, int, float, bool, type(None))):
        return item
    return (
        str(getattr(item, "key", "") or ""),
        str(getattr(item, "persistent_key", "") or ""),
        int(getattr(item, "profile_index", -1) or -1),
        str(getattr(item, "display_name", "") or ""),
        bool(getattr(item, "enabled", False)),
        bool(getattr(item, "in_preset", False)),
        str(getattr(item, "strategy_id", "") or ""),
        str(getattr(item, "strategy_name", "") or ""),
        tuple(str(line or "") for line in tuple(getattr(item, "match_lines", ()) or ())),
        str(getattr(item, "list_type", "") or ""),
        str(getattr(item, "rating", "") or ""),
        bool(getattr(item, "favorite", False)),
        str(getattr(item, "group", "") or ""),
        str(getattr(item, "group_name", "") or ""),
        int(getattr(item, "order", 0) or 0),
        bool(getattr(item, "order_is_manual", False)),
        bool(getattr(item, "group_collapsed", False)),
        str(getattr(item, "user_profile_id", "") or ""),
        str(getattr(item, "profile_name", "") or ""),
        tuple(_profile_strategy_branch_signature(branch) for branch in tuple(getattr(item, "strategy_branches", ()) or ())),
    )


def _profile_strategy_branch_signature(branch) -> tuple[object, ...]:
    return (
        str(getattr(branch, "branch_id", "") or ""),
        str(getattr(branch, "payload", "") or ""),
        str(getattr(branch, "in_range", "") or ""),
        str(getattr(branch, "out_range", "") or ""),
        str(getattr(branch, "strategy_id", "") or ""),
        str(getattr(branch, "strategy_name", "") or ""),
        str(getattr(branch, "raw_strategy_text", "") or ""),
        str(getattr(branch, "match_tab_text", "") or ""),
    )


def _freeze_signature_value(value) -> object:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return tuple(
            (str(key), _freeze_signature_value(item))
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        )
    if isinstance(value, (list, tuple, set, frozenset)):
        return tuple(_freeze_signature_value(item) for item in value)

    if hasattr(value, "all_items") and hasattr(value, "rows"):
        return (
            "ProfileListViewState",
            tuple(_profile_item_signature(item) for item in tuple(getattr(value, "all_items", ()) or ())),
            _freeze_signature_value(getattr(value, "group_expanded", {})),
            tuple(sorted(str(item) for item in set(getattr(value, "active_profile_types", set()) or set()))),
            str(getattr(value, "search_query", "") or ""),
            _freeze_signature_value(getattr(value, "rows", ())),
        )

    return repr(value)


__all__ = [
    "profile_payload_apply_signature",
    "profile_payload_apply_signature_base",
]
