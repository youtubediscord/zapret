# launcher_common/port_filters.py
"""
Конфигурация фильтров портов и их связь с target'ами legacy registry-слоя.

Этот модуль определяет:
- Какие фильтры доступны (TCP 80, TCP 443, UDP 443 и т.д.)
- Какие target'ы требуют какие фильтры
- Функции для управления фильтрами и target'ами
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

def get_filter_for_target(target_info) -> Set[str]:
    """
    Определяет какие фильтры нужны для данного target'а.

    Args:
        target_info: TargetInfo объект с полями protocol, ports, strategy_type, requires_all_ports

    Returns:
        Set[str] - множество ключей фильтров (например {'tcp_80', 'tcp_443'})
    """
    required_filters = set()

    if not target_info:
        return required_filters

    protocol = target_info.protocol.upper() if target_info.protocol else ""
    ports_str = target_info.ports.lower() if target_info.ports else ""
    strategy_type = target_info.strategy_type if target_info.strategy_type else ""
    requires_all = getattr(target_info, 'requires_all_ports', False)
    target_key = target_info.key if hasattr(target_info, 'key') else ""

    # === Raw-фильтры для discord_voice ===
    if strategy_type == "discord_voice":
        required_filters.add('raw_discord')
        required_filters.add('raw_stun')
        required_filters.add('raw_wireguard')
        return required_filters

    # === HTTP80 target'ы ===
    if strategy_type == "http80":
        required_filters.add('tcp_80')
        return required_filters

    # === WARP target'ы (TCP 443, 853) ===
    is_warp = "warp" in target_key.lower() or strategy_type == "warp"
    if is_warp and "TCP" in protocol:
        required_filters.add('tcp_warp')
        required_filters.add('tcp_443')
        return required_filters

    # === Определяем протокол ===
    is_tcp = "TCP" in protocol
    is_udp = "UDP" in protocol or "QUIC" in protocol

    # === Парсим порты ===
    has_80 = "80" in ports_str
    has_443 = "443" in ports_str
    has_6568 = "6568" in ports_str or target_key == "anydesk_tcp"
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


def get_targets_for_filter(filter_key: str) -> List[str]:
    """
    Возвращает список target'ов, которые требуют данный фильтр.

    Args:
        filter_key: Ключ фильтра (например 'tcp_443')

    Returns:
        List[str] - список ключей target'ов
    """
    from strategy_menu.strategies_registry import registry

    targets = []
    all_target_keys = registry.get_all_target_keys()

    for target_key in all_target_keys:
        target_info = registry.get_target_info(target_key)
        if target_info:
            required_filters = get_filter_for_target(target_info)
            if filter_key in required_filters:
                targets.append(target_key)

    return targets


def build_filter_to_targets_map() -> Dict[str, List[str]]:
    """
    Строит полный маппинг: фильтр → список target'ов.

    Returns:
        Dict[str, List[str]] - {filter_key: [target_key, ...]}
    """
    filter_map = {key: [] for key in FILTERS.keys()}

    from strategy_menu.strategies_registry import registry
    all_target_keys = registry.get_all_target_keys()

    for target_key in all_target_keys:
        target_info = registry.get_target_info(target_key)
        if target_info:
            required_filters = get_filter_for_target(target_info)
            for filter_key in required_filters:
                if filter_key in filter_map:
                    filter_map[filter_key].append(target_key)

    return filter_map


def build_target_to_filters_map() -> Dict[str, Set[str]]:
    """
    Строит полный маппинг: target → набор фильтров.

    Returns:
        Dict[str, Set[str]] - {target_key: {filter_key, ...}}
    """
    target_map = {}

    from strategy_menu.strategies_registry import registry
    all_target_keys = registry.get_all_target_keys()

    for target_key in all_target_keys:
        target_info = registry.get_target_info(target_key)
        if target_info:
            target_map[target_key] = get_filter_for_target(target_info)
        else:
            target_map[target_key] = set()

    return target_map


def log_filter_category_map():
    """Выводит в лог полный маппинг фильтров и target'ов (для отладки)."""
    filter_map = build_filter_to_targets_map()

    log("=== МАППИНГ ФИЛЬТРОВ → TARGET'Ы ===", "DEBUG")
    for filter_key, targets in filter_map.items():
        filter_info = FILTERS.get(filter_key, {})
        filter_name = filter_info.get('name', filter_key)
        if targets:
            log(f"  {filter_name}: {', '.join(targets)}", "DEBUG")
        else:
            log(f"  {filter_name}: (нет target'ов)", "DEBUG")
