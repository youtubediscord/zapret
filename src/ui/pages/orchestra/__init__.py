"""Ленивые экспорты orchestra UI pages."""

from __future__ import annotations

from importlib import import_module


_PAGE_EXPORTS: dict[str, tuple[str, str]] = {
    "OrchestraPage": (".orchestra_page", "OrchestraPage"),
    "OrchestraSettingsPage": (".orchestra_settings_page", "OrchestraSettingsPage"),
    "OrchestraLockedPage": (".locked_page", "OrchestraLockedPage"),
    "OrchestraBlockedPage": (".blocked_page", "OrchestraBlockedPage"),
    "OrchestraWhitelistPage": (".whitelist_page", "OrchestraWhitelistPage"),
    "OrchestraRatingsPage": (".ratings_page", "OrchestraRatingsPage"),
}

__all__ = list(_PAGE_EXPORTS)


def __getattr__(name: str):
    spec = _PAGE_EXPORTS.get(name)
    if spec is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    module_name, attr_name = spec
    module = import_module(module_name, __name__)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
