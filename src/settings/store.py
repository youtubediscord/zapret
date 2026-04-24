from __future__ import annotations

import copy
import json
from pathlib import Path
from threading import RLock
from typing import Any

import winreg

from config.config import MAIN_DIRECTORY
from settings.normalize import (
    as_clean_str as _as_clean_str,
    as_dict as _as_dict,
    as_int as _as_int,
    normalize_askey as _normalize_askey,
    normalize_settings as _normalize_settings,
    normalize_target_key as _normalize_target_key,
    unique_int_list as _unique_int_list,
    unique_str_list as _unique_str_list,
)
from settings.schema import (
    DEFAULT_TG_PROXY_HOST as _DEFAULT_TG_PROXY_HOST,
    DEFAULT_TG_PROXY_PORT as _DEFAULT_TG_PROXY_PORT,
    DEFAULT_TG_PROXY_UPSTREAM_PORT as _DEFAULT_TG_PROXY_UPSTREAM_PORT,
    DEFAULT_TINTED_INTENSITY as _DEFAULT_TINTED_INTENSITY,
    DEFAULT_WINDOW_OPACITY as _DEFAULT_WINDOW_OPACITY,
    SETTINGS_DIR_NAME as _SETTINGS_DIR_NAME,
    SETTINGS_FILE_NAME as _SETTINGS_FILE_NAME,
    build_default_settings as _build_default_settings,
)
from utils.atomic_text import atomic_write_text

_SETTINGS_LOCK = RLock()
_DIRECT_PRESET_SELECTION_PATHS = {
    "winws1": ("program", "selected_source_preset_file_name_winws1"),
    "winws2": ("program", "selected_source_preset_file_name_winws2"),
}


def _settings_root() -> Path:
    base = str(MAIN_DIRECTORY or "").strip()
    if not base:
        raise RuntimeError("Не удалось определить папку программы для settings.json")
    return Path(base)


def get_settings_path() -> Path:
    return _settings_root() / _SETTINGS_DIR_NAME / _SETTINGS_FILE_NAME


def _format_settings_json(data: dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)


def _write_settings_file_locked(data: dict[str, Any]) -> None:
    normalized = _normalize_settings(data)
    path = get_settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(path, _format_settings_json(normalized), encoding="utf-8")


def _read_settings_file_locked(*, materialize: bool = True) -> dict[str, Any]:
    path = get_settings_path()
    defaults = _build_default_settings()
    if not path.exists():
        if materialize:
            _write_settings_file_locked(defaults)
        return defaults

    try:
        raw_text = path.read_text(encoding="utf-8")
        raw = json.loads(raw_text)
    except Exception:
        if materialize:
            _write_settings_file_locked(defaults)
        return defaults

    normalized = _normalize_settings(raw)
    should_rewrite = False
    if materialize:
        should_rewrite = _format_settings_json(normalized) != _format_settings_json(raw)
    if should_rewrite:
        _write_settings_file_locked(normalized)
    return normalized


def read_settings() -> dict[str, Any]:
    with _SETTINGS_LOCK:
        return copy.deepcopy(_read_settings_file_locked())


def materialize_settings_file() -> dict[str, Any]:
    """Гарантирует, что settings.json существует и содержит полный нормализованный JSON."""
    with _SETTINGS_LOCK:
        return copy.deepcopy(_read_settings_file_locked(materialize=True))


def reset_settings() -> dict[str, Any]:
    data = _build_default_settings()
    with _SETTINGS_LOCK:
        _write_settings_file_locked(data)
    return copy.deepcopy(data)


def _get_path_value(data: dict[str, Any], path: tuple[str, ...], default: Any = None) -> Any:
    current: Any = data
    for part in path:
        if not isinstance(current, dict) or part not in current:
            return default
        current = current[part]
    return current


def _set_path_value(data: dict[str, Any], path: tuple[str, ...], value: Any) -> None:
    current = data
    for part in path[:-1]:
        if not isinstance(current.get(part), dict):
            current[part] = {}
        current = current[part]
    current[path[-1]] = value


def _update_settings(mutator) -> dict[str, Any]:
    with _SETTINGS_LOCK:
        current = _read_settings_file_locked()
        working = copy.deepcopy(current)
        mutator(working)
        normalized = _normalize_settings(working)
        _write_settings_file_locked(normalized)
        return copy.deepcopy(normalized)


def _get_bool(path: tuple[str, ...], default: bool = False) -> bool:
    return bool(_get_path_value(read_settings(), path, default))


def _set_bool(path: tuple[str, ...], value: bool) -> bool:
    _update_settings(lambda data: _set_path_value(data, path, bool(value)))
    return True


