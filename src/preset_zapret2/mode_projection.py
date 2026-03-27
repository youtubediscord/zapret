from __future__ import annotations

from copy import deepcopy

from .block_semantics import reset_structured_advanced_state


def normalize_direct_zapret2_ui_mode(mode: str | None) -> str:
    value = (mode or "").strip().lower()
    return value if value in ("basic", "advanced") else "basic"


def project_preset_for_direct_ui_mode(preset, ui_mode: str | None):
    projected = deepcopy(preset)
    mode = normalize_direct_zapret2_ui_mode(ui_mode)

    if mode != "basic":
        return projected

    for category in (projected.categories or {}).values():
        tcp_raw = str(getattr(category, "tcp_args_raw", "") or "").strip()
        udp_raw = str(getattr(category, "udp_args_raw", "") or "").strip()

        if tcp_raw:
            category.tcp_args = tcp_raw
        if udp_raw:
            category.udp_args = udp_raw

        reset_structured_advanced_state(category)

    return projected
