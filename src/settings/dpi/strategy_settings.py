from __future__ import annotations

import configparser
import json
import os
from pathlib import Path

from config import APPDATA_DIR, get_zapret_userdata_dir
from log import log
from safe_construct import safe_construct

_LAUNCH_METHOD_FILE = os.path.join(APPDATA_DIR, "strategy_Launch_method.ini")
_LAUNCH_METHOD_SECTION = "Settings"
_LAUNCH_METHOD_KEY = "StrategyLaunchMethod"
_LAUNCH_METHOD_DEFAULT = "direct_zapret2"
_SUPPORTED_LAUNCH_METHODS = {
    "direct_zapret2",
    "direct_zapret1",
    "orchestra",
}

DIRECT_UI_MODE_DEFAULT = "basic"
_VALID_DIRECT_ZAPRET2_UI_MODES = frozenset({"basic", "advanced"})


def _ui_prefs_path() -> Path:
    base = ""
    try:
        base = (get_zapret_userdata_dir() or "").strip()
    except Exception:
        base = ""

    if not base:
        appdata = (os.environ.get("APPDATA") or "").strip()
        if appdata:
            base = os.path.join(appdata, "zapret")

    if not base:
        raise RuntimeError("APPDATA is required for DPI UI preferences")

    # Старый пользовательский путь сохранён специально: так не теряем уже записанные
    # настройки интерфейса после переноса исходников из strategy_menu.
    return Path(base) / "strategy_menu" / "ui_prefs.json"


def _load_ui_prefs_state() -> dict:
    path = _ui_prefs_path()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception as e:
        log(f"Ошибка чтения DPI UI prefs из {path}: {e}", "DEBUG")
        return {}


def _save_ui_prefs_state(state: dict) -> bool:
    path = _ui_prefs_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return True
    except Exception as e:
        log(f"Ошибка сохранения DPI UI prefs в {path}: {e}", "ERROR")
        return False


def normalize_direct_ui_mode(value: object) -> str:
    mode = str(value or "").strip().lower()
    if mode in _VALID_DIRECT_ZAPRET2_UI_MODES:
        return mode
    return DIRECT_UI_MODE_DEFAULT


def get_strategy_launch_method() -> str:
    try:
        if os.path.isfile(_LAUNCH_METHOD_FILE):
            cfg = safe_construct(configparser.ConfigParser)
            cfg.read(_LAUNCH_METHOD_FILE, encoding="utf-8")
            value = cfg.get(_LAUNCH_METHOD_SECTION, _LAUNCH_METHOD_KEY, fallback="")
            if value:
                normalized = str(value or "").strip().lower()
                if normalized in _SUPPORTED_LAUNCH_METHODS:
                    return normalized
                log(
                    f"Обнаружен неподдерживаемый сохранённый метод запуска: {normalized}. "
                    f"Возвращаем значение по умолчанию: {_LAUNCH_METHOD_DEFAULT}",
                    "WARNING",
                )
    except Exception as e:
        log(f"Ошибка чтения метода запуска из {_LAUNCH_METHOD_FILE}: {e}", "ERROR")

    return _LAUNCH_METHOD_DEFAULT


def set_strategy_launch_method(method: str) -> bool:
    try:
        normalized = str(method or "").strip().lower()
        if normalized not in _SUPPORTED_LAUNCH_METHODS:
            log(
                f"Попытка сохранить неподдерживаемый метод запуска: {normalized or 'empty'}. "
                f"Используем {_LAUNCH_METHOD_DEFAULT}",
                "WARNING",
            )
            normalized = _LAUNCH_METHOD_DEFAULT

        os.makedirs(APPDATA_DIR, exist_ok=True)
        cfg = safe_construct(configparser.ConfigParser)
        cfg[_LAUNCH_METHOD_SECTION] = {_LAUNCH_METHOD_KEY: normalized}
        with open(_LAUNCH_METHOD_FILE, "w", encoding="utf-8") as f:
            cfg.write(f)
        log(f"Метод запуска стратегий изменен на: {normalized}", "INFO")
        return True
    except Exception as e:
        log(f"Ошибка сохранения метода запуска: {e}", "ERROR")
        return False


def get_direct_ui_mode() -> str:
    state = _load_ui_prefs_state()
    return normalize_direct_ui_mode(state.get("direct_zapret2_ui_mode"))


def set_direct_ui_mode(mode: str) -> bool:
    value = normalize_direct_ui_mode(mode)
    state = _load_ui_prefs_state()
    state["direct_zapret2_ui_mode"] = value
    ok = _save_ui_prefs_state(state)
    if ok:
        log(f"Direct UI mode set to: {value}", "DEBUG")
    return ok


def _get_direct_preset_facade(*, app_context=None):
    try:
        method = (get_strategy_launch_method() or "").strip().lower()
        if method in ("direct_zapret2", "direct_zapret1") and app_context is not None:
            from core.presets.direct_facade import DirectPresetFacade

            return DirectPresetFacade.from_launch_method(
                method,
                app_context=app_context,
            )
    except Exception:
        pass
    return None


def get_wssize_enabled(*, app_context=None) -> bool:
    facade = _get_direct_preset_facade(app_context=app_context)
    if facade is not None:
        try:
            return bool(facade.get_wssize_enabled())
        except Exception:
            return False
    return False


def set_wssize_enabled(enabled: bool, *, app_context=None) -> bool:
    facade = _get_direct_preset_facade(app_context=app_context)
    if facade is not None:
        try:
            return bool(facade.set_wssize_enabled(bool(enabled)))
        except Exception:
            return False
    return False


def get_debug_log_enabled(*, app_context=None) -> bool:
    facade = _get_direct_preset_facade(app_context=app_context)
    if facade is not None:
        try:
            return bool(facade.get_debug_log_enabled())
        except Exception:
            return False
    return False


def set_debug_log_enabled(enabled: bool, *, app_context=None) -> bool:
    facade = _get_direct_preset_facade(app_context=app_context)
    if facade is not None:
        try:
            return bool(facade.set_debug_log_enabled(bool(enabled)))
        except Exception:
            return False
    return False


def get_debug_log_file(*, app_context=None) -> str:
    facade = _get_direct_preset_facade(app_context=app_context)
    if facade is not None:
        try:
            return str(facade.get_debug_log_file() or "")
        except Exception:
            return ""
    return ""


__all__ = [
    "get_strategy_launch_method",
    "set_strategy_launch_method",
    "DIRECT_UI_MODE_DEFAULT",
    "normalize_direct_ui_mode",
    "get_direct_ui_mode",
    "set_direct_ui_mode",
    "get_wssize_enabled",
    "set_wssize_enabled",
    "get_debug_log_enabled",
    "get_debug_log_file",
    "set_debug_log_enabled",
]
