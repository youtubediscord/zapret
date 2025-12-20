# strategy_menu/filters_config.py
"""
Конфигурация фильтров портов и их связь с категориями.

Этот модуль определяет:
- Какие фильтры доступны (TCP 80, TCP 443, UDP 443 и т.д.)
- Какие категории требуют какие фильтры
- Функции для управления фильтрами и категориями
"""

from typing import Dict, List, Set
from log import log


# ═══════════════════════════════════════════════════════════════════════════════
# КОНФИГУРАЦИЯ ФИЛЬТРОВ
# ═══════════════════════════════════════════════════════════════════════════════

FILTERS = {
    # TCP фильтры
    'tcp_80': {
        'name': 'Port 80 (HTTP)',
        'description': 'Перехват HTTP трафика',
        'protocol': 'TCP',
        'ports': ['80'],
        'icon': 'fa5s.globe',
        'color': '#4CAF50',
        'warning': None,
    },
    'tcp_443': {
        'name': 'Port 443 (HTTPS/TLS)',
        'description': 'Перехват HTTPS трафика',
        'protocol': 'TCP',
        'ports': ['443'],
        'icon': 'fa5s.lock',
        'color': '#4CAF50',
        'warning': None,
    },
    'tcp_6568': {
        'name': 'Port 6568 (AnyDesk)',
        'description': 'Перехват AnyDesk трафика',
        'protocol': 'TCP',
        'ports': ['6568'],
        'icon': 'fa5s.desktop',
        'color': '#4CAF50',
        'warning': None,
        'special_categories': ['anydesk_tcp'],  # Только для этих категорий
    },
    'tcp_all_ports': {
        'name': 'Ports 444-65535 (game filter)',
        'description': 'Перехват всех TCP портов',
        'protocol': 'TCP',
        'ports': ['444-65535'],
        'icon': 'fa5s.bolt',
        'color': '#ff9800',
        'warning': 'Высокая нагрузка на CPU',
    },

    # UDP фильтры
    'udp_443': {
        'name': 'Port 443 (QUIC)',
        'description': 'YouTube QUIC и HTTP/3',
        'protocol': 'UDP',
        'ports': ['443'],
        'icon': 'fa5s.fire',
        'color': '#ff9800',
        'warning': None,
    },
    'tcp_warp': {
        'name': 'Ports 443, 853 (WARP)',
        'description': 'Cloudflare WARP VPN',
        'protocol': 'TCP',
        'ports': ['443', '853'],
        'icon': 'fa5s.cloud',
        'color': '#F48120',
        'warning': None,
        'special_categories': ['warp_tcp'],  # Только для категорий warp
    },
    'udp_all_ports': {
        'name': 'Ports 444-65535 (game filter)',
        'description': 'Перехват всех UDP портов',
        'protocol': 'UDP',
        'ports': ['444-65535'],
        'icon': 'fa5s.bolt',
        'color': '#f44336',
        'warning': 'Очень высокая нагрузка на CPU',
    },

    # Raw-part фильтры (не по портам, а по сигнатурам)
    'raw_discord': {
        'name': 'Discord Media',
        'description': 'Голосовые каналы Discord',
        'protocol': 'RAW',
        'ports': [],
        'icon': 'mdi.discord',
        'color': '#7289da',
        'warning': None,
        'strategy_types': ['discord_voice'],  # Для категорий с этим strategy_type
    },
    'raw_stun': {
        'name': 'STUN (голосовые звонки)',
        'description': 'Discord, Telegram звонки',
        'protocol': 'RAW',
        'ports': [],
        'icon': 'fa5s.phone',
        'color': '#00bcd4',
        'warning': None,
        'strategy_types': ['discord_voice'],
    },
    'raw_wireguard': {
        'name': 'WireGuard (VPN)',
        'description': 'Обход блокировки VPN',
        'protocol': 'RAW',
        'ports': [],
        'icon': 'fa5s.shield-alt',
        'color': '#e91e63',
        'warning': None,
        'strategy_types': ['discord_voice'],
    },
}


# ═══════════════════════════════════════════════════════════════════════════════
# ФУНКЦИИ ДЛЯ РАБОТЫ С ФИЛЬТРАМИ И КАТЕГОРИЯМИ
# ═══════════════════════════════════════════════════════════════════════════════

