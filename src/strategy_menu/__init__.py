# strategy_menu/__init__.py
"""
Модуль управления стратегиями DPI-обхода.
Предоставляет единый интерфейс для работы со стратегиями.
"""

import os
import configparser
import json
import winreg
from log import log
from config import APPDATA_DIR, get_zapret_userdata_dir, reg, REGISTRY_PATH
from safe_construct import safe_construct

DIRECT_PATH = rf"{REGISTRY_PATH}\DirectMethod"
DIRECT_STRATEGY_KEY = rf"{REGISTRY_PATH}\DirectStrategy"

# ==================== ИНИЦИАЛИЗАЦИЯ DIRECT ORCHESTRA ====================

def is_direct_zapret2_orchestra_initialized() -> bool:
    """Compatibility helper: mode is considered initialized when default preset exists."""
    try:
        from preset_orchestra_zapret2 import ensure_default_preset_exists

        return bool(ensure_default_preset_exists() is not False)
    except Exception:
        return False


def set_direct_zapret2_orchestra_initialized(initialized: bool = True) -> bool:
    """Compatibility no-op to avoid registry state for orchestra mode."""
    _ = initialized
    try:
        from preset_orchestra_zapret2 import ensure_default_preset_exists

        return bool(ensure_default_preset_exists() is not False)
    except Exception:
        return False


def clear_direct_zapret2_orchestra_strategies() -> bool:
    """Очищает все сохранённые стратегии для режима direct_zapret2_orchestra (устанавливает все в 'none')"""
    from .strategies_registry import registry

    try:
        log("🧹 Очистка стратегий DirectOrchestra (первая инициализация)...", "INFO")

        from preset_orchestra_zapret2 import ensure_default_preset_exists, PresetManager

        if not ensure_default_preset_exists():
            return False

        manager = PresetManager()
        selections = {category_key: "none" for category_key in registry.get_all_category_keys()}
        manager.set_strategy_selections(selections, save_and_sync=True)

        # Сбрасываем кэш
        invalidate_direct_selections_cache()

        log("✅ Все стратегии DirectOrchestra установлены в 'none'", "INFO")
        return True

    except Exception as e:
        log(f"Ошибка очистки стратегий DirectOrchestra: {e}", "ERROR")
        return False


def _get_current_strategy_key() -> str:
    """Возвращает ключ реестра для legacy direct-режимов."""
    return DIRECT_STRATEGY_KEY

# ==================== МЕТОД ЗАПУСКА ====================

_LAUNCH_METHOD_FILE = os.path.join(APPDATA_DIR, "strategy_Launch_method.ini")
_LAUNCH_METHOD_SECTION = "Settings"
_LAUNCH_METHOD_KEY = "StrategyLaunchMethod"
_LAUNCH_METHOD_DEFAULT = "direct_zapret2"


# ==================== DIRECT_ZAPRET2 UI MODE (BASIC/ADVANCED) ====================

_DIRECT_ZAPRET2_UI_MODE_DEFAULT = "basic"

# Store UI mode in Roaming AppData (stable for both dev/stable builds):
#   %APPDATA%\zapret\direct_zapret2\direct_zapret2_mode.ini
_DIRECT_ZAPRET2_UI_MODE_DIR = os.path.join(get_zapret_userdata_dir(), "direct_zapret2")
_DIRECT_ZAPRET2_UI_MODE_FILE = os.path.join(_DIRECT_ZAPRET2_UI_MODE_DIR, "direct_zapret2_mode.ini")
_DIRECT_ZAPRET2_UI_MODE_SECTION = "Settings"
_DIRECT_ZAPRET2_UI_MODE_KEY = "mode"

# Legacy registry value for one-time migration.
_DIRECT_ZAPRET2_UI_MODE_LEGACY_REG_KEY = "DirectZapret2UiMode"


def get_direct_zapret2_ui_mode() -> str:
    """Returns UI mode for direct_zapret2: "basic" or "advanced"."""
    # Primary source: INI file in Roaming AppData.
    try:
        if os.path.isfile(_DIRECT_ZAPRET2_UI_MODE_FILE):
            cfg = safe_construct(configparser.ConfigParser)
            cfg.read(_DIRECT_ZAPRET2_UI_MODE_FILE, encoding="utf-8")
            value = cfg.get(_DIRECT_ZAPRET2_UI_MODE_SECTION, _DIRECT_ZAPRET2_UI_MODE_KEY, fallback="")
            value = (value or "").strip().lower()
            if value in ("basic", "advanced"):
                return value
    except Exception as e:
        log(f"Ошибка чтения direct_zapret2_mode из {_DIRECT_ZAPRET2_UI_MODE_FILE}: {e}", "DEBUG")

    # Backward compatibility: migrate from the legacy registry value.
    try:
        raw = reg(DIRECT_PATH, _DIRECT_ZAPRET2_UI_MODE_LEGACY_REG_KEY)
        if isinstance(raw, str):
            value = raw.strip().lower()
            if value in ("basic", "advanced"):
                try:
                    set_direct_zapret2_ui_mode(value)
                except Exception:
                    pass
                return value
    except Exception:
        pass

    # Ensure the file exists with default value (best-effort).
    try:
        set_direct_zapret2_ui_mode(_DIRECT_ZAPRET2_UI_MODE_DEFAULT)
    except Exception:
        pass
    return _DIRECT_ZAPRET2_UI_MODE_DEFAULT


