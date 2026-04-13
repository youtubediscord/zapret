from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Iterable

from ui.page_names import PageName


@dataclass(frozen=True, slots=True)
class PageRouteSpec:
    page_name: PageName
    module_name: str
    class_name: str
    route_key: str
    is_top_level: bool
    is_hidden: bool
    launch_modes: tuple[str, ...]
    breadcrumb_parent: PageName | None
    sidebar_group: str | None
    attr_name: str
    cleanup_priority: int = 10_000


_COMMON = ()
_Z2_DIRECT = ("direct_zapret2",)
_Z1_DIRECT = ("direct_zapret1",)
_ORCHESTRA = ("orchestra",)


PAGE_ROUTE_SPECS: dict[PageName, PageRouteSpec] = {
    PageName.CONTROL: PageRouteSpec(
        page_name=PageName.CONTROL,
        attr_name="control_page",
        module_name="ui.pages.control_page",
        class_name="ControlPage",
        route_key="ControlPage",
        is_top_level=True,
        is_hidden=False,
        launch_modes=_COMMON,
        breadcrumb_parent=None,
        sidebar_group="root",
    ),
    PageName.ZAPRET2_DIRECT_CONTROL: PageRouteSpec(
        page_name=PageName.ZAPRET2_DIRECT_CONTROL,
        attr_name="zapret2_direct_control_page",
        module_name="direct_preset.ui.control.zapret2.page",
        class_name="Zapret2DirectControlPage",
        route_key="Zapret2DirectControlPage",
        is_top_level=True,
        is_hidden=False,
        launch_modes=_Z2_DIRECT,
        breadcrumb_parent=None,
        sidebar_group="root",
    ),
    PageName.ZAPRET2_DIRECT: PageRouteSpec(
        page_name=PageName.ZAPRET2_DIRECT,
        attr_name="zapret2_strategies_page",
        module_name="filters.ui.filter_list.zapret2.targets_page",
        class_name="Zapret2StrategiesPageNew",
        route_key="Zapret2StrategiesPageNew",
        is_top_level=False,
        is_hidden=True,
        launch_modes=_Z2_DIRECT,
        breadcrumb_parent=PageName.ZAPRET2_DIRECT_CONTROL,
        sidebar_group=None,
    ),
    PageName.ZAPRET2_STRATEGY_DETAIL: PageRouteSpec(
        page_name=PageName.ZAPRET2_STRATEGY_DETAIL,
        attr_name="strategy_detail_page",
        module_name="filters.ui.filter_list.zapret2.strategy_detail_page",
        class_name="StrategyDetailPage",
        route_key="StrategyDetailPage",
        is_top_level=False,
        is_hidden=True,
        launch_modes=_Z2_DIRECT,
        breadcrumb_parent=PageName.ZAPRET2_DIRECT,
        sidebar_group=None,
    ),
    PageName.ZAPRET2_PRESET_DETAIL: PageRouteSpec(
        page_name=PageName.ZAPRET2_PRESET_DETAIL,
        attr_name="zapret2_preset_detail_page",
        module_name="direct_preset.ui.zapret2.preset_detail_page",
        class_name="Zapret2PresetDetailPage",
        route_key="Zapret2PresetDetailPage",
        is_top_level=False,
        is_hidden=True,
        launch_modes=_Z2_DIRECT,
        breadcrumb_parent=PageName.ZAPRET2_USER_PRESETS,
        sidebar_group=None,
    ),
    PageName.ZAPRET1_DIRECT_CONTROL: PageRouteSpec(
        page_name=PageName.ZAPRET1_DIRECT_CONTROL,
        attr_name="zapret1_direct_control_page",
        module_name="direct_preset.ui.control.zapret1.page",
        class_name="Zapret1DirectControlPage",
        route_key="Zapret1DirectControlPage",
        is_top_level=True,
        is_hidden=False,
        launch_modes=_Z1_DIRECT,
        breadcrumb_parent=None,
        sidebar_group="root",
    ),
    PageName.ZAPRET1_DIRECT: PageRouteSpec(
        page_name=PageName.ZAPRET1_DIRECT,
        attr_name="zapret1_strategies_page",
        module_name="filters.ui.filter_list.zapret1.targets_page",
        class_name="Zapret1StrategiesPage",
        route_key="Zapret1StrategiesPage",
        is_top_level=False,
        is_hidden=True,
        launch_modes=_Z1_DIRECT,
        breadcrumb_parent=PageName.ZAPRET1_DIRECT_CONTROL,
        sidebar_group=None,
    ),
    PageName.ZAPRET1_USER_PRESETS: PageRouteSpec(
        page_name=PageName.ZAPRET1_USER_PRESETS,
        attr_name="zapret1_user_presets_page",
        module_name="direct_preset.ui.zapret1.user_presets_page",
        class_name="Zapret1UserPresetsPage",
        route_key="Zapret1UserPresetsPage",
        is_top_level=False,
        is_hidden=True,
        launch_modes=_Z1_DIRECT,
        breadcrumb_parent=PageName.ZAPRET1_DIRECT_CONTROL,
        sidebar_group=None,
    ),
    PageName.ZAPRET1_STRATEGY_DETAIL: PageRouteSpec(
        page_name=PageName.ZAPRET1_STRATEGY_DETAIL,
        attr_name="zapret1_strategy_detail_page",
        module_name="filters.ui.filter_list.zapret1.strategy_detail_page",
        class_name="Zapret1StrategyDetailPage",
        route_key="Zapret1StrategyDetailPage",
        is_top_level=False,
        is_hidden=True,
        launch_modes=_Z1_DIRECT,
        breadcrumb_parent=PageName.ZAPRET1_DIRECT,
        sidebar_group=None,
    ),
    PageName.ZAPRET1_PRESET_DETAIL: PageRouteSpec(
        page_name=PageName.ZAPRET1_PRESET_DETAIL,
        attr_name="zapret1_preset_detail_page",
        module_name="direct_preset.ui.zapret1.preset_detail_page",
        class_name="Zapret1PresetDetailPage",
        route_key="Zapret1PresetDetailPage",
        is_top_level=False,
        is_hidden=True,
        launch_modes=_Z1_DIRECT,
        breadcrumb_parent=PageName.ZAPRET1_USER_PRESETS,
        sidebar_group=None,
    ),
    PageName.HOSTLIST: PageRouteSpec(
        page_name=PageName.HOSTLIST,
        attr_name="hostlist_page",
        module_name="lists.ui.hostlist_page",
        class_name="HostlistPage",
        route_key="HostlistPage",
        is_top_level=True,
        is_hidden=False,
        launch_modes=_COMMON,
        breadcrumb_parent=None,
        sidebar_group="settings",
    ),
    PageName.BLOBS: PageRouteSpec(
        page_name=PageName.BLOBS,
        attr_name="blobs_page",
        module_name="blobs.ui.page",
        class_name="BlobsPage",
        route_key="BlobsPage",
        is_top_level=False,
        is_hidden=True,
        launch_modes=_COMMON,
        breadcrumb_parent=None,
        sidebar_group=None,
    ),
    PageName.DPI_SETTINGS: PageRouteSpec(
        page_name=PageName.DPI_SETTINGS,
        attr_name="dpi_settings_page",
        module_name="settings.dpi.page",
        class_name="DpiSettingsPage",
        route_key="DpiSettingsPage",
        is_top_level=True,
        is_hidden=False,
        launch_modes=_COMMON,
        breadcrumb_parent=None,
        sidebar_group="settings",
    ),
    PageName.ZAPRET2_USER_PRESETS: PageRouteSpec(
        page_name=PageName.ZAPRET2_USER_PRESETS,
        attr_name="zapret2_user_presets_page",
        module_name="direct_preset.ui.zapret2.user_presets_page",
        class_name="Zapret2UserPresetsPage",
        route_key="Zapret2UserPresetsPage_Direct",
        is_top_level=False,
        is_hidden=True,
        launch_modes=_Z2_DIRECT,
        breadcrumb_parent=PageName.ZAPRET2_DIRECT_CONTROL,
        sidebar_group=None,
    ),
    PageName.NETROGAT: PageRouteSpec(
        page_name=PageName.NETROGAT,
        attr_name="netrogat_page",
        module_name="lists.ui.netrogat_page",
        class_name="NetrogatPage",
        route_key="NetrogatPage",
        is_top_level=False,
        is_hidden=False,
        launch_modes=_COMMON,
        breadcrumb_parent=None,
        sidebar_group=None,
    ),
    PageName.CUSTOM_DOMAINS: PageRouteSpec(
        page_name=PageName.CUSTOM_DOMAINS,
        attr_name="custom_domains_page",
        module_name="lists.ui.custom_domains_page",
        class_name="CustomDomainsPage",
        route_key="CustomDomainsPage",
        is_top_level=False,
        is_hidden=False,
        launch_modes=_COMMON,
        breadcrumb_parent=None,
        sidebar_group=None,
    ),
    PageName.CUSTOM_IPSET: PageRouteSpec(
        page_name=PageName.CUSTOM_IPSET,
        attr_name="custom_ipset_page",
        module_name="lists.ui.custom_ipset_page",
        class_name="CustomIpSetPage",
        route_key="CustomIpSetPage",
        is_top_level=False,
        is_hidden=False,
        launch_modes=_COMMON,
        breadcrumb_parent=None,
        sidebar_group=None,
    ),
    PageName.AUTOSTART: PageRouteSpec(
        page_name=PageName.AUTOSTART,
        attr_name="autostart_page",
        module_name="autostart.ui.page",
        class_name="AutostartPage",
        route_key="AutostartPage",
        is_top_level=True,
        is_hidden=False,
        launch_modes=_COMMON,
        breadcrumb_parent=None,
        sidebar_group="system",
    ),
    PageName.NETWORK: PageRouteSpec(
        page_name=PageName.NETWORK,
        attr_name="network_page",
        module_name="dns.ui.page",
        class_name="NetworkPage",
        route_key="NetworkPage",
        is_top_level=True,
        is_hidden=False,
        launch_modes=_COMMON,
        breadcrumb_parent=None,
        sidebar_group="system",
    ),
    PageName.HOSTS: PageRouteSpec(
        page_name=PageName.HOSTS,
        attr_name="hosts_page",
        module_name="hosts.ui.page",
        class_name="HostsPage",
        route_key="HostsPage",
        is_top_level=True,
        is_hidden=False,
        launch_modes=_COMMON,
        breadcrumb_parent=None,
        sidebar_group="diagnostics",
    ),
    PageName.BLOCKCHECK: PageRouteSpec(
        page_name=PageName.BLOCKCHECK,
        attr_name="blockcheck_page",
        module_name="blockcheck.ui.page",
        class_name="BlockcheckPage",
        route_key="BlockcheckPage",
        is_top_level=True,
        is_hidden=False,
        launch_modes=_COMMON,
        breadcrumb_parent=None,
        sidebar_group="diagnostics",
    ),
    PageName.APPEARANCE: PageRouteSpec(
        page_name=PageName.APPEARANCE,
        attr_name="appearance_page",
        module_name="ui.pages.appearance_page",
        class_name="AppearancePage",
        route_key="AppearancePage",
        is_top_level=True,
        is_hidden=False,
        launch_modes=_COMMON,
        breadcrumb_parent=None,
        sidebar_group="appearance",
    ),
    PageName.PREMIUM: PageRouteSpec(
        page_name=PageName.PREMIUM,
        attr_name="premium_page",
        module_name="donater.ui.page",
        class_name="PremiumPage",
        route_key="PremiumPage",
        is_top_level=True,
        is_hidden=False,
        launch_modes=_COMMON,
        breadcrumb_parent=None,
        sidebar_group="appearance",
    ),
    PageName.LOGS: PageRouteSpec(
        page_name=PageName.LOGS,
        attr_name="logs_page",
        module_name="log.ui.page",
        class_name="LogsPage",
        route_key="LogsPage",
        is_top_level=True,
        is_hidden=False,
        launch_modes=_COMMON,
        breadcrumb_parent=None,
        sidebar_group="appearance",
    ),
    PageName.SERVERS: PageRouteSpec(
        page_name=PageName.SERVERS,
        attr_name="servers_page",
        module_name="updater.ui.page",
        class_name="ServersPage",
        route_key="ServersPage",
        is_top_level=False,
        is_hidden=True,
        launch_modes=_COMMON,
        breadcrumb_parent=PageName.ABOUT,
        sidebar_group=None,
    ),
    PageName.ABOUT: PageRouteSpec(
        page_name=PageName.ABOUT,
        attr_name="about_page",
        module_name="ui.pages.about_page",
        class_name="AboutPage",
        route_key="AboutPage",
        is_top_level=True,
        is_hidden=False,
        launch_modes=_COMMON,
        breadcrumb_parent=None,
        sidebar_group="appearance",
    ),
    PageName.SUPPORT: PageRouteSpec(
        page_name=PageName.SUPPORT,
        attr_name="support_page",
        module_name="ui.pages.support_page",
        class_name="SupportPage",
        route_key="SupportPage",
        is_top_level=False,
        is_hidden=True,
        launch_modes=_COMMON,
        breadcrumb_parent=PageName.ABOUT,
        sidebar_group=None,
    ),
    PageName.ORCHESTRA: PageRouteSpec(
        page_name=PageName.ORCHESTRA,
        attr_name="orchestra_page",
        module_name="orchestra.ui.page",
        class_name="OrchestraPage",
        route_key="OrchestraPage",
        is_top_level=True,
        is_hidden=False,
        launch_modes=_ORCHESTRA,
        breadcrumb_parent=None,
        sidebar_group="root",
    ),
    PageName.ORCHESTRA_SETTINGS: PageRouteSpec(
        page_name=PageName.ORCHESTRA_SETTINGS,
        attr_name="orchestra_settings_page",
        module_name="orchestra.ui.settings_page",
        class_name="OrchestraSettingsPage",
        route_key="OrchestraSettingsPage",
        is_top_level=True,
        is_hidden=False,
        launch_modes=_ORCHESTRA,
        breadcrumb_parent=None,
        sidebar_group="settings",
    ),
    PageName.TELEGRAM_PROXY: PageRouteSpec(
        page_name=PageName.TELEGRAM_PROXY,
        attr_name="telegram_proxy_page",
        module_name="telegram_proxy.ui.page",
        class_name="TelegramProxyPage",
        route_key="TelegramProxyPage",
        is_top_level=True,
        is_hidden=False,
        launch_modes=_COMMON,
        breadcrumb_parent=None,
        sidebar_group="system",
    ),
}

