"""Ленивая точка входа orchestra.

Runner и связанные константы не нужны при каждом `import orchestra`.
Поэтому экспортируем их лениво, чтобы не тянуть раннер раньше времени.
"""

from __future__ import annotations

from importlib import import_module

__all__ = [
    "OrchestraRunner",
    "DEFAULT_WHITELIST_DOMAINS",
    "REGISTRY_ORCHESTRA",
    "MAX_ORCHESTRA_LOGS",
]


def __getattr__(name: str):
    if name not in __all__:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    module = import_module(".orchestra_runner", __name__)
    value = getattr(module, name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
