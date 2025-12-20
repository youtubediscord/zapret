# config/__init__.py
from .config import (
    BIN_FOLDER, EXE_FOLDER, LUA_FOLDER, THEME_FOLDER, BAT_FOLDER, LISTS_FOLDER,
    LOGS_FOLDER, WINWS_EXE, WINWS2_EXE, ICON_PATH, ICON_TEST_PATH, OTHER_PATH,
    OTHER2_PATH, NETROGAT_PATH, NETROGAT2_PATH, STRATEGIES_FOLDER, WIDTH, HEIGHT,
    INDEXJSON_FOLDER, DEFAULT_STRAT, REG_LATEST_STRATEGY, WINDIVERT_FILTER,
    MAX_LOG_FILES, MAX_DEBUG_LOG_FILES, MAIN_DIRECTORY, HELP_FOLDER, PROGRAMDATA_PATH,
    # Пути реестра
    REGISTRY_PATH, REGISTRY_PATH_AUTOSTART, REGISTRY_PATH_GUI,
    REGISTRY_PATH_DIRECT, REGISTRY_PATH_STRATEGIES, REGISTRY_PATH_WINDOW,
    # Функции окна
    get_window_position, set_window_position, get_window_size, set_window_size,
    # Функции настроек анимации
    get_wall_animation_enabled, set_wall_animation_enabled,
    # Функции определения exe по методу
    ZAPRET2_MODES, get_winws_exe_for_method, is_zapret2_mode
)
from .build_info import APP_VERSION, CHANNEL
from .reg import reg, HKCU, get_last_strategy, set_last_strategy, get_last_bat_strategy, set_last_bat_strategy, get_dpi_autostart, set_dpi_autostart, get_subscription_check_interval, get_remove_github_api, get_active_hosts_domains, set_active_hosts_domains, get_auto_update_enabled, set_auto_update_enabled, get_tray_hint_shown, set_tray_hint_shown

__all__ = [
    # build_info.py
    'APP_VERSION',
    'CHANNEL',
    # config.py - папки
    'THEME_FOLDER',
    'EXE_FOLDER',
    'BIN_FOLDER',
    'LUA_FOLDER',
    'BAT_FOLDER',
    'LISTS_FOLDER',
    'LOGS_FOLDER',
    'INDEXJSON_FOLDER',
    'WINDIVERT_FILTER',
    'MAIN_DIRECTORY',
    'HELP_FOLDER',
    'PROGRAMDATA_PATH',
    # config.py - пути реестра
    'REGISTRY_PATH',
    'REGISTRY_PATH_AUTOSTART',
    'REGISTRY_PATH_GUI',
    'REGISTRY_PATH_DIRECT',
    'REGISTRY_PATH_STRATEGIES',
    'REGISTRY_PATH_WINDOW',
    # config.py - остальное
    'REG_LATEST_STRATEGY',
    'DEFAULT_STRAT',
    'WINWS_EXE',
    'WINWS2_EXE',
    'ZAPRET2_MODES',
    'get_winws_exe_for_method',
    'is_zapret2_mode',
    'ICON_PATH',
    'ICON_TEST_PATH',
    'OTHER_PATH',
    'OTHER2_PATH',
    'NETROGAT_PATH',
    'NETROGAT2_PATH',
    'STRATEGIES_FOLDER',
    'MAX_LOG_FILES',
    'MAX_DEBUG_LOG_FILES',
    'WIDTH',
    'HEIGHT',
    # reg.py
    'get_last_strategy',  # УСТАРЕВШАЯ - используйте get_last_bat_strategy
    'set_last_strategy',  # УСТАРЕВШАЯ - используйте set_last_bat_strategy
    'get_last_bat_strategy',
    'set_last_bat_strategy',
    'get_dpi_autostart',
    'set_dpi_autostart',
    'get_subscription_check_interval',
    'get_remove_github_api',
    'get_active_hosts_domains',
    'set_active_hosts_domains',
    'get_auto_update_enabled',
    'set_auto_update_enabled',
    'get_tray_hint_shown',
    'set_tray_hint_shown',
    'get_window_position',
    'set_window_position',
    'get_window_size',
    'set_window_size',
    'get_wall_animation_enabled',
    'set_wall_animation_enabled',
    'reg',
    'HKCU'
]