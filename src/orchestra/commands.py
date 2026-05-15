from __future__ import annotations

from orchestra.blocked_strategies_manager import ASKEY_ALL


def create_loaded_locked_manager():
    from orchestra.locked_strategies_manager import LockedStrategiesManager

    manager = LockedStrategiesManager()
    manager.load()
    return manager


def create_loaded_blocked_manager():
    from orchestra.blocked_strategies_manager import BlockedStrategiesManager

    manager = BlockedStrategiesManager()
    manager.load()
    return manager


def is_default_blocked_pass_domain(hostname: str) -> bool:
    from orchestra.blocked_strategies_manager import is_default_blocked_pass_domain as _is_default

    return bool(_is_default(hostname))


def get_whitelist_snapshot(orchestra_runner=None, *, whitelist_service, refresh: bool = False):
    return whitelist_service.get_snapshot(
        orchestra_runner,
        refresh=refresh,
    )


def add_whitelist_domain(orchestra_runner, domain: str, *, whitelist_service) -> bool:
    return bool(whitelist_service.add_domain(orchestra_runner, domain))


def remove_whitelist_domain(orchestra_runner, domain: str, *, whitelist_service) -> bool:
    return bool(whitelist_service.remove_domain(orchestra_runner, domain))


def clear_whitelist_user_domains(orchestra_runner, domains: list[str], *, whitelist_service) -> int:
    return int(whitelist_service.clear_user_domains(orchestra_runner, domains))
