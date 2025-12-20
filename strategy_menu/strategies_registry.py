"""
Централизованный реестр всех стратегий и категорий.
Управляет импортом, метаданными и предоставляет единый интерфейс.

Стратегии и категории загружаются из JSON файлов:
- {INDEXJSON_FOLDER}/strategies/builtin/*.json - встроенные стратегии и категории
- {INDEXJSON_FOLDER}/strategies/user/*.json - пользовательские стратегии и категории

Категории (вкладки сервисов) теперь загружаются из categories.json,
что позволяет пользователям добавлять свои сервисы без редактирования кода.
"""

from typing import Dict, Tuple, List, Optional, Any
from dataclasses import dataclass, field
from log import log

# ==================== LAZY IMPORTS ====================

_strategies_cache = {}  # {(strategy_type, strategy_set): strategies_dict} - кешируем по типу и набору
_imported_types = set()  # Какие (type, set) пары уже загружены
_logged_missing_strategies = set()  # Чтобы не спамить логи одними и теми же предупреждениями
_current_strategy_set = None  # Текущий набор стратегий (None = стандартный, "orchestra" и т.д.)


def get_current_strategy_set() -> Optional[str]:
    """
    Возвращает текущий набор стратегий на основе метода запуска.

    Returns:
        None для стандартного набора, "orchestra" для direct_orchestra и т.д.
    """
    try:
        from strategy_menu import get_strategy_launch_method
        method = get_strategy_launch_method()

        # Маппинг метода запуска на набор стратегий
        method_to_set = {
            "direct": None,           # стандартный набор (tcp.json)
            "direct_orchestra": "orchestra",  # tcp_orchestra.json
            "bat": None,              # BAT не использует JSON стратегии
            "orchestra": None,        # Orchestra использует свой механизм
        }
        return method_to_set.get(method, None)
    except Exception:
        return None


def set_strategy_set(strategy_set: Optional[str]):
    """
    Принудительно устанавливает набор стратегий (для тестирования).
    Сбрасывает кэш при смене набора.
    """
    global _current_strategy_set, _strategies_cache, _imported_types

    if _current_strategy_set != strategy_set:
        _current_strategy_set = strategy_set
        # Сбрасываем кэш при смене набора
        _strategies_cache.clear()
        _imported_types.clear()
        log(f"Набор стратегий изменён на: {strategy_set or 'стандартный'}", "INFO")


# ==================== КОНСТАНТЫ ФИЛЬТРОВ ====================

# Discord Voice фильтр (используется в base_filter)
DISCORD_VOICE_FILTER = "--filter-l7=discord,stun"


def _load_strategies_from_json(strategy_type: str, strategy_set: str = None) -> Dict:
    """
    Загружает стратегии из JSON файлов.
    Сначала builtin, потом user (user перезаписывает builtin).

    Args:
        strategy_type: Тип стратегий (tcp, udp, http80, discord_voice)
        strategy_set: Набор стратегий (None = стандартный, "orchestra" и т.д.)
    """
    try:
        from .strategies.strategy_loader import load_strategies_as_dict
        strategies = load_strategies_as_dict(strategy_type, strategy_set)
        if strategies:
            set_name = strategy_set or "стандартный"
            log(f"Загружено {len(strategies)} стратегий типа '{strategy_type}' (набор: {set_name})", "DEBUG")
            return strategies
    except Exception as e:
        log(f"Ошибка загрузки JSON стратегий типа '{strategy_type}': {e}", "WARNING")

    return {}


# Кэш для strip_payload результатов (оптимизация - избегаем повторных regex)
_strip_payload_cache: Dict[str, str] = {}