def set_direct_zapret2_ui_mode(mode: str) -> bool:
    """Persists UI mode for direct_zapret2 ("basic" or "advanced")."""
    value = str(mode or "").strip().lower()
    if value not in ("basic", "advanced"):
        value = _DIRECT_ZAPRET2_UI_MODE_DEFAULT
    try:
        os.makedirs(_DIRECT_ZAPRET2_UI_MODE_DIR, exist_ok=True)
        cfg = safe_construct(configparser.ConfigParser)
        cfg[_DIRECT_ZAPRET2_UI_MODE_SECTION] = {_DIRECT_ZAPRET2_UI_MODE_KEY: value}
        with open(_DIRECT_ZAPRET2_UI_MODE_FILE, "w", encoding="utf-8") as f:
            cfg.write(f)
        log(f"DirectZapret2 UI mode set to: {value}", "DEBUG")
        return True
    except Exception as e:
        log(f"Ошибка сохранения direct_zapret2_mode в {_DIRECT_ZAPRET2_UI_MODE_FILE}: {e}", "ERROR")
        return False


def get_strategy_launch_method() -> str:
    """Получает метод запуска стратегий из INI-файла в AppData"""
    try:
        if os.path.isfile(_LAUNCH_METHOD_FILE):
            cfg = safe_construct(configparser.ConfigParser)
            cfg.read(_LAUNCH_METHOD_FILE, encoding="utf-8")
            value = cfg.get(_LAUNCH_METHOD_SECTION, _LAUNCH_METHOD_KEY, fallback="")
            if value:
                return value.lower()
    except Exception as e:
        log(f"Ошибка чтения метода запуска из {_LAUNCH_METHOD_FILE}: {e}", "ERROR")

    # Файл не найден или пуст — создаём с дефолтом
    set_strategy_launch_method(_LAUNCH_METHOD_DEFAULT)
    log(f"Установлен метод запуска по умолчанию: {_LAUNCH_METHOD_DEFAULT}", "INFO")
    return _LAUNCH_METHOD_DEFAULT


def set_strategy_launch_method(method: str) -> bool:
    """Сохраняет метод запуска стратегий в INI-файл в AppData"""
    try:
        os.makedirs(APPDATA_DIR, exist_ok=True)
        cfg = safe_construct(configparser.ConfigParser)
        cfg[_LAUNCH_METHOD_SECTION] = {_LAUNCH_METHOD_KEY: method}
        with open(_LAUNCH_METHOD_FILE, "w", encoding="utf-8") as f:
            cfg.write(f)
        log(f"Метод запуска стратегий изменен на: {method}", "INFO")
        return True
    except Exception as e:
        log(f"Ошибка сохранения метода запуска: {e}", "ERROR")
        return False


# ==================== НАСТРОЙКИ UI ДИАЛОГА ====================

def get_tabs_pinned() -> bool:
    """Получает состояние закрепления боковой панели табов"""
    result = reg(DIRECT_PATH, "TabsPinned")
    if result is not None:
        try:
            return bool(int(result))
        except (ValueError, TypeError):
            return False
    return True

def set_tabs_pinned(pinned: bool) -> bool:
    """Сохраняет состояние закрепления боковой панели табов"""
    success = reg(DIRECT_PATH, "TabsPinned", int(pinned))
    if success:
        log(f"Настройка закрепления табов: {'закреплено' if pinned else 'не закреплено'}", "DEBUG")
    return success

def get_keep_dialog_open() -> bool:
    """Получает настройку сохранения диалога открытым"""
    result = reg(DIRECT_PATH, "KeepDialogOpen")
    if result is not None:
        try:
            return bool(int(result))
        except (ValueError, TypeError):
            return False
    return False

def set_keep_dialog_open(enabled: bool) -> bool:
    """Сохраняет настройку сохранения диалога открытым"""
    success = reg(DIRECT_PATH, "KeepDialogOpen", int(enabled))
    if success:
        log(f"Настройка 'не закрывать окно': {'вкл' if enabled else 'выкл'}", "DEBUG")
    return success


# ==================== КЭШИРОВАНИЕ ====================

# Кэш избранных стратегий
_favorites_cache = {}
_favorites_cache_time = 0
FAVORITES_CACHE_TTL = 5.0  # 5 секунд (было 0.5)

