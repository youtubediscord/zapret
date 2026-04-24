from __future__ import annotations


def strategy_identity_modes() -> tuple[str, ...]:
    return ("keep_send_syndata", "helpers_stripped")


def keep_payload_in_identity(candidates: tuple[str, ...] | list[str] | None) -> bool:
    names = {
        str(name or "").strip().lower()
        for name in (candidates or ())
        if str(name or "").strip()
    }
    return "http80" not in names


def tcp_phase_mode(*, strategy_type: str, protocol_is_udp_like: bool) -> bool:
    _ = (strategy_type, protocol_is_udp_like)
    return False


def show_advanced_transport_controls(*, protocol_is_udp_like: bool, is_circular_preset: bool) -> bool:
    _ = (protocol_is_udp_like, is_circular_preset)
    return False


def show_reset_row(*, protocol_is_udp_like: bool) -> bool:
    _ = protocol_is_udp_like
    return False


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
    _ = (strategy_type, is_circular_preset)
    return {
        "tcp_phase_mode": False,
        "show_filter_button": True,
        "show_phases_bar": False,
        "show_filter_mode_frame": bool(has_ipset and has_hostlist),
        "show_send_frame": False,
        "show_syndata_frame": False,
        "show_reset_row": False,
        "force_disable_send": bool(protocol_is_udp_like),
        "force_disable_syndata": bool(protocol_is_udp_like),
    }
