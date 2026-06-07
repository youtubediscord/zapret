from __future__ import annotations

from typing import Any

from settings.mode import (
    ALL_LAUNCH_METHODS,
    DEFAULT_LAUNCH_METHOD,
    SELECTED_SOURCE_PRESET_FILE_NAME_KEY_WINWS1,
    SELECTED_SOURCE_PRESET_FILE_NAME_KEY_WINWS2,
)

SETTINGS_DIR_NAME = "settings"
SETTINGS_FILE_NAME = "settings.json"
SETTINGS_VERSION = 1

DEFAULT_WINDOW_OPACITY = 100
DEFAULT_TINTED_INTENSITY = 15
DEFAULT_TG_PROXY_HOST = "127.0.0.1"
DEFAULT_TG_PROXY_PORT = 1353
DEFAULT_TG_PROXY_UPSTREAM_PORT = 1080

VALID_LAUNCH_METHODS = ALL_LAUNCH_METHODS
VALID_DISPLAY_MODES = frozenset({"dark", "light", "system"})
VALID_UI_LANGUAGES = frozenset({"ru", "en"})
VALID_BACKGROUND_PRESETS = frozenset({"standard", "amoled", "rkn_chan"})
VALID_SIDEBAR_ICON_STYLES = frozenset({"standard", "windows11_fluent"})
VALID_TG_PROXY_MODES = frozenset({"socks5", "transparent", "both", "mtproxy"})
VALID_TG_PROXY_UPSTREAM_MODES = frozenset({"fallback", "always"})
ORCHESTRA_ASKEYS = (
    "tls",
    "http",
    "quic",
    "discord",
    "wireguard",
    "mtproto",
    "dns",
    "stun",
    "unknown",
)


def default_program() -> dict[str, Any]:
    return {
        "dpi_autostart": True,
        "gui_autostart_enabled": False,
        "strategy_launch_method": DEFAULT_LAUNCH_METHOD,
        SELECTED_SOURCE_PRESET_FILE_NAME_KEY_WINWS1: "",
        SELECTED_SOURCE_PRESET_FILE_NAME_KEY_WINWS2: "",
        "auto_update_enabled": True,
        "remove_github_api": True,
        "discord_auto_restart": True,
        "max_blocked": False,
        "defender_disabled": False,
    }


def default_window() -> dict[str, Any]:
    return {
        "x": None,
        "y": None,
        "width": None,
        "height": None,
        "maximized": False,
        "opacity": DEFAULT_WINDOW_OPACITY,
        "hide_to_tray_on_minimize_close": False,
    }


def default_appearance() -> dict[str, Any]:
    return {
        "display_mode": "dark",
        "ui_language": "ru",
        "mica_enabled": True,
        "accent_color": None,
        "follow_windows_accent": False,
        "tinted_background": False,
        "tinted_background_intensity": DEFAULT_TINTED_INTENSITY,
        "background_preset": "standard",
        "rkn_background": None,
        "animations_enabled": False,
        "smooth_scroll_enabled": False,
        "editor_smooth_scroll_enabled": False,
        "sidebar_icon_style": "standard",
        "garland_enabled": False,
        "snowflakes_enabled": False,
        "selected_theme": "",
    }


def default_warnings() -> dict[str, Any]:
    return {
        "tray_hint_shown": False,
        "disable_telega_warning": False,
        "disable_kaspersky_warning": False,
        "isp_dns_info_shown": False,
        "tg_proxy_deeplink_done": False,
    }


def default_telegram_proxy() -> dict[str, Any]:
    return {
        "enabled": True,
        "host": DEFAULT_TG_PROXY_HOST,
        "port": DEFAULT_TG_PROXY_PORT,
        "mode": "socks5",
        "upstream_enabled": False,
        "upstream_host": "",
        "upstream_port": DEFAULT_TG_PROXY_UPSTREAM_PORT,
        "upstream_mode": "fallback",
        "upstream_user": "",
        "upstream_pass": "",
        "cloudflare_enabled": False,
        "cloudflare_domains": [],
        "cloudflare_worker_enabled": False,
        "cloudflare_worker_domains": [],
        "mtproxy_secret": "",
    }


def default_dns() -> dict[str, Any]:
    return {
        "force_dns_enabled": True,
        "dns_crash_count": 0,
    }


def default_hosts() -> dict[str, Any]:
    return {
        "bootstrap_signature": None,
        "active_domains": [],
        "selection": {},
    }


def default_premium() -> dict[str, Any]:
    return {
        "device_id": "",
        "device_token": None,
        "last_check": None,
        "last_network_failure_ts": None,
        "pair_code": None,
        "pair_expires_at": None,
        "premium_cache": None,
    }


def default_ui_state() -> dict[str, Any]:
    return {
        "sidebar_expanded": True,
    }


def default_profile_strategy_state() -> dict[str, Any]:
    return {
        "version": 1,
        "profiles": {},
    }


def default_user_profiles() -> dict[str, Any]:
    return {
        "version": 1,
        "profiles": {},
    }


def default_orchestra_settings() -> dict[str, Any]:
    return {
        "strict_detection": True,
        "keep_debug_file": False,
        "auto_restart_on_discord_fail": True,
        "discord_fails_for_restart": 3,
        "lock_successes": 3,
        "unlock_fails": 3,
    }


def default_orchestra_locked_maps() -> dict[str, dict[str, int]]:
    return {askey: {} for askey in ORCHESTRA_ASKEYS}


def default_orchestra_user_locked_maps() -> dict[str, list[str]]:
    return {askey: [] for askey in ORCHESTRA_ASKEYS}


def default_orchestra_user_blocked_maps() -> dict[str, dict[str, list[int]]]:
    return {askey: {} for askey in ORCHESTRA_ASKEYS}


def default_orchestra() -> dict[str, Any]:
    return {
        "settings": default_orchestra_settings(),
        "whitelist": {"user_domains": []},
        "locked": default_orchestra_locked_maps(),
        "user_locked": default_orchestra_user_locked_maps(),
        "user_blocked": default_orchestra_user_blocked_maps(),
        "history": {},
    }


def default_updater() -> dict[str, Any]:
    return {
        "release_cache": {},
        "rate_limit": {},
        "github_cache": {},
        "github_rate_limit_reset": None,
        "server_pool": {
            "stats": {},
            "selected_server_id": None,
            "selected_at": None,
        },
        "release_manager": {
            "vps_block_until": 0,
            "server_stats": {},
        },
    }


def default_blockcheck() -> dict[str, Any]:
    return {
        "user_domains": [],
        "scan_resume": {"domains": {}},
    }


def default_folders() -> dict[str, Any]:
    from folders.defaults import build_default_preset_folders, build_default_profile_folders

    return {
        "version": 1,
        "presets": {
            "winws2": build_default_preset_folders("winws2"),
            "winws1": build_default_preset_folders("winws1"),
        },
        "profiles": build_default_profile_folders(),
    }


def build_default_settings() -> dict[str, Any]:
    return {
        "version": SETTINGS_VERSION,
        "program": default_program(),
        "window": default_window(),
        "appearance": default_appearance(),
        "warnings": default_warnings(),
        "telegram_proxy": default_telegram_proxy(),
        "dns": default_dns(),
        "hosts": default_hosts(),
        "premium": default_premium(),
        "ui_state": default_ui_state(),
        "profile_strategy_state": default_profile_strategy_state(),
        "user_profiles": default_user_profiles(),
        "orchestra": default_orchestra(),
        "updater": default_updater(),
        "blockcheck": default_blockcheck(),
        "folders": default_folders(),
    }