PAGE_CLEANUP_ORDER: tuple[PageName, ...] = (
    PageName.AUTOSTART,
    PageName.BLOBS,
    PageName.CONTROL,
    PageName.CUSTOM_DOMAINS,
    PageName.CUSTOM_IPSET,
    PageName.ZAPRET2_DIRECT_CONTROL,
    PageName.ZAPRET2_DIRECT,
    PageName.ZAPRET2_STRATEGY_DETAIL,
    PageName.ZAPRET2_USER_PRESETS,
    PageName.ZAPRET1_DIRECT_CONTROL,
    PageName.ZAPRET1_DIRECT,
    PageName.ZAPRET1_STRATEGY_DETAIL,
    PageName.ZAPRET1_USER_PRESETS,
    PageName.NETROGAT,
    PageName.HOSTLIST,
    PageName.LOGS,
    PageName.SERVERS,
    PageName.ABOUT,
    PageName.BLOCKCHECK,
    PageName.HOSTS,
    PageName.NETWORK,
    PageName.ORCHESTRA,
    PageName.ORCHESTRA_SETTINGS,
    PageName.APPEARANCE,
    PageName.PREMIUM,
    PageName.TELEGRAM_PROXY,
)

_PAGE_CLEANUP_PRIORITY_OVERRIDES: dict[PageName, int] = {
    page_name: index
    for index, page_name in enumerate(PAGE_CLEANUP_ORDER)
}