def _get_int(path: tuple[str, ...], default: int = 0) -> int:
    return int(_get_path_value(read_settings(), path, default))


def _set_int(path: tuple[str, ...], value: int) -> bool:
    _update_settings(lambda data: _set_path_value(data, path, int(value)))
    return True


def _get_str(path: tuple[str, ...], default: str = "") -> str:
    return str(_get_path_value(read_settings(), path, default) or "")


def _set_str(path: tuple[str, ...], value: str) -> bool:
    _update_settings(lambda data: _set_path_value(data, path, str(value)))
    return True


def _get_nullable_str(path: tuple[str, ...]) -> str | None:
    value = _get_path_value(read_settings(), path, None)
    return value if isinstance(value, str) and value.strip() else None


def _set_nullable_str(path: tuple[str, ...], value: str | None) -> bool:
    _update_settings(lambda data: _set_path_value(data, path, None if value is None else str(value)))
    return True


def _direct_preset_selection_path(engine: str) -> tuple[str, ...]:
    normalized = _as_clean_str(engine).lower()
    if normalized not in _DIRECT_PRESET_SELECTION_PATHS:
        raise ValueError(f"Unsupported preset selection engine: {engine}")
    return _DIRECT_PRESET_SELECTION_PATHS[normalized]


def get_program_settings() -> dict[str, Any]:
    return copy.deepcopy(read_settings()["program"])


def set_program_settings(values: dict[str, Any]) -> dict[str, Any]:
    updated = _update_settings(lambda data: data["program"].update(_as_dict(values)))
    return copy.deepcopy(updated["program"])


def get_window_settings() -> dict[str, Any]:
    return copy.deepcopy(read_settings()["window"])


def set_window_settings(values: dict[str, Any]) -> dict[str, Any]:
    updated = _update_settings(lambda data: data["window"].update(_as_dict(values)))
    return copy.deepcopy(updated["window"])


def get_appearance_settings() -> dict[str, Any]:
    return copy.deepcopy(read_settings()["appearance"])


def set_appearance_settings(values: dict[str, Any]) -> dict[str, Any]:
    updated = _update_settings(lambda data: data["appearance"].update(_as_dict(values)))
    return copy.deepcopy(updated["appearance"])


def get_warnings_settings() -> dict[str, Any]:
    return copy.deepcopy(read_settings()["warnings"])


def set_warnings_settings(values: dict[str, Any]) -> dict[str, Any]:
    updated = _update_settings(lambda data: data["warnings"].update(_as_dict(values)))
    return copy.deepcopy(updated["warnings"])


def get_telegram_proxy_settings() -> dict[str, Any]:
    return copy.deepcopy(read_settings()["telegram_proxy"])


def set_telegram_proxy_settings(values: dict[str, Any]) -> dict[str, Any]:
    updated = _update_settings(lambda data: data["telegram_proxy"].update(_as_dict(values)))
    return copy.deepcopy(updated["telegram_proxy"])


def get_dns_settings() -> dict[str, Any]:
    return copy.deepcopy(read_settings()["dns"])


def set_dns_settings(values: dict[str, Any]) -> dict[str, Any]:
    updated = _update_settings(lambda data: data["dns"].update(_as_dict(values)))
    return copy.deepcopy(updated["dns"])


def get_hosts_settings() -> dict[str, Any]:
    return copy.deepcopy(read_settings()["hosts"])


def set_hosts_settings(values: dict[str, Any]) -> dict[str, Any]:
    updated = _update_settings(lambda data: data["hosts"].update(_as_dict(values)))
    return copy.deepcopy(updated["hosts"])


def get_ui_state_settings() -> dict[str, Any]:
    return copy.deepcopy(read_settings()["ui_state"])


def set_ui_state_settings(values: dict[str, Any]) -> dict[str, Any]:
    updated = _update_settings(lambda data: data["ui_state"].update(_as_dict(values)))
    return copy.deepcopy(updated["ui_state"])


def get_orchestra_settings() -> dict[str, Any]:
    return copy.deepcopy(read_settings()["orchestra"]["settings"])


def set_orchestra_settings(values: dict[str, Any]) -> dict[str, Any]:
    updated = _update_settings(lambda data: data["orchestra"]["settings"].update(_as_dict(values)))
    return copy.deepcopy(updated["orchestra"]["settings"])


def get_dpi_autostart() -> bool:
    return _get_bool(("program", "dpi_autostart"), True)


def set_dpi_autostart(value: bool) -> bool:
    return _set_bool(("program", "dpi_autostart"), value)


def get_strategy_launch_method() -> str:
    return _get_str(("program", "strategy_launch_method"), "direct_zapret2")


def set_strategy_launch_method(value: str) -> bool:
    return _set_str(("program", "strategy_launch_method"), value)


