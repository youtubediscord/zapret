from __future__ import annotations

from dataclasses import dataclass


DIRECT_ZAPRET2_UI_MODE_DEFAULT = "basic"
_VALID_DIRECT_ZAPRET2_UI_MODES = frozenset({"basic", "advanced"})
_UDP_LIKE_PROTOCOL_MARKERS = ("UDP", "QUIC", "L7")


def normalize_direct_zapret2_ui_mode(value: object) -> str:
    mode = str(value or "").strip().lower()
    if mode in _VALID_DIRECT_ZAPRET2_UI_MODES:
        return mode
    return DIRECT_ZAPRET2_UI_MODE_DEFAULT


def get_current_direct_zapret2_ui_mode() -> str:
    try:
        from strategy_menu.ui_prefs_store import get_direct_zapret2_ui_mode

        return normalize_direct_zapret2_ui_mode(get_direct_zapret2_ui_mode())
    except Exception:
        return DIRECT_ZAPRET2_UI_MODE_DEFAULT


def is_udp_like_protocol(protocol: object) -> bool:
    protocol_text = str(protocol or "").upper()
    return any(marker in protocol_text for marker in _UDP_LIKE_PROTOCOL_MARKERS)


@dataclass(frozen=True, slots=True)
class StrategyDetailModePolicy:
    strategy_set: str
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
    strategy_set: str | None = None,
    is_circular_preset: bool = False,
) -> StrategyDetailModePolicy:
    resolved_strategy_set = normalize_direct_zapret2_ui_mode(
        strategy_set if strategy_set is not None else get_current_direct_zapret2_ui_mode()
    )
    resolved_strategy_type = str(getattr(target_info, "strategy_type", "") or "tcp").strip().lower() or "tcp"
    resolved_protocol = str(getattr(target_info, "protocol", "") or "").strip()
    is_basic_direct = resolved_strategy_set == "basic"
    is_udp_like = is_udp_like_protocol(resolved_protocol)
    tcp_phase_mode = (
        resolved_strategy_type == "tcp"
        and not is_udp_like
        and not is_basic_direct
    )
    has_ipset = bool(str(getattr(target_info, "base_filter_ipset", "") or "").strip())
    has_hostlist = bool(str(getattr(target_info, "base_filter_hostlist", "") or "").strip())
    show_advanced_transport_controls = (not is_basic_direct) and (not is_udp_like) and (not is_circular_preset)

    return StrategyDetailModePolicy(
        strategy_set=resolved_strategy_set,
        strategy_type=resolved_strategy_type,
        protocol=resolved_protocol,
        is_basic_direct=is_basic_direct,
        is_udp_like=is_udp_like,
        tcp_phase_mode=tcp_phase_mode,
        show_filter_button=not tcp_phase_mode,
        show_phases_bar=tcp_phase_mode,
        show_filter_mode_frame=has_ipset and has_hostlist,
        show_send_frame=show_advanced_transport_controls,
        show_syndata_frame=show_advanced_transport_controls,
        show_reset_row=(not is_basic_direct) and is_udp_like,
        force_disable_send=is_udp_like,
        force_disable_syndata=is_udp_like,
    )