_DEFAULT_CLEANUP_PRIORITY_BASE = 10_000

PAGE_ROUTE_SPECS = {
    page_name: replace(
        spec,
        cleanup_priority=_PAGE_CLEANUP_PRIORITY_OVERRIDES.get(
            page_name,
            _DEFAULT_CLEANUP_PRIORITY_BASE + index,
        ),
    )
    for index, (page_name, spec) in enumerate(PAGE_ROUTE_SPECS.items())
}


SIDEBAR_GROUP_ORDER: tuple[str, ...] = ("root", "settings", "system", "diagnostics", "appearance")

DETAIL_PAGE_NAMES: frozenset[PageName] = frozenset(
    {
        PageName.ZAPRET2_STRATEGY_DETAIL,
        PageName.ZAPRET2_PRESET_DETAIL,
        PageName.ZAPRET1_STRATEGY_DETAIL,
        PageName.ZAPRET1_PRESET_DETAIL,
    }
)

MODE_ENTRY_PAGES: dict[str, PageName] = {
    "direct_zapret2": PageName.ZAPRET2_DIRECT_CONTROL,
    "direct_zapret1": PageName.ZAPRET1_DIRECT_CONTROL,
    "orchestra": PageName.ORCHESTRA,
}


def get_page_spec(page_name: PageName) -> PageRouteSpec:
    return PAGE_ROUTE_SPECS[page_name]


