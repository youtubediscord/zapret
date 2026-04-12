# dns/__init__.py
"""
Единая точка входа в DNS библиотеку (Win32 API версия).

Доступны:
    DNSManager                 – менеджер DNS на Win32 API (быстрый)
    DEFAULT_EXCLUSIONS         – список исключаемых адаптеров
    refresh_exclusion_cache()  – сброс кэша исключений

    DNSForceManager            – менеджер принудительного DNS
    ensure_default_force_dns() – создание ключа ForceDNS по умолчанию

    DNS_PROVIDERS              – словарь провайдеров DNS (категоризированный)

    DNSUIManager               – менеджер UI для DNS операций
    DNSStartupManager          – менеджер DNS при запуске
    SafeDNSWorker              – воркер для фоновых операций

Все модули оптимизированы для работы с Win32 API.
"""

from __future__ import annotations

# ══════════════════════════════════════════════════════════════════════
#  Импорты из dns_core (Win32 API)
# ══════════════════════════════════════════════════════════════════════
from .dns_core import (
    DNSManager,
    DEFAULT_EXCLUSIONS,
    refresh_exclusion_cache,
    # Низкоуровневые функции (опционально)
    get_adapters_info_native,
    set_dns_via_registry,
    flush_dns_cache_native,
)

# ══════════════════════════════════════════════════════════════════════
#  Импорты из dns_force (упрощенная версия)
# ══════════════════════════════════════════════════════════════════════
from .dns_force import (
    DNSForceManager,
    ensure_default_force_dns,
)

# ══════════════════════════════════════════════════════════════════════
#  Импорты из dns_providers (список провайдеров)
# ══════════════════════════════════════════════════════════════════════
from .dns_providers import DNS_PROVIDERS

# ══════════════════════════════════════════════════════════════════════
#  Импорты из dns_worker (упрощенные воркеры)
# ══════════════════════════════════════════════════════════════════════
from .dns_worker import (
    SafeDNSWorker,
    DNSUIManager,
    DNSStartupManager,
)

# ══════════════════════════════════════════════════════════════════════
#  Экспорт
# ══════════════════════════════════════════════════════════════════════

__all__ = (
    # Core
    "DNSManager",
    "DEFAULT_EXCLUSIONS",
    "refresh_exclusion_cache",
    
    # Низкоуровневые функции
    "get_adapters_info_native",
    "set_dns_via_registry",
    "flush_dns_cache_native",
    
    # Force DNS
    "DNSForceManager",
    "ensure_default_force_dns",
    
    # Providers
    "DNS_PROVIDERS",
    
    # Workers
    "SafeDNSWorker",
    "DNSUIManager",
    "DNSStartupManager",
)

# ══════════════════════════════════════════════════════════════════════
#  Информация о версии
# ══════════════════════════════════════════════════════════════════════

__version__ = "2.0.0"  # Версия с Win32 API
__author__ = "ZapretReg2 Team"
__description__ = "DNS management library based on Win32 API"

# ══════════════════════════════════════════════════════════════════════
#  Утилиты для dir()
# ══════════════════════════════════════════════════════════════════════

def __dir__():
    """Показывает все доступные элементы модуля"""
    return sorted(list(__all__) + list(globals().keys()))