def get_filter_for_category(category_info) -> Set[str]:
    """
    Определяет какие фильтры нужны для данной категории.

    Args:
        category_info: CategoryInfo объект с полями protocol, ports, strategy_type, requires_all_ports

    Returns:
        Set[str] - множество ключей фильтров (например {'tcp_80', 'tcp_443'})
    """
    required_filters = set()

    if not category_info:
        return required_filters

    protocol = category_info.protocol.upper() if category_info.protocol else ""
    ports_str = category_info.ports.lower() if category_info.ports else ""
    strategy_type = category_info.strategy_type if category_info.strategy_type else ""
    requires_all = getattr(category_info, 'requires_all_ports', False)
    category_key = category_info.key if hasattr(category_info, 'key') else ""

    # === Raw-фильтры для discord_voice ===
    if strategy_type == "discord_voice":
        required_filters.add('raw_discord')
        required_filters.add('raw_stun')
        required_filters.add('raw_wireguard')
        return required_filters

    # === WARP категории (TCP 443, 853) ===
    is_warp = "warp" in category_key.lower() or strategy_type == "warp"
    if is_warp and "TCP" in protocol:
        required_filters.add('tcp_warp')
        return required_filters

    # === Определяем протокол ===
    is_tcp = "TCP" in protocol
    is_udp = "UDP" in protocol or "QUIC" in protocol

    # === Парсим порты ===
    has_80 = "80" in ports_str
    has_443 = "443" in ports_str
    has_6568 = "6568" in ports_str or category_key == "anydesk_tcp"
    has_all_ports = requires_all or "65535" in ports_str or "*" in ports_str

    # === Устанавливаем фильтры ===
    if is_tcp:
        if has_80:
            required_filters.add('tcp_80')
        if has_443:
            required_filters.add('tcp_443')
        if has_6568:
            required_filters.add('tcp_6568')
        if has_all_ports:
            required_filters.add('tcp_all_ports')

    if is_udp:
        if has_443:
            required_filters.add('udp_443')
        if has_all_ports:
            required_filters.add('udp_all_ports')

    return required_filters


def get_categories_for_filter(filter_key: str) -> List[str]:
    """
    Возвращает список категорий, которые требуют данный фильтр.

    Args:
        filter_key: Ключ фильтра (например 'tcp_443')

    Returns:
        List[str] - список ключей категорий
    """
    from .strategies_registry import registry

    categories = []
    all_category_keys = registry.get_all_category_keys()

    for category_key in all_category_keys:
        category_info = registry.get_category_info(category_key)
        if category_info:
            required_filters = get_filter_for_category(category_info)
            if filter_key in required_filters:
                categories.append(category_key)

    return categories


def build_filter_to_categories_map() -> Dict[str, List[str]]:
    """
    Строит полный маппинг: фильтр → список категорий.

    Returns:
        Dict[str, List[str]] - {filter_key: [category_key, ...]}
    """
    filter_map = {key: [] for key in FILTERS.keys()}

    from .strategies_registry import registry
    all_category_keys = registry.get_all_category_keys()

    for category_key in all_category_keys:
        category_info = registry.get_category_info(category_key)
        if category_info:
            required_filters = get_filter_for_category(category_info)
            for filter_key in required_filters:
                if filter_key in filter_map:
                    filter_map[filter_key].append(category_key)

    return filter_map


def build_category_to_filters_map() -> Dict[str, Set[str]]:
    """
    Строит полный маппинг: категория → набор фильтров.

    Returns:
        Dict[str, Set[str]] - {category_key: {filter_key, ...}}
    """
    category_map = {}

    from .strategies_registry import registry
    all_category_keys = registry.get_all_category_keys()

    for category_key in all_category_keys:
        category_info = registry.get_category_info(category_key)
        if category_info:
            category_map[category_key] = get_filter_for_category(category_info)
        else:
            category_map[category_key] = set()

    return category_map


def get_categories_to_disable_on_filter_off(filter_key: str, current_selections: dict) -> List[str]:
    """
    Возвращает список категорий, которые нужно отключить при выключении фильтра.

    Возвращает только те категории, которые сейчас активны (не "none").

    Args:
        filter_key: Ключ фильтра который отключается
        current_selections: Текущие выборы категорий {category_key: strategy_id}

    Returns:
        List[str] - список категорий для отключения
    """
    categories_for_filter = get_categories_for_filter(filter_key)
    categories_to_disable = []

    for category_key in categories_for_filter:
        strategy_id = current_selections.get(category_key, "none")
        if strategy_id and strategy_id != "none":
            categories_to_disable.append(category_key)

    return categories_to_disable


def log_filter_category_map():
    """Выводит в лог полный маппинг фильтров и категорий (для отладки)."""
    filter_map = build_filter_to_categories_map()

    log("=== МАППИНГ ФИЛЬТРОВ → КАТЕГОРИИ ===", "DEBUG")
    for filter_key, categories in filter_map.items():
        filter_info = FILTERS.get(filter_key, {})
        filter_name = filter_info.get('name', filter_key)
        if categories:
            log(f"  {filter_name}: {', '.join(categories)}", "DEBUG")
        else:
            log(f"  {filter_name}: (нет категорий)", "DEBUG")
