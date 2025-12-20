# dns/__init__.py
"""
Единая точка входа в DNS библиотеку (Win32 API версия).

Доступны:
    DNSManager                 – менеджер DNS на Win32 API (быстрый)
    DEFAULT_EXCLUSIONS         – список исключаемых адаптеров
    refresh_exclusion_cache()  – сброс кэша исключений
    _normalize_alias()         – нормализация имени адаптера

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
    _normalize_alias,
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
    "_normalize_alias",
    
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

# ══════════════════════════════════════════════════════════════════════
#  Обратная совместимость (опционально)
# ══════════════════════════════════════════════════════════════════════


# Если старый код использует AsyncDNSForceManager (теперь не нужен)
class AsyncDNSForceManager(DNSForceManager):
    """
    Устаревший класс для обратной совместимости.
    Теперь DNSForceManager сам по себе достаточно быстрый (Win32 API).
    """
    def __init__(self, *args, **kwargs):
        import warnings
        warnings.warn(
            "AsyncDNSForceManager устарел. Используйте DNSForceManager напрямую.",
            DeprecationWarning,
            stacklevel=2
        )
        super().__init__(*args, **kwargs)

# Устаревшая функция
def apply_force_dns_if_enabled_async(callback=None):
    """
    Устаревшая функция для обратной совместимости.
    Используйте DNSUIManager.apply_dns_settings_async() вместо этого.
    """
    import warnings
    warnings.warn(
        "apply_force_dns_if_enabled_async устарела. "
        "Используйте DNSUIManager.apply_dns_settings_async().",
        DeprecationWarning,
        stacklevel=2
    )
    
    # Простая реализация для совместимости
    manager = DNSForceManager()
    if manager.is_force_dns_enabled():
        success, total = manager.force_dns_on_all_adapters()
        if callback:
            callback(success > 0)
        return True
    return False

# Добавляем в __all__ для обратной совместимости
__all__ += (
    "AsyncDNSForceManager",
    "apply_force_dns_if_enabled_async",
)
