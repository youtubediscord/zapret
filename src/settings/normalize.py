from __future__ import annotations

from ipaddress import IPv4Address, ip_address
from typing import Any

from settings import schema
from settings.mode import (
    SELECTED_SOURCE_PRESET_FILE_NAME_KEY_WINWS1,
    SELECTED_SOURCE_PRESET_FILE_NAME_KEY_WINWS2,
)


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


def normalize_hex_secret(value: object) -> str:
    text = as_clean_str(value).lower()
    if len(text) != 32:
        return ""
    if not all(ch in "0123456789abcdef" for ch in text):
        return ""
    return text


def normalize_domain(value: object) -> str:
    text = as_clean_str(value).strip(".").lower()
    if not text or len(text) > 253:
        return ""
    labels = text.split(".")
    if any(not label or len(label) > 63 for label in labels):
        return ""
    allowed = set("abcdefghijklmnopqrstuvwxyz0123456789-")
    for label in labels:
        if label.startswith("-") or label.endswith("-"):
            return ""
        if any(ch not in allowed for ch in label):
            return ""
    return text


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


def _is_valid_domain(value: str) -> bool:
    if not value or len(value) > 253:
        return False
    if value.startswith(".") or value.endswith("."):
        return False
    labels = value.split(".")
    if len(labels) < 2:
        return False
    for label in labels:
        if not label or len(label) > 63:
            return False
        if label[0] == "-" or label[-1] == "-":
            return False
        if not all(ch.isalnum() or ch == "-" for ch in label):
            return False
    return len(labels[-1]) >= 2 and any(ch.isalpha() for ch in labels[-1])


def unique_domain_list(value: object) -> list[str]:
    if isinstance(value, str):
        raw_items = value.replace(",", " ").replace(";", " ").split()
    elif isinstance(value, (list, tuple, set)):
        raw_items = []
        for item in value:
            if isinstance(item, str):
                raw_items.extend(item.replace(",", " ").replace(";", " ").split())
    else:
        raw_items = []
    result: list[str] = []
    seen: set[str] = set()
    for item in raw_items:
        domain = item.strip().lower()
        if domain in seen or not _is_valid_domain(domain):
            continue
        seen.add(domain)
        result.append(domain)
    return result


def unique_dc_ip_list(value: object) -> list[str]:
    if isinstance(value, str):
        raw_items = value.replace(",", " ").replace(";", " ").split()
    elif isinstance(value, (list, tuple, set)):
        raw_items = []
        for item in value:
            if isinstance(item, str):
                raw_items.extend(item.replace(",", " ").replace(";", " ").split())
    else:
        raw_items = []

    by_dc: dict[int, str] = {}
    order: list[int] = []
    for item in raw_items:
        text = item.strip()
        if ":" not in text:
            continue
        dc_text, ip_text = text.split(":", 1)
        try:
            dc = int(dc_text.strip())
            ip = str(IPv4Address(ip_text.strip()))
        except Exception:
            continue
        if dc not in {1, 2, 3, 4, 5, 203}:
            continue
        if dc not in by_dc:
            order.append(dc)
        by_dc[dc] = ip
    return [f"{dc}:{by_dc[dc]}" for dc in order]


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


def unique_ip_list(value: object) -> list[str]:
    if isinstance(value, str):
        raw_items = value.replace(",", " ").replace(";", " ").split()
    elif isinstance(value, (list, tuple, set)):
        raw_items = []
        for item in value:
            if isinstance(item, str):
                raw_items.extend(item.replace(",", " ").replace(";", " ").split())
            else:
                raw_items.append(str(item))
    else:
        raw_items = []

    result: list[str] = []
    seen: set[str] = set()
    for item in raw_items:
        try:
            normalized = str(ip_address(str(item).strip()))
        except Exception:
            continue
        if normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return result