# Кэш выборов стратегий для Direct режима
_direct_selections_cache = None
_direct_selections_cache_time = 0
_direct_selections_cache_method = None
_direct_selections_cache_preset_mtime = None
DIRECT_SELECTIONS_CACHE_TTL = 5.0  # 5 секунд

# Кэш предупреждений о невалидных стратегиях (чтобы не спамить)
_warned_invalid_strategies = set()

def get_favorites_for_category(category_key):
    """Получает избранные стратегии для категории (с кэшем)"""
    import time
    global _favorites_cache, _favorites_cache_time
    
    current_time = time.time()
    
    if current_time - _favorites_cache_time < FAVORITES_CACHE_TTL:
        return _favorites_cache.get(category_key, set())
    
    favorites = get_favorite_strategies()
    _favorites_cache = {
        key: set(values) for key, values in favorites.items()
    }
    _favorites_cache_time = current_time
    
    return _favorites_cache.get(category_key, set())

def invalidate_favorites_cache():
    """Сбрасывает кэш избранных"""
    global _favorites_cache_time
    _favorites_cache_time = 0


# ==================== ИЗБРАННЫЕ СТРАТЕГИИ ====================

def get_favorite_strategies(category=None):
    """
    Получает избранные стратегии.
    
    Args:
        category: категория или None для всех
    
    Returns:
        list (если category) или dict {category: [strategy_ids]}
    """
    try:
        result = reg(REGISTRY_PATH, "FavoriteStrategiesByCategory")
        if result:
            favorites_dict = json.loads(result)
            if category:
                return favorites_dict.get(category, [])
            return favorites_dict
        return [] if category else {}
    except Exception as e:
        log(f"Ошибка загрузки избранных: {e}", "DEBUG")
        return [] if category else {}

def add_favorite_strategy(strategy_id, category):
    """Добавляет стратегию в избранные"""
    try:
        favorites_dict = get_favorite_strategies()
        if not isinstance(favorites_dict, dict):
            favorites_dict = {}
        
        if category not in favorites_dict:
            favorites_dict[category] = []
        
        if strategy_id not in favorites_dict[category]:
            favorites_dict[category].append(strategy_id)
            reg(REGISTRY_PATH, "FavoriteStrategiesByCategory", json.dumps(favorites_dict))
            invalidate_favorites_cache()
            log(f"Стратегия {strategy_id} добавлена в избранные ({category})", "DEBUG")
            return True
        return False
    except Exception as e:
        log(f"Ошибка добавления в избранные: {e}", "ERROR")
        return False

def remove_favorite_strategy(strategy_id, category):
    """Удаляет стратегию из избранных"""
    try:
        favorites_dict = get_favorite_strategies()
        if not isinstance(favorites_dict, dict):
            return False
        
        if category in favorites_dict and strategy_id in favorites_dict[category]:
            favorites_dict[category].remove(strategy_id)
            
            if not favorites_dict[category]:
                del favorites_dict[category]
                
            reg(REGISTRY_PATH, "FavoriteStrategiesByCategory", json.dumps(favorites_dict))
            invalidate_favorites_cache()
            log(f"Стратегия {strategy_id} удалена из избранных ({category})", "DEBUG")
            return True
        return False
    except Exception as e:
        log(f"Ошибка удаления из избранных: {e}", "ERROR")
        return False

def is_favorite_strategy(strategy_id, category=None):
    """Проверяет, является ли стратегия избранной"""
    favorites_dict = get_favorite_strategies()
    if not isinstance(favorites_dict, dict):
        return False
    
    if category:
        return strategy_id in favorites_dict.get(category, [])
    else:
        for cat_favorites in favorites_dict.values():
            if strategy_id in cat_favorites:
                return True
        return False

def toggle_favorite_strategy(strategy_id, category):
    """Переключает статус избранной стратегии"""
    if is_favorite_strategy(strategy_id, category):
        remove_favorite_strategy(strategy_id, category)
        return False
    else:
        add_favorite_strategy(strategy_id, category)
        return True

def clear_favorite_strategies(category=None):
    """Очищает избранные стратегии"""
    try:
        if category:
            favorites_dict = get_favorite_strategies()
            if isinstance(favorites_dict, dict) and category in favorites_dict:
                del favorites_dict[category]
                reg(REGISTRY_PATH, "FavoriteStrategiesByCategory", json.dumps(favorites_dict))
                invalidate_favorites_cache()
        else:
            reg(REGISTRY_PATH, "FavoriteStrategiesByCategory", json.dumps({}))
            invalidate_favorites_cache()
        return True
    except Exception as e:
        log(f"Ошибка очистки избранных: {e}", "ERROR")
        return False

def get_all_favorite_strategies_flat():
    """Возвращает плоский список всех избранных"""
    favorites_dict = get_favorite_strategies()
    if not isinstance(favorites_dict, dict):
        return []
    
    all_favorites = set()
    for cat_favorites in favorites_dict.values():
        all_favorites.update(cat_favorites)
    
    return list(all_favorites)