def _strip_payload_from_args(args: str) -> str:
    """
    Удаляет --payload=... из аргументов стратегии.

    Используется для IPset категорий без фильтра портов,
    чтобы стратегия применялась ко ВСЕМУ трафику, а не только к TLS/HTTP.

    Args:
        args: Строка аргументов стратегии

    Returns:
        Строка аргументов без --payload=
    """
    # Кэширование для оптимизации
    if args in _strip_payload_cache:
        return _strip_payload_cache[args]

    import re

    # Убираем --payload=... (например: --payload=tls_client_hello или --payload=http_req)
    result = re.sub(r'--payload=[^\s]+\s*', '', args)

    # Также убираем --filter-l7=... если есть (это фильтр по типу трафика)
    result = re.sub(r'--filter-l7=[^\s]+\s*', '', result)

    # Очищаем множественные пробелы
    result = ' '.join(result.split())

    # Кэшируем результат
    _strip_payload_cache[args] = result

    return result


def _lazy_import_base_strategies(strategy_type: str) -> Dict:
    """
    Ленивый импорт базовых стратегий по типу из JSON файлов.
    Учитывает текущий набор стратегий (strategy_set).
    """
    global _strategies_cache, _imported_types

    # Получаем текущий набор стратегий
    strategy_set = get_current_strategy_set()
    cache_key = (strategy_type, strategy_set)

    if cache_key in _imported_types:
        return _strategies_cache.get(cache_key, {})

    strategies = _load_strategies_from_json(strategy_type, strategy_set)

    if strategies:
        _strategies_cache[cache_key] = strategies
        _imported_types.add(cache_key)
        return strategies

    log(f"Не удалось загрузить стратегии типа '{strategy_type}'", "WARNING")
    _imported_types.add(cache_key)
    return {}

def _lazy_import_all_strategies() -> Dict[str, Dict]:
    """Импортирует ВСЕ базовые стратегии (только если очень нужно)"""
    # Загружаем все типы
    for strategy_type in ["tcp", "udp", "http80", "discord_voice"]:
        _lazy_import_base_strategies(strategy_type)
    
    return _strategies_cache

# ==================== МЕТАДАННЫЕ КАТЕГОРИЙ ====================
@dataclass
class CategoryInfo:
    """Информация о категории стратегий"""
    key: str
    full_name: str
    description: str
    tooltip: str
    color: str
    default_strategy: str
    ports: str
    protocol: str
    order: int
    command_order: int
    needs_new_separator: bool = False
    command_group: str = "default"
    icon_name: str = 'fa5s.globe'
    icon_color: str = '#2196F3'
    
    # Фильтр для категории (hostlist, ipset, filter-tcp/udp)
    base_filter: str = ""
    # Тип базовых стратегий: "tcp", "udp", "http80", "discord_voice"
    strategy_type: str = "tcp"
    # Требует ли категория агрессивного режима (все порты)
    # True = скрывается в аккуратных режимах
    requires_all_ports: bool = False
    # Убирать --payload из стратегий (для IPset категорий без фильтра портов)
    # Если True - стратегия применяется ко ВСЕМУ трафику, не только к TLS
    strip_payload: bool = False
    # Источник категории: 'builtin' или 'user'
    _source: str = field(default='builtin', repr=False)


def _load_categories_from_json() -> Dict[str, CategoryInfo]:
    """
    Загружает категории из JSON файлов и конвертирует в CategoryInfo.
    
    Returns:
        Словарь {category_key: CategoryInfo}
    """
    try:
        from .strategies.strategy_loader import load_categories
        
        raw_categories = load_categories()
        result = {}
        
        for key, data in raw_categories.items():
            try:
                cat_info = CategoryInfo(
                    key=data.get('key', key),
                    full_name=data.get('full_name', key),
                    description=data.get('description', ''),
                    tooltip=data.get('tooltip', ''),
                    color=data.get('color', '#2196F3'),
                    default_strategy=data.get('default_strategy', 'none'),
                    ports=data.get('ports', '443'),
                    protocol=data.get('protocol', 'TCP'),
                    order=data.get('order', 999),
                    command_order=data.get('command_order', 999),
                    needs_new_separator=data.get('needs_new_separator', False),
                    command_group=data.get('command_group', 'default'),
                    icon_name=data.get('icon_name', 'fa5s.globe'),
                    icon_color=data.get('icon_color', '#2196F3'),
                    base_filter=data.get('base_filter', ''),
                    strategy_type=data.get('strategy_type', 'tcp'),
                    requires_all_ports=data.get('requires_all_ports', False),
                    strip_payload=data.get('strip_payload', False),
                    _source=data.get('_source', 'builtin')
                )
                result[key] = cat_info
            except Exception as e:
                log(f"Ошибка загрузки категории '{key}': {e}", "WARNING")
        
        if result:
            log(f"Загружено {len(result)} категорий из JSON", "INFO")
            return result
        
    except Exception as e:
        log(f"Ошибка загрузки категорий из JSON: {e}", "WARNING")
    
    # Возвращаем пустой словарь если не удалось загрузить
    return {}


