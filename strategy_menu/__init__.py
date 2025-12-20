# strategy_menu/__init__.py
"""
Модуль управления стратегиями DPI-обхода.
Предоставляет единый интерфейс для работы со стратегиями.
"""

import winreg
import json
from log import log
from config import reg, REGISTRY_PATH

DIRECT_PATH = rf"{REGISTRY_PATH}\DirectMethod"
DIRECT_STRATEGY_KEY = rf"{REGISTRY_PATH}\DirectStrategy"
DIRECT_ORCHESTRA_STRATEGY_KEY = rf"{REGISTRY_PATH}\DirectOrchestraStrategy"


# ==================== ФЛАГ ИНИЦИАЛИЗАЦИИ ОРКЕСТРАТОРА ====================

def is_direct_orchestra_initialized() -> bool:
    """Проверяет, был ли режим direct_orchestra уже инициализирован (первый запуск)"""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REGISTRY_PATH) as key:
            value, _ = winreg.QueryValueEx(key, "DirectOrchestraInitialized")
            return bool(value)
    except:
        return False


def set_direct_orchestra_initialized(initialized: bool = True) -> bool:
    """Устанавливает флаг инициализации режима direct_orchestra"""
    try:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, REGISTRY_PATH) as key:
            winreg.SetValueEx(key, "DirectOrchestraInitialized", 0, winreg.REG_DWORD, 1 if initialized else 0)
            log(f"Флаг инициализации DirectOrchestra: {initialized}", "DEBUG")
            return True
    except Exception as e:
        log(f"Ошибка установки флага DirectOrchestraInitialized: {e}", "ERROR")
        return False


def clear_direct_orchestra_strategies() -> bool:
    """Очищает все сохранённые стратегии для режима direct_orchestra (устанавливает все в 'none')"""
    from .strategies_registry import registry

    try:
        log("🧹 Очистка стратегий DirectOrchestra (первая инициализация)...", "INFO")

        # Устанавливаем все категории в "none"
        for category_key in registry.get_all_category_keys():
            reg_key = _category_to_reg_key(category_key)
            reg(DIRECT_ORCHESTRA_STRATEGY_KEY, reg_key, "none")

        # Сбрасываем кэш
        invalidate_direct_selections_cache()

        log("✅ Все стратегии DirectOrchestra установлены в 'none'", "INFO")
        return True

    except Exception as e:
        log(f"Ошибка очистки стратегий DirectOrchestra: {e}", "ERROR")
        return False


def _get_current_strategy_key() -> str:
    """Возвращает ключ реестра для выборов стратегий в зависимости от метода запуска"""
    method = get_strategy_launch_method()
    if method == "direct_orchestra":
        return DIRECT_ORCHESTRA_STRATEGY_KEY
    return DIRECT_STRATEGY_KEY

# ==================== МЕТОД ЗАПУСКА ====================

def get_strategy_launch_method():
    """Получает метод запуска стратегий из реестра"""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REGISTRY_PATH) as key:
            value, _ = winreg.QueryValueEx(key, "StrategyLaunchMethod")
            return value.lower() if value else "direct"
    except:
        default_method = "direct"
        set_strategy_launch_method(default_method)
        log(f"Установлен метод запуска по умолчанию: {default_method}", "INFO")
        return default_method

def set_strategy_launch_method(method: str):
    """Сохраняет метод запуска стратегий в реестр"""
    try:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, REGISTRY_PATH) as key:
            winreg.SetValueEx(key, "StrategyLaunchMethod", 0, winreg.REG_SZ, method)
            log(f"Метод запуска стратегий изменен на: {method}", "INFO")
            return True
    except Exception as e:
        log(f"Ошибка сохранения метода запуска: {e}", "❌ ERROR")
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

def get_allzone_hostlist_enabled() -> bool:
    """Получает состояние замены other.txt на allzone.txt"""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, DIRECT_PATH) as key:
            value, _ = winreg.QueryValueEx(key, "AllzoneHostlistEnabled")
            return bool(value)
    except:
        return False