# ==================== LEGACY ИЗБРАННЫЕ (для совместимости) ====================

def get_favorite_strategies_legacy():
    """[LEGACY] Получает список ID избранных стратегий"""
    try:
        result = reg(REGISTRY_PATH, "FavoriteStrategies")
        if result:
            return json.loads(result)
        return []
    except:
        return []

def is_favorite_strategy_legacy(strategy_id):
    """[LEGACY] Проверяет, является ли стратегия избранной"""
    return strategy_id in get_favorite_strategies_legacy()

def toggle_favorite_strategy_legacy(strategy_id):
    """[LEGACY] Переключает статус избранной"""
    favorites = get_favorite_strategies_legacy()
    if strategy_id in favorites:
        favorites.remove(strategy_id)
    else:
        favorites.append(strategy_id)
    reg(REGISTRY_PATH, "FavoriteStrategies", json.dumps(favorites))
    return strategy_id in favorites


# ==================== НАСТРОЙКИ ПРЯМОГО РЕЖИМА ====================

def get_base_args_selection() -> str:
    """Получает выбранный вариант базовых аргументов"""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, DIRECT_PATH) as key:
            value, _ = winreg.QueryValueEx(key, "BaseArgsSelection")
            return value
    except:
        return "windivert_all"

def set_base_args_selection(selection: str) -> bool:
    """Сохраняет вариант базовых аргументов"""
    try:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, DIRECT_PATH) as key:
            winreg.SetValueEx(key, "BaseArgsSelection", 0, winreg.REG_SZ, selection)
            log(f"Базовые аргументы: {selection}", "INFO")
            return True
    except Exception as e:
        log(f"Ошибка сохранения базовых аргументов: {e}", "❌ ERROR")
        return False

def get_wssize_enabled() -> bool:
    """Получает настройку включения --wssize"""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, DIRECT_PATH) as key:
            value, _ = winreg.QueryValueEx(key, "WSSizeEnabled")
            return bool(value)
    except:
        return False

def set_wssize_enabled(enabled: bool) -> bool:
    """Сохраняет настройку --wssize"""
    try:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, DIRECT_PATH) as key:
            winreg.SetValueEx(key, "WSSizeEnabled", 0, winreg.REG_DWORD, int(enabled))
            return True
    except:
        return False

def _category_to_reg_key(category_key: str) -> str:
    """Преобразует ключ категории в ключ реестра"""
    # youtube_udp -> YoutubeUdp
    parts = category_key.split('_')
    return "DirectStrategy" + ''.join(part.capitalize() for part in parts)


# ==================== DEBUG LOG НАСТРОЙКИ ====================

def get_debug_log_enabled() -> bool:
    """Получает настройку включения логирования --debug"""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, DIRECT_PATH) as key:
            value, _ = winreg.QueryValueEx(key, "DebugLogEnabled")
            return bool(value)
    except:
        return False

def set_debug_log_enabled(enabled: bool) -> bool:
    """Сохраняет настройку логирования --debug"""
    try:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, DIRECT_PATH) as key:
            winreg.SetValueEx(key, "DebugLogEnabled", 0, winreg.REG_DWORD, int(enabled))
            if enabled:
                try:
                    winreg.QueryValueEx(key, "DebugLogFile")
                except Exception:
                    from datetime import datetime
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    winreg.SetValueEx(
                        key,
                        "DebugLogFile",
                        0,
                        winreg.REG_SZ,
                        f"logs/zapret_winws2_debug_{timestamp}.log",
                    )
            else:
                try:
                    winreg.DeleteValue(key, "DebugLogFile")
                except Exception:
                    pass
            return True
    except:
        return False

def get_debug_log_file() -> str:
    """Получает относительный путь к debug лог-файлу winws2 (без @)."""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, DIRECT_PATH) as key:
            value, _ = winreg.QueryValueEx(key, "DebugLogFile")
            return str(value or "")
    except Exception:
        return ""


# ==================== ВЫБОРЫ СТРАТЕГИЙ ====================

def invalidate_direct_selections_cache():
    """Сбрасывает кэш выборов стратегий"""
    global _direct_selections_cache_time
    _direct_selections_cache_time = 0
    global _direct_selections_cache_method
    _direct_selections_cache_method = None
    global _direct_selections_cache_preset_mtime
    _direct_selections_cache_preset_mtime = None


