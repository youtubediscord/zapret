from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from app.page_names import PageName


_WINDOWS11_SIDEBAR_ICON_FILES: dict[PageName, str] = {
    PageName.ZAPRET2_MODE_CONTROL: "home.svg",
    PageName.ZAPRET1_MODE_CONTROL: "home.svg",
    PageName.ORCHESTRA: "services.svg",
    PageName.ZAPRET2_USER_PRESETS: "folder.svg",
    PageName.ZAPRET1_USER_PRESETS: "folder.svg",
    PageName.ZAPRET2_PRESET_SETUP: "play.svg",
    PageName.ZAPRET1_PRESET_SETUP: "play.svg",
    PageName.DPI_SETTINGS: "settings.svg",
    PageName.AUTOSTART: "play.svg",
    PageName.NETWORK: "search.svg",
    PageName.TELEGRAM_PROXY: "share.svg",
    PageName.HOSTS: "document.svg",
    PageName.BLOCKCHECK: "binoculars.svg",
    PageName.APPEARANCE: "picture.svg",
    PageName.PREMIUM: "bookmark.svg",
    PageName.LOGS: "history.svg",
    PageName.ABOUT: "info.svg",
    PageName.SERVERS: "cloud-download.svg",
    PageName.SUPPORT: "share.svg",
    PageName.BLOBS: "key.svg",
    PageName.ORCHESTRA_SETTINGS: "settings.svg",
}


def normalize_sidebar_icon_style(style: str | None) -> str:
    try:
        from settings.appearance import normalize_sidebar_icon_style as _normalize

        return _normalize(style)
    except Exception:
        return "standard"


def current_sidebar_icon_style() -> str:
    try:
        from settings.appearance import load_sidebar_icon_style, peek_warmed_sidebar_icon_style

        warmed = peek_warmed_sidebar_icon_style()
        if warmed is not None:
            return normalize_sidebar_icon_style(warmed)
        return normalize_sidebar_icon_style(load_sidebar_icon_style().style)
    except Exception:
        return "standard"


def build_standard_nav_icons() -> dict[PageName, Any]:
    from qfluentwidgets import FluentIcon

    return {
        PageName.ZAPRET2_MODE_CONTROL: FluentIcon.GAME,
        PageName.AUTOSTART: FluentIcon.POWER_BUTTON,
        PageName.NETWORK: FluentIcon.WIFI,
        PageName.HOSTS: FluentIcon.GLOBE,
        PageName.BLOCKCHECK: FluentIcon.CODE,
        PageName.APPEARANCE: FluentIcon.PALETTE,
        PageName.PREMIUM: FluentIcon.HEART,
        PageName.LOGS: FluentIcon.HISTORY,
        PageName.ABOUT: FluentIcon.INFO,
        PageName.DPI_SETTINGS: FluentIcon.SETTING,
        PageName.BLOBS: FluentIcon.CLOUD,
        PageName.ZAPRET2_USER_PRESETS: FluentIcon.FOLDER,
        PageName.SERVERS: FluentIcon.UPDATE,
        PageName.SUPPORT: FluentIcon.CHAT,
        PageName.ORCHESTRA: FluentIcon.MUSIC,
        PageName.ORCHESTRA_SETTINGS: FluentIcon.SETTING,
        PageName.ZAPRET2_PRESET_SETUP: FluentIcon.PLAY,
        PageName.ZAPRET1_MODE_CONTROL: FluentIcon.GAME,
        PageName.ZAPRET1_PRESET_SETUP: FluentIcon.PLAY,
        PageName.ZAPRET1_USER_PRESETS: FluentIcon.FOLDER,
        PageName.TELEGRAM_PROXY: FluentIcon.SEND,
    }


def _resource_roots() -> tuple[Path, ...]:
    roots: list[Path] = []
    if getattr(sys, "frozen", False):
        roots.append(Path(sys.executable).resolve().parent)
    roots.append(Path.cwd())
    roots.append(Path(__file__).resolve().parents[3])
    return tuple(dict.fromkeys(roots))


def _windows11_sidebar_icon_path(file_name: str) -> Path | None:
    relative = Path("ico") / "windows11_fluent" / "sidebar" / file_name
    for root in _resource_roots():
        candidate = root / relative
        if candidate.exists():
            return candidate
    return None


def build_windows11_fluent_nav_icons() -> dict[PageName, Any]:
    from PyQt6.QtGui import QIcon

    standard = build_standard_nav_icons()
    icons: dict[PageName, Any] = {}
    for page_name, fallback_icon in standard.items():
        file_name = _WINDOWS11_SIDEBAR_ICON_FILES.get(page_name)
        icon_path = _windows11_sidebar_icon_path(file_name or "")
        if icon_path is None:
            icons[page_name] = fallback_icon
            continue
        icon = QIcon(str(icon_path))
        icons[page_name] = fallback_icon if icon.isNull() else icon
    return icons


def build_nav_icons(style: str | None = None) -> dict[PageName, Any]:
    if normalize_sidebar_icon_style(style or current_sidebar_icon_style()) == "windows11_fluent":
        return build_windows11_fluent_nav_icons()
    return build_standard_nav_icons()


def default_nav_icon(style: str | None = None) -> Any:
    normalized = normalize_sidebar_icon_style(style or current_sidebar_icon_style())
    if normalized == "windows11_fluent":
        from PyQt6.QtGui import QIcon

        icon_path = _windows11_sidebar_icon_path("home.svg")
        if icon_path is not None:
            icon = QIcon(str(icon_path))
            if not icon.isNull():
                return icon
    from qfluentwidgets import FluentIcon

    return FluentIcon.APPLICATION


def apply_sidebar_icon_style(window, style: str | None) -> None:
    from ui.window_ui_session import get_window_ui_session

    session = get_window_ui_session(window)
    if session is None:
        return
    normalized = normalize_sidebar_icon_style(style)
    session.nav_icons = build_nav_icons(normalized)
    session.default_nav_icon = default_nav_icon(normalized)
    for page_name, item in tuple((getattr(session, "nav_items", {}) or {}).items()):
        icon = session.nav_icons.get(page_name, session.default_nav_icon)
        set_icon = getattr(item, "setIcon", None)
        if callable(set_icon):
            set_icon(icon)


__all__ = [
    "apply_sidebar_icon_style",
    "build_nav_icons",
    "current_sidebar_icon_style",
    "default_nav_icon",
]