def normalize_custom_dns_servers(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    result: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    seen_names: set[str] = set()
    for index, item in enumerate(value):
        raw = as_dict(item)
        server_id = as_clean_str(raw.get("id")) or f"custom-{index + 1}"
        name = as_clean_str(raw.get("name")) or "Свой DNS"
        ipv4 = [ip for ip in unique_ip_list(raw.get("ipv4")) if "." in ip]
        ipv6 = [ip for ip in unique_ip_list(raw.get("ipv6")) if ":" in ip]
        if not ipv4 and not ipv6:
            continue
        server_id_key = server_id.lower()
        name_key = name.lower()
        if server_id_key in seen_ids or name_key in seen_names:
            continue
        seen_ids.add(server_id_key)
        seen_names.add(name_key)
        result.append({
            "id": server_id,
            "name": name,
            "ipv4": ipv4,
            "ipv6": ipv6,
        })
    return result


def normalize_lookup_key(value: object) -> str:
    return as_clean_str(value).lower()


def normalize_askey(value: object) -> str:
    normalized = as_clean_str(value).lower()
    return normalized if normalized in schema.ORCHESTRA_ASKEYS else "tls"


def normalize_program(data: object) -> dict[str, Any]:
    raw = as_dict(data)
    defaults = schema.default_program()
    return {
        "dpi_autostart": as_bool(raw.get("dpi_autostart"), defaults["dpi_autostart"]),
        "gui_autostart_enabled": as_bool(raw.get("gui_autostart_enabled"), defaults["gui_autostart_enabled"]),
        "strategy_launch_method": as_str_in(raw.get("strategy_launch_method"), schema.VALID_LAUNCH_METHODS, defaults["strategy_launch_method"]),
        SELECTED_SOURCE_PRESET_FILE_NAME_KEY_WINWS1: as_clean_str(
            raw.get(SELECTED_SOURCE_PRESET_FILE_NAME_KEY_WINWS1),
            defaults[SELECTED_SOURCE_PRESET_FILE_NAME_KEY_WINWS1],
        ),
        SELECTED_SOURCE_PRESET_FILE_NAME_KEY_WINWS2: as_clean_str(
            raw.get(SELECTED_SOURCE_PRESET_FILE_NAME_KEY_WINWS2),
            defaults[SELECTED_SOURCE_PRESET_FILE_NAME_KEY_WINWS2],
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
        "tray_close_mode": as_str_in(
            raw.get("tray_close_mode"),
            schema.VALID_TRAY_CLOSE_MODES,
            defaults["tray_close_mode"],
        ),
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
            maximum=schema.MAX_TINTED_INTENSITY,
        ),
        "background_preset": as_str_in(raw.get("background_preset"), schema.VALID_BACKGROUND_PRESETS, defaults["background_preset"]),
        "rkn_background": as_nullable_str(raw.get("rkn_background")),
        "animations_enabled": as_bool(raw.get("animations_enabled"), defaults["animations_enabled"]),
        "smooth_scroll_enabled": as_bool(raw.get("smooth_scroll_enabled"), defaults["smooth_scroll_enabled"]),
        "editor_smooth_scroll_enabled": as_bool(raw.get("editor_smooth_scroll_enabled"), defaults["editor_smooth_scroll_enabled"]),
        "sidebar_icon_style": as_str_in(
            raw.get("sidebar_icon_style"),
            schema.VALID_SIDEBAR_ICON_STYLES,
            defaults["sidebar_icon_style"],
        ),
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
        "upstream_preset_id": as_clean_str(raw.get("upstream_preset_id"), defaults["upstream_preset_id"]),
        "upstream_mode": as_str_in(
            raw.get("upstream_mode"),
            schema.VALID_TG_PROXY_UPSTREAM_MODES,
            defaults["upstream_mode"],
        ),
        "upstream_udp_enabled": as_bool(
            raw.get("upstream_udp_enabled"),
            defaults["upstream_udp_enabled"],
        ),
        "upstream_user": as_clean_str(raw.get("upstream_user"), defaults["upstream_user"]),
        "upstream_pass": as_str(raw.get("upstream_pass"), defaults["upstream_pass"]),
        "cloudflare_enabled": as_bool(raw.get("cloudflare_enabled"), defaults["cloudflare_enabled"]),
        "cloudflare_domains": unique_domain_list(raw.get("cloudflare_domains")),
        "cloudflare_worker_enabled": as_bool(
            raw.get("cloudflare_worker_enabled"),
            defaults["cloudflare_worker_enabled"],
        ),
        "cloudflare_worker_domains": unique_domain_list(raw.get("cloudflare_worker_domains")),
        "mtproxy_secret": normalize_hex_secret(raw.get("mtproxy_secret")),
        "dc_ip": unique_dc_ip_list(raw.get("dc_ip")),
        "pool_size": as_int(raw.get("pool_size"), defaults["pool_size"], minimum=0, maximum=32),
        "buffer_kb": as_int(raw.get("buffer_kb"), defaults["buffer_kb"], minimum=4, maximum=4096),
        "fake_tls_domain": normalize_domain(raw.get("fake_tls_domain")),
        "proxy_protocol": as_bool(raw.get("proxy_protocol"), defaults["proxy_protocol"]),
    }


def normalize_dns(data: object) -> dict[str, Any]:
    raw = as_dict(data)
    defaults = schema.default_dns()
    return {
        "force_dns_enabled": as_bool(raw.get("force_dns_enabled"), defaults["force_dns_enabled"]),
        "dns_crash_count": as_int(raw.get("dns_crash_count"), defaults["dns_crash_count"], minimum=0),
        "custom_servers": normalize_custom_dns_servers(raw.get("custom_servers")),
    }


def normalize_hosts(data: object) -> dict[str, Any]:
    raw = as_dict(data)
    selection_raw = as_dict(raw.get("selection"))
    selection: dict[str, str] = {}
    for raw_service_name, raw_profile_name in selection_raw.items():
        service_name = as_clean_str(raw_service_name)
        profile_name = as_clean_str(raw_profile_name)
        if service_name and profile_name:
            selection[service_name] = profile_name
    return {
        "bootstrap_signature": as_nullable_str(raw.get("bootstrap_signature")),
        "active_domains": unique_str_list(raw.get("active_domains")),
        "selection": selection,
    }


def normalize_premium(data: object) -> dict[str, Any]:
    raw = as_dict(data)
    cache = raw.get("premium_cache")
    pair_code = as_clean_str(raw.get("pair_code")).upper()
    return {
        "device_id": as_clean_str(raw.get("device_id")),
        "device_token": as_nullable_str(raw.get("device_token")),
        "last_check": as_nullable_str(raw.get("last_check")),
        "last_network_failure_ts": as_nullable_int(raw.get("last_network_failure_ts")),
        "pair_code": pair_code or None,
        "pair_expires_at": as_nullable_int(raw.get("pair_expires_at")),
        "premium_cache": cache if isinstance(cache, dict) else None,
    }


def normalize_ui_state(data: object) -> dict[str, Any]:
    raw = as_dict(data)
    defaults = schema.default_ui_state()
    return {
        "sidebar_expanded": as_bool(raw.get("sidebar_expanded"), defaults["sidebar_expanded"]),
    }


def normalize_profile_strategy_state(data: object) -> dict[str, Any]:
    raw = as_dict(data)

    profiles: dict[str, Any] = {}
    raw_profiles = as_dict(raw.get("profiles"))
    for raw_profile_key, raw_profile_row in raw_profiles.items():
        profile_key = as_clean_str(raw_profile_key)
        if not (profile_key.startswith("name:") or profile_key.startswith("sig:")):
            continue
        profile_row = as_dict(raw_profile_row)
        raw_strategies = as_dict(profile_row.get("strategies"))
        strategies: dict[str, Any] = {}
        for raw_strategy_id, raw_strategy_row in raw_strategies.items():
            strategy_id = as_clean_str(raw_strategy_id)
            if not strategy_id or strategy_id in {"none", "custom"}:
                continue
            strategy_row = as_dict(raw_strategy_row)
            rating = as_clean_str(strategy_row.get("rating")).lower()
            if rating not in {"", "work", "notwork"}:
                rating = ""
            favorite = as_bool(strategy_row.get("favorite"), False)
            if not rating and not favorite:
                continue
            normalized_row: dict[str, Any] = {
                "favorite": favorite,
                "rating": rating,
            }
            updated_at = as_clean_str(strategy_row.get("updated_at"))
            if updated_at:
                normalized_row["updated_at"] = updated_at
            strategies[strategy_id] = normalized_row
        if strategies:
            profiles[profile_key] = {"strategies": strategies}

    return {
        "version": 1,
        "profiles": profiles,
    }


def normalize_user_profiles(data: object) -> dict[str, Any]:
    raw = as_dict(data)
    profiles: dict[str, Any] = {}
    for raw_profile_id, raw_profile in as_dict(raw.get("profiles")).items():
        profile_id = normalize_lookup_key(raw_profile_id)
        profile = as_dict(raw_profile)
        name = as_clean_str(profile.get("name"))
        protocol = as_clean_str(profile.get("protocol")).lower()
        ports = as_clean_str(profile.get("ports"))
        hostlist = as_clean_str(profile.get("hostlist"))
        ipset = as_clean_str(profile.get("ipset"))
        if not profile_id or not name or protocol not in {"tcp", "udp", "l7"} or not ports or not hostlist or not ipset:
            continue
        profiles[profile_id] = {
            "name": name,
            "protocol": protocol,
            "ports": ports,
            "hostlist": hostlist,
            "ipset": ipset,
        }
    return {
        "version": 1,
        "profiles": profiles,
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
        for lookup_key, strategy in source.items():
            target = normalize_lookup_key(lookup_key)
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
        normalized[askey] = [normalize_lookup_key(item) for item in values if normalize_lookup_key(item)]
    return normalized


def normalize_orchestra_user_blocked_maps(data: object) -> dict[str, dict[str, list[int]]]:
    raw = as_dict(data)
    normalized: dict[str, dict[str, list[int]]] = {}
    for askey in schema.ORCHESTRA_ASKEYS:
        source = as_dict(raw.get(askey))
        entries: dict[str, list[int]] = {}
        for lookup_key, strategies in source.items():
            target = normalize_lookup_key(lookup_key)
            if not target:
                continue
            entries[target] = unique_int_list(strategies)
        normalized[askey] = entries
    return normalized


def normalize_orchestra_history(data: object) -> dict[str, Any]:
    raw = as_dict(data)
    normalized: dict[str, dict[str, dict[str, int]]] = {}
    for lookup_key, strategies in raw.items():
        target = normalize_lookup_key(lookup_key)
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
                normalize_lookup_key(item)
                for item in unique_str_list(whitelist_raw.get("user_domains"))
                if normalize_lookup_key(item)
            ],
        },
        "locked": normalize_orchestra_locked_maps(raw.get("locked")),
        "user_locked": normalize_orchestra_user_locked_maps(raw.get("user_locked")),
        "user_blocked": normalize_orchestra_user_blocked_maps(raw.get("user_blocked")),
        "history": normalize_orchestra_history(raw.get("history")),
    }