def get_direct_strategy_selections() -> dict:
    """
    Возвращает сохраненные выборы стратегий для прямого запуска.

    ✅ Кэширует результат на 5 секунд для быстрого доступа
    ✅ Валидирует каждый сохранённый strategy_id:
    - Если стратегия не найдена в каталоге, использует значение по умолчанию
    - Логирует предупреждения о замене невалидных стратегий
    """
    import time
    global _direct_selections_cache, _direct_selections_cache_time, _direct_selections_cache_preset_mtime, _direct_selections_cache_method

    method = get_strategy_launch_method()

    cache_mtime = None
    if method == "direct_zapret1":
        try:
            from core.services import get_direct_flow_coordinator

            preset_path = get_direct_flow_coordinator().get_selected_source_path("direct_zapret1")
            cache_mtime = preset_path.stat().st_mtime if preset_path.exists() else None
        except Exception:
            cache_mtime = None
    elif method == "direct_zapret2":
        try:
            from core.services import get_direct_flow_coordinator

            preset_path = get_direct_flow_coordinator().get_selected_source_path("direct_zapret2")
            cache_mtime = preset_path.stat().st_mtime if preset_path.exists() else None
        except Exception:
            cache_mtime = None

    # Проверяем кэш
    current_time = time.time()
    if _direct_selections_cache is not None and \
       current_time - _direct_selections_cache_time < DIRECT_SELECTIONS_CACHE_TTL and \
       _direct_selections_cache_method == method and \
       _direct_selections_cache_preset_mtime == cache_mtime:
        return _direct_selections_cache.copy()

    from .strategies_registry import registry

    try:
        selections: dict[str, str] = {}
        default_selections = registry.get_default_selections()
        invalid_count = 0

        # direct_zapret2: source of truth is selected preset file (not runtime txt / registry)
        if method == "direct_zapret2":
            try:
                from core.services import get_direct_flow_coordinator
                from preset_zapret2 import load_preset

                selected_name = (get_direct_flow_coordinator().get_selected_preset_name("direct_zapret2") or "").strip()
                selections = {k: "none" for k in registry.get_all_category_keys()}
                if selected_name:
                    preset_path = get_direct_flow_coordinator().get_selected_source_path("direct_zapret2")
                    if preset_path.exists():
                        preset = load_preset(selected_name)
                        if preset is not None:
                            selections.update(
                                {
                                    k: (getattr(v, "strategy_id", "") or "none")
                                    for k, v in (preset.categories or {}).items()
                                }
                            )
            except Exception as e:
                log(f"Ошибка чтения selected preset для выбора стратегий direct_zapret2: {e}", "DEBUG")
                selections = {k: "none" for k in registry.get_all_category_keys()}

        # direct_zapret1: source of truth is selected preset file (not runtime txt / registry)
        elif method == "direct_zapret1":
            try:
                from core.services import get_direct_flow_coordinator
                from preset_zapret1 import load_preset_v1

                selected_name = (get_direct_flow_coordinator().get_selected_preset_name("direct_zapret1") or "").strip()
                selections = {k: "none" for k in registry.get_all_category_keys()}
                if selected_name:
                    preset_path = get_direct_flow_coordinator().get_selected_source_path("direct_zapret1")
                    if preset_path.exists():
                        preset = load_preset_v1(selected_name)
                        if preset is not None:
                            selections.update(
                                {
                                    k: (getattr(v, "strategy_id", "") or "none")
                                    for k, v in (preset.categories or {}).items()
                                }
                            )
            except Exception as e:
                log(f"Ошибка чтения selected preset для выбора стратегий direct_zapret1: {e}", "DEBUG")
                selections = {k: "none" for k in registry.get_all_category_keys()}
        elif method == "direct_zapret2_orchestra":
            try:
                from preset_orchestra_zapret2 import PresetManager, ensure_default_preset_exists

                ensure_default_preset_exists()
                preset_manager = PresetManager()
                preset_selections = preset_manager.get_strategy_selections() or {}
                selections = {k: "none" for k in registry.get_all_category_keys()}
                selections.update({k: (v or "none") for k, v in preset_selections.items()})
            except Exception as e:
                log(f"Ошибка чтения preset-zapret2-orchestra.txt для выбора стратегий: {e}", "DEBUG")
                selections = {k: "none" for k in registry.get_all_category_keys()}
        else:
            strategy_key = _get_current_strategy_key()
            for category_key in registry.get_all_category_keys():
                reg_key = _category_to_reg_key(category_key)
                value = reg(strategy_key, reg_key)

                if value:
                    # ✅ Валидация: проверяем существование стратегии
                    if value == "none":
                        # "none" - специальное значение, всегда валидно
                        selections[category_key] = value
                    else:
                        # Проверяем что стратегия существует в реестре
                        args = registry.get_strategy_args_safe(category_key, value)
                        if args is not None:
                            # Стратегия найдена
                            selections[category_key] = value
                        else:
                            # ⚠️ Стратегия не найдена - используем значение по умолчанию
                            # Для direct_zapret2_orchestra всегда "none", для direct - default из категории
                            if method == "direct_zapret2_orchestra":
                                default_value = "none"
                            else:
                                default_value = default_selections.get(category_key, "none")
                            selections[category_key] = default_value
                            invalid_count += 1
                            # Логируем только один раз за сессию
                            warn_key = f"{category_key}:{value}"
                            if warn_key not in _warned_invalid_strategies:
                                _warned_invalid_strategies.add(warn_key)
                                log(f"⚠️ Стратегия '{value}' не найдена в категории '{category_key}', "
                                    f"заменена на '{default_value}'", "WARNING")

        # Заполняем недостающие значения
        for key, default_value in default_selections.items():
            if key not in selections:
                # Для direct_zapret2_orchestra по умолчанию все категории отключены
                if method == "direct_zapret2_orchestra":
                    selections[key] = "none"
                elif method == "direct_zapret1":
                    selections[key] = "none"
                else:
                    selections[key] = default_value

        # Сохраняем в кэш
        _direct_selections_cache = selections
        _direct_selections_cache_time = current_time
        _direct_selections_cache_method = method
        _direct_selections_cache_preset_mtime = cache_mtime

        return selections

    except Exception as e:
        log(f"Ошибка загрузки выборов стратегий: {e}", "❌ ERROR")
        import traceback
        log(traceback.format_exc(), "DEBUG")
        from .strategies_registry import registry
        return registry.get_default_selections()