def set_allzone_hostlist_enabled(enabled: bool) -> bool:
    """Сохраняет состояние замены other.txt на allzone.txt"""
    try:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, DIRECT_PATH) as key:
            winreg.SetValueEx(key, "AllzoneHostlistEnabled", 0, winreg.REG_DWORD, int(enabled))
            return True
    except:
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

def get_remove_hostlists_enabled() -> bool:
    """Получает состояние 'применить ко всем сайтам'"""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, DIRECT_PATH) as key:
            value, _ = winreg.QueryValueEx(key, "RemoveHostlistsEnabled")
            return bool(value)
    except:
        return False

def set_remove_hostlists_enabled(enabled: bool) -> bool:
    """Сохраняет 'применить ко всем сайтам'"""
    try:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, DIRECT_PATH) as key:
            winreg.SetValueEx(key, "RemoveHostlistsEnabled", 0, winreg.REG_DWORD, int(enabled))
            return True
    except:
        return False

def get_remove_ipsets_enabled() -> bool:
    """Получает состояние 'применить ко всем IP'"""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, DIRECT_PATH) as key:
            value, _ = winreg.QueryValueEx(key, "RemoveIpsetsEnabled")
            return bool(value)
    except:
        return False

def set_remove_ipsets_enabled(enabled: bool) -> bool:
    """Сохраняет 'применить ко всем IP'"""
    try:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, DIRECT_PATH) as key:
            winreg.SetValueEx(key, "RemoveIpsetsEnabled", 0, winreg.REG_DWORD, int(enabled))
            return True
    except:
        return False


# ==================== НАСТРОЙКИ ФИЛЬТРОВ WINDIVERT ====================

# Путь для хранения настроек фильтров
WINDIVERT_FILTERS_PATH = rf"{REGISTRY_PATH}\WinDivertFilters"

def _get_filter_enabled(filter_name: str, default: bool = True) -> bool:
    """Получает состояние отдельного фильтра WinDivert"""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, WINDIVERT_FILTERS_PATH) as key:
            value, _ = winreg.QueryValueEx(key, filter_name)
            return bool(value)
    except:
        return default

def _set_filter_enabled(filter_name: str, enabled: bool) -> bool:
    """Сохраняет состояние отдельного фильтра WinDivert"""
    try:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, WINDIVERT_FILTERS_PATH) as key:
            winreg.SetValueEx(key, filter_name, 0, winreg.REG_DWORD, int(enabled))
            return True
    except Exception as e:
        log(f"Ошибка сохранения фильтра {filter_name}: {e}", "❌ ERROR")
        return False

def _reset_disabled_categories_strategies():
    """
    Сбрасывает стратегии в 'none' для всех категорий, 
    которые отключены текущими настройками фильтров.
    Вызывается при выключении фильтра.
    """
    from .strategies_registry import registry
    
    reset_count = 0
    for category_key in registry.get_all_category_keys():
        if not registry.is_category_enabled_by_filters(category_key):
            # Категория отключена - проверяем текущую стратегию
            reg_key = _category_to_reg_key(category_key)
            current = reg(DIRECT_STRATEGY_KEY, reg_key)
            if current and current != "none":
                # Сбрасываем в none
                reg(DIRECT_STRATEGY_KEY, reg_key, "none")
                reset_count += 1
                log(f"⚠️ Категория '{category_key}' отключена фильтром, стратегия сброшена в 'none'", "INFO")
    
    if reset_count > 0:
        log(f"Сброшено {reset_count} стратегий для отключённых категорий", "INFO")

def _category_to_reg_key(category_key: str) -> str:
    """Преобразует ключ категории в ключ реестра"""
    # youtube_udp -> YoutubeUdp
    parts = category_key.split('_')
    return "DirectStrategy" + ''.join(part.capitalize() for part in parts)

# --- TCP порты ---

def get_wf_tcp_80_enabled() -> bool:
    """TCP порт 80 (HTTP)"""
    return _get_filter_enabled("TcpPort80", default=True)

