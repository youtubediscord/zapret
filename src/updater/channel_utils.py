from __future__ import annotations

from config.config import CHANNEL_DEV, CHANNEL_STABLE

CANONICAL_UPDATE_CHANNELS = (CHANNEL_STABLE, CHANNEL_DEV)


def normalize_update_channel(channel: str) -> str:
    """Normalize runtime update channel to one canonical value."""
    normalized = str(channel or "").strip().lower()
    if normalized in CANONICAL_UPDATE_CHANNELS:
        return normalized
    return CHANNEL_STABLE


def is_dev_update_channel(channel: str) -> bool:
    return normalize_update_channel(channel) == CHANNEL_DEV


def get_channel_installer_name(channel: str) -> str:
    return "Zapret2Setup_DEV.exe" if is_dev_update_channel(channel) else "Zapret2Setup.exe"


def is_dev_release_asset_name(file_name: str) -> bool:
    upper_name = str(file_name or "").strip().upper()
    return upper_name.startswith("ZAPRET2SETUP_DEV") or "_DEV" in upper_name