def set_direct_strategy_selections(selections: dict) -> bool:
    """Сохраняет выборы стратегий для прямого запуска"""
    from .strategies_registry import registry

    try:
        # direct_zapret2: selections are stored in selected preset file (not runtime txt / registry)
        if get_strategy_launch_method() == "direct_zapret2":
            from core.presets.direct_facade import DirectPresetFacade

            facade = DirectPresetFacade.from_launch_method("direct_zapret2")
            for category_key, strategy_id in (selections or {}).items():
                if category_key in registry.get_all_category_keys():
                    facade.set_strategy_selection(category_key, strategy_id, save_and_sync=True)
            invalidate_direct_selections_cache()
            log("Выборы стратегий сохранены (selected source preset direct_zapret2)", "DEBUG")
            return True

        # direct_zapret1: selections are stored in selected preset file (not runtime txt / registry)
        if get_strategy_launch_method() == "direct_zapret1":
            from core.presets.direct_facade import DirectPresetFacade

            facade = DirectPresetFacade.from_launch_method("direct_zapret1")
            success = True
            for category_key, strategy_id in (selections or {}).items():
                if category_key in registry.get_all_category_keys():
                    result = facade.set_strategy_selection(category_key, strategy_id, save_and_sync=True)
                    success = success and bool(result)
            invalidate_direct_selections_cache()
            log("Выборы стратегий сохранены (selected source preset direct_zapret1)", "DEBUG")
            return success

        if get_strategy_launch_method() == "direct_zapret2_orchestra":
            from preset_orchestra_zapret2 import PresetManager, ensure_default_preset_exists

            if not ensure_default_preset_exists():
                return False

            preset_manager = PresetManager()
            payload = {
                category_key: (str((selections or {}).get(category_key) or "none").strip() or "none")
                for category_key in registry.get_all_category_keys()
            }
            preset_manager.set_strategy_selections(payload, save_and_sync=True)
            invalidate_direct_selections_cache()
            log("Выборы стратегий сохранены (preset-zapret2-orchestra.txt)", "DEBUG")
            return True

        success = True
        strategy_key = _get_current_strategy_key()

        for category_key, strategy_id in selections.items():
            if category_key in registry.get_all_category_keys():
                reg_key = _category_to_reg_key(category_key)
                result = reg(strategy_key, reg_key, strategy_id)
                success = success and (result is not False)

        if success:
            invalidate_direct_selections_cache()  # Сбрасываем кэш
            log("Выборы стратегий сохранены", "DEBUG")

        return success

    except Exception as e:
        log(f"Ошибка сохранения выборов: {e}", "❌ ERROR")
        return False


def get_direct_strategy_for_category(category_key: str) -> str:
    """Получает выбранную стратегию для конкретной категории"""
    from .strategies_registry import registry

    # direct_zapret2: source of truth is selected source preset
    if get_strategy_launch_method() == "direct_zapret2":
        selections = get_direct_strategy_selections()
        return selections.get(category_key, "none") or "none"

    # direct_zapret1: source of truth is selected source preset
    if get_strategy_launch_method() == "direct_zapret1":
        selections = get_direct_strategy_selections()
        return selections.get(category_key, "none") or "none"

    method = get_strategy_launch_method()
    if method == "direct_zapret2_orchestra":
        selections = get_direct_strategy_selections()
        return selections.get(category_key, "none") or "none"

    strategy_key = _get_current_strategy_key()
    reg_key = _category_to_reg_key(category_key)
    value = reg(strategy_key, reg_key)

    if value:
        return value

    # Для direct_zapret2_orchestra по умолчанию все категории отключены
    # (пользователь должен явно выбрать что включить)
    method = get_strategy_launch_method()
    if method == "direct_zapret2_orchestra":
        return "none"

    # Для обычного direct возвращаем значение по умолчанию из категории
    category_info = registry.get_category_info(category_key)
    if category_info:
        return category_info.default_strategy

    return "none"


