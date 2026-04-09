from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from ui.page_names import PageName


PAGE_CLASS_SPECS: dict[PageName, tuple[str, str, str]] = {
    PageName.CONTROL: ("control_page", "ui.pages.control_page", "ControlPage"),
    PageName.ZAPRET2_DIRECT_CONTROL: (
        "zapret2_direct_control_page",
        "ui.pages.zapret2.direct_control_page",
        "Zapret2DirectControlPage",
    ),
    PageName.ZAPRET2_DIRECT: (
        "zapret2_strategies_page",
        "ui.pages.zapret2.direct_zapret2_page",
        "Zapret2StrategiesPageNew",
    ),
    PageName.ZAPRET2_STRATEGY_DETAIL: (
        "strategy_detail_page",
        "ui.pages.zapret2.strategy_detail_page",
        "StrategyDetailPage",
    ),
    PageName.ZAPRET2_PRESET_DETAIL: (
        "zapret2_preset_detail_page",
        "ui.pages.zapret2.preset_detail_page",
        "Zapret2PresetDetailPage",
    ),
    PageName.ZAPRET2_ORCHESTRA: (
        "zapret2_orchestra_strategies_page",
        "ui.pages.zapret2_orchestra_strategies_page",
        "Zapret2OrchestraStrategiesPage",
    ),
    PageName.ZAPRET2_ORCHESTRA_CONTROL: (
        "orchestra_zapret2_control_page",
        "ui.pages.orchestra_zapret2.direct_control_page",
        "OrchestraZapret2DirectControlPage",
    ),
    PageName.ZAPRET2_ORCHESTRA_USER_PRESETS: (
        "orchestra_zapret2_user_presets_page",
        "ui.pages.orchestra_zapret2.user_presets_page",
        "OrchestraZapret2UserPresetsPage",
    ),
    PageName.ZAPRET2_ORCHESTRA_STRATEGY_DETAIL: (
        "orchestra_strategy_detail_page",
        "ui.pages.orchestra_zapret2.strategy_detail_page",
        "OrchestraZapret2StrategyDetailPage",
    ),
    PageName.ZAPRET2_ORCHESTRA_PRESET_DETAIL: (
        "orchestra_zapret2_preset_detail_page",
        "ui.pages.orchestra_zapret2.preset_detail_page",
        "OrchestraZapret2PresetDetailPage",
    ),
    PageName.ZAPRET1_DIRECT_CONTROL: (
        "zapret1_direct_control_page",
        "ui.pages.zapret1.direct_control_page",
        "Zapret1DirectControlPage",
    ),
    PageName.ZAPRET1_DIRECT: (
        "zapret1_strategies_page",
        "ui.pages.zapret1.direct_zapret1_page",
        "Zapret1StrategiesPage",
    ),
    PageName.ZAPRET1_USER_PRESETS: (
        "zapret1_user_presets_page",
        "ui.pages.zapret1.user_presets_page",
        "Zapret1UserPresetsPage",
    ),
    PageName.ZAPRET1_STRATEGY_DETAIL: (
        "zapret1_strategy_detail_page",
        "ui.pages.zapret1.strategy_detail_page_v1",
        "Zapret1StrategyDetailPage",
    ),
    PageName.ZAPRET1_PRESET_DETAIL: (
        "zapret1_preset_detail_page",
        "ui.pages.zapret1.preset_detail_page",
        "Zapret1PresetDetailPage",
    ),
    PageName.HOSTLIST: ("hostlist_page", "ui.pages.hostlist_page", "HostlistPage"),
    PageName.BLOBS: ("blobs_page", "ui.pages.blobs_page", "BlobsPage"),
    PageName.DPI_SETTINGS: ("dpi_settings_page", "ui.pages.dpi_settings_page", "DpiSettingsPage"),
    PageName.ZAPRET2_USER_PRESETS: (
        "zapret2_user_presets_page",
        "ui.pages.zapret2.user_presets_page",
        "Zapret2UserPresetsPage",
    ),
    PageName.NETROGAT: ("netrogat_page", "ui.pages.netrogat_page", "NetrogatPage"),
    PageName.CUSTOM_DOMAINS: ("custom_domains_page", "ui.pages.custom_domains_page", "CustomDomainsPage"),
    PageName.CUSTOM_IPSET: ("custom_ipset_page", "ui.pages.custom_ipset_page", "CustomIpSetPage"),
    PageName.AUTOSTART: ("autostart_page", "ui.pages.autostart_page", "AutostartPage"),
    PageName.NETWORK: ("network_page", "ui.pages.network_page", "NetworkPage"),
    PageName.HOSTS: ("hosts_page", "ui.pages.hosts_page", "HostsPage"),
    PageName.BLOCKCHECK: ("blockcheck_page", "ui.pages.blockcheck_page", "BlockcheckPage"),
    PageName.APPEARANCE: ("appearance_page", "ui.pages.appearance_page", "AppearancePage"),
    PageName.PREMIUM: ("premium_page", "ui.pages.premium_page", "PremiumPage"),
    PageName.LOGS: ("logs_page", "ui.pages.logs_page", "LogsPage"),
    PageName.SERVERS: ("servers_page", "ui.pages.servers_page", "ServersPage"),
    PageName.ABOUT: ("about_page", "ui.pages.about_page", "AboutPage"),
    PageName.SUPPORT: ("support_page", "ui.pages.support_page", "SupportPage"),
    PageName.ORCHESTRA: (
        "orchestra_page",
        "ui.pages.orchestra.orchestra_page",
        "OrchestraPage",
    ),
    PageName.ORCHESTRA_SETTINGS: (
        "orchestra_settings_page",
        "ui.pages.orchestra.orchestra_settings_page",
        "OrchestraSettingsPage",
    ),
    PageName.TELEGRAM_PROXY: (
        "telegram_proxy_page",
        "ui.pages.telegram_proxy_page",
        "TelegramProxyPage",
    ),
}

