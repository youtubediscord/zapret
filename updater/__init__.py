"""
updater/__init__.py
────────────────────────────────────────────────────────────────
Модуль обновления программы

ПРИМЕЧАНИЕ: Автообновление при запуске ОТКЛЮЧЕНО.
Обновления проверяются и устанавливаются только через вкладку "Серверы" (ui/pages/servers_page.py)
"""

from .release_manager import (
    get_latest_release,
    invalidate_cache,
    get_cache_info,
    get_release_manager,
    get_vps_block_info
)
from .rate_limiter import UpdateRateLimiter

__all__ = [
    'get_latest_release',
    'invalidate_cache',
    'get_cache_info',
    'get_release_manager',
    'get_vps_block_info',
    'UpdateRateLimiter'
]