# Кеш загруженных категорий
_categories_cache: Dict[str, CategoryInfo] = {}
_categories_loaded = False


def _get_categories() -> Dict[str, CategoryInfo]:
    """Получает категории из JSON"""
    global _categories_cache, _categories_loaded
    
    if not _categories_loaded:
        _categories_cache = _load_categories_from_json()
        _categories_loaded = True
        
        if not _categories_cache:
            log("КРИТИЧЕСКАЯ ОШИБКА: Не удалось загрузить категории из JSON! Проверьте файл strategies/builtin/categories.json", "ERROR")
    
    return _categories_cache


def reload_categories():
    """Перезагружает категории из JSON"""
    global _categories_cache, _categories_loaded
    _categories_cache = {}
    _categories_loaded = False
    return _get_categories()

# Режимы которые требуют агрессивной фильтрации (все порты)
AGGRESSIVE_MODES = {"windivert_all", "wf-l3-all"}
# Режимы аккуратной фильтрации (ограниченные порты)
CAREFUL_MODES = {"windivert-discord-media-stun-sites", "wf-l3"}

def get_category_icon(category_key: str):
    """Возвращает Font Awesome иконку для категории"""
    import qtawesome as qta
    
    categories = _get_categories()
    category = categories.get(category_key)
    if category:
        try:
            icon_name = category.icon_name
            if icon_name and icon_name.startswith(('fa5s.', 'fa5b.', 'fa.', 'mdi.')):
                return qta.icon(icon_name, color=category.icon_color)
        except Exception as e:
            log(f"Ошибка создания иконки для {category_key}: {e}", "⚠ WARNING")
    
    # Безопасный fallback
    try:
        return qta.icon('fa5s.globe', color='#2196F3')
    except:
        return None
    
# ==================== ОСНОВНЫЕ ФУНКЦИИ ====================

