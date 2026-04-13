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
    "ControlPage": (".control_page", "ControlPage"),
    "Zapret2DirectControlPage": ("direct_preset.ui.control.zapret2.page", "Zapret2DirectControlPage"),
    "Zapret2PresetDetailPage": ("direct_preset.ui.zapret2.preset_detail_page", "Zapret2PresetDetailPage"),
    "Zapret2StrategiesPageNew": ("filters.pages.direct_zapret2_targets_page", "Zapret2StrategiesPageNew"),
    "Zapret2UserPresetsPage": ("direct_preset.ui.zapret2.user_presets_page", "Zapret2UserPresetsPage"),
    "StrategyDetailPage": ("filters.strategy_detail.zapret2.page", "StrategyDetailPage"),
    "Zapret1DirectControlPage": ("direct_preset.ui.control.zapret1.page", "Zapret1DirectControlPage"),
    "Zapret1PresetDetailPage": ("direct_preset.ui.zapret1.preset_detail_page", "Zapret1PresetDetailPage"),
    "Zapret1StrategiesPage": ("filters.pages.direct_zapret1_targets_page", "Zapret1StrategiesPage"),
    "Zapret1StrategyDetailPage": ("filters.strategy_detail.zapret1.page", "Zapret1StrategyDetailPage"),
    "Zapret1UserPresetsPage": ("direct_preset.ui.zapret1.user_presets_page", "Zapret1UserPresetsPage"),
    "HostlistPage": ("lists.ui.hostlist_page", "HostlistPage"),
    "IpsetPage": ("lists.ui.ipset_page", "IpsetPage"),
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
    "DNSCheckPage": ("dns.ui.dns_check_page", "DNSCheckPage"),
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
