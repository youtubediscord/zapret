from __future__ import annotations

from dataclasses import dataclass

from direct_preset.modes import resolve_direct_mode_logic
from filters.mode_runtime import (
    DIRECT_MODE_DEFAULT,
    is_udp_like_protocol,
    load_current_direct_mode,
    normalize_direct_mode,
)


def get_current_direct_zapret2_ui_mode() -> str:
    resolved = load_current_direct_mode()
    return resolved or DIRECT_MODE_DEFAULT


@dataclass(frozen=True, slots=True)
class StrategyDetailModePolicy:
    direct_mode: str
    strategy_type: str
    protocol: str
    is_basic_direct: bool
    is_udp_like: bool
    tcp_phase_mode: bool
    show_filter_button: bool
    show_phases_bar: bool
    show_filter_mode_frame: bool
    show_send_frame: bool
    show_syndata_frame: bool
    show_reset_row: bool
    force_disable_send: bool
    force_disable_syndata: bool


def build_strategy_detail_mode_policy(
    target_info,
    *,
    direct_mode: str | None = None,
    is_circular_preset: bool = False,
) -> StrategyDetailModePolicy:
    resolved_direct_mode = normalize_direct_mode(
        direct_mode if direct_mode is not None else get_current_direct_zapret2_ui_mode()
    )
    resolved_strategy_type = str(getattr(target_info, "strategy_type", "") or "tcp").strip().lower() or "tcp"
    resolved_protocol = str(getattr(target_info, "protocol", "") or "").strip()
    is_udp_like = is_udp_like_protocol(resolved_protocol)
    has_ipset = bool(str(getattr(target_info, "base_filter_ipset", "") or "").strip())
    has_hostlist = bool(str(getattr(target_info, "base_filter_hostlist", "") or "").strip())
    mode_logic = resolve_direct_mode_logic("winws2", resolved_direct_mode)
    if mode_logic is None:
        raise RuntimeError(f"Mode logic is not available for direct_mode={resolved_direct_mode!r}")

    flags = mode_logic.build_detail_policy_flags(
        has_ipset=has_ipset,
        has_hostlist=has_hostlist,
        strategy_type=resolved_strategy_type,
        protocol_is_udp_like=is_udp_like,
        is_circular_preset=bool(is_circular_preset),
    )

    return StrategyDetailModePolicy(
        direct_mode=resolved_direct_mode,
        strategy_type=resolved_strategy_type,
        protocol=resolved_protocol,
        is_basic_direct=bool(resolved_direct_mode == "basic"),
        is_udp_like=is_udp_like,
        tcp_phase_mode=bool(flags["tcp_phase_mode"]),
        show_filter_button=bool(flags["show_filter_button"]),
        show_phases_bar=bool(flags["show_phases_bar"]),
        show_filter_mode_frame=bool(flags["show_filter_mode_frame"]),
        show_send_frame=bool(flags["show_send_frame"]),
        show_syndata_frame=bool(flags["show_syndata_frame"]),
        show_reset_row=bool(flags["show_reset_row"]),
        force_disable_send=bool(flags["force_disable_send"]),
        force_disable_syndata=bool(flags["force_disable_syndata"]),
    )