def set_direct_strategy_for_category(category_key: str, strategy_id: str) -> bool:
    """Сохраняет выбранную стратегию для категории"""
    method = get_strategy_launch_method()

    if method == "direct_zapret2":
        try:
            from core.presets.direct_facade import DirectPresetFacade

            DirectPresetFacade.from_launch_method("direct_zapret2").set_strategy_selection(
                category_key,
                strategy_id,
                save_and_sync=True,
            )
            invalidate_direct_selections_cache()
            return True
        except Exception as e:
            log(f"Ошибка сохранения стратегии в selected preset direct_zapret2: {e}", "DEBUG")
            return False

    if method == "direct_zapret1":
        try:
            from core.presets.direct_facade import DirectPresetFacade

            DirectPresetFacade.from_launch_method("direct_zapret1").set_strategy_selection(
                category_key,
                strategy_id,
                save_and_sync=True,
            )
            invalidate_direct_selections_cache()
            return True
        except Exception as e:
            log(f"Ошибка сохранения стратегии в selected preset direct_zapret1: {e}", "DEBUG")
            return False

    if method == "direct_zapret2_orchestra":
        try:
            from preset_orchestra_zapret2 import PresetManager, ensure_default_preset_exists

            if not ensure_default_preset_exists():
                return False

            preset_manager = PresetManager()
            preset_manager.set_strategy_selection(category_key, strategy_id or "none", save_and_sync=True)
            invalidate_direct_selections_cache()
            return True
        except Exception as e:
            log(f"Ошибка сохранения стратегии в preset-zapret2-orchestra.txt: {e}", "DEBUG")
            return False

    strategy_key = _get_current_strategy_key()
    reg_key = _category_to_reg_key(category_key)
    result = reg(strategy_key, reg_key, strategy_id)
    if result:
        invalidate_direct_selections_cache()  # Сбрасываем кэш
    return result


# ==================== ИМПОРТ СТРАТЕГИЙ ====================

from .strategies_registry import (
    registry,
    get_strategies_registry,
    get_category_strategies,
    get_category_info,
    get_tab_names,
    get_tab_tooltips,
    get_default_selections,
    get_category_icon,
    CategoryInfo,
    reload_categories,
)


# ==================== ОЦЕНКИ СТРАТЕГИЙ (РАБОЧАЯ/НЕРАБОЧАЯ) ====================

STRATEGY_RATINGS_PATH = rf"{REGISTRY_PATH}\StrategyRatings"

# Кэш оценок
_ratings_cache = None

def invalidate_ratings_cache():
    """Сбрасывает кэш оценок"""
    global _ratings_cache
    _ratings_cache = None

def get_all_strategy_ratings() -> dict:
    """Возвращает все оценки стратегий {category_key: {strategy_id: rating}}
    rating: 'working' - рабочая, 'broken' - нерабочая, None - без оценки
    """
    global _ratings_cache

    if _ratings_cache is not None:
        return _ratings_cache

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, STRATEGY_RATINGS_PATH) as key:
            value, _ = winreg.QueryValueEx(key, "Ratings")
            _ratings_cache = json.loads(value) if value else {}
            return _ratings_cache
    except FileNotFoundError:
        _ratings_cache = {}
        return {}
    except Exception as e:
        log(f"Ошибка загрузки оценок стратегий: {e}", "⚠ WARNING")
        _ratings_cache = {}
        return {}

def _save_strategy_ratings(ratings: dict) -> bool:
    """Сохраняет оценки стратегий в реестр"""
    global _ratings_cache
    try:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, STRATEGY_RATINGS_PATH) as key:
            winreg.SetValueEx(key, "Ratings", 0, winreg.REG_SZ, json.dumps(ratings))
            _ratings_cache = ratings
            return True
    except Exception as e:
        log(f"Ошибка сохранения оценок стратегий: {e}", "❌ ERROR")
        return False

def get_strategy_rating(strategy_id: str, category_key: str = None) -> str:
    """Возвращает оценку стратегии: 'working', 'broken' или None

    Args:
        strategy_id: ID стратегии
        category_key: Ключ категории (если None, ищет в legacy формате)
    """
    ratings = get_all_strategy_ratings()

    if category_key:
        # Новый формат с категориями
        category_ratings = ratings.get(category_key, {})
        return category_ratings.get(strategy_id)
    else:
        # Legacy формат - ищем по всем категориям
        for cat_ratings in ratings.values():
            if isinstance(cat_ratings, dict) and strategy_id in cat_ratings:
                return cat_ratings[strategy_id]
        return None

