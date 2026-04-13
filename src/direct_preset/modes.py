from __future__ import annotations

from dataclasses import dataclass


DIRECT_UI_MODE_DEFAULT = "basic"
_VALID_DIRECT_ZAPRET2_UI_MODES = frozenset({"basic", "advanced"})
_UDP_LIKE_PROTOCOL_MARKERS = ("UDP", "QUIC", "L7")


def normalize_direct_ui_mode_for_engine(engine: str, value: object) -> str:
    normalized_engine = str(engine or "").strip().lower()
    if normalized_engine != "winws2":
        return ""
    mode = str(value or "").strip().lower()
    if mode in _VALID_DIRECT_ZAPRET2_UI_MODES:
        return mode
    return DIRECT_UI_MODE_DEFAULT


def load_current_direct_ui_mode(engine: str) -> str:
    normalized_engine = str(engine or "").strip().lower()
    if normalized_engine != "winws2":
        return ""
    try:
        from settings.dpi.strategy_settings import get_direct_ui_mode

        return normalize_direct_ui_mode_for_engine(normalized_engine, get_direct_ui_mode())
    except Exception:
        return DIRECT_UI_MODE_DEFAULT


def is_udp_like_protocol(protocol: object) -> bool:
    protocol_text = str(protocol or "").upper()
    return any(marker in protocol_text for marker in _UDP_LIKE_PROTOCOL_MARKERS)


@dataclass(frozen=True)
class DirectPresetModeAdapter:
    engine: str
    strategy_set: str

    @property
    def is_basic_direct(self) -> bool:
        return self.engine == "winws2" and self.strategy_set == "basic"

    @property
    def is_advanced_direct(self) -> bool:
        return self.engine == "winws2" and self.strategy_set == "advanced"

    def strategy_identity_modes(self) -> tuple[str, ...]:
        if self.is_basic_direct:
            return ("keep_send_syndata", "helpers_stripped")
        return ("helpers_stripped",)

    def keep_payload_in_identity(self, candidates: tuple[str, ...] | list[str] | None) -> bool:
        names = {
            str(name or "").strip().lower()
            for name in (candidates or ())
            if str(name or "").strip()
        }
        return "http80" not in names

    def tcp_phase_mode(self, *, strategy_type: str, protocol: object) -> bool:
        return (
            self.is_advanced_direct
            and str(strategy_type or "").strip().lower() == "tcp"
            and not is_udp_like_protocol(protocol)
        )

    def show_advanced_transport_controls(self, *, protocol: object, is_circular_preset: bool) -> bool:
        return self.is_advanced_direct and (not is_udp_like_protocol(protocol)) and (not is_circular_preset)

    def show_reset_row(self, *, protocol: object) -> bool:
        return self.is_advanced_direct and is_udp_like_protocol(protocol)

    def force_disable_send(self, *, protocol: object) -> bool:
        return is_udp_like_protocol(protocol)

    def force_disable_syndata(self, *, protocol: object) -> bool:
        return is_udp_like_protocol(protocol)


def get_direct_preset_mode_adapter(engine: str, strategy_set: object) -> DirectPresetModeAdapter:
    normalized_engine = str(engine or "").strip().lower()
    normalized_set = normalize_direct_ui_mode_for_engine(normalized_engine, strategy_set)
    return DirectPresetModeAdapter(
        engine=normalized_engine,
        strategy_set=normalized_set,
    )


__all__ = [
    "DIRECT_UI_MODE_DEFAULT",
    "DirectPresetModeAdapter",
    "get_direct_preset_mode_adapter",
    "is_udp_like_protocol",
    "load_current_direct_ui_mode",
    "normalize_direct_ui_mode_for_engine",
]