def iter_page_specs() -> Iterable[PageRouteSpec]:
    return PAGE_ROUTE_SPECS.values()


def get_page_cleanup_priority(page_name: PageName) -> int:
    spec = PAGE_ROUTE_SPECS.get(page_name)
    if spec is None:
        return _DEFAULT_CLEANUP_PRIORITY_BASE * 2
    return int(spec.cleanup_priority)


def iter_page_names_for_cleanup(page_names: Iterable[PageName]) -> tuple[PageName, ...]:
    indexed_page_names = list(enumerate(page_names))
    indexed_page_names.sort(
        key=lambda item: (get_page_cleanup_priority(item[1]), item[0])
    )
    return tuple(page_name for _index, page_name in indexed_page_names)


def normalize_launch_method_for_ui(method: str | None) -> str:
    normalized = (method or "").strip().lower()
    return normalized or "direct_zapret2"


def _matches_method(spec: PageRouteSpec, method: str | None) -> bool:
    if not spec.launch_modes:
        return True
    normalized_method = normalize_launch_method_for_ui(method)
    return normalized_method in spec.launch_modes


def _is_sidebar_visible_in_method(spec: PageRouteSpec, method: str | None) -> bool:
    normalized_method = normalize_launch_method_for_ui(method)

    if spec.page_name == PageName.CONTROL:
        return normalized_method not in {
            "direct_zapret2",
            "direct_zapret1",
            "orchestra",
        }

    return _matches_method(spec, normalized_method)


