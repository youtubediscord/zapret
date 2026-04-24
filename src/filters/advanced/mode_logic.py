from __future__ import annotations


def strategy_identity_modes() -> tuple[str, ...]:
    return ("helpers_stripped",)


def keep_payload_in_identity(candidates: tuple[str, ...] | list[str] | None) -> bool:
    _ = candidates
    return True


def tcp_phase_mode(*, strategy_type: str, protocol_is_udp_like: bool) -> bool:
    return str(strategy_type or "").strip().lower() == "tcp" and not bool(protocol_is_udp_like)


def show_advanced_transport_controls(*, protocol_is_udp_like: bool, is_circular_preset: bool) -> bool:
    return (not bool(protocol_is_udp_like)) and (not bool(is_circular_preset))


def show_reset_row(*, protocol_is_udp_like: bool) -> bool:
    return bool(protocol_is_udp_like)


def force_disable_send(*, protocol_is_udp_like: bool) -> bool:
    return bool(protocol_is_udp_like)


def force_disable_syndata(*, protocol_is_udp_like: bool) -> bool:
    return bool(protocol_is_udp_like)


def build_detail_policy_flags(
    *,
    has_ipset: bool,
    has_hostlist: bool,
    strategy_type: str,
    protocol_is_udp_like: bool,
    is_circular_preset: bool,
) -> dict[str, bool]:
    tcp_phase = tcp_phase_mode(
        strategy_type=strategy_type,
        protocol_is_udp_like=protocol_is_udp_like,
    )
    show_transport = show_advanced_transport_controls(
        protocol_is_udp_like=protocol_is_udp_like,
        is_circular_preset=is_circular_preset,
    )
    return {
        "tcp_phase_mode": bool(tcp_phase),
        "show_filter_button": not bool(tcp_phase),
        "show_phases_bar": bool(tcp_phase),
        "show_filter_mode_frame": bool(has_ipset and has_hostlist),
        "show_send_frame": bool(show_transport),
        "show_syndata_frame": bool(show_transport),
        "show_reset_row": bool(show_reset_row(protocol_is_udp_like=protocol_is_udp_like)),
        "force_disable_send": bool(force_disable_send(protocol_is_udp_like=protocol_is_udp_like)),
        "force_disable_syndata": bool(force_disable_syndata(protocol_is_udp_like=protocol_is_udp_like)),
    }
