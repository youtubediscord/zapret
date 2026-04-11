"""Ленивые экспорты страниц главного окна.

Важно: пакет `ui.pages` не должен eagerly импортировать все страницы сразу.
Главное окно загружает страницы по прямым путям вроде `ui.pages.network_page`,
и если `__init__.py` тянет весь пакет целиком, то первая lazy-инициализация
любой страницы фактически импортирует десятки чужих модулей и их зависимости.

Это ломает изоляцию lazy-загрузки, ухудшает старт и может показывать ошибку
не той страницы, которая реально открывалась первой.
"""

from __future__ import annotations

from importlib import import_module


_PAGE_EXPORTS: dict[str, tuple[str, str]] = {
    "ControlPage": (".control_page", "ControlPage"),
    "Zapret2OrchestraStrategiesPage": (".zapret2_orchestra_strategies_page", "Zapret2OrchestraStrategiesPage"),
    "Zapret2DirectControlPage": (".zapret2", "Zapret2DirectControlPage"),
    "Zapret2PresetDetailPage": (".zapret2", "Zapret2PresetDetailPage"),
    "Zapret2StrategiesPageNew": (".zapret2", "Zapret2StrategiesPageNew"),
    "Zapret2UserPresetsPage": (".zapret2", "Zapret2UserPresetsPage"),
    "StrategyDetailPage": (".zapret2", "StrategyDetailPage"),
    "Zapret1DirectControlPage": (".zapret1", "Zapret1DirectControlPage"),
    "Zapret1PresetDetailPage": (".zapret1", "Zapret1PresetDetailPage"),
    "Zapret1StrategiesPage": (".zapret1", "Zapret1StrategiesPage"),
    "Zapret1UserPresetsPage": (".zapret1", "Zapret1UserPresetsPage"),
    "HostlistPage": (".hostlist_page", "HostlistPage"),
    "IpsetPage": (".ipset_page", "IpsetPage"),
    "BlobsPage": (".blobs_page", "BlobsPage"),
    "DpiSettingsPage": (".dpi_settings_page", "DpiSettingsPage"),
    "AutostartPage": (".autostart_page", "AutostartPage"),
    "NetworkPage": (".network_page", "NetworkPage"),
    "HostsPage": (".hosts_page", "HostsPage"),
    "AppearancePage": (".appearance_page", "AppearancePage"),
    "AboutPage": (".about_page", "AboutPage"),
    "SupportPage": (".support_page", "SupportPage"),
    "LogsPage": (".logs_page", "LogsPage"),
    "PremiumPage": (".premium_page", "PremiumPage"),
    "BlockcheckPage": (".blockcheck_page", "BlockcheckPage"),
    "ServersPage": (".servers_page", "ServersPage"),
    "CustomDomainsPage": (".custom_domains_page", "CustomDomainsPage"),
    "CustomIpSetPage": (".custom_ipset_page", "CustomIpSetPage"),
    "NetrogatPage": (".netrogat_page", "NetrogatPage"),
    "ConnectionTestPage": (".connection_page", "ConnectionTestPage"),
    "DNSCheckPage": (".dns_check_page", "DNSCheckPage"),
    "OrchestraPage": (".orchestra", "OrchestraPage"),
    "OrchestraSettingsPage": (".orchestra", "OrchestraSettingsPage"),
    "OrchestraLockedPage": (".orchestra", "OrchestraLockedPage"),
    "OrchestraBlockedPage": (".orchestra", "OrchestraBlockedPage"),
    "OrchestraWhitelistPage": (".orchestra", "OrchestraWhitelistPage"),
    "OrchestraRatingsPage": (".orchestra", "OrchestraRatingsPage"),
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
