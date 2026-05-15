"""Ленивые экспорты страниц главного окна.

Важно: пакет `ui.pages` не должен eagerly импортировать все страницы сразу.
Главное окно загружает страницы по прямым путям вроде `ui.pages.appearance_page`,
и если `__init__.py` тянет весь пакет целиком, то первая lazy-инициализация
любой страницы фактически импортирует десятки чужих модулей и их зависимости.

Это ломает изоляцию lazy-загрузки, ухудшает старт и может показывать ошибку
не той страницы, которая реально открывалась первой.
"""

from __future__ import annotations

from importlib import import_module


_PAGE_EXPORTS: dict[str, tuple[str, str]] = {
    "Zapret2ModeControlPage": ("presets.ui.control.zapret2.page", "Zapret2ModeControlPage"),
    "Zapret2PresetSetupPage": ("profile.ui.preset_setup_page", "Zapret2PresetSetupPage"),
    "Zapret2UserPresetsPage": ("presets.ui.zapret2.user_presets_page", "Zapret2UserPresetsPage"),
    "Zapret2ProfileSetupPage": ("profile.ui.profile_setup_page", "Zapret2ProfileSetupPage"),
    "Zapret1ModeControlPage": ("presets.ui.control.zapret1.page", "Zapret1ModeControlPage"),
    "Zapret1PresetSetupPage": ("profile.ui.preset_setup_page", "Zapret1PresetSetupPage"),
    "Zapret1ProfileSetupPage": ("profile.ui.profile_setup_page", "Zapret1ProfileSetupPage"),
    "Zapret1UserPresetsPage": ("presets.ui.zapret1.user_presets_page", "Zapret1UserPresetsPage"),
    "HostlistPage": ("lists.ui.hostlist_page", "HostlistPage"),
    "BlobsPage": ("blobs.ui.page", "BlobsPage"),
    "DpiSettingsPage": ("settings.dpi.page", "DpiSettingsPage"),
    "AutostartPage": ("autostart.ui.page", "AutostartPage"),
    "NetworkPage": ("dns.ui.page", "NetworkPage"),
    "HostsPage": ("hosts.ui.page", "HostsPage"),
    "AppearancePage": (".appearance_page", "AppearancePage"),
    "AboutPage": (".about_page", "AboutPage"),
    "SupportPage": (".support_page", "SupportPage"),
    "LogsPage": ("log.ui.page", "LogsPage"),
    "PremiumPage": ("donater.ui.page", "PremiumPage"),
    "BlockcheckPage": ("blockcheck.ui.page", "BlockcheckPage"),
    "ServersPage": ("updater.ui.page", "ServersPage"),
    "CustomDomainsPage": ("lists.ui.custom_domains_page", "CustomDomainsPage"),
    "CustomIpSetPage": ("lists.ui.custom_ipset_page", "CustomIpSetPage"),
    "NetrogatPage": ("lists.ui.netrogat_page", "NetrogatPage"),
    "ConnectionTestPage": ("diagnostics.ui.page", "ConnectionTestPage"),
    "OrchestraPage": ("orchestra.ui.page", "OrchestraPage"),
    "OrchestraSettingsPage": ("orchestra.ui.settings_page", "OrchestraSettingsPage"),
    "OrchestraLockedPage": ("orchestra.ui.locked_page", "OrchestraLockedPage"),
    "OrchestraBlockedPage": ("orchestra.ui.blocked_page", "OrchestraBlockedPage"),
    "OrchestraWhitelistPage": ("orchestra.ui.whitelist_page", "OrchestraWhitelistPage"),
    "OrchestraRatingsPage": ("orchestra.ui.ratings_page", "OrchestraRatingsPage"),
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