def get_direct_ui_mode() -> str:
    return _get_str(("program", "direct_ui_mode"), "basic")


def set_direct_ui_mode(value: str) -> bool:
    return _set_str(("program", "direct_ui_mode"), value)


def get_selected_source_preset_file_name(engine: str) -> str | None:
    value = _get_str(_direct_preset_selection_path(engine), "")
    return value or None


def set_selected_source_preset_file_name(engine: str, value: str | None) -> bool:
    normalized = _as_clean_str(value)
    return _set_str(_direct_preset_selection_path(engine), normalized)


def clear_selected_source_preset_file_name(engine: str) -> bool:
    return _set_str(_direct_preset_selection_path(engine), "")


def get_auto_update_enabled() -> bool:
    return _get_bool(("program", "auto_update_enabled"), True)


def set_auto_update_enabled(value: bool) -> bool:
    return _set_bool(("program", "auto_update_enabled"), value)


def get_remove_github_api() -> bool:
    return _get_bool(("program", "remove_github_api"), True)


def set_remove_github_api(value: bool) -> bool:
    return _set_bool(("program", "remove_github_api"), value)


def get_discord_restart_enabled() -> bool:
    return _get_bool(("program", "discord_auto_restart"), True)


def set_discord_restart_enabled(value: bool) -> bool:
    return _set_bool(("program", "discord_auto_restart"), value)


def get_max_blocked() -> bool:
    return _get_bool(("program", "max_blocked"), False)


def set_max_blocked(value: bool) -> bool:
    return _set_bool(("program", "max_blocked"), value)


def set_defender_disabled_memory(value: bool) -> bool:
    return _set_bool(("program", "defender_disabled"), value)


def get_window_geometry() -> dict[str, Any]:
    return copy.deepcopy(
        {
            "x": _get_path_value(read_settings(), ("window", "x"), None),
            "y": _get_path_value(read_settings(), ("window", "y"), None),
            "width": _get_path_value(read_settings(), ("window", "width"), None),
            "height": _get_path_value(read_settings(), ("window", "height"), None),
            "maximized": _get_bool(("window", "maximized"), False),
        }
    )


def set_window_geometry(*, x: int | None, y: int | None, width: int | None, height: int | None, maximized: bool) -> bool:
    _update_settings(
        lambda data: data["window"].update(
            {
                "x": x,
                "y": y,
                "width": width,
                "height": height,
                "maximized": bool(maximized),
            }
        )
    )
    return True


def get_window_opacity() -> int:
    return _get_int(("window", "opacity"), _DEFAULT_WINDOW_OPACITY)


def set_window_opacity(value: int) -> bool:
    return _set_int(("window", "opacity"), value)


def get_display_mode() -> str:
    return _get_str(("appearance", "display_mode"), "dark")


def set_display_mode(value: str) -> bool:
    return _set_str(("appearance", "display_mode"), value)


def get_ui_language() -> str:
    return _get_str(("appearance", "ui_language"), "ru")


def set_ui_language(value: str) -> bool:
    return _set_str(("appearance", "ui_language"), value)


def get_mica_enabled() -> bool:
    return _get_bool(("appearance", "mica_enabled"), True)


def set_mica_enabled(value: bool) -> bool:
    return _set_bool(("appearance", "mica_enabled"), value)


def get_background_preset() -> str:
    return _get_str(("appearance", "background_preset"), "standard")


def set_background_preset(value: str) -> bool:
    return _set_str(("appearance", "background_preset"), value)


def get_rkn_background() -> str | None:
    return _get_nullable_str(("appearance", "rkn_background"))


def set_rkn_background(value: str | None) -> bool:
    return _set_nullable_str(("appearance", "rkn_background"), value)


def get_animations_enabled() -> bool:
    return _get_bool(("appearance", "animations_enabled"), False)


def set_animations_enabled(value: bool) -> bool:
    return _set_bool(("appearance", "animations_enabled"), value)


def get_smooth_scroll_enabled() -> bool:
    return _get_bool(("appearance", "smooth_scroll_enabled"), False)


def set_smooth_scroll_enabled(value: bool) -> bool:
    return _set_bool(("appearance", "smooth_scroll_enabled"), value)


def get_editor_smooth_scroll_enabled() -> bool:
    return _get_bool(("appearance", "editor_smooth_scroll_enabled"), False)


def set_editor_smooth_scroll_enabled(value: bool) -> bool:
    return _set_bool(("appearance", "editor_smooth_scroll_enabled"), value)


def get_accent_color() -> str | None:
    return _get_nullable_str(("appearance", "accent_color"))


def set_accent_color(value: str | None) -> bool:
    return _set_nullable_str(("appearance", "accent_color"), value)


