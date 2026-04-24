from __future__ import annotations

from filters.mode_runtime import (
    DIRECT_MODE_DEFAULT,
    is_udp_like_protocol,
    load_current_direct_mode,
    normalize_direct_mode,
    resolve_direct_mode_logic as _resolve_direct_mode_logic,
)


DIRECT_UI_MODE_DEFAULT = DIRECT_MODE_DEFAULT


def normalize_direct_ui_mode_for_engine(engine: str, value: object) -> str:
    normalized_engine = str(engine or "").strip().lower()
    if normalized_engine != "winws2":
        return ""
    return normalize_direct_mode(value)


def load_current_direct_ui_mode(engine: str) -> str:
    normalized_engine = str(engine or "").strip().lower()
    if normalized_engine != "winws2":
        return ""
    return load_current_direct_mode()


def resolve_direct_mode_logic(engine: str, direct_mode: str):
    normalized_engine = str(engine or "").strip().lower()
    if normalized_engine != "winws2":
        return None
    return _resolve_direct_mode_logic(direct_mode)


__all__ = [
    "DIRECT_UI_MODE_DEFAULT",
    "is_udp_like_protocol",
    "load_current_direct_ui_mode",
    "normalize_direct_ui_mode_for_engine",
    "resolve_direct_mode_logic",
]
