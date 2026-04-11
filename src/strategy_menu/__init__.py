# strategy_menu/__init__.py
"""
Модуль управления стратегиями DPI-обхода.

Важно:
- для direct_zapret1/direct_zapret2 источник истины теперь selected source preset;
- этот модуль — фасад launch method / UI prefs / marks / direct source-preset helpers;
- registry/orchestra helpers должны импортироваться явно из legacy модулей, а не через этот общий фасад.
"""

from log import log

from .launch_method_store import (
    get_strategy_launch_method,
    set_strategy_launch_method,
)
from .ui_prefs_store import (
    get_direct_zapret2_ui_mode,
    set_direct_zapret2_ui_mode,
    get_tabs_pinned,
    set_tabs_pinned,
    get_keep_dialog_open,
    set_keep_dialog_open,
)
from .marks_store_bridge import (
    get_favorites_for_target,
    invalidate_favorites_cache,
    get_favorite_strategies,
    add_favorite_strategy,
    remove_favorite_strategy,
    is_favorite_strategy,
    toggle_favorite_strategy,
    clear_favorite_strategies,
    get_all_favorite_strategies_flat,
    invalidate_ratings_cache,
    get_all_strategy_ratings,
    get_strategy_rating,
    set_strategy_rating,
    toggle_strategy_rating,
    clear_all_strategy_ratings,
)
# ==================== НАСТРОЙКИ DIRECT SOURCE PRESET ====================

def _get_direct_preset_facade():
    """Возвращает фасад нового direct preset core для direct_zapret1/direct_zapret2."""
    try:
        method = (get_strategy_launch_method() or "").strip().lower()
        if method in ("direct_zapret2", "direct_zapret1"):
            from core.presets.direct_facade import DirectPresetFacade

            return DirectPresetFacade.from_launch_method(method)
    except Exception:
        pass
    return None


def get_wssize_enabled() -> bool:
    """Получает настройку включения --wssize."""
    facade = _get_direct_preset_facade()
    if facade is not None:
        try:
            return bool(facade.get_wssize_enabled())
        except Exception:
            return False
    return False


def set_wssize_enabled(enabled: bool) -> bool:
    """Сохраняет настройку --wssize."""
    facade = _get_direct_preset_facade()
    if facade is not None:
        try:
            return bool(facade.set_wssize_enabled(bool(enabled)))
        except Exception:
            return False
    return False


def get_debug_log_enabled() -> bool:
    """Получает настройку включения логирования --debug."""
    facade = _get_direct_preset_facade()
    if facade is not None:
        try:
            return bool(facade.get_debug_log_enabled())
        except Exception:
            return False
    return False


def set_debug_log_enabled(enabled: bool) -> bool:
    """Сохраняет настройку логирования --debug."""
    facade = _get_direct_preset_facade()
    if facade is not None:
        try:
            return bool(facade.set_debug_log_enabled(bool(enabled)))
        except Exception:
            return False
    return False


def get_debug_log_file() -> str:
    """Получает относительный путь к debug лог-файлу winws2 (без @)."""
    facade = _get_direct_preset_facade()
    if facade is not None:
        try:
            return str(facade.get_debug_log_file() or "")
        except Exception:
            return ""
    return ""


__all__ = [
    # Launch method
    "get_strategy_launch_method",
    "set_strategy_launch_method",

    # UI prefs
    "get_direct_zapret2_ui_mode",
    "set_direct_zapret2_ui_mode",
    "get_tabs_pinned",
    "set_tabs_pinned",
    "get_keep_dialog_open",
    "set_keep_dialog_open",

    # Marks / favorites / ratings bridge
    "get_favorites_for_target",
    "invalidate_favorites_cache",
    "get_favorite_strategies",
    "add_favorite_strategy",
    "remove_favorite_strategy",
    "is_favorite_strategy",
    "toggle_favorite_strategy",
    "clear_favorite_strategies",
    "get_all_favorite_strategies_flat",
    "invalidate_ratings_cache",
    "get_all_strategy_ratings",
    "get_strategy_rating",
    "set_strategy_rating",
    "toggle_strategy_rating",
    "clear_all_strategy_ratings",

    # Direct helpers
    "get_wssize_enabled",
    "set_wssize_enabled",
    "get_debug_log_enabled",
    "get_debug_log_file",
    "set_debug_log_enabled",
]