def _json_safe(value: object) -> object:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {as_clean_str(key): _json_safe(item) for key, item in value.items() if as_clean_str(key)}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return as_str(value)


def normalize_updater(data: object) -> dict[str, Any]:
    raw = as_dict(data)
    defaults = schema.default_updater()

    server_pool_raw = as_dict(raw.get("server_pool"))
    release_manager_raw = as_dict(raw.get("release_manager"))

    return {
        "release_cache": as_dict(_json_safe(raw.get("release_cache"))),
        "rate_limit": as_dict(_json_safe(raw.get("rate_limit"))),
        "github_cache": {},
        "github_rate_limit_reset": as_nullable_int(raw.get("github_rate_limit_reset")),
        "server_pool": {
            "stats": as_dict(_json_safe(server_pool_raw.get("stats"))),
            "selected_server_id": as_nullable_str(server_pool_raw.get("selected_server_id")),
            "selected_at": as_nullable_int(server_pool_raw.get("selected_at")),
        },
        "release_manager": {
            "vps_block_until": as_int(
                release_manager_raw.get("vps_block_until"),
                defaults["release_manager"]["vps_block_until"],
                minimum=0,
            ),
            "server_stats": as_dict(_json_safe(release_manager_raw.get("server_stats"))),
        },
    }