def get_follow_windows_accent() -> bool:
    return _get_bool(("appearance", "follow_windows_accent"), False)


def set_follow_windows_accent(value: bool) -> bool:
    return _set_bool(("appearance", "follow_windows_accent"), value)


def get_tinted_background() -> bool:
    return _get_bool(("appearance", "tinted_background"), False)


def set_tinted_background(value: bool) -> bool:
    return _set_bool(("appearance", "tinted_background"), value)


def get_tinted_background_intensity() -> int:
    return _get_int(("appearance", "tinted_background_intensity"), _DEFAULT_TINTED_INTENSITY)


def set_tinted_background_intensity(value: int) -> bool:
    return _set_int(("appearance", "tinted_background_intensity"), value)


def get_garland_enabled() -> bool:
    return _get_bool(("appearance", "garland_enabled"), False)


def set_garland_enabled(value: bool) -> bool:
    return _set_bool(("appearance", "garland_enabled"), value)


def get_snowflakes_enabled() -> bool:
    return _get_bool(("appearance", "snowflakes_enabled"), False)


def set_snowflakes_enabled(value: bool) -> bool:
    return _set_bool(("appearance", "snowflakes_enabled"), value)


def get_selected_theme() -> str:
    return _get_str(("appearance", "selected_theme"), "")


def set_selected_theme(value: str) -> bool:
    return _set_str(("appearance", "selected_theme"), value)


def get_windows_system_accent() -> str | None:
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\Accent",
            0,
            winreg.KEY_READ,
        ) as key:
            value, _ = winreg.QueryValueEx(key, "AccentColorMenu")
            r = value & 0xFF
            g = (value >> 8) & 0xFF
            b = (value >> 16) & 0xFF
            return f"#{r:02x}{g:02x}{b:02x}"
    except Exception:
        return None


def get_tray_hint_shown() -> bool:
    return _get_bool(("warnings", "tray_hint_shown"), False)


def set_tray_hint_shown(value: bool = True) -> bool:
    return _set_bool(("warnings", "tray_hint_shown"), value)


def get_telega_warning_disabled() -> bool:
    return _get_bool(("warnings", "disable_telega_warning"), False)


def set_telega_warning_disabled(value: bool) -> bool:
    return _set_bool(("warnings", "disable_telega_warning"), value)


def get_kaspersky_warning_disabled() -> bool:
    return _get_bool(("warnings", "disable_kaspersky_warning"), False)


def set_kaspersky_warning_disabled(value: bool) -> bool:
    return _set_bool(("warnings", "disable_kaspersky_warning"), value)


def get_isp_dns_info_shown() -> bool:
    return _get_bool(("warnings", "isp_dns_info_shown"), False)


def set_isp_dns_info_shown(value: bool) -> bool:
    return _set_bool(("warnings", "isp_dns_info_shown"), value)


def get_tg_proxy_deeplink_done() -> bool:
    return _get_bool(("warnings", "tg_proxy_deeplink_done"), False)


def set_tg_proxy_deeplink_done(value: bool) -> bool:
    return _set_bool(("warnings", "tg_proxy_deeplink_done"), value)


def get_tcp_phase_tabs_by_target() -> dict[str, str]:
    data = _get_path_value(read_settings(), ("ui_state", "tcp_phase_tabs_by_target"), {})
    return copy.deepcopy(data if isinstance(data, dict) else {})


def set_tcp_phase_tabs_by_target(data: dict[str, str]) -> bool:
    _update_settings(lambda settings: _set_path_value(settings, ("ui_state", "tcp_phase_tabs_by_target"), _as_dict(data)))
    return True


def get_last_tcp_phase_tab(target_key: str) -> str | None:
    key = _normalize_target_key(target_key)
    if not key:
        return None
    return get_tcp_phase_tabs_by_target().get(key)


def set_last_tcp_phase_tab(target_key: str, phase_key: str) -> bool:
    target = _normalize_target_key(target_key)
    phase = _as_clean_str(phase_key).lower()
    if not target or not phase:
        return False

    def _mutator(data: dict[str, Any]) -> None:
        tabs = _as_dict(_get_path_value(data, ("ui_state", "tcp_phase_tabs_by_target"), {}))
        tabs[target] = phase
        _set_path_value(data, ("ui_state", "tcp_phase_tabs_by_target"), tabs)

    _update_settings(_mutator)
    return True


def get_force_dns_enabled() -> bool:
    return _get_bool(("dns", "force_dns_enabled"), True)


def set_force_dns_enabled(value: bool) -> bool:
    return _set_bool(("dns", "force_dns_enabled"), value)


def get_dns_crash_count() -> int:
    return _get_int(("dns", "dns_crash_count"), 0)


