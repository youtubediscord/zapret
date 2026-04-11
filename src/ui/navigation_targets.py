from __future__ import annotations

from dataclasses import dataclass

from ui.page_names import PageName


@dataclass(frozen=True)
class Z2NavigationPages:
    control_page: PageName
    strategies_page: PageName
    user_presets_page: PageName
    preset_detail_page: PageName
    strategy_detail_page: PageName


@dataclass(frozen=True)
class Z1NavigationPages:
    control_page: PageName
    strategies_page: PageName
    user_presets_page: PageName
    preset_detail_page: PageName
    strategy_detail_page: PageName


def resolve_zapret2_navigation_pages(method: str | None) -> Z2NavigationPages:
    return Z2NavigationPages(
        control_page=PageName.ZAPRET2_DIRECT_CONTROL,
        strategies_page=PageName.ZAPRET2_DIRECT,
        user_presets_page=PageName.ZAPRET2_USER_PRESETS,
        preset_detail_page=PageName.ZAPRET2_PRESET_DETAIL,
        strategy_detail_page=PageName.ZAPRET2_STRATEGY_DETAIL,
    )


def resolve_zapret1_navigation_pages() -> Z1NavigationPages:
    return Z1NavigationPages(
        control_page=PageName.ZAPRET1_DIRECT_CONTROL,
        strategies_page=PageName.ZAPRET1_DIRECT,
        user_presets_page=PageName.ZAPRET1_USER_PRESETS,
        preset_detail_page=PageName.ZAPRET1_PRESET_DETAIL,
        strategy_detail_page=PageName.ZAPRET1_STRATEGY_DETAIL,
    )


def resolve_control_page_for_method(method: str | None) -> PageName:
    normalized = str(method or "").strip().lower()
    if normalized == "orchestra":
        return PageName.ORCHESTRA
    if normalized == "direct_zapret2":
        return resolve_zapret2_navigation_pages(normalized).control_page
    if normalized == "direct_zapret1":
        return resolve_zapret1_navigation_pages().control_page
    return PageName.CONTROL


def resolve_strategy_page_for_method(method: str | None) -> PageName | None:
    normalized = str(method or "").strip().lower()
    if normalized == "direct_zapret2":
        return resolve_zapret2_navigation_pages(normalized).strategies_page
    if normalized == "direct_zapret1":
        return resolve_zapret1_navigation_pages().strategies_page
    return None


def resolve_user_presets_page_for_method(method: str | None) -> PageName | None:
    normalized = str(method or "").strip().lower()
    if normalized == "direct_zapret2":
        return resolve_zapret2_navigation_pages(normalized).user_presets_page
    if normalized == "direct_zapret1":
        return resolve_zapret1_navigation_pages().user_presets_page
    return None


def resolve_preset_detail_page_for_method(method: str | None) -> PageName | None:
    normalized = str(method or "").strip().lower()
    if normalized == "direct_zapret2":
        return resolve_zapret2_navigation_pages(normalized).preset_detail_page
    if normalized == "direct_zapret1":
        return resolve_zapret1_navigation_pages().preset_detail_page
    return None


def resolve_strategy_detail_page_for_method(method: str | None) -> PageName | None:
    normalized = str(method or "").strip().lower()
    if normalized == "direct_zapret2":
        return resolve_zapret2_navigation_pages(normalized).strategy_detail_page
    if normalized == "direct_zapret1":
        return resolve_zapret1_navigation_pages().strategy_detail_page
    return None


def resolve_strategy_detail_back_page_for_method(method: str | None) -> PageName:
    normalized = str(method or "").strip().lower()
    if normalized == "direct_zapret2":
        return resolve_zapret2_navigation_pages(normalized).strategies_page
    if normalized == "direct_zapret1":
        return resolve_zapret1_navigation_pages().control_page
    if normalized == "orchestra":
        return PageName.ORCHESTRA
    return PageName.CONTROL


def resolve_preset_detail_back_page_for_method(method: str | None) -> PageName | None:
    normalized = str(method or "").strip().lower()
    if normalized == "direct_zapret2":
        return resolve_zapret2_navigation_pages(normalized).user_presets_page
    if normalized == "direct_zapret1":
        return resolve_zapret1_navigation_pages().user_presets_page
    return None


def resolve_preset_detail_root_page_for_method(method: str | None) -> PageName:
    normalized = str(method or "").strip().lower()
    if normalized == "direct_zapret2":
        return resolve_zapret2_navigation_pages(normalized).control_page
    if normalized == "direct_zapret1":
        return resolve_zapret1_navigation_pages().control_page
    return PageName.CONTROL


def resolve_strategy_detail_root_page_for_method(method: str | None) -> PageName:
    normalized = str(method or "").strip().lower()
    if normalized == "direct_zapret2":
        return resolve_zapret2_navigation_pages(normalized).control_page
    if normalized == "direct_zapret1":
        return resolve_zapret1_navigation_pages().control_page
    if normalized == "orchestra":
        return PageName.ORCHESTRA
    return PageName.CONTROL


def get_zapret2_strategy_detail_pages() -> tuple[PageName]:
    return (resolve_zapret2_navigation_pages("direct_zapret2").strategy_detail_page,)
