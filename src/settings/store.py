from __future__ import annotations

import copy
import json
from pathlib import Path
from threading import RLock
from typing import Any

try:
    import winreg
except ImportError:  # pragma: no cover - WSL/static checks only
    winreg = None

from config.config import MAIN_DIRECTORY
from settings.mode import (
    DEFAULT_LAUNCH_METHOD,
    ENGINE_WINWS1,
    ENGINE_WINWS2,
    SELECTED_SOURCE_PRESET_FILE_NAME_KEY_WINWS1,
    SELECTED_SOURCE_PRESET_FILE_NAME_KEY_WINWS2,
    normalize_launch_method,
)
from settings.normalize import (
    as_clean_str as _as_clean_str,
    as_dict as _as_dict,
    as_int as _as_int,
    normalize_askey as _normalize_askey,
    normalize_hex_secret as _normalize_hex_secret,
    normalize_settings as _normalize_settings,
    normalize_lookup_key as _normalize_lookup_key,
    unique_dc_ip_list as _unique_dc_ip_list,
    unique_domain_list as _unique_domain_list,
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
_SETTINGS_CACHE: dict[str, Any] | None = None
_SETTINGS_CACHE_SIGNATURE: tuple[str, int | None, int | None] | None = None
_DIRECT_PRESET_SELECTION_PATHS = {
    ENGINE_WINWS1: ("program", SELECTED_SOURCE_PRESET_FILE_NAME_KEY_WINWS1),
    ENGINE_WINWS2: ("program", SELECTED_SOURCE_PRESET_FILE_NAME_KEY_WINWS2),
}


def _settings_root() -> Path:
    base = str(MAIN_DIRECTORY or "").strip()
    if not base:
        raise RuntimeError("Не удалось определить папку программы для settings.json")
    return Path(base)


def get_settings_path() -> Path:
    return _settings_root() / _SETTINGS_DIR_NAME / _SETTINGS_FILE_NAME


def _settings_file_signature(path: Path | None = None) -> tuple[str, int | None, int | None]:
    resolved = path or get_settings_path()
    try:
        stat = resolved.stat()
        return (str(resolved), int(stat.st_mtime_ns), int(stat.st_size))
    except OSError:
        return (str(resolved), None, None)


def _format_settings_json(data: dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)


def _write_settings_file_locked(data: dict[str, Any]) -> None:
    global _SETTINGS_CACHE, _SETTINGS_CACHE_SIGNATURE

    normalized = _normalize_settings(data)
    path = get_settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(path, _format_settings_json(normalized), encoding="utf-8")
    _SETTINGS_CACHE = copy.deepcopy(normalized)
    _SETTINGS_CACHE_SIGNATURE = _settings_file_signature(path)


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


def _read_settings_cached_locked(*, materialize: bool = True) -> dict[str, Any]:
    global _SETTINGS_CACHE, _SETTINGS_CACHE_SIGNATURE

    signature = _settings_file_signature()
    if _SETTINGS_CACHE is not None and _SETTINGS_CACHE_SIGNATURE == signature:
        return _SETTINGS_CACHE

    data = _read_settings_file_locked(materialize=materialize)
    _SETTINGS_CACHE = copy.deepcopy(data)
    _SETTINGS_CACHE_SIGNATURE = _settings_file_signature()
    return _SETTINGS_CACHE


def read_settings() -> dict[str, Any]:
    with _SETTINGS_LOCK:
        return copy.deepcopy(_read_settings_cached_locked())


def materialize_settings_file() -> dict[str, Any]:
    """Гарантирует, что settings.json существует и содержит полный нормализованный JSON."""
    with _SETTINGS_LOCK:
        return copy.deepcopy(_read_settings_cached_locked(materialize=True))


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
        current = _read_settings_cached_locked()
        working = copy.deepcopy(current)
        mutator(working)
        normalized = _normalize_settings(working)
        if normalized == current:
            return copy.deepcopy(current)
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


def _get_str_list(path: tuple[str, ...]) -> list[str]:
    value = _get_path_value(read_settings(), path, [])
    return list(value) if isinstance(value, list) else []


def _set_str_list(path: tuple[str, ...], value: object) -> bool:
    _update_settings(lambda data: _set_path_value(data, path, _unique_domain_list(value)))
    return True


def _set_dc_ip_list(path: tuple[str, ...], value: object) -> bool:
    _update_settings(lambda data: _set_path_value(data, path, _unique_dc_ip_list(value)))
    return True


def _get_nullable_str(path: tuple[str, ...]) -> str | None:
    value = _get_path_value(read_settings(), path, None)
    return value if isinstance(value, str) and value.strip() else None


def _set_nullable_str(path: tuple[str, ...], value: str | None) -> bool:
    _update_settings(lambda data: _set_path_value(data, path, None if value is None else str(value)))
    return True


def _presets_selection_path(engine: str) -> tuple[str, ...]:
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


def get_premium_settings() -> dict[str, Any]:
    return copy.deepcopy(read_settings()["premium"])


def set_premium_settings(values: dict[str, Any]) -> dict[str, Any]:
    updated = _update_settings(lambda data: data["premium"].update(_as_dict(values)))
    return copy.deepcopy(updated["premium"])


def get_ui_state_settings() -> dict[str, Any]:
    return copy.deepcopy(read_settings()["ui_state"])


def set_ui_state_settings(values: dict[str, Any]) -> dict[str, Any]:
    updated = _update_settings(lambda data: data["ui_state"].update(_as_dict(values)))
    return copy.deepcopy(updated["ui_state"])


def get_profile_strategy_state_settings() -> dict[str, Any]:
    return copy.deepcopy(read_settings()["profile_strategy_state"])


def set_profile_strategy_state_settings(values: dict[str, Any]) -> dict[str, Any]:
    updated = _update_settings(lambda data: _set_path_value(data, ("profile_strategy_state",), _as_dict(values)))
    return copy.deepcopy(updated["profile_strategy_state"])


def get_user_profiles_settings() -> dict[str, Any]:
    return copy.deepcopy(read_settings()["user_profiles"])


def set_user_profiles_settings(values: dict[str, Any]) -> dict[str, Any]:
    updated = _update_settings(lambda data: _set_path_value(data, ("user_profiles",), _as_dict(values)))
    return copy.deepcopy(updated["user_profiles"])


def get_updater_settings() -> dict[str, Any]:
    return copy.deepcopy(read_settings()["updater"])


def set_updater_settings(values: dict[str, Any]) -> dict[str, Any]:
    updated = _update_settings(lambda data: data["updater"].update(_as_dict(values)))
    return copy.deepcopy(updated["updater"])


def get_blockcheck_settings() -> dict[str, Any]:
    return copy.deepcopy(read_settings()["blockcheck"])


def set_blockcheck_settings(values: dict[str, Any]) -> dict[str, Any]:
    updated = _update_settings(lambda data: data["blockcheck"].update(_as_dict(values)))
    return copy.deepcopy(updated["blockcheck"])


def get_folders_settings() -> dict[str, Any]:
    return copy.deepcopy(read_settings()["folders"])


def set_folders_settings(values: dict[str, Any]) -> dict[str, Any]:
    updated = _update_settings(lambda data: _set_path_value(data, ("folders",), _as_dict(values)))
    return copy.deepcopy(updated["folders"])


def get_orchestra_settings() -> dict[str, Any]:
    return copy.deepcopy(read_settings()["orchestra"]["settings"])


def set_orchestra_settings(values: dict[str, Any]) -> dict[str, Any]:
    updated = _update_settings(lambda data: data["orchestra"]["settings"].update(_as_dict(values)))
    return copy.deepcopy(updated["orchestra"]["settings"])


def get_dpi_autostart() -> bool:
    return _get_bool(("program", "dpi_autostart"), True)


def set_dpi_autostart(value: bool) -> bool:
    return _set_bool(("program", "dpi_autostart"), value)


def get_gui_autostart_enabled() -> bool:
    return _get_bool(("program", "gui_autostart_enabled"), False)


def set_gui_autostart_enabled(value: bool) -> bool:
    return _set_bool(("program", "gui_autostart_enabled"), value)


def get_strategy_launch_method() -> str:
    return normalize_launch_method(_get_str(("program", "strategy_launch_method"), DEFAULT_LAUNCH_METHOD))


def set_strategy_launch_method(value: str) -> bool:
    return _set_str(("program", "strategy_launch_method"), normalize_launch_method(value))


def get_selected_source_preset_file_name(engine: str) -> str | None:
    value = _get_str(_presets_selection_path(engine), "")
    return value or None


def set_selected_source_preset_file_name(engine: str, value: str | None) -> bool:
    normalized = _as_clean_str(value)
    return _set_str(_presets_selection_path(engine), normalized)


def clear_selected_source_preset_file_name(engine: str) -> bool:
    return _set_str(_presets_selection_path(engine), "")


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


def get_defender_disabled_memory() -> bool:
    return _get_bool(("program", "defender_disabled"), False)


def get_window_geometry() -> dict[str, Any]:
    data = read_settings()
    return copy.deepcopy(
        {
            "x": _get_path_value(data, ("window", "x"), None),
            "y": _get_path_value(data, ("window", "y"), None),
            "width": _get_path_value(data, ("window", "width"), None),
            "height": _get_path_value(data, ("window", "height"), None),
            "maximized": bool(_get_path_value(data, ("window", "maximized"), False)),
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


def get_hide_to_tray_on_minimize_close() -> bool:
    return _get_bool(("window", "hide_to_tray_on_minimize_close"), False)


def set_hide_to_tray_on_minimize_close(value: bool) -> bool:
    return _set_bool(("window", "hide_to_tray_on_minimize_close"), value)


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


def get_sidebar_icon_style() -> str:
    return _get_str(("appearance", "sidebar_icon_style"), "standard")


def set_sidebar_icon_style(value: str) -> bool:
    return _set_str(("appearance", "sidebar_icon_style"), value)


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
    if winreg is None:
        return None
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


def get_hosts_selection() -> dict[str, str]:
    data = _get_path_value(read_settings(), ("hosts", "selection"), {})
    if not isinstance(data, dict):
        return {}
    out: dict[str, str] = {}
    for raw_service_name, raw_profile_name in data.items():
        service_name = _as_clean_str(raw_service_name)
        profile_name = _as_clean_str(raw_profile_name)
        if service_name and profile_name:
            out[service_name] = profile_name
    return out


def set_hosts_selection(selection: dict[str, str]) -> bool:
    normalized: dict[str, str] = {}
    for raw_service_name, raw_profile_name in _as_dict(selection).items():
        service_name = _as_clean_str(raw_service_name)
        profile_name = _as_clean_str(raw_profile_name)
        if service_name and profile_name:
            normalized[service_name] = profile_name
    _update_settings(lambda data: _set_path_value(data, ("hosts", "selection"), normalized))
    return True


def get_premium_device_id() -> str:
    return _get_str(("premium", "device_id"), "")


def set_premium_device_id(value: str) -> bool:
    return _set_str(("premium", "device_id"), _as_clean_str(value))


def get_premium_device_token() -> str | None:
    return _get_nullable_str(("premium", "device_token"))


def set_premium_device_token(value: str | None) -> bool:
    return _set_nullable_str(("premium", "device_token"), _as_clean_str(value) or None)


def get_premium_last_check() -> str | None:
    return _get_nullable_str(("premium", "last_check"))


def set_premium_last_check(value: str | None) -> bool:
    return _set_nullable_str(("premium", "last_check"), value)


def get_premium_last_network_failure_ts() -> int | None:
    value = _get_path_value(read_settings(), ("premium", "last_network_failure_ts"), None)
    try:
        return int(value) if value is not None else None
    except Exception:
        return None


def set_premium_last_network_failure_ts(value: int | None) -> bool:
    _update_settings(
        lambda data: _set_path_value(
            data,
            ("premium", "last_network_failure_ts"),
            None if value is None else int(value),
        )
    )
    return True


def get_premium_pair_code() -> str | None:
    value = _get_nullable_str(("premium", "pair_code"))
    return value.upper() if value else None


def set_premium_pair_code(*, code: str | None, expires_at: int | None) -> bool:
    normalized_code = _as_clean_str(code).upper()
    expires = None
    if expires_at is not None:
        try:
            expires = int(expires_at)
        except Exception:
            expires = None
    if not normalized_code or not expires or expires <= 0:
        normalized_code = ""
        expires = None
    _update_settings(
        lambda data: (
            _set_path_value(data, ("premium", "pair_code"), normalized_code or None),
            _set_path_value(data, ("premium", "pair_expires_at"), expires),
        )
    )
    return True


def get_premium_pair_expires_at() -> int | None:
    value = _get_path_value(read_settings(), ("premium", "pair_expires_at"), None)
    try:
        return int(value) if value is not None else None
    except Exception:
        return None


def get_premium_cache() -> dict[str, Any] | None:
    cache = _get_path_value(read_settings(), ("premium", "premium_cache"), None)
    return copy.deepcopy(cache) if isinstance(cache, dict) else None


def set_premium_cache(cache: dict[str, Any] | None) -> bool:
    _update_settings(
        lambda data: _set_path_value(
            data,
            ("premium", "premium_cache"),
            copy.deepcopy(cache) if isinstance(cache, dict) else None,
        )
    )
    return True


def get_tg_proxy_enabled() -> bool:
    return _get_bool(("telegram_proxy", "enabled"), True)


def set_tg_proxy_enabled(value: bool) -> bool:
    return _set_bool(("telegram_proxy", "enabled"), value)


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


def get_tg_proxy_cloudflare_enabled() -> bool:
    return _get_bool(("telegram_proxy", "cloudflare_enabled"), False)


def set_tg_proxy_cloudflare_enabled(value: bool) -> bool:
    return _set_bool(("telegram_proxy", "cloudflare_enabled"), value)


def get_tg_proxy_cloudflare_domains() -> list[str]:
    return _get_str_list(("telegram_proxy", "cloudflare_domains"))


def set_tg_proxy_cloudflare_domains(value: object) -> bool:
    return _set_str_list(("telegram_proxy", "cloudflare_domains"), value)


def get_tg_proxy_cloudflare_worker_enabled() -> bool:
    return _get_bool(("telegram_proxy", "cloudflare_worker_enabled"), False)


def set_tg_proxy_cloudflare_worker_enabled(value: bool) -> bool:
    return _set_bool(("telegram_proxy", "cloudflare_worker_enabled"), value)


def get_tg_proxy_cloudflare_worker_domains() -> list[str]:
    return _get_str_list(("telegram_proxy", "cloudflare_worker_domains"))


def set_tg_proxy_cloudflare_worker_domains(value: object) -> bool:
    return _set_str_list(("telegram_proxy", "cloudflare_worker_domains"), value)


def get_tg_proxy_mtproxy_secret() -> str:
    return _get_str(("telegram_proxy", "mtproxy_secret"), "")


def set_tg_proxy_mtproxy_secret(value: str) -> bool:
    return _set_str(("telegram_proxy", "mtproxy_secret"), _normalize_hex_secret(value))


def get_tg_proxy_dc_ip() -> list[str]:
    return _get_str_list(("telegram_proxy", "dc_ip"))


def set_tg_proxy_dc_ip(value: object) -> bool:
    return _set_dc_ip_list(("telegram_proxy", "dc_ip"), value)


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
    normalized = [_normalize_lookup_key(item) for item in _unique_str_list(domains) if _normalize_lookup_key(item)]
    _update_settings(lambda data: _set_path_value(data, ("orchestra", "whitelist", "user_domains"), normalized))
    return True


def add_orchestra_whitelist_domain(domain: str) -> bool:
    items = get_orchestra_whitelist_user_domains()
    value = _normalize_lookup_key(domain)
    if value and value not in items:
        items.append(value)
    return set_orchestra_whitelist_user_domains(items)


def remove_orchestra_whitelist_domain(domain: str) -> bool:
    value = _normalize_lookup_key(domain)
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
    lookup_key = _normalize_lookup_key(target)
    if not lookup_key:
        return False

    def _mutator(data: dict[str, Any]) -> None:
        mapping = _as_dict(_get_path_value(data, ("orchestra", "locked", key), {}))
        mapping[lookup_key] = int(strategy)
        _set_path_value(data, ("orchestra", "locked", key), mapping)

    _update_settings(_mutator)
    return True


def remove_orchestra_locked_target(askey: str, target: str) -> bool:
    key = _normalize_askey(askey)
    lookup_key = _normalize_lookup_key(target)

    def _mutator(data: dict[str, Any]) -> None:
        mapping = _as_dict(_get_path_value(data, ("orchestra", "locked", key), {}))
        mapping.pop(lookup_key, None)
        _set_path_value(data, ("orchestra", "locked", key), mapping)

    _update_settings(_mutator)
    return True


def clear_orchestra_locked_map(askey: str) -> bool:
    return set_orchestra_locked_map(askey, {})


def get_orchestra_user_locked(askey: str) -> list[str]:
    key = _normalize_askey(askey)
    values = _get_path_value(read_settings(), ("orchestra", "user_locked", key), [])
    return [_normalize_lookup_key(item) for item in _unique_str_list(values) if _normalize_lookup_key(item)]


def set_orchestra_user_locked(askey: str, values: list[str]) -> bool:
    key = _normalize_askey(askey)
    normalized = [_normalize_lookup_key(item) for item in _unique_str_list(values) if _normalize_lookup_key(item)]
    _update_settings(lambda data: _set_path_value(data, ("orchestra", "user_locked", key), normalized))
    return True


def add_orchestra_user_locked(askey: str, target: str) -> bool:
    items = get_orchestra_user_locked(askey)
    value = _normalize_lookup_key(target)
    if value and value not in items:
        items.append(value)
    return set_orchestra_user_locked(askey, items)


def remove_orchestra_user_locked(askey: str, target: str) -> bool:
    value = _normalize_lookup_key(target)
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
    lookup_key = _normalize_lookup_key(target)
    if not lookup_key:
        return False

    def _mutator(data: dict[str, Any]) -> None:
        mapping = _as_dict(_get_path_value(data, ("orchestra", "user_blocked", key), {}))
        normalized = _unique_int_list(strategies)
        if normalized:
            mapping[lookup_key] = normalized
        else:
            mapping.pop(lookup_key, None)
        _set_path_value(data, ("orchestra", "user_blocked", key), mapping)

    _update_settings(_mutator)
    return True


def remove_orchestra_user_blocked_target(askey: str, target: str) -> bool:
    key = _normalize_askey(askey)
    lookup_key = _normalize_lookup_key(target)

    def _mutator(data: dict[str, Any]) -> None:
        mapping = _as_dict(_get_path_value(data, ("orchestra", "user_blocked", key), {}))
        mapping.pop(lookup_key, None)
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
    lookup_key = _normalize_lookup_key(target)
    return copy.deepcopy(get_orchestra_history().get(lookup_key, {}))


def set_orchestra_history_for_target(target: str, data: dict[str, Any]) -> bool:
    lookup_key = _normalize_lookup_key(target)
    if not lookup_key:
        return False

    def _mutator(settings: dict[str, Any]) -> None:
        history = _as_dict(_get_path_value(settings, ("orchestra", "history"), {}))
        history[lookup_key] = _as_dict(data)
        _set_path_value(settings, ("orchestra", "history"), history)

    _update_settings(_mutator)
    return True


def remove_orchestra_history_target(target: str) -> bool:
    lookup_key = _normalize_lookup_key(target)

    def _mutator(settings: dict[str, Any]) -> None:
        history = _as_dict(_get_path_value(settings, ("orchestra", "history"), {}))
        history.pop(lookup_key, None)
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
    "get_discord_restart_enabled",
    "get_display_mode",
    "get_dns_crash_count",
    "get_dpi_autostart",
    "get_editor_smooth_scroll_enabled",
    "get_defender_disabled_memory",
    "get_follow_windows_accent",
    "get_force_dns_enabled",
    "get_folders_settings",
    "get_garland_enabled",
    "get_gui_autostart_enabled",
    "get_hosts_bootstrap_signature",
    "get_hosts_selection",
    "get_hide_to_tray_on_minimize_close",
    "get_isp_dns_info_shown",
    "get_kaspersky_warning_disabled",
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
    "get_premium_cache",
    "get_premium_device_id",
    "get_premium_device_token",
    "get_premium_last_check",
    "get_premium_last_network_failure_ts",
    "get_premium_pair_code",
    "get_premium_pair_expires_at",
    "get_premium_settings",
    "get_profile_strategy_state_settings",
    "get_remove_github_api",
    "get_rkn_background",
    "get_selected_theme",
    "get_selected_source_preset_file_name",
    "get_sidebar_icon_style",
    "get_settings_path",
    "get_smooth_scroll_enabled",
    "get_snowflakes_enabled",
    "get_strategy_launch_method",
    "get_telega_warning_disabled",
    "get_tg_proxy_deeplink_done",
    "get_tg_proxy_cloudflare_domains",
    "get_tg_proxy_cloudflare_enabled",
    "get_tg_proxy_cloudflare_worker_domains",
    "get_tg_proxy_cloudflare_worker_enabled",
    "get_tg_proxy_dc_ip",
    "get_tg_proxy_enabled",
    "get_tg_proxy_host",
    "get_tg_proxy_mode",
    "get_tg_proxy_mtproxy_secret",
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
    "set_discord_restart_enabled",
    "set_display_mode",
    "set_dns_crash_count",
    "set_dpi_autostart",
    "set_editor_smooth_scroll_enabled",
    "set_follow_windows_accent",
    "set_force_dns_enabled",
    "set_folders_settings",
    "set_garland_enabled",
    "set_gui_autostart_enabled",
    "set_hosts_bootstrap_signature",
    "set_hosts_selection",
    "set_hide_to_tray_on_minimize_close",
    "set_isp_dns_info_shown",
    "set_kaspersky_warning_disabled",
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
    "set_premium_cache",
    "set_premium_device_id",
    "set_premium_device_token",
    "set_premium_last_check",
    "set_premium_last_network_failure_ts",
    "set_premium_pair_code",
    "set_premium_settings",
    "set_profile_strategy_state_settings",
    "set_remove_github_api",
    "set_rkn_background",
    "set_selected_theme",
    "set_selected_source_preset_file_name",
    "set_sidebar_icon_style",
    "set_smooth_scroll_enabled",
    "set_snowflakes_enabled",
    "set_strategy_launch_method",
    "set_telega_warning_disabled",
    "set_tg_proxy_deeplink_done",
    "set_tg_proxy_cloudflare_domains",
    "set_tg_proxy_cloudflare_enabled",
    "set_tg_proxy_cloudflare_worker_domains",
    "set_tg_proxy_cloudflare_worker_enabled",
    "set_tg_proxy_dc_ip",
    "set_tg_proxy_enabled",
    "set_tg_proxy_host",
    "set_tg_proxy_mode",
    "set_tg_proxy_mtproxy_secret",
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