class StrategiesRegistry:
    """Главный класс для управления всеми стратегиями"""

    def __init__(self):
        # Категории загружаются динамически из JSON
        # Кэш отсортированных ключей категорий
        self._sorted_keys_cache = None
        self._sorted_keys_by_command_cache = None

    @property
    def _categories(self) -> Dict[str, CategoryInfo]:
        """Получает категории (загружаются из JSON)"""
        return _get_categories()

    def reload_strategies(self):
        """
        Перезагружает все стратегии из JSON файлов.
        Очищает кеш и заставляет перечитать файлы с диска.
        """
        global _strategies_cache, _imported_types, _logged_missing_strategies

        log("🔄 Перезагрузка стратегий и категорий из JSON...", "INFO")

        # Очищаем все кеши
        _strategies_cache.clear()
        _imported_types.clear()
        _logged_missing_strategies.clear()

        # Сбрасываем кэш отсортированных ключей
        self._sorted_keys_cache = None
        self._sorted_keys_by_command_cache = None

        # Перезагружаем категории
        reload_categories()

        # Получаем текущий набор стратегий
        strategy_set = get_current_strategy_set()
        set_name = strategy_set or "стандартный"

        # Принудительно загружаем все типы стратегий
        for strategy_type in ["tcp", "udp", "http80", "discord_voice"]:
            strategies = _load_strategies_from_json(strategy_type, strategy_set)
            if strategies:
                cache_key = (strategy_type, strategy_set)
                _strategies_cache[cache_key] = strategies
                _imported_types.add(cache_key)
                log(f"✅ Перезагружено {len(strategies)} стратегий типа '{strategy_type}' (набор: {set_name})", "DEBUG")

        log(f"✅ Перезагрузка завершена, категорий: {len(self._categories)}, типов стратегий: {len(_strategies_cache)}", "INFO")

    @property
    def strategies(self) -> Dict[str, Dict]:
        """
        Получение всех стратегий (загружает ВСЕ типы)
        ⚠️ Используйте get_category_strategies() для лучшей производительности
        """
        return _lazy_import_all_strategies()
    
    @property
    def categories(self) -> Dict[str, CategoryInfo]:
        """Получение всех категорий"""
        return self._categories

    def get_category_strategies(self, category_key: str) -> Dict[str, Any]:
        """Получить стратегии для категории"""
        category_info = self._categories.get(category_key)
        if not category_info:
            return {}
        return _lazy_import_base_strategies(category_info.strategy_type)
    
    def get_category_info(self, category_key: str) -> Optional[CategoryInfo]:
        """Получить информацию о категории"""
        return self._categories.get(category_key)

    def get_strategy_args_safe(self, category_key: str, strategy_id: str) -> Optional[str]:
        """
        Получить полные аргументы стратегии.
        
        Логика:
        1. Если strategy_id == "none" - возвращаем пустую строку
        2. Для discord_voice - если args содержит --filter - используем как есть
        3. Для остальных - склеиваем base_filter + техника
        4. Если strip_payload=True - убираем --payload= из аргументов
        """
        # Проверка на none
        if strategy_id == "none":
            return ""
        
        category_info = self.get_category_info(category_key)
        if not category_info:
            log(f"Категория {category_key} не найдена", "⚠ WARNING")
            return None
        
        strategy_type = category_info.strategy_type
        base_filter = category_info.base_filter
        
        # Получаем стратегию из BASE файла
        base_strategies = _lazy_import_base_strategies(strategy_type)
        strategy = base_strategies.get(strategy_id)
        
        if not strategy:
            # Логируем только один раз за сессию (чтобы не спамить)
            warn_key = f"{strategy_type}:{strategy_id}"
            if warn_key not in _logged_missing_strategies:
                _logged_missing_strategies.add(warn_key)
                log(f"Стратегия {strategy_id} не найдена в типе {strategy_type}", "DEBUG")
            return None
        
        base_args = strategy.get("args", "")
        
        # Если args пустой - категория отключена
        if not base_args:
            return ""
        
        # ✅ Если strip_payload=True - убираем --payload= из аргументов
        # Это нужно для IPset категорий без фильтра портов,
        # чтобы стратегия применялась ко ВСЕМУ трафику, а не только к TLS
        if category_info.strip_payload:
            base_args = _strip_payload_from_args(base_args)
        
        # Для discord_voice - проверяем, содержит ли args уже фильтры
        if strategy_type == "discord_voice":
            if "--filter-" in base_args or "--new" in base_args:
                # Сложная стратегия с полной командой
                return base_args
            # Простая стратегия - добавляем base_filter

        # Склеиваем: base_filter + техника
        if base_filter and base_args:
            return f"{base_filter} {base_args}"
        elif base_filter:
            return base_filter
        else:
            return base_args

    def get_strategy_name_safe(self, category_key: str, strategy_id: str) -> str:
        """Получить имя стратегии"""
        if strategy_id == "none":
            return "⛔ Отключено"
        
        category_info = self.get_category_info(category_key)
        if not category_info:
            return strategy_id or "Unknown"
        
        base_strategies = _lazy_import_base_strategies(category_info.strategy_type)
        strategy = base_strategies.get(strategy_id)
        
        if strategy:
            return strategy.get('name', strategy_id)
        return strategy_id or "Unknown"
    
    def get_default_selections(self) -> Dict[str, str]:
        """Получить стратегии по умолчанию для всех категорий"""
        return {
            key: info.default_strategy
            for key, info in self._categories.items()
        }
    
    def get_none_strategies(self) -> Dict[str, str]:
        """Получить 'none' стратегии для всех категорий"""
        # Теперь для всех категорий используется единая стратегия "none"
        return {
            key: "none"
            for key in self._categories.keys()
        }

    def get_all_category_keys(self) -> List[str]:
        """Получить все ключи категорий в порядке сортировки"""
        return sorted(self._categories.keys(), key=lambda k: self._categories[k].order)
    
    def get_tab_names_dict(self) -> Dict[str, Tuple[str, str]]:
        """Получить словарь имен табов (полное, полное) - для совместимости"""
        return {
            key: (info.full_name, info.full_name)
            for key, info in self._categories.items()
        }
    
    def get_tab_tooltips_dict(self) -> Dict[str, str]:
        """Получить словарь подсказок для табов"""
        return {
            key: info.tooltip
            for key, info in self._categories.items()
        }
    
    def get_category_colors_dict(self) -> Dict[str, str]:
        """Получить словарь цветов для категорий"""
        return {
            key: info.color
            for key, info in self._categories.items()
        }

    def get_all_category_keys_by_command_order(self) -> List[str]:
        """Получить все ключи категорий в порядке командной строки (с кэшем)"""
        if self._sorted_keys_by_command_cache is None:
            self._sorted_keys_by_command_cache = sorted(
                self._categories.keys(),
                key=lambda k: self._categories[k].command_order
            )
        return self._sorted_keys_by_command_cache

    def get_all_category_keys_sorted(self) -> List[str]:
        """
        Получить все ключи категорий, отсортированных по order (с кэшем).
        Теперь все категории показываются, но некоторые могут быть заблокированы.

        Returns:
            Список всех ключей категорий, отсортированных по order
        """
        if self._sorted_keys_cache is None:
            self._sorted_keys_cache = sorted(
                self._categories.keys(),
                key=lambda k: self._categories[k].order
            )
        return self._sorted_keys_cache
    
    def is_category_blocked(self, category_key: str, base_args_mode: str) -> bool:
        """
        Проверяет, заблокирована ли категория для данного режима фильтрации.
        Заблокированные категории показываются полупрозрачными с курсором 🚫.
        
        Args:
            category_key: Ключ категории
            base_args_mode: Режим фильтрации ('windivert-discord-media-stun-sites', 'wf-l3', 
                           'windivert_all', 'wf-l3-all')
        
        Returns:
            True если категория заблокирована (полупрозрачная, нельзя выбрать)
        """
        category_info = self._categories.get(category_key)
        if not category_info:
            return True  # Неизвестные категории блокируем
        
        is_careful_mode = base_args_mode in CAREFUL_MODES
        
        # Если аккуратный режим и категория требует все порты - блокируем
        if is_careful_mode and category_info.requires_all_ports:
            return True
        
        return False
    
    def get_blocked_categories_for_mode(self, base_args_mode: str) -> List[str]:
        """
        Возвращает список заблокированных категорий для данного режима.
        
        Args:
            base_args_mode: Режим фильтрации
            
        Returns:
            Список ключей заблокированных категорий
        """
        is_careful_mode = base_args_mode in CAREFUL_MODES
        
        if not is_careful_mode:
            return []
        
        return [
            key for key, info in self._categories.items()
            if info.requires_all_ports
        ]
    
    def is_category_enabled_by_filters(self, category_key: str) -> bool:
        """
        Проверяет, включена ли категория на основе текущих настроек фильтров.
        Возвращает True если категория должна быть видна.
        """
        from strategy_menu import (
            get_wf_tcp_80_enabled, get_wf_tcp_443_enabled,
            get_wf_tcp_warp_enabled, get_wf_udp_443_enabled,
            get_wf_tcp_all_ports_enabled, get_wf_udp_all_ports_enabled,
            get_wf_raw_discord_media_enabled, get_wf_raw_stun_enabled
        )

        category_info = self._categories.get(category_key)
        if not category_info:
            return False

        protocol = category_info.protocol
        base_filter = category_info.base_filter
        requires_all = category_info.requires_all_ports
        strategy_type = category_info.strategy_type if category_info.strategy_type else ""

        # HTTP 80 port (все категории с strategy_type="http80")
        if strategy_type == "http80":
            return get_wf_tcp_80_enabled()

        # WARP категории (TCP 443, 853)
        is_warp = "warp" in category_key.lower() or strategy_type == "warp"
        if is_warp and protocol == 'TCP':
            return get_wf_tcp_warp_enabled()

        # Discord Voice UDP (raw filters)
        if category_key == 'discord_voice_udp':
            return get_wf_raw_discord_media_enabled() or get_wf_raw_stun_enabled()

        # YouTube QUIC - теперь зависит от UDP 443 (дублирование с QUIC Initial убрано)
        if category_key == 'youtube_udp':
            return get_wf_udp_443_enabled()

        # UDP категории
        if protocol in ('UDP', 'QUIC/UDP'):
            # UDP 443 (QUIC) - udp_discord и другие
            if '443' in category_info.ports and not requires_all:
                return get_wf_udp_443_enabled()
            # UDP all ports - игры и ipset (все не-443 порты)
            return get_wf_udp_all_ports_enabled()

        # TCP категории
        if protocol == 'TCP':
            # TCP all ports - ipset категории
            if requires_all:
                return get_wf_tcp_all_ports_enabled()
            # TCP 443 - основные категории
            return get_wf_tcp_443_enabled()

        return True
    
    def get_enabled_category_keys(self) -> List[str]:
        """Получить ключи категорий, включенных по текущим фильтрам"""
        enabled = []
        for key in self._categories.keys():
            if self.is_category_enabled_by_filters(key):
                enabled.append(key)
        return sorted(enabled, key=lambda k: self._categories[k].order)