def set_wf_tcp_80_enabled(enabled: bool) -> bool:
    result = _set_filter_enabled("TcpPort80", enabled)
    if result and not enabled:
        _reset_disabled_categories_strategies()
    return result

def get_wf_tcp_443_enabled() -> bool:
    """TCP порт 443 (HTTPS/TLS)"""
    return _get_filter_enabled("TcpPort443", default=True)

def set_wf_tcp_443_enabled(enabled: bool) -> bool:
    result = _set_filter_enabled("TcpPort443", enabled)
    if result and not enabled:
        _reset_disabled_categories_strategies()
    return result

# --- UDP порты ---

def get_wf_udp_443_enabled() -> bool:
    """UDP порт 443 (QUIC) - перехват всего порта, нагружает CPU"""
    return _get_filter_enabled("UdpPort443", default=False)

def set_wf_udp_443_enabled(enabled: bool) -> bool:
    result = _set_filter_enabled("UdpPort443", enabled)
    if result and not enabled:
        _reset_disabled_categories_strategies()
    return result

def get_wf_tcp_warp_enabled() -> bool:
    """TCP порты 443, 853 (WARP) - Cloudflare WARP VPN"""
    return _get_filter_enabled("TcpWarp", default=False)

def set_wf_tcp_warp_enabled(enabled: bool) -> bool:
    result = _set_filter_enabled("TcpWarp", enabled)
    if result and not enabled:
        _reset_disabled_categories_strategies()
    return result

# --- Raw-part фильтры (эффективные по CPU) ---

def get_wf_raw_discord_media_enabled() -> bool:
    """Discord Media (raw-part фильтр, эффективный)"""
    return _get_filter_enabled("RawDiscordMedia", default=True)

def set_wf_raw_discord_media_enabled(enabled: bool) -> bool:
    result = _set_filter_enabled("RawDiscordMedia", enabled)
    if result and not enabled:
        _reset_disabled_categories_strategies()
    return result

def get_wf_raw_stun_enabled() -> bool:
    """STUN (raw-part фильтр для голосовых звонков)"""
    return _get_filter_enabled("RawStun", default=True)

def set_wf_raw_stun_enabled(enabled: bool) -> bool:
    result = _set_filter_enabled("RawStun", enabled)
    if result and not enabled:
        _reset_disabled_categories_strategies()
    return result

def get_wf_raw_wireguard_enabled() -> bool:
    """WireGuard (raw-part фильтр для VPN)"""
    return _get_filter_enabled("RawWireguard", default=True)

def set_wf_raw_wireguard_enabled(enabled: bool) -> bool:
    result = _set_filter_enabled("RawWireguard", enabled)
    if result and not enabled:
        _reset_disabled_categories_strategies()
    return result   

# --- Расширенные порты (высокая нагрузка на CPU!) ---

def get_wf_tcp_all_ports_enabled() -> bool:
    """TCP порты 444-65535 (ВСЕ остальные порты, высокая нагрузка!)"""
    return _get_filter_enabled("TcpAllPorts", default=False)

def set_wf_tcp_all_ports_enabled(enabled: bool) -> bool:
    result = _set_filter_enabled("TcpAllPorts", enabled)
    if result and not enabled:
        _reset_disabled_categories_strategies()
    return result

def get_wf_udp_all_ports_enabled() -> bool:
    """UDP порты 444-65535 (ВСЕ остальные порты, очень высокая нагрузка!)"""
    return _get_filter_enabled("UdpAllPorts", default=False)

def set_wf_udp_all_ports_enabled(enabled: bool) -> bool:
    result = _set_filter_enabled("UdpAllPorts", enabled)
    if result and not enabled:
        _reset_disabled_categories_strategies()
    return result


