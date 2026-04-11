"""
Централизованный реестр всех стратегий и категорий.
Управляет импортом, метаданными и предоставляет единый интерфейс.

Стратегии загружаются из TXT (INI-подобный формат) в:
- {INDEXJSON_FOLDER}/strategies/builtin/*.txt - встроенные стратегии/категории
- {INDEXJSON_FOLDER}/strategies/user/*.txt - пользовательские стратегии (если используются)

Категории (base_filter*) берутся из:
- builtin/categories.txt (в папке установки/индекса)
- один общий пользовательский файл вне папки установки (чтобы обновления не затирали)
"""

from typing import Dict, Tuple, List, Optional, Any
from dataclasses import dataclass, field
import time
from log import log

# ==================== LAZY IMPORTS ====================

_strategies_cache = {}  # {(strategy_type, strategy_set): strategies_dict} - кешируем по типу и набору
_imported_types = set()  # Какие (type, set) пары уже загружены
_logged_missing_strategies = set()  # Чтобы не спамить логи одними и теми же предупреждениями
_current_strategy_set = None  # Текущий набор стратегий (например: basic/advanced/zapret1)
_failed_import_last_attempt_at = {}  # {(strategy_type, strategy_set): monotonic_time}
_failed_import_logged = set()  # {(strategy_type, strategy_set)}
_FAILED_IMPORT_RETRY_SECONDS = 1.0


def get_current_strategy_set() -> Optional[str]:
    """
    Возвращает текущий набор стратегий на основе метода запуска.

    Returns:
        "basic"/"advanced" для direct_zapret2,
        "zapret1" для direct_zapret1 и т.д.
    """
    from strategy_menu.strategy_set_resolver import get_current_strategy_set as _resolve_current_strategy_set

    return _resolve_current_strategy_set()


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
DISCORD_VOICE_FILTER = "--filter-l7=stun,discord"


def _load_strategies_from_json(strategy_type: str, strategy_set: Optional[str] = None) -> Dict:
    """
    Загружает стратегии из JSON файлов.
    Сначала builtin, потом user (user перезаписывает builtin).

    Args:
        strategy_type: Тип стратегий (tcp, udp, http80, discord_voice)
        strategy_set: Набор стратегий (например: basic/advanced/orchestra, None = стандартный)
    """
    try:
        from .strategy_loader import load_strategies_as_dict

        strategies = load_strategies_as_dict(strategy_type, strategy_set)
        if strategies:
            set_name = strategy_set or "стандартный"
            log(f"Загружено {len(strategies)} стратегий типа '{strategy_type}' (набор: {set_name})", "DEBUG")
            return strategies
    except Exception as e:
        log(f"Ошибка загрузки JSON стратегий типа '{strategy_type}': {e}", "WARNING")

    return {}


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

    # Avoid permanently caching an empty result: on first run / during updates
    # the strategies files may appear a bit later. Use a small backoff to avoid
    # hot-looping when the catalog is genuinely missing.
    try:
        now = time.monotonic()
    except Exception:
        now = 0.0
    last = _failed_import_last_attempt_at.get(cache_key, 0.0)
    if last and now and (now - last) < _FAILED_IMPORT_RETRY_SECONDS:
        return {}
    _failed_import_last_attempt_at[cache_key] = now or 0.0

    strategies = _load_strategies_from_json(strategy_type, strategy_set)

    if strategies:
        _strategies_cache[cache_key] = strategies
        _imported_types.add(cache_key)
        _failed_import_last_attempt_at.pop(cache_key, None)
        _failed_import_logged.discard(cache_key)
        return strategies

    # Don't mark as imported when load failed/returned empty: allow retry later.
    if cache_key not in _failed_import_logged:
        _failed_import_logged.add(cache_key)
        log(f"Не удалось загрузить стратегии типа '{strategy_type}'", "WARNING")
    return {}

def _lazy_import_all_strategies() -> Dict[str, Dict]:
    """Импортирует ВСЕ базовые стратегии (только если очень нужно)"""
    # Загружаем все типы
    for strategy_type in ["tcp", "udp", "http80", "discord_voice"]:
        _lazy_import_base_strategies(strategy_type)
    
    return _strategies_cache

# ==================== МЕТАДАННЫЕ КАТЕГОРИЙ ====================
@dataclass
class TargetInfo:
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
    
    # Фильтр для категории когда НЕТ выбора между режимами (единственный вариант)
    base_filter: str = ""
    # Фильтр для ipset режима (когда ЕСТЬ выбор между ipset и hostlist)
    base_filter_ipset: str = ""
    # Фильтр для hostlist режима (когда ЕСТЬ выбор между ipset и hostlist)
    base_filter_hostlist: str = ""
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