# ==================== ГЛОБАЛЬНЫЙ ЭКЗЕМПЛЯР ====================

# Создаем глобальный экземпляр реестра
registry = StrategiesRegistry()

# ==================== ФУНКЦИИ СОВМЕСТИМОСТИ ====================

def get_strategies_registry() -> StrategiesRegistry:
    """Получить глобальный экземпляр реестра"""
    return registry

def get_category_strategies(category_key: str) -> Dict[str, Any]:
    """Совместимость: получить стратегии категории"""
    return registry.get_category_strategies(category_key)

def get_category_info(category_key: str) -> Optional[CategoryInfo]:
    """Совместимость: получить информацию о категории"""
    return registry.get_category_info(category_key)

def get_all_strategies() -> Dict[str, Dict]:
    """Совместимость: получить все стратегии"""
    return registry.strategies

def get_tab_names() -> Dict[str, Tuple[str, str]]:
    """Совместимость: получить имена табов"""
    return registry.get_tab_names_dict()

def get_tab_tooltips() -> Dict[str, str]:
    """Совместимость: получить подсказки табов"""
    return registry.get_tab_tooltips_dict()

def get_default_selections() -> Dict[str, str]:
    """Совместимость: получить стратегии по умолчанию"""
    return registry.get_default_selections()