def set_dns_crash_count(value: int) -> bool:
    return _set_int(("dns", "dns_crash_count"), value)


def increment_dns_crash_count() -> int:
    updated = _update_settings(
        lambda data: _set_path_value(
            data,
            ("dns", "dns_crash_count"),
            _as_int(_get_path_value(data, ("dns", "dns_crash_count"), 0), 0, minimum=0) + 1,
        )
    )
    return int(updated["dns"]["dns_crash_count"])


def reset_dns_crash_count() -> bool:
    return _set_int(("dns", "dns_crash_count"), 0)


def get_hosts_bootstrap_signature() -> str | None:
    return _get_nullable_str(("hosts", "bootstrap_signature"))


def set_hosts_bootstrap_signature(value: str | None) -> bool:
    return _set_nullable_str(("hosts", "bootstrap_signature"), value)


def get_active_hosts_domains() -> set[str]:
    items = _get_path_value(read_settings(), ("hosts", "active_domains"), [])
    if not isinstance(items, list):
        return set()
    return set(_unique_str_list(items))


def set_active_hosts_domains(domains: set[str] | list[str]) -> bool:
    normalized = _unique_str_list(list(domains) if isinstance(domains, set) else domains)
    _update_settings(lambda data: _set_path_value(data, ("hosts", "active_domains"), normalized))
    return True


def add_active_hosts_domain(domain: str) -> bool:
    domains = get_active_hosts_domains()
    item = _as_clean_str(domain)
    if item:
        domains.add(item)
    return set_active_hosts_domains(domains)


def remove_active_hosts_domain(domain: str) -> bool:
    domains = get_active_hosts_domains()
    domains.discard(_as_clean_str(domain))
    return set_active_hosts_domains(domains)


def clear_active_hosts_domains() -> bool:
    return set_active_hosts_domains(set())


def get_tg_proxy_enabled() -> bool:
    return _get_bool(("telegram_proxy", "enabled"), False)


def set_tg_proxy_enabled(value: bool) -> bool:
    return _set_bool(("telegram_proxy", "enabled"), value)


def get_tg_proxy_autostart() -> bool:
    return _get_bool(("telegram_proxy", "autostart"), True)


def set_tg_proxy_autostart(value: bool) -> bool:
    return _set_bool(("telegram_proxy", "autostart"), value)


def get_tg_proxy_host() -> str:
    return _get_str(("telegram_proxy", "host"), _DEFAULT_TG_PROXY_HOST)


def set_tg_proxy_host(value: str) -> bool:
    return _set_str(("telegram_proxy", "host"), value)


def get_tg_proxy_port() -> int:
    return _get_int(("telegram_proxy", "port"), _DEFAULT_TG_PROXY_PORT)


def set_tg_proxy_port(value: int) -> bool:
    return _set_int(("telegram_proxy", "port"), value)


def get_tg_proxy_mode() -> str:
    return _get_str(("telegram_proxy", "mode"), "socks5")


def set_tg_proxy_mode(value: str) -> bool:
    return _set_str(("telegram_proxy", "mode"), value)


def get_tg_proxy_upstream_enabled() -> bool:
    return _get_bool(("telegram_proxy", "upstream_enabled"), False)


def set_tg_proxy_upstream_enabled(value: bool) -> bool:
    return _set_bool(("telegram_proxy", "upstream_enabled"), value)


def get_tg_proxy_upstream_host() -> str:
    return _get_str(("telegram_proxy", "upstream_host"), "")


def set_tg_proxy_upstream_host(value: str) -> bool:
    return _set_str(("telegram_proxy", "upstream_host"), value)


def get_tg_proxy_upstream_port() -> int:
    return _get_int(("telegram_proxy", "upstream_port"), _DEFAULT_TG_PROXY_UPSTREAM_PORT)


def set_tg_proxy_upstream_port(value: int) -> bool:
    return _set_int(("telegram_proxy", "upstream_port"), value)


def get_tg_proxy_upstream_mode() -> str:
    return _get_str(("telegram_proxy", "upstream_mode"), "fallback")


def set_tg_proxy_upstream_mode(value: str) -> bool:
    return _set_str(("telegram_proxy", "upstream_mode"), value)


def get_tg_proxy_upstream_user() -> str:
    return _get_str(("telegram_proxy", "upstream_user"), "")


def set_tg_proxy_upstream_user(value: str) -> bool:
    return _set_str(("telegram_proxy", "upstream_user"), value)


def get_tg_proxy_upstream_pass() -> str:
    return _get_str(("telegram_proxy", "upstream_pass"), "")


def set_tg_proxy_upstream_pass(value: str) -> bool:
    return _set_str(("telegram_proxy", "upstream_pass"), value)