def _load_categories_from_json() -> Dict[str, TargetInfo]:
    """
    Загружает категории из JSON файлов и конвертирует в TargetInfo.
    
    Returns:
        Словарь {target_key: TargetInfo}
    """
    try:
        from .strategy_loader import load_categories

        raw_categories = load_categories()
        result = {}
        
        for key, data in raw_categories.items():
            try:
                cat_info = TargetInfo(
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
                    base_filter_ipset=data.get('base_filter_ipset', ''),
                    base_filter_hostlist=data.get('base_filter_hostlist', ''),
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
_categories_cache: Dict[str, TargetInfo] = {}
_categories_loaded = False


def _get_targets() -> Dict[str, TargetInfo]:
    """Получает категории из JSON"""
    global _categories_cache, _categories_loaded
    
    if not _categories_loaded:
        _categories_cache = _load_categories_from_json()
        _categories_loaded = True
        
        if not _categories_cache:
            log(
                "КРИТИЧЕСКАЯ ОШИБКА: Не удалось загрузить категории! "
                "Проверьте файл strategies/builtin/categories.txt",
                "ERROR",
            )
    
    return _categories_cache


def reload_targets():
    """Перезагружает категории из JSON"""
    global _categories_cache, _categories_loaded
    _categories_cache = {}
    _categories_loaded = False
    return _get_targets()

def get_target_icon(target_key: str):
    """Возвращает Font Awesome иконку для категории"""
    import qtawesome as qta
    
    targets = _get_targets()
    category = targets.get(target_key)
    if category:
        try:
            icon_name = category.icon_name
            if icon_name and icon_name.startswith(('fa5s.', 'fa5b.', 'fa.', 'mdi.')):
                return qta.icon(icon_name, color=category.icon_color)
        except Exception as e:
            log(f"Ошибка создания иконки для {target_key}: {e}", "⚠ WARNING")
    
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
    def _targets(self) -> Dict[str, TargetInfo]:
        """Получает категории (загружаются из JSON)"""
        return _get_targets()

    @property
    def _categories(self) -> Dict[str, TargetInfo]:
        """Legacy alias для старого orchestra/UI кода, который ещё читает registry._categories."""
        return self._targets

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
        reload_targets()

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

        log(f"✅ Перезагрузка завершена, категорий: {len(self._targets)}, типов стратегий: {len(_strategies_cache)}", "INFO")

    @property
    def strategies(self) -> Dict[str, Dict]:
        """
        Получение всех стратегий (загружает ВСЕ типы)
        ⚠️ Используйте get_target_strategies() для лучшей производительности
        """
        return _lazy_import_all_strategies()
    
    @property
    def targets(self) -> Dict[str, TargetInfo]:
        """Получение всех категорий"""
        return self._targets

    @property
    def categories(self) -> Dict[str, TargetInfo]:
        """Совместимый alias для legacy orchestra UI."""
        return self._targets

    def get_target_strategies(self, target_key: str) -> Dict[str, Any]:
        """Получить стратегии для категории"""
        target_info = self._targets.get(target_key)
        if not target_info:
            return {}
        return _lazy_import_base_strategies(target_info.strategy_type)

    def get_category_strategies(self, target_key: str) -> Dict[str, Any]:
        """Legacy alias: старый UI оркестра ожидает имя get_category_strategies()."""
        return self.get_target_strategies(target_key)
    
    def get_target_info(self, target_key: str) -> Optional[TargetInfo]:
        """Получить информацию о категории"""
        return self._targets.get(target_key)

    def get_strategy_args_safe(self, target_key: str, strategy_id: str) -> Optional[str]:
        """
        Получить полные аргументы стратегии.

        Логика:
        1. Если strategy_id == "none" - возвращаем пустую строку
        2. Для discord_voice - если args содержит --filter - используем как есть
        3. Для остальных - склеиваем base_filter + техника
        4. Если strip_payload=True - убираем --payload= из аргументов
        5. Учитывает filter_mode из настроек (hostlist/ipset)
        """
        # Проверка на none
        if strategy_id == "none":
            return ""

        target_info = self.get_target_info(target_key)
        if not target_info:
            log(f"Категория {target_key} не найдена", "⚠ WARNING")
            return None

        strategy_type = target_info.strategy_type

        # Выбираем base_filter на основе filter_mode из настроек (per-category)
        from strategy_menu.command_builder import get_filter_mode
        filter_mode = get_filter_mode(target_key)  # "hostlist" или "ipset"

        # Определяем какой фильтр использовать
        if target_info.base_filter_ipset and target_info.base_filter_hostlist:
            # Есть выбор между режимами - используем в зависимости от filter_mode
            if filter_mode == "hostlist":
                base_filter = target_info.base_filter_hostlist
            else:
                base_filter = target_info.base_filter_ipset
        else:
            # Нет выбора - используем base_filter (единственный вариант)
            base_filter = target_info.base_filter
        
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
        if target_info.strip_payload:
            # Lazy import для избежания циклического импорта
            from strategy_menu.command_builder import strip_payload_from_args
            base_args = strip_payload_from_args(base_args)
        
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

    def get_strategy_name_safe(self, target_key: str, strategy_id: str) -> str:
        """Получить имя стратегии"""
        if strategy_id == "none":
            return "⛔ Отключено"
        if strategy_id == "custom":
            return "Свой набор"
        
        target_info = self.get_target_info(target_key)
        if not target_info:
            return strategy_id or "Unknown"
        
        base_strategies = _lazy_import_base_strategies(target_info.strategy_type)
        strategy = base_strategies.get(strategy_id)
        
        # TCP multi-phase UI can store a strategy_id from tcp_fake.txt (e.g., hostfakesplit_multi).
        # Provide a name fallback so main lists don't show raw ids or "custom" unnecessarily.
        if not strategy and target_info.strategy_type == "tcp":
            try:
                from .strategy_loader import load_strategies_as_dict
                # В advanced-режиме tcp_fake берётся из advanced_strategies;
                # в остальных режимах используем обычный набор без отдельного strategy_set.
                current_set = get_current_strategy_set()
                fake_set = "advanced" if current_set == "advanced" else None
                fake_strategies = load_strategies_as_dict("tcp_fake", fake_set)
                strategy = (fake_strategies or {}).get(strategy_id)
            except Exception:
                strategy = None

        if strategy:
            return strategy.get('name', strategy_id)
        return strategy_id or "Unknown"
    
    def get_default_selections(self) -> Dict[str, str]:
        """Получить стратегии по умолчанию для всех категорий"""
        return {
            key: info.default_strategy
            for key, info in self._targets.items()
        }
    
    def get_none_strategies(self) -> Dict[str, str]:
        """Получить 'none' стратегии для всех категорий"""
        # Теперь для всех категорий используется единая стратегия "none"
        return {
            key: "none"
            for key in self._targets.keys()
        }

    def get_all_target_keys(self) -> List[str]:
        """Получить все ключи категорий в порядке сортировки"""
        return sorted(self._targets.keys(), key=lambda k: self._targets[k].order)
    
    def get_tab_names_dict(self) -> Dict[str, Tuple[str, str]]:
        """Получить словарь имен табов (полное, полное) - для совместимости"""
        return {
            key: (info.full_name, info.full_name)
            for key, info in self._targets.items()
        }
    
    def get_tab_tooltips_dict(self) -> Dict[str, str]:
        """Получить словарь подсказок для табов"""
        return {
            key: info.tooltip
            for key, info in self._targets.items()
        }
    
    def get_target_colors_dict(self) -> Dict[str, str]:
        """Получить словарь цветов для target."""
        return {
            key: info.color
            for key, info in self._targets.items()
        }

    def get_all_target_keys_by_command_order(self) -> List[str]:
        """Получить все ключи категорий в порядке командной строки (с кэшем)"""
        if self._sorted_keys_by_command_cache is None:
            self._sorted_keys_by_command_cache = sorted(
                self._targets.keys(),
                key=lambda k: self._targets[k].command_order
            )
        return self._sorted_keys_by_command_cache

    def get_all_target_keys_sorted(self) -> List[str]:
        """
        Получить все ключи категорий, отсортированных по order (с кэшем).
        Теперь все категории показываются, но некоторые могут быть заблокированы.

        Returns:
            Список всех ключей категорий, отсортированных по order
        """
        if self._sorted_keys_cache is None:
            self._sorted_keys_cache = sorted(
                self._targets.keys(),
                key=lambda k: self._targets[k].order
            )
        return self._sorted_keys_cache
    
# ==================== ГЛОБАЛЬНЫЙ ЭКЗЕМПЛЯР ====================

# Создаем глобальный экземпляр реестра
registry = StrategiesRegistry()

# ==================== ФУНКЦИИ СОВМЕСТИМОСТИ ====================

def get_strategies_registry() -> StrategiesRegistry:
    """Получить глобальный экземпляр реестра"""
    return registry

def get_target_strategies(target_key: str) -> Dict[str, Any]:
    """Совместимость: получить стратегии категории"""
    return registry.get_target_strategies(target_key)

def get_target_info(target_key: str) -> Optional[TargetInfo]:
    """Совместимость: получить информацию о категории"""
    return registry.get_target_info(target_key)

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
    'TargetInfo',
    'registry',
    'get_strategies_registry',
    'get_target_strategies',
    'get_target_info',
    'get_all_strategies',
    'get_tab_names',
    'get_tab_tooltips',
    'get_default_selections',
    'get_target_icon',
    'reload_targets',
    # Strategy set
    'get_current_strategy_set',
    'set_strategy_set',
]