def get_all_wf_filters() -> dict:
    """Возвращает все настройки фильтров WinDivert"""
    return {
        'tcp_80': get_wf_tcp_80_enabled(),
        'tcp_443': get_wf_tcp_443_enabled(),
        'tcp_warp': get_wf_tcp_warp_enabled(),
        'tcp_all_ports': get_wf_tcp_all_ports_enabled(),
        'udp_443': get_wf_udp_443_enabled(),
        'udp_all_ports': get_wf_udp_all_ports_enabled(),
        'raw_discord_media': get_wf_raw_discord_media_enabled(),
        'raw_stun': get_wf_raw_stun_enabled(),
        'raw_wireguard': get_wf_raw_wireguard_enabled(),
    }

def set_all_wf_filters(filters: dict) -> bool:
    """Устанавливает все настройки фильтров WinDivert"""
    success = True
    if 'tcp_80' in filters:
        success &= set_wf_tcp_80_enabled(filters['tcp_80'])
    if 'tcp_443' in filters:
        success &= set_wf_tcp_443_enabled(filters['tcp_443'])
    if 'tcp_warp' in filters:
        success &= set_wf_tcp_warp_enabled(filters['tcp_warp'])
    if 'udp_443' in filters:
        success &= set_wf_udp_443_enabled(filters['udp_443'])
    if 'raw_discord_media' in filters:
        success &= set_wf_raw_discord_media_enabled(filters['raw_discord_media'])
    if 'raw_stun' in filters:
        success &= set_wf_raw_stun_enabled(filters['raw_stun'])
    if 'raw_wireguard' in filters:
        success &= set_wf_raw_wireguard_enabled(filters['raw_wireguard'])
    return success


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
            return True
    except:
        return False


# ==================== OUT-RANGE НАСТРОЙКИ ====================

OUT_RANGE_PATH = rf"{REGISTRY_PATH}\OutRange"

def _get_out_range_value(key_name: str, default: int = 10) -> int:
    """Получает значение out-range из реестра"""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, OUT_RANGE_PATH) as key:
            value, _ = winreg.QueryValueEx(key, key_name)
            return int(value)
    except:
        return default

def _set_out_range_value(key_name: str, value: int) -> bool:
    """Сохраняет значение out-range в реестр"""
    try:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, OUT_RANGE_PATH) as key:
            winreg.SetValueEx(key, key_name, 0, winreg.REG_DWORD, max(0, int(value)))
            return True
    except Exception as e:
        log(f"Ошибка сохранения OutRange {key_name}: {e}", "❌ ERROR")
        return False

def get_out_range_discord() -> int:
    """Возвращает значение out-range для Discord (по умолчанию 10)"""
    return _get_out_range_value("Discord", default=10)

def set_out_range_discord(value: int) -> bool:
    """Устанавливает значение out-range для Discord"""
    return _set_out_range_value("Discord", value)

def get_out_range_youtube() -> int:
    """Возвращает значение out-range для YouTube (по умолчанию 10)"""
    return _get_out_range_value("YouTube", default=10)

def set_out_range_youtube(value: int) -> bool:
    """Устанавливает значение out-range для YouTube"""
    return _set_out_range_value("YouTube", value)


# ==================== ВЫБОРЫ СТРАТЕГИЙ ====================

def invalidate_direct_selections_cache():
    """Сбрасывает кэш выборов стратегий"""
    global _direct_selections_cache_time
    _direct_selections_cache_time = 0


