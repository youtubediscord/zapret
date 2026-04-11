from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from ui.page_names import PageName
from ui.router import iter_page_specs


PAGE_CLASS_SPECS: dict[PageName, tuple[str, str, str]] = {
    spec.page_name: (spec.attr_name, spec.module_name, spec.class_name)
    for spec in iter_page_specs()
}


@dataclass(frozen=True, slots=True)
class PagePerformanceProfile:
    page_kind: str
    first_show_budget_ms: int
    repeat_show_budget_ms: int


def _profile(kind: str, first_show_budget_ms: int, repeat_show_budget_ms: int = 40) -> PagePerformanceProfile:
    return PagePerformanceProfile(
        page_kind=kind,
        first_show_budget_ms=int(first_show_budget_ms),
        repeat_show_budget_ms=int(repeat_show_budget_ms),
    )


PAGE_PERFORMANCE_PROFILES: dict[PageName, PagePerformanceProfile] = {
    PageName.CONTROL: _profile("heavy_list", 200),
    PageName.ZAPRET2_DIRECT_CONTROL: _profile("heavy_list", 200),
    PageName.ZAPRET2_DIRECT: _profile("heavy_list", 200),
    PageName.ZAPRET2_STRATEGY_DETAIL: _profile("heavy_list", 200),
    PageName.ZAPRET2_PRESET_DETAIL: _profile("heavy_list", 200),
    PageName.ZAPRET1_DIRECT_CONTROL: _profile("heavy_list", 200),
    PageName.ZAPRET1_DIRECT: _profile("heavy_list", 200),
    PageName.ZAPRET1_USER_PRESETS: _profile("heavy_list", 200),
    PageName.ZAPRET1_STRATEGY_DETAIL: _profile("heavy_list", 200),
    PageName.ZAPRET1_PRESET_DETAIL: _profile("heavy_list", 200),
    PageName.HOSTLIST: _profile("data", 120),
    PageName.BLOBS: _profile("data", 120),
    PageName.DPI_SETTINGS: _profile("static", 120),
    PageName.ZAPRET2_USER_PRESETS: _profile("heavy_list", 200),
    PageName.NETROGAT: _profile("data", 120),
    PageName.CUSTOM_DOMAINS: _profile("data", 120),
    PageName.CUSTOM_IPSET: _profile("data", 120),
    PageName.AUTOSTART: _profile("live", 160),
    PageName.NETWORK: _profile("data", 120),
    PageName.HOSTS: _profile("live", 160),
    PageName.BLOCKCHECK: _profile("live", 160),
    PageName.APPEARANCE: _profile("static", 120),
    PageName.PREMIUM: _profile("data", 120),
    PageName.LOGS: _profile("live", 160),
    PageName.SERVERS: _profile("live", 160),
    PageName.ABOUT: _profile("static", 120),
    PageName.SUPPORT: _profile("static", 120),
    PageName.ORCHESTRA: _profile("live", 160),
    PageName.ORCHESTRA_SETTINGS: _profile("static", 120),
    PageName.TELEGRAM_PROXY: _profile("live", 160),
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