def is_page_allowed_for_method(page_name: PageName, method: str | None) -> bool:
    spec = PAGE_ROUTE_SPECS.get(page_name)
    if spec is None:
        return False
    return _matches_method(spec, method)


def is_page_direct_open_allowed(page_name: PageName) -> bool:
    return page_name not in DETAIL_PAGE_NAMES


def is_page_search_visible(page_name: PageName) -> bool:
    return page_name not in DETAIL_PAGE_NAMES


def get_page_route_key(page_name: PageName) -> str:
    return str(get_page_spec(page_name).route_key)


def get_mode_entry_page(method: str | None) -> PageName:
    normalized = normalize_launch_method_for_ui(method)
    return MODE_ENTRY_PAGES.get(normalized, PageName.CONTROL)


def get_eager_page_names_for_method(method: str | None) -> tuple[PageName, ...]:
    return (get_mode_entry_page(method),)


def get_sidebar_pages_for_method(method: str | None, *, sidebar_group: str | None = None) -> tuple[PageName, ...]:
    pages: list[PageName] = []
    for spec in iter_page_specs():
        if not spec.is_top_level or spec.is_hidden:
            continue
        if sidebar_group is not None and spec.sidebar_group != sidebar_group:
            continue
        if not _is_sidebar_visible_in_method(spec, method):
            continue
        pages.append(spec.page_name)
    return tuple(pages)


def get_hidden_pages_for_method(method: str | None) -> tuple[PageName, ...]:
    pages: list[PageName] = []
    for spec in iter_page_specs():
        if not spec.is_hidden:
            continue
        if not _matches_method(spec, method):
            continue
        pages.append(spec.page_name)
    return tuple(pages)


def get_breadcrumb_chain(page_name: PageName) -> tuple[PageName, ...]:
    chain: list[PageName] = []
    seen: set[PageName] = set()
    current: PageName | None = page_name
    while current is not None and current not in seen:
        seen.add(current)
        chain.append(current)
        current = get_page_spec(current).breadcrumb_parent
    chain.reverse()
    return tuple(chain)


def get_mode_gated_nav_pages() -> frozenset[PageName]:
    return frozenset(
        spec.page_name
        for spec in iter_page_specs()
        if spec.is_top_level and bool(spec.launch_modes)
    )


def get_nav_visibility(method: str | None) -> dict[PageName, bool]:
    visibility: dict[PageName, bool] = {}
    for spec in iter_page_specs():
        if not spec.is_top_level or spec.is_hidden:
            continue
        visibility[spec.page_name] = _is_sidebar_visible_in_method(spec, method)
    return visibility


def get_sidebar_search_pages_for_method(method: str | None, all_pages: set[PageName]) -> set[PageName]:
    allowed_pages: set[PageName] = set()
    for page_name in all_pages:
        spec = PAGE_ROUTE_SPECS.get(page_name)
        if spec is None:
            continue
        if _matches_method(spec, method) and is_page_search_visible(page_name):
            allowed_pages.add(page_name)
    return allowed_pages


__all__ = [
    "MODE_ENTRY_PAGES",
    "PAGE_CLEANUP_ORDER",
    "PAGE_ROUTE_SPECS",
    "SIDEBAR_GROUP_ORDER",
    "PageRouteSpec",
    "get_breadcrumb_chain",
    "get_page_cleanup_priority",
    "get_eager_page_names_for_method",
    "get_hidden_pages_for_method",
    "get_mode_entry_page",
    "get_mode_gated_nav_pages",
    "get_nav_visibility",
    "get_page_route_key",
    "get_page_spec",
    "is_page_allowed_for_method",
    "is_page_direct_open_allowed",
    "is_page_search_visible",
    "iter_page_names_for_cleanup",
    "get_sidebar_pages_for_method",
    "get_sidebar_search_pages_for_method",
    "iter_page_specs",
    "normalize_launch_method_for_ui",
]
