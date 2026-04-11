"""Публичная точка входа donater с ленивыми экспортами.

Важно: не импортируем тяжёлые подпакеты сразу на уровне модуля.
Иначе даже простой импорт `donater.premium_worker` сначала выполняет
`donater.__init__`, который может потянуть сетевой стек и внешние зависимости.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

__all__ = [
    "DonateChecker",
    "PremiumService",
    "get_premium_service",
    "PremiumStorage",
]

if TYPE_CHECKING:
    from .donate import DonateChecker
    from .service import PremiumService, get_premium_service
    from .storage import PremiumStorage


def __getattr__(name: str):
    if name == "DonateChecker":
        from .donate import DonateChecker

        return DonateChecker
    if name == "PremiumService":
        from .service import PremiumService

        return PremiumService
    if name == "get_premium_service":
        from .service import get_premium_service

        return get_premium_service
    if name == "PremiumStorage":
        from .storage import PremiumStorage

        return PremiumStorage
    raise AttributeError(name)