def normalize_blockcheck_scan_resume(data: object) -> dict[str, Any]:
    raw = as_dict(data)
    domains: dict[str, dict[str, int]] = {}
    for raw_key, raw_value in as_dict(raw.get("domains")).items():
        key = as_clean_str(raw_key).lower()
        if not key:
            continue
        value_raw = as_dict(raw_value)
        domains[key] = {"next_index": as_int(value_raw.get("next_index"), 0, minimum=0)}
    return {"domains": domains}


def normalize_blockcheck(data: object) -> dict[str, Any]:
    raw = as_dict(data)
    return {
        "user_domains": [
            normalize_lookup_key(item)
            for item in unique_str_list(raw.get("user_domains"))
            if normalize_lookup_key(item)
        ],
        "scan_resume": normalize_blockcheck_scan_resume(raw.get("scan_resume")),
    }


def normalize_folders(data: object) -> dict[str, Any]:
    from folders.defaults import build_default_preset_folders, build_default_profile_folders
    from folders.store import normalize_folder_state

    raw = as_dict(data)
    raw_presets = as_dict(raw.get("presets"))
    return {
        "version": 1,
        "presets": {
            "winws2": normalize_folder_state(raw_presets.get("winws2"), build_default_preset_folders("winws2")),
            "winws1": normalize_folder_state(raw_presets.get("winws1"), build_default_preset_folders("winws1")),
        },
        "profiles": normalize_folder_state(raw.get("profiles"), build_default_profile_folders()),
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
        "premium": normalize_premium(raw.get("premium")),
        "ui_state": normalize_ui_state(raw.get("ui_state")),
        "profile_strategy_state": normalize_profile_strategy_state(raw.get("profile_strategy_state")),
        "user_profiles": normalize_user_profiles(raw.get("user_profiles")),
        "orchestra": normalize_orchestra(raw.get("orchestra")),
        "updater": normalize_updater(raw.get("updater")),
        "blockcheck": normalize_blockcheck(raw.get("blockcheck")),
        "folders": normalize_folders(raw.get("folders")),
    }