def get_direct_strategy_selections() -> dict:
    """
    Возвращает сохраненные выборы стратегий для прямого запуска.

    ✅ Кэширует результат на 5 секунд для быстрого доступа
    ✅ Валидирует каждый сохранённый strategy_id:
    - Если стратегия не найдена в реестре, использует значение по умолчанию
    - Логирует предупреждения о замене невалидных стратегий
    """
    import time
    global _direct_selections_cache, _direct_selections_cache_time

    # Проверяем кэш
    current_time = time.time()
    if _direct_selections_cache is not None and \
       current_time - _direct_selections_cache_time < DIRECT_SELECTIONS_CACHE_TTL:
        return _direct_selections_cache.copy()

    from .strategies_registry import registry

    try:
        selections = {}
        default_selections = registry.get_default_selections()
        invalid_count = 0

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
                        # Для direct_orchestra всегда "none", для direct - default из категории
                        method = get_strategy_launch_method()
                        if method == "direct_orchestra":
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
        method = get_strategy_launch_method()
        for key, default_value in default_selections.items():
            if key not in selections:
                # Для direct_orchestra по умолчанию все категории отключены
                if method == "direct_orchestra":
                    selections[key] = "none"
                else:
                    selections[key] = default_value

        # Сохраняем в кэш
        _direct_selections_cache = selections
        _direct_selections_cache_time = current_time

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

    strategy_key = _get_current_strategy_key()
    reg_key = _category_to_reg_key(category_key)
    value = reg(strategy_key, reg_key)

    if value:
        return value

    # Для direct_orchestra по умолчанию все категории отключены
    # (пользователь должен явно выбрать что включить)
    method = get_strategy_launch_method()
    if method == "direct_orchestra":
        return "none"

    # Для обычного direct возвращаем значение по умолчанию из категории
    category_info = registry.get_category_info(category_key)
    if category_info:
        return category_info.default_strategy

    return "none"


def set_direct_strategy_for_category(category_key: str, strategy_id: str) -> bool:
    """Сохраняет выбранную стратегию для категории"""
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
    'get_allzone_hostlist_enabled',
    'set_allzone_hostlist_enabled',
    'get_wssize_enabled',
    'set_wssize_enabled',
    'get_remove_hostlists_enabled',
    'set_remove_hostlists_enabled',
    'get_remove_ipsets_enabled',
    'set_remove_ipsets_enabled',
    
    # Out-range настройки
    'get_out_range_discord',
    'set_out_range_discord',
    'get_out_range_youtube',
    'set_out_range_youtube',
    
    # Debug log настройки
    'get_debug_log_enabled',
    'set_debug_log_enabled',
    
    # Выборы стратегий
    'DIRECT_STRATEGY_KEY',
    'get_direct_strategy_selections',
    'set_direct_strategy_selections',
    'get_direct_strategy_for_category',
    'set_direct_strategy_for_category',
    'invalidate_direct_selections_cache',

    # Инициализация DirectOrchestra
    'is_direct_orchestra_initialized',
    'set_direct_orchestra_initialized',
    'clear_direct_orchestra_strategies',

    # Оценки стратегий
    'get_all_strategy_ratings',
    'get_strategy_rating',
    'set_strategy_rating',
    'toggle_strategy_rating',
    'clear_all_strategy_ratings',
    'invalidate_ratings_cache',
    
    # Фильтры WinDivert
    'get_wf_tcp_80_enabled',
    'set_wf_tcp_80_enabled',
    'get_wf_tcp_443_enabled',
    'set_wf_tcp_443_enabled',
    'get_wf_tcp_warp_enabled',
    'set_wf_tcp_warp_enabled',
    'get_wf_tcp_all_ports_enabled',
    'set_wf_tcp_all_ports_enabled',
    'get_wf_udp_443_enabled',
    'set_wf_udp_443_enabled',
    'get_wf_udp_all_ports_enabled',
    'set_wf_udp_all_ports_enabled',
    'get_wf_raw_discord_media_enabled',
    'set_wf_raw_discord_media_enabled',
    'get_wf_raw_stun_enabled',
    'set_wf_raw_stun_enabled',
    'get_wf_raw_wireguard_enabled',
    'set_wf_raw_wireguard_enabled',
    'get_all_wf_filters',
    'set_all_wf_filters',
    
    # Алиасы для совместимости
    'save_direct_strategy_selection',
    'save_direct_strategy_selections',
    
    # Комбинирование стратегий
    'combine_strategies',
    'calculate_required_filters',
]

# Алиасы для совместимости со старым кодом
save_direct_strategy_selection = set_direct_strategy_for_category
save_direct_strategy_selections = set_direct_strategy_selections

# Импорт combine_strategies и calculate_required_filters из strategy_lists_separated
from strategy_menu.strategy_lists_separated import combine_strategies, calculate_required_filters