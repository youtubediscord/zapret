from __future__ import annotations


PROFILE_UI_MODE_DEFAULT = "basic"
_VALID_PROFILE_UI_MODES = frozenset({"basic"})


def normalize_profile_ui_mode(value: object) -> str:
    mode = str(value or "").strip().lower()
    if mode in _VALID_PROFILE_UI_MODES:
        return mode
    return PROFILE_UI_MODE_DEFAULT


def load_current_profile_ui_mode() -> str:
    try:
        from settings.dpi.strategy_settings import get_profile_ui_mode

        return normalize_profile_ui_mode(get_profile_ui_mode())
    except Exception:
        return PROFILE_UI_MODE_DEFAULT