def get_orchestra_strict_detection() -> bool:
    return _get_bool(("orchestra", "settings", "strict_detection"), True)


def set_orchestra_strict_detection(value: bool) -> bool:
    return _set_bool(("orchestra", "settings", "strict_detection"), value)


def get_orchestra_keep_debug_file() -> bool:
    return _get_bool(("orchestra", "settings", "keep_debug_file"), False)


def set_orchestra_keep_debug_file(value: bool) -> bool:
    return _set_bool(("orchestra", "settings", "keep_debug_file"), value)


def get_orchestra_auto_restart_on_discord_fail() -> bool:
    return _get_bool(("orchestra", "settings", "auto_restart_on_discord_fail"), True)


def set_orchestra_auto_restart_on_discord_fail(value: bool) -> bool:
    return _set_bool(("orchestra", "settings", "auto_restart_on_discord_fail"), value)


def get_orchestra_discord_fails_for_restart() -> int:
    return _get_int(("orchestra", "settings", "discord_fails_for_restart"), 3)


def set_orchestra_discord_fails_for_restart(value: int) -> bool:
    return _set_int(("orchestra", "settings", "discord_fails_for_restart"), value)


def get_orchestra_lock_successes() -> int:
    return _get_int(("orchestra", "settings", "lock_successes"), 3)


def set_orchestra_lock_successes(value: int) -> bool:
    return _set_int(("orchestra", "settings", "lock_successes"), value)


def get_orchestra_unlock_fails() -> int:
    return _get_int(("orchestra", "settings", "unlock_fails"), 3)


def set_orchestra_unlock_fails(value: int) -> bool:
    return _set_int(("orchestra", "settings", "unlock_fails"), value)


def get_orchestra_whitelist_user_domains() -> list[str]:
    values = _get_path_value(read_settings(), ("orchestra", "whitelist", "user_domains"), [])
    return _unique_str_list(values)


def set_orchestra_whitelist_user_domains(domains: list[str]) -> bool:
    normalized = [_normalize_target_key(item) for item in _unique_str_list(domains) if _normalize_target_key(item)]
    _update_settings(lambda data: _set_path_value(data, ("orchestra", "whitelist", "user_domains"), normalized))
    return True


def add_orchestra_whitelist_domain(domain: str) -> bool:
    items = get_orchestra_whitelist_user_domains()
    value = _normalize_target_key(domain)
    if value and value not in items:
        items.append(value)
    return set_orchestra_whitelist_user_domains(items)


def remove_orchestra_whitelist_domain(domain: str) -> bool:
    value = _normalize_target_key(domain)
    items = [item for item in get_orchestra_whitelist_user_domains() if item != value]
    return set_orchestra_whitelist_user_domains(items)


def clear_orchestra_whitelist_user_domains() -> bool:
    return set_orchestra_whitelist_user_domains([])


def get_orchestra_locked_map(askey: str) -> dict[str, int]:
    key = _normalize_askey(askey)
    data = _get_path_value(read_settings(), ("orchestra", "locked", key), {})
    return copy.deepcopy(data if isinstance(data, dict) else {})


def set_orchestra_locked_map(askey: str, data: dict[str, int]) -> bool:
    key = _normalize_askey(askey)
    _update_settings(lambda settings: _set_path_value(settings, ("orchestra", "locked", key), _as_dict(data)))
    return True


def set_orchestra_locked_strategy(askey: str, target: str, strategy: int) -> bool:
    key = _normalize_askey(askey)
    target_key = _normalize_target_key(target)
    if not target_key:
        return False

    def _mutator(data: dict[str, Any]) -> None:
        mapping = _as_dict(_get_path_value(data, ("orchestra", "locked", key), {}))
        mapping[target_key] = int(strategy)
        _set_path_value(data, ("orchestra", "locked", key), mapping)

    _update_settings(_mutator)
    return True


def remove_orchestra_locked_target(askey: str, target: str) -> bool:
    key = _normalize_askey(askey)
    target_key = _normalize_target_key(target)

    def _mutator(data: dict[str, Any]) -> None:
        mapping = _as_dict(_get_path_value(data, ("orchestra", "locked", key), {}))
        mapping.pop(target_key, None)
        _set_path_value(data, ("orchestra", "locked", key), mapping)

    _update_settings(_mutator)
    return True


def clear_orchestra_locked_map(askey: str) -> bool:
    return set_orchestra_locked_map(askey, {})


def get_orchestra_user_locked(askey: str) -> list[str]:
    key = _normalize_askey(askey)
    values = _get_path_value(read_settings(), ("orchestra", "user_locked", key), [])
    return [_normalize_target_key(item) for item in _unique_str_list(values) if _normalize_target_key(item)]


