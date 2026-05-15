"""
updater
────────────────────────────────────────────────────────────────
Ленивые экспорты update-слоя.

Важно: пакет не должен тянуть `release_manager` и сетевые зависимости уже при
самом факте `import updater` или `import updater.rate_limiter`.
Иначе даже косвенный импорт runtime/UI-страниц начинает требовать `requests`
и другие heavy-зависимости раньше реальной проверки обновлений.
"""

from __future__ import annotations

from importlib import import_module


_EXPORTS: dict[str, tuple[str, str]] = {
    "get_latest_release": (".release_manager", "get_latest_release"),
    "invalidate_cache": (".release_manager", "invalidate_cache"),
    "get_cache_info": (".release_manager", "get_cache_info"),
    "get_release_manager": (".release_manager", "get_release_manager"),
    "get_vps_block_info": (".release_manager", "get_vps_block_info"),
    "UpdateRateLimiter": (".rate_limiter", "UpdateRateLimiter"),
}

__all__ = list(_EXPORTS)


def __getattr__(name: str):
    spec = _EXPORTS.get(name)
    if spec is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    module_name, attr_name = spec
    module = import_module(module_name, __name__)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
