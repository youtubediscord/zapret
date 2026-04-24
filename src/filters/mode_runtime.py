from __future__ import annotations


DIRECT_MODE_DEFAULT = "basic"
_VALID_DIRECT_MODES = frozenset({"basic", "advanced"})
_UDP_LIKE_PROTOCOL_MARKERS = ("UDP", "QUIC", "L7")


def normalize_direct_mode(value: object) -> str:
    mode = str(value or "").strip().lower()
    if mode in _VALID_DIRECT_MODES:
        return mode
    return DIRECT_MODE_DEFAULT


def load_current_direct_mode() -> str:
    try:
        from settings.dpi.strategy_settings import get_direct_ui_mode

        return normalize_direct_mode(get_direct_ui_mode())
    except Exception:
        return DIRECT_MODE_DEFAULT


def resolve_direct_mode_override(value: object) -> str | None:
    normalized = str(value or "").strip().lower()
    if normalized not in _VALID_DIRECT_MODES:
        return None
    return normalized


def is_udp_like_protocol(protocol: object) -> bool:
    protocol_text = str(protocol or "").upper()
    return any(marker in protocol_text for marker in _UDP_LIKE_PROTOCOL_MARKERS)


def resolve_direct_mode_logic(direct_mode: object):
    normalized_mode = normalize_direct_mode(direct_mode)
    if normalized_mode == "advanced":
        from filters import advanced as mode_logic

        return mode_logic
    from filters import basic as mode_logic

    return mode_logic