def set_orchestra_user_locked(askey: str, values: list[str]) -> bool:
    key = _normalize_askey(askey)
    normalized = [_normalize_target_key(item) for item in _unique_str_list(values) if _normalize_target_key(item)]
    _update_settings(lambda data: _set_path_value(data, ("orchestra", "user_locked", key), normalized))
    return True


def add_orchestra_user_locked(askey: str, target: str) -> bool:
    items = get_orchestra_user_locked(askey)
    value = _normalize_target_key(target)
    if value and value not in items:
        items.append(value)
    return set_orchestra_user_locked(askey, items)


def remove_orchestra_user_locked(askey: str, target: str) -> bool:
    value = _normalize_target_key(target)
    items = [item for item in get_orchestra_user_locked(askey) if item != value]
    return set_orchestra_user_locked(askey, items)


def clear_orchestra_user_locked(askey: str) -> bool:
    return set_orchestra_user_locked(askey, [])


def get_orchestra_user_blocked(askey: str) -> dict[str, list[int]]:
    key = _normalize_askey(askey)
    data = _get_path_value(read_settings(), ("orchestra", "user_blocked", key), {})
    return copy.deepcopy(data if isinstance(data, dict) else {})


def set_orchestra_user_blocked(askey: str, data: dict[str, list[int]]) -> bool:
    key = _normalize_askey(askey)
    _update_settings(lambda settings: _set_path_value(settings, ("orchestra", "user_blocked", key), _as_dict(data)))
    return True


def set_orchestra_user_blocked_strategies(askey: str, target: str, strategies: list[int]) -> bool:
    key = _normalize_askey(askey)
    target_key = _normalize_target_key(target)
    if not target_key:
        return False

    def _mutator(data: dict[str, Any]) -> None:
        mapping = _as_dict(_get_path_value(data, ("orchestra", "user_blocked", key), {}))
        normalized = _unique_int_list(strategies)
        if normalized:
            mapping[target_key] = normalized
        else:
            mapping.pop(target_key, None)
        _set_path_value(data, ("orchestra", "user_blocked", key), mapping)

    _update_settings(_mutator)
    return True


def remove_orchestra_user_blocked_target(askey: str, target: str) -> bool:
    key = _normalize_askey(askey)
    target_key = _normalize_target_key(target)

    def _mutator(data: dict[str, Any]) -> None:
        mapping = _as_dict(_get_path_value(data, ("orchestra", "user_blocked", key), {}))
        mapping.pop(target_key, None)
        _set_path_value(data, ("orchestra", "user_blocked", key), mapping)

    _update_settings(_mutator)
    return True


def clear_orchestra_user_blocked(askey: str) -> bool:
    return set_orchestra_user_blocked(askey, {})


def get_orchestra_history() -> dict[str, Any]:
    data = _get_path_value(read_settings(), ("orchestra", "history"), {})
    return copy.deepcopy(data if isinstance(data, dict) else {})


def set_orchestra_history(data: dict[str, Any]) -> bool:
    _update_settings(lambda settings: _set_path_value(settings, ("orchestra", "history"), _as_dict(data)))
    return True


def get_orchestra_history_for_target(target: str) -> dict[str, Any]:
    target_key = _normalize_target_key(target)
    return copy.deepcopy(get_orchestra_history().get(target_key, {}))


def set_orchestra_history_for_target(target: str, data: dict[str, Any]) -> bool:
    target_key = _normalize_target_key(target)
    if not target_key:
        return False

    def _mutator(settings: dict[str, Any]) -> None:
        history = _as_dict(_get_path_value(settings, ("orchestra", "history"), {}))
        history[target_key] = _as_dict(data)
        _set_path_value(settings, ("orchestra", "history"), history)

    _update_settings(_mutator)
    return True


def remove_orchestra_history_target(target: str) -> bool:
    target_key = _normalize_target_key(target)

    def _mutator(settings: dict[str, Any]) -> None:
        history = _as_dict(_get_path_value(settings, ("orchestra", "history"), {}))
        history.pop(target_key, None)
        _set_path_value(settings, ("orchestra", "history"), history)

    _update_settings(_mutator)
    return True


def clear_orchestra_history() -> bool:
    return set_orchestra_history({})


