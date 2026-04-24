from __future__ import annotations

from typing import Any

from settings import schema


def as_dict(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_bool(value: object, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return bool(value)
    if isinstance(value, str):
        text = value.strip().lower()
        if text in {"1", "true", "yes", "on"}:
            return True
        if text in {"0", "false", "no", "off"}:
            return False
    return bool(default)


def as_int(value: object, default: int, *, minimum: int | None = None, maximum: int | None = None) -> int:
    try:
        result = int(value)  # type: ignore[arg-type]
    except Exception:
        result = int(default)
    if minimum is not None:
        result = max(minimum, result)
    if maximum is not None:
        result = min(maximum, result)
    return result


def as_nullable_int(value: object) -> int | None:
    try:
        return int(value)  # type: ignore[arg-type]
    except Exception:
        return None


def as_str(value: object, default: str = "") -> str:
    if value is None:
        return str(default or "")
    return str(value)


def as_clean_str(value: object, default: str = "") -> str:
    return as_str(value, default).strip()


def as_nullable_str(value: object) -> str | None:
    text = as_clean_str(value)
    return text or None


def as_str_in(value: object, allowed: frozenset[str], default: str) -> str:
    text = as_clean_str(value).lower()
    if text in allowed:
        return text
    return default


def unique_str_list(value: object) -> list[str]:
    if not isinstance(value, (list, tuple, set)):
        return []
    result: list[str] = []
    seen: set[str] = set()
    for item in value:
        text = as_clean_str(item)
        if not text:
            continue
        normalized = text.lower()
        if normalized in seen:
            continue
        seen.add(normalized)
        result.append(text)
    return result


def unique_int_list(value: object) -> list[int]:
    if not isinstance(value, (list, tuple, set)):
        return []
    result: list[int] = []
    seen: set[int] = set()
    for item in value:
        try:
            number = int(item)  # type: ignore[arg-type]
        except Exception:
            continue
        if number in seen:
            continue
        seen.add(number)
        result.append(number)
    return result


def normalize_target_key(value: object) -> str:
    return as_clean_str(value).lower()


def normalize_askey(value: object) -> str:
    normalized = as_clean_str(value).lower()
    return normalized if normalized in schema.ORCHESTRA_ASKEYS else "tls"


def normalize_program(data: object) -> dict[str, Any]:
    raw = as_dict(data)
    defaults = schema.default_program()
    return {
        "dpi_autostart": as_bool(raw.get("dpi_autostart"), defaults["dpi_autostart"]),
        "strategy_launch_method": as_str_in(raw.get("strategy_launch_method"), schema.VALID_LAUNCH_METHODS, defaults["strategy_launch_method"]),
        "direct_ui_mode": as_str_in(raw.get("direct_ui_mode"), schema.VALID_DIRECT_UI_MODES, defaults["direct_ui_mode"]),
        "selected_source_preset_file_name_winws1": as_clean_str(
            raw.get("selected_source_preset_file_name_winws1"),
            defaults["selected_source_preset_file_name_winws1"],
        ),
        "selected_source_preset_file_name_winws2": as_clean_str(
            raw.get("selected_source_preset_file_name_winws2"),
            defaults["selected_source_preset_file_name_winws2"],
        ),
        "auto_update_enabled": as_bool(raw.get("auto_update_enabled"), defaults["auto_update_enabled"]),
        "remove_github_api": as_bool(raw.get("remove_github_api"), defaults["remove_github_api"]),
        "discord_auto_restart": as_bool(raw.get("discord_auto_restart"), defaults["discord_auto_restart"]),
        "max_blocked": as_bool(raw.get("max_blocked"), defaults["max_blocked"]),
        "defender_disabled": as_bool(raw.get("defender_disabled"), defaults["defender_disabled"]),
    }


def normalize_window(data: object) -> dict[str, Any]:
    raw = as_dict(data)
    defaults = schema.default_window()
    return {
        "x": as_nullable_int(raw.get("x")),
        "y": as_nullable_int(raw.get("y")),
        "width": as_nullable_int(raw.get("width")),
        "height": as_nullable_int(raw.get("height")),
        "maximized": as_bool(raw.get("maximized"), defaults["maximized"]),
        "opacity": as_int(raw.get("opacity"), defaults["opacity"], minimum=0, maximum=100),
    }


def normalize_appearance(data: object) -> dict[str, Any]:
    raw = as_dict(data)
    defaults = schema.default_appearance()
    return {
        "display_mode": as_str_in(raw.get("display_mode"), schema.VALID_DISPLAY_MODES, defaults["display_mode"]),
        "ui_language": as_str_in(raw.get("ui_language"), schema.VALID_UI_LANGUAGES, defaults["ui_language"]),
        "mica_enabled": as_bool(raw.get("mica_enabled"), defaults["mica_enabled"]),
        "accent_color": as_nullable_str(raw.get("accent_color")),
        "follow_windows_accent": as_bool(raw.get("follow_windows_accent"), defaults["follow_windows_accent"]),
        "tinted_background": as_bool(raw.get("tinted_background"), defaults["tinted_background"]),
        "tinted_background_intensity": as_int(
            raw.get("tinted_background_intensity"),
            defaults["tinted_background_intensity"],
            minimum=0,
            maximum=30,
        ),
        "background_preset": as_str_in(raw.get("background_preset"), schema.VALID_BACKGROUND_PRESETS, defaults["background_preset"]),
        "rkn_background": as_nullable_str(raw.get("rkn_background")),
        "animations_enabled": as_bool(raw.get("animations_enabled"), defaults["animations_enabled"]),
        "smooth_scroll_enabled": as_bool(raw.get("smooth_scroll_enabled"), defaults["smooth_scroll_enabled"]),
        "editor_smooth_scroll_enabled": as_bool(raw.get("editor_smooth_scroll_enabled"), defaults["editor_smooth_scroll_enabled"]),
        "garland_enabled": as_bool(raw.get("garland_enabled"), defaults["garland_enabled"]),
        "snowflakes_enabled": as_bool(raw.get("snowflakes_enabled"), defaults["snowflakes_enabled"]),
        "selected_theme": as_clean_str(raw.get("selected_theme"), defaults["selected_theme"]),
    }


def normalize_warnings(data: object) -> dict[str, Any]:
    raw = as_dict(data)
    defaults = schema.default_warnings()
    return {
        "tray_hint_shown": as_bool(raw.get("tray_hint_shown"), defaults["tray_hint_shown"]),
        "disable_telega_warning": as_bool(raw.get("disable_telega_warning"), defaults["disable_telega_warning"]),
        "disable_kaspersky_warning": as_bool(raw.get("disable_kaspersky_warning"), defaults["disable_kaspersky_warning"]),
        "isp_dns_info_shown": as_bool(raw.get("isp_dns_info_shown"), defaults["isp_dns_info_shown"]),
        "tg_proxy_deeplink_done": as_bool(raw.get("tg_proxy_deeplink_done"), defaults["tg_proxy_deeplink_done"]),
    }


def normalize_telegram_proxy(data: object) -> dict[str, Any]:
    raw = as_dict(data)
    defaults = schema.default_telegram_proxy()
    return {
        "enabled": as_bool(raw.get("enabled"), defaults["enabled"]),
        "autostart": as_bool(raw.get("autostart"), defaults["autostart"]),
        "host": as_clean_str(raw.get("host"), defaults["host"]) or defaults["host"],
        "port": as_int(raw.get("port"), defaults["port"], minimum=1024, maximum=65535),
        "mode": as_str_in(raw.get("mode"), schema.VALID_TG_PROXY_MODES, defaults["mode"]),
        "upstream_enabled": as_bool(raw.get("upstream_enabled"), defaults["upstream_enabled"]),
        "upstream_host": as_clean_str(raw.get("upstream_host"), defaults["upstream_host"]),
        "upstream_port": as_int(
            raw.get("upstream_port"),
            defaults["upstream_port"],
            minimum=1,
            maximum=65535,
        ),
        "upstream_mode": as_str_in(
            raw.get("upstream_mode"),
            schema.VALID_TG_PROXY_UPSTREAM_MODES,
            defaults["upstream_mode"],
        ),
        "upstream_user": as_clean_str(raw.get("upstream_user"), defaults["upstream_user"]),
        "upstream_pass": as_str(raw.get("upstream_pass"), defaults["upstream_pass"]),
    }


def normalize_dns(data: object) -> dict[str, Any]:
    raw = as_dict(data)
    defaults = schema.default_dns()
    return {
        "force_dns_enabled": as_bool(raw.get("force_dns_enabled"), defaults["force_dns_enabled"]),
        "dns_crash_count": as_int(raw.get("dns_crash_count"), defaults["dns_crash_count"], minimum=0),
    }


def normalize_hosts(data: object) -> dict[str, Any]:
    raw = as_dict(data)
    return {
        "bootstrap_signature": as_nullable_str(raw.get("bootstrap_signature")),
        "active_domains": unique_str_list(raw.get("active_domains")),
    }


def normalize_ui_state(data: object) -> dict[str, Any]:
    raw = as_dict(data)
    tabs_raw = as_dict(raw.get("tcp_phase_tabs_by_target"))
    tabs: dict[str, str] = {}
    for target_key, phase_key in tabs_raw.items():
        target = normalize_target_key(target_key)
        phase = as_clean_str(phase_key).lower()
        if not target or not phase:
            continue
        tabs[target] = phase
    return {
        "tcp_phase_tabs_by_target": tabs,
    }


def normalize_orchestra_settings(data: object) -> dict[str, Any]:
    raw = as_dict(data)
    defaults = schema.default_orchestra_settings()
    return {
        "strict_detection": as_bool(raw.get("strict_detection"), defaults["strict_detection"]),
        "keep_debug_file": as_bool(raw.get("keep_debug_file"), defaults["keep_debug_file"]),
        "auto_restart_on_discord_fail": as_bool(
            raw.get("auto_restart_on_discord_fail"),
            defaults["auto_restart_on_discord_fail"],
        ),
        "discord_fails_for_restart": as_int(
            raw.get("discord_fails_for_restart"),
            defaults["discord_fails_for_restart"],
            minimum=1,
        ),
        "lock_successes": as_int(raw.get("lock_successes"), defaults["lock_successes"], minimum=1),
        "unlock_fails": as_int(raw.get("unlock_fails"), defaults["unlock_fails"], minimum=1),
    }


def normalize_orchestra_locked_maps(data: object) -> dict[str, dict[str, int]]:
    raw = as_dict(data)
    normalized: dict[str, dict[str, int]] = {}
    for askey in schema.ORCHESTRA_ASKEYS:
        source = as_dict(raw.get(askey))
        entries: dict[str, int] = {}
        for target_key, strategy in source.items():
            target = normalize_target_key(target_key)
            if not target:
                continue
            entries[target] = as_int(strategy, 0, minimum=0)
        normalized[askey] = entries
    return normalized


def normalize_orchestra_user_locked_maps(data: object) -> dict[str, list[str]]:
    raw = as_dict(data)
    normalized: dict[str, list[str]] = {}
    for askey in schema.ORCHESTRA_ASKEYS:
        values = unique_str_list(raw.get(askey))
        normalized[askey] = [normalize_target_key(item) for item in values if normalize_target_key(item)]
    return normalized


def normalize_orchestra_user_blocked_maps(data: object) -> dict[str, dict[str, list[int]]]:
    raw = as_dict(data)
    normalized: dict[str, dict[str, list[int]]] = {}
    for askey in schema.ORCHESTRA_ASKEYS:
        source = as_dict(raw.get(askey))
        entries: dict[str, list[int]] = {}
        for target_key, strategies in source.items():
            target = normalize_target_key(target_key)
            if not target:
                continue
            entries[target] = unique_int_list(strategies)
        normalized[askey] = entries
    return normalized


def normalize_orchestra_history(data: object) -> dict[str, Any]:
    raw = as_dict(data)
    normalized: dict[str, dict[str, dict[str, int]]] = {}
    for target_key, strategies in raw.items():
        target = normalize_target_key(target_key)
        if not target:
            continue
        strategies_raw = as_dict(strategies)
        strategies_out: dict[str, dict[str, int]] = {}
        for strategy_key, metrics in strategies_raw.items():
            strategy_name = as_clean_str(strategy_key)
            if not strategy_name:
                continue
            metrics_raw = as_dict(metrics)
            strategies_out[strategy_name] = {
                "successes": as_int(metrics_raw.get("successes"), 0, minimum=0),
                "failures": as_int(metrics_raw.get("failures"), 0, minimum=0),
            }
        normalized[target] = strategies_out
    return normalized


def normalize_orchestra(data: object) -> dict[str, Any]:
    raw = as_dict(data)
    whitelist_raw = as_dict(raw.get("whitelist"))
    return {
        "settings": normalize_orchestra_settings(raw.get("settings")),
        "whitelist": {
            "user_domains": [
                normalize_target_key(item)
                for item in unique_str_list(whitelist_raw.get("user_domains"))
                if normalize_target_key(item)
            ],
        },
        "locked": normalize_orchestra_locked_maps(raw.get("locked")),
        "user_locked": normalize_orchestra_user_locked_maps(raw.get("user_locked")),
        "user_blocked": normalize_orchestra_user_blocked_maps(raw.get("user_blocked")),
        "history": normalize_orchestra_history(raw.get("history")),
    }


def normalize_settings(data: object) -> dict[str, Any]:
    raw = as_dict(data)
    return {
        "version": schema.SETTINGS_VERSION,
        "program": normalize_program(raw.get("program")),
        "window": normalize_window(raw.get("window")),
        "appearance": normalize_appearance(raw.get("appearance")),
        "warnings": normalize_warnings(raw.get("warnings")),
        "telegram_proxy": normalize_telegram_proxy(raw.get("telegram_proxy")),
        "dns": normalize_dns(raw.get("dns")),
        "hosts": normalize_hosts(raw.get("hosts")),
        "ui_state": normalize_ui_state(raw.get("ui_state")),
        "orchestra": normalize_orchestra(raw.get("orchestra")),
    }