# ==================== ЭКСПОРТ ====================

__all__ = [
    'StrategiesRegistry',
    'CategoryInfo',
    'AGGRESSIVE_MODES',
    'CAREFUL_MODES',
    'registry',
    'get_strategies_registry',
    'get_category_strategies',
    'get_category_info',
    'get_all_strategies',
    'get_tab_names',
    'get_tab_tooltips',
    'get_default_selections',
    'get_category_icon',
    'is_category_enabled_by_filters',
    'get_enabled_category_keys',
    'reload_categories',
    'is_category_blocked',
    'get_blocked_categories_for_mode',
    # Strategy set
    'get_current_strategy_set',
    'set_strategy_set',
]

def is_category_enabled_by_filters(category_key: str) -> bool:
    """Совместимость: проверить включена ли категория по фильтрам"""
    return registry.is_category_enabled_by_filters(category_key)

def get_enabled_category_keys() -> List[str]:
    """Совместимость: получить включенные категории"""
    return registry.get_enabled_category_keys()

def is_category_blocked(category_key: str, base_args_mode: str) -> bool:
    """Совместимость: проверить заблокирована ли категория для режима"""
    return registry.is_category_blocked(category_key, base_args_mode)

def get_blocked_categories_for_mode(base_args_mode: str) -> List[str]:
    """Совместимость: получить список заблокированных категорий для режима"""
    return registry.get_blocked_categories_for_mode(base_args_mode)