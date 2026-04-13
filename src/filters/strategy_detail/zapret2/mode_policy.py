from __future__ import annotations

from dataclasses import dataclass

from direct_preset.modes import (
    DIRECT_UI_MODE_DEFAULT,
    get_direct_preset_mode_adapter,
    is_udp_like_protocol,
    load_current_direct_ui_mode,
    normalize_direct_ui_mode_for_engine,
)


def get_current_direct_zapret2_ui_mode() -> str:
    resolved = load_current_direct_ui_mode("winws2")
    return resolved or DIRECT_UI_MODE_DEFAULT


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
    resolved_strategy_set = normalize_direct_ui_mode_for_engine(
        "winws2",
        strategy_set if strategy_set is not None else get_current_direct_zapret2_ui_mode(),
    )
    resolved_strategy_type = str(getattr(target_info, "strategy_type", "") or "tcp").strip().lower() or "tcp"
    resolved_protocol = str(getattr(target_info, "protocol", "") or "").strip()
    mode_adapter = get_direct_preset_mode_adapter("winws2", resolved_strategy_set)
    is_basic_direct = mode_adapter.is_basic_direct
    is_udp_like = is_udp_like_protocol(resolved_protocol)
    tcp_phase_mode = mode_adapter.tcp_phase_mode(
        strategy_type=resolved_strategy_type,
        protocol=resolved_protocol,
    )
    has_ipset = bool(str(getattr(target_info, "base_filter_ipset", "") or "").strip())
    has_hostlist = bool(str(getattr(target_info, "base_filter_hostlist", "") or "").strip())
    show_advanced_transport_controls = mode_adapter.show_advanced_transport_controls(
        protocol=resolved_protocol,
        is_circular_preset=bool(is_circular_preset),
    )

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
        show_reset_row=mode_adapter.show_reset_row(protocol=resolved_protocol),
        force_disable_send=mode_adapter.force_disable_send(protocol=resolved_protocol),
        force_disable_syndata=mode_adapter.force_disable_syndata(protocol=resolved_protocol),
    )
