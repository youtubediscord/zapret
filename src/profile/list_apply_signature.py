from __future__ import annotations


def profile_payload_apply_signature_base(payload, *, view_state=None) -> tuple[object, ...]:
    return (
        tuple(getattr(payload, "items", ()) or ()),
        str(getattr(payload, "selected_preset_file_name", "") or ""),
        str(getattr(payload, "selected_preset_name", "") or ""),
        int(getattr(payload, "normalized_split_profiles", 0) or 0),
        int(getattr(payload, "normalized_created_profiles", 0) or 0),
        view_state,
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


__all__ = [
    "profile_payload_apply_signature",
    "profile_payload_apply_signature_base",
]