__all__ = [
    "get_accent_color",
    "get_active_hosts_domains",
    "get_animations_enabled",
    "get_auto_update_enabled",
    "get_background_preset",
    "get_direct_ui_mode",
    "get_discord_restart_enabled",
    "get_display_mode",
    "get_dns_crash_count",
    "get_dpi_autostart",
    "get_editor_smooth_scroll_enabled",
    "get_follow_windows_accent",
    "get_force_dns_enabled",
    "get_garland_enabled",
    "get_hosts_bootstrap_signature",
    "get_isp_dns_info_shown",
    "get_kaspersky_warning_disabled",
    "get_last_tcp_phase_tab",
    "get_max_blocked",
    "get_mica_enabled",
    "get_orchestra_auto_restart_on_discord_fail",
    "get_orchestra_discord_fails_for_restart",
    "get_orchestra_history",
    "get_orchestra_history_for_target",
    "get_orchestra_keep_debug_file",
    "get_orchestra_lock_successes",
    "get_orchestra_locked_map",
    "get_orchestra_settings",
    "get_orchestra_strict_detection",
    "get_orchestra_unlock_fails",
    "get_orchestra_user_blocked",
    "get_orchestra_user_locked",
    "get_orchestra_whitelist_user_domains",
    "get_program_settings",
    "get_remove_github_api",
    "get_rkn_background",
    "get_selected_theme",
    "get_selected_source_preset_file_name",
    "get_settings_path",
    "get_smooth_scroll_enabled",
    "get_snowflakes_enabled",
    "get_strategy_launch_method",
    "get_tcp_phase_tabs_by_target",
    "get_telega_warning_disabled",
    "get_tg_proxy_autostart",
    "get_tg_proxy_deeplink_done",
    "get_tg_proxy_enabled",
    "get_tg_proxy_host",
    "get_tg_proxy_mode",
    "get_tg_proxy_port",
    "get_tg_proxy_upstream_enabled",
    "get_tg_proxy_upstream_host",
    "get_tg_proxy_upstream_mode",
    "get_tg_proxy_upstream_pass",
    "get_tg_proxy_upstream_port",
    "get_tg_proxy_upstream_user",
    "get_tinted_background",
    "get_tinted_background_intensity",
    "get_tray_hint_shown",
    "get_ui_language",
    "get_window_geometry",
    "get_window_opacity",
    "get_windows_system_accent",
    "increment_dns_crash_count",
    "materialize_settings_file",
    "read_settings",
    "remove_active_hosts_domain",
    "remove_orchestra_history_target",
    "remove_orchestra_locked_target",
    "remove_orchestra_user_blocked_target",
    "remove_orchestra_user_locked",
    "remove_orchestra_whitelist_domain",
    "reset_dns_crash_count",
    "reset_settings",
    "set_accent_color",
    "set_active_hosts_domains",
    "set_animations_enabled",
    "set_auto_update_enabled",
    "set_background_preset",
    "set_defender_disabled_memory",
    "set_direct_ui_mode",
    "set_discord_restart_enabled",
    "set_display_mode",
    "set_dns_crash_count",
    "set_dpi_autostart",
    "set_editor_smooth_scroll_enabled",
    "set_follow_windows_accent",
    "set_force_dns_enabled",
    "set_garland_enabled",
    "set_hosts_bootstrap_signature",
    "set_isp_dns_info_shown",
    "set_kaspersky_warning_disabled",
    "set_last_tcp_phase_tab",
    "set_max_blocked",
    "set_mica_enabled",
    "set_orchestra_auto_restart_on_discord_fail",
    "set_orchestra_discord_fails_for_restart",
    "set_orchestra_history",
    "set_orchestra_history_for_target",
    "set_orchestra_keep_debug_file",
    "set_orchestra_lock_successes",
    "set_orchestra_locked_map",
    "set_orchestra_locked_strategy",
    "set_orchestra_settings",
    "set_orchestra_strict_detection",
    "set_orchestra_unlock_fails",
    "set_orchestra_user_blocked",
    "set_orchestra_user_blocked_strategies",
    "set_orchestra_user_locked",
    "set_orchestra_whitelist_user_domains",
    "set_program_settings",
    "set_remove_github_api",
    "set_rkn_background",
    "set_selected_theme",
    "set_selected_source_preset_file_name",
    "set_smooth_scroll_enabled",
    "set_snowflakes_enabled",
    "set_strategy_launch_method",
    "set_tcp_phase_tabs_by_target",
    "set_telega_warning_disabled",
    "set_tg_proxy_autostart",
    "set_tg_proxy_deeplink_done",
    "set_tg_proxy_enabled",
    "set_tg_proxy_host",
    "set_tg_proxy_mode",
    "set_tg_proxy_port",
    "set_tg_proxy_upstream_enabled",
    "set_tg_proxy_upstream_host",
    "set_tg_proxy_upstream_mode",
    "set_tg_proxy_upstream_pass",
    "set_tg_proxy_upstream_port",
    "set_tg_proxy_upstream_user",
    "set_tinted_background",
    "set_tinted_background_intensity",
    "set_tray_hint_shown",
    "set_ui_language",
    "set_window_geometry",
    "set_window_opacity",
    "clear_selected_source_preset_file_name",
]
