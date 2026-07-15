from __future__ import annotations

from typing import Any

from app.navigation_icon_resources import resolve_windows11_sidebar_icon_path
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
    PageName.NETWORK: "search.svg",
    PageName.TELEGRAM_PROXY: "share.svg",
    PageName.HOSTS: "document.svg",
    PageName.BLOCKCHECK: "binoculars.svg",
    PageName.WINWS_LOG_ANALYZER: "search.svg",
    PageName.APPEARANCE: "picture.svg",
    PageName.PREMIUM: "bookmark.svg",
    PageName.LOGS: "history.svg",
    PageName.ABOUT: "info.svg",
    PageName.SERVERS: "cloud-download.svg",
    PageName.SUPPORT: "share.svg",
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
        from settings.appearance import peek_warmed_sidebar_icon_style

        warmed = peek_warmed_sidebar_icon_style()
        if warmed is not None:
            return normalize_sidebar_icon_style(warmed)
    except Exception:
        pass
    return "standard"


def build_standard_nav_icons() -> dict[PageName, Any]:
    from qfluentwidgets import FluentIcon

    return {
        PageName.ZAPRET2_MODE_CONTROL: FluentIcon.GAME,
        PageName.NETWORK: FluentIcon.WIFI,
        PageName.HOSTS: FluentIcon.GLOBE,
        PageName.BLOCKCHECK: FluentIcon.CODE,
        PageName.WINWS_LOG_ANALYZER: FluentIcon.SEARCH,
        PageName.APPEARANCE: FluentIcon.PALETTE,
        PageName.PREMIUM: FluentIcon.HEART,
        PageName.LOGS: FluentIcon.HISTORY,
        PageName.ABOUT: FluentIcon.INFO,
        PageName.DPI_SETTINGS: FluentIcon.SETTING,
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


def build_windows11_fluent_nav_icons() -> dict[PageName, Any]:
    from PyQt6.QtGui import QIcon

    standard = build_standard_nav_icons()
    icons: dict[PageName, Any] = {}
    for page_name, fallback_icon in standard.items():
        file_name = _WINDOWS11_SIDEBAR_ICON_FILES.get(page_name)
        icon_path = resolve_windows11_sidebar_icon_path(file_name or "")
        if not icon_path:
            icons[page_name] = fallback_icon
            continue
        icon = QIcon(icon_path)
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

        icon_path = resolve_windows11_sidebar_icon_path("home.svg")
        if icon_path:
            icon = QIcon(icon_path)
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