def set_strategy_rating(strategy_id: str, rating: str, category_key: str = None) -> bool:
    """Устанавливает оценку стратегии

    Args:
        strategy_id: ID стратегии
        rating: 'working' - рабочая, 'broken' - нерабочая, None - убрать оценку
        category_key: Ключ категории (обязательно для нового формата)
    """
    if not category_key:
        log("⚠️ set_strategy_rating вызван без category_key", "WARNING")
        return False

    ratings = get_all_strategy_ratings().copy()

    # Инициализируем категорию если её нет
    if category_key not in ratings:
        ratings[category_key] = {}

    if rating is None:
        # Убираем оценку
        if strategy_id in ratings[category_key]:
            del ratings[category_key][strategy_id]
            # Удаляем пустую категорию
            if not ratings[category_key]:
                del ratings[category_key]
    else:
        ratings[category_key][strategy_id] = rating

    return _save_strategy_ratings(ratings)

def toggle_strategy_rating(strategy_id: str, rating: str, category_key: str = None) -> str:
    """Переключает оценку стратегии. Если уже установлена такая же - убирает.

    Args:
        strategy_id: ID стратегии
        rating: 'working' или 'broken'
        category_key: Ключ категории

    Returns:
        Новая оценка или None если убрана
    """
    if not category_key:
        log("⚠️ toggle_strategy_rating вызван без category_key", "WARNING")
        return None

    current = get_strategy_rating(strategy_id, category_key)

    if current == rating:
        # Убираем оценку
        set_strategy_rating(strategy_id, None, category_key)
        return None
    else:
        # Устанавливаем новую оценку
        set_strategy_rating(strategy_id, rating, category_key)
        return rating

def clear_all_strategy_ratings() -> bool:
    """Очищает все оценки стратегий"""
    return _save_strategy_ratings({})


# ==================== ЭКСПОРТ ====================

__all__ = [
    # Реестр стратегий
    'registry',
    'get_strategies_registry',
    'get_category_strategies', 
    'get_category_info',
    'get_tab_names',
    'get_tab_tooltips',
    'get_default_selections',
    'get_category_icon',
    'CategoryInfo',
    'reload_categories',
    
    # Настройки UI
    'get_tabs_pinned',
    'set_tabs_pinned',
    'get_keep_dialog_open',
    'set_keep_dialog_open',
    
    # Методы запуска
    'get_strategy_launch_method',
    'set_strategy_launch_method',
    
    # Избранные стратегии
    'get_favorite_strategies',
    'get_favorites_for_category',
    'invalidate_favorites_cache',
    'add_favorite_strategy',
    'remove_favorite_strategy',
    'is_favorite_strategy',
    'toggle_favorite_strategy',
    'clear_favorite_strategies',
    'get_all_favorite_strategies_flat',
    
    # Legacy избранные
    'get_favorite_strategies_legacy',
    'is_favorite_strategy_legacy',
    'toggle_favorite_strategy_legacy',
    
    # Настройки прямого режима
    'get_base_args_selection',
    'set_base_args_selection',
    'get_wssize_enabled',
    'set_wssize_enabled',

    # Debug log настройки
    'get_debug_log_enabled',
    'get_debug_log_file',
    'set_debug_log_enabled',
    
    # Выборы стратегий
    'DIRECT_STRATEGY_KEY',
    'get_direct_strategy_selections',
    'set_direct_strategy_selections',
    'get_direct_strategy_for_category',
    'set_direct_strategy_for_category',
    'invalidate_direct_selections_cache',

    # Инициализация DirectOrchestra
    'is_direct_zapret2_orchestra_initialized',
    'set_direct_zapret2_orchestra_initialized',
    'clear_direct_zapret2_orchestra_strategies',

    # Оценки стратегий
    'get_all_strategy_ratings',
    'get_strategy_rating',
    'set_strategy_rating',
    'toggle_strategy_rating',
    'clear_all_strategy_ratings',
    'invalidate_ratings_cache',
    
    # Алиасы для совместимости
    'save_direct_strategy_selection',
    'save_direct_strategy_selections',

    # Комбинирование стратегий
    'combine_strategies',
    'calculate_required_filters',
    'apply_all_filters',

    # Launcher functions (re-exported from launcher_common)
    'get_strategy_runner',
    'reset_strategy_runner',
    'invalidate_strategy_runner',
    'get_current_runner',
]

# Алиасы для совместимости со старым кодом
save_direct_strategy_selection = set_direct_strategy_for_category
save_direct_strategy_selections = set_direct_strategy_selections

# Re-export launcher functions for backwards compatibility
from launcher_common import (
    get_strategy_runner,
    reset_strategy_runner,
    invalidate_strategy_runner,
    get_current_runner,
    combine_strategies,
    calculate_required_filters,
    apply_all_filters
)
