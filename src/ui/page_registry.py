from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from ui.navigation.schema import iter_page_specs
from ui.page_names import PageName


PAGE_CLASS_SPECS: dict[PageName, tuple[str, str, str]] = {
    spec.page_name: (spec.attr_name, spec.module_name, spec.class_name)
    for spec in iter_page_specs()
}


@dataclass(frozen=True, slots=True)
class PagePerformanceProfile:
    first_show_budget_ms: int
    repeat_show_budget_ms: int


def _profile(first_show_budget_ms: int, repeat_show_budget_ms: int = 40) -> PagePerformanceProfile:
    return PagePerformanceProfile(
        first_show_budget_ms=int(first_show_budget_ms),
        repeat_show_budget_ms=int(repeat_show_budget_ms),
    )


DEFAULT_PAGE_PERFORMANCE_PROFILE = _profile(120)


def _profiles_for(
    page_names: tuple[PageName, ...],
    profile: PagePerformanceProfile,
) -> dict[PageName, PagePerformanceProfile]:
    return {
        page_name: profile
        for page_name in page_names
    }


PAGE_PERFORMANCE_PROFILE_OVERRIDES: dict[PageName, PagePerformanceProfile] = {
    **_profiles_for(
        (
            PageName.CONTROL,
            PageName.ZAPRET2_DIRECT_CONTROL,
            PageName.ZAPRET2_DIRECT,
            PageName.ZAPRET2_STRATEGY_DETAIL,
            PageName.ZAPRET2_PRESET_DETAIL,
            PageName.ZAPRET1_DIRECT_CONTROL,
            PageName.ZAPRET1_DIRECT,
            PageName.ZAPRET1_USER_PRESETS,
            PageName.ZAPRET1_STRATEGY_DETAIL,
            PageName.ZAPRET1_PRESET_DETAIL,
            PageName.ZAPRET2_USER_PRESETS,
        ),
        _profile(200),
    ),
    **_profiles_for(
        (
            PageName.HOSTLIST,
            PageName.BLOBS,
            PageName.NETROGAT,
            PageName.CUSTOM_DOMAINS,
            PageName.CUSTOM_IPSET,
            PageName.NETWORK,
            PageName.PREMIUM,
        ),
        _profile(120),
    ),
    **_profiles_for(
        (
            PageName.AUTOSTART,
            PageName.HOSTS,
            PageName.BLOCKCHECK,
            PageName.LOGS,
            PageName.SERVERS,
            PageName.ORCHESTRA,
            PageName.TELEGRAM_PROXY,
        ),
        _profile(160),
    ),
}


_UNKNOWN_PAGE_PROFILE_OVERRIDES = tuple(
    page_name
    for page_name in PAGE_PERFORMANCE_PROFILE_OVERRIDES
    if page_name not in PAGE_CLASS_SPECS
)
if _UNKNOWN_PAGE_PROFILE_OVERRIDES:
    raise RuntimeError(
        f"Unknown page performance profile overrides: {_UNKNOWN_PAGE_PROFILE_OVERRIDES!r}"
    )


def get_page_performance_profile(page_name: PageName) -> PagePerformanceProfile:
    return PAGE_PERFORMANCE_PROFILE_OVERRIDES.get(
        page_name,
        DEFAULT_PAGE_PERFORMANCE_PROFILE,
    )


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