PAGE_ALIASES: dict[PageName, PageName] = {}

EAGER_PAGE_NAMES_BASE: tuple[PageName, ...] = ()

EAGER_MODE_ENTRY_PAGE: dict[str, PageName] = {
    "direct_zapret2": PageName.ZAPRET2_DIRECT_CONTROL,
    "direct_zapret2_orchestra": PageName.ZAPRET2_ORCHESTRA_CONTROL,
    "direct_zapret1": PageName.ZAPRET1_DIRECT_CONTROL,
    "orchestra": PageName.ORCHESTRA,
}


@dataclass(frozen=True, slots=True)
class PagePerformanceProfile:
    page_kind: str
    warmup_policy: str
    first_show_budget_ms: int
    repeat_show_budget_ms: int


def _profile(kind: str, warmup_policy: str, first_show_budget_ms: int, repeat_show_budget_ms: int = 40) -> PagePerformanceProfile:
    return PagePerformanceProfile(
        page_kind=kind,
        warmup_policy=warmup_policy,
        first_show_budget_ms=int(first_show_budget_ms),
        repeat_show_budget_ms=int(repeat_show_budget_ms),
    )


PAGE_PERFORMANCE_PROFILES: dict[PageName, PagePerformanceProfile] = {
    PageName.CONTROL: _profile("heavy_list", "module", 200),
    PageName.ZAPRET2_DIRECT_CONTROL: _profile("heavy_list", "module", 200),
    PageName.ZAPRET2_DIRECT: _profile("heavy_list", "module", 200),
    PageName.ZAPRET2_STRATEGY_DETAIL: _profile("heavy_list", "none", 200),
    PageName.ZAPRET2_PRESET_DETAIL: _profile("heavy_list", "none", 200),
    PageName.ZAPRET2_ORCHESTRA: _profile("heavy_list", "module", 200),
    PageName.ZAPRET2_ORCHESTRA_CONTROL: _profile("heavy_list", "module", 200),
    PageName.ZAPRET2_ORCHESTRA_USER_PRESETS: _profile("heavy_list", "module", 200),
    PageName.ZAPRET2_ORCHESTRA_STRATEGY_DETAIL: _profile("heavy_list", "none", 200),
    PageName.ZAPRET2_ORCHESTRA_PRESET_DETAIL: _profile("heavy_list", "none", 200),
    PageName.ZAPRET1_DIRECT_CONTROL: _profile("heavy_list", "module", 200),
    PageName.ZAPRET1_DIRECT: _profile("heavy_list", "module", 200),
    PageName.ZAPRET1_USER_PRESETS: _profile("heavy_list", "module", 200),
    PageName.ZAPRET1_STRATEGY_DETAIL: _profile("heavy_list", "none", 200),
    PageName.ZAPRET1_PRESET_DETAIL: _profile("heavy_list", "none", 200),
    PageName.HOSTLIST: _profile("data", "module", 120),
    PageName.BLOBS: _profile("data", "ui", 120),
    PageName.DPI_SETTINGS: _profile("static", "ui", 120),
    PageName.ZAPRET2_USER_PRESETS: _profile("heavy_list", "module", 200),
    PageName.NETROGAT: _profile("data", "ui", 120),
    PageName.CUSTOM_DOMAINS: _profile("data", "ui", 120),
    PageName.CUSTOM_IPSET: _profile("data", "ui", 120),
    PageName.AUTOSTART: _profile("live", "module", 160),
    PageName.NETWORK: _profile("data", "module", 120),
    PageName.HOSTS: _profile("live", "module", 160),
    PageName.BLOCKCHECK: _profile("live", "module", 160),
    PageName.APPEARANCE: _profile("static", "ui", 120),
    PageName.PREMIUM: _profile("data", "ui", 120),
    PageName.LOGS: _profile("live", "module", 160),
    PageName.SERVERS: _profile("live", "ui", 160),
    PageName.ABOUT: _profile("static", "ui", 120),
    PageName.SUPPORT: _profile("static", "ui", 120),
    PageName.ORCHESTRA: _profile("live", "module", 160),
    PageName.ORCHESTRA_SETTINGS: _profile("static", "ui", 120),
    PageName.TELEGRAM_PROXY: _profile("live", "module", 160),
}


def get_page_performance_profile(page_name: PageName) -> PagePerformanceProfile:
    return PAGE_PERFORMANCE_PROFILES[page_name]


_MISSING_PAGE_PROFILES = tuple(name for name in PAGE_CLASS_SPECS if name not in PAGE_PERFORMANCE_PROFILES)
if _MISSING_PAGE_PROFILES:
    raise RuntimeError(f"Missing page performance profiles: {_MISSING_PAGE_PROFILES!r}")


def iter_lazy_page_modules() -> tuple[str, ...]:
    seen: set[str] = set()
    modules: list[str] = []
    for _attr_name, module_name, _class_name in PAGE_CLASS_SPECS.values():
        module = str(module_name or "").strip()
        if not module or module in seen:
            continue
        seen.add(module)
        modules.append(module)
    return tuple(modules)


def iter_lazy_page_specs() -> Iterable[tuple[PageName, tuple[str, str, str]]]:
    return PAGE_CLASS_SPECS.items()
