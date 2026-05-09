from __future__ import annotations

from dataclasses import dataclass

from ui.page_names import PageName


@dataclass(frozen=True)
class Z2NavigationPages:
    control_page: PageName
    profiles_page: PageName
    user_presets_page: PageName
    preset_detail_page: PageName
    profile_detail_page: PageName


@dataclass(frozen=True)
class Z1NavigationPages:
    control_page: PageName
    profiles_page: PageName
    user_presets_page: PageName
    preset_detail_page: PageName
    profile_detail_page: PageName


def resolve_zapret2_navigation_pages() -> Z2NavigationPages:
    return Z2NavigationPages(
        control_page=PageName.ZAPRET2_MODE_CONTROL,
        profiles_page=PageName.ZAPRET2_MODE,
        user_presets_page=PageName.ZAPRET2_USER_PRESETS,
        preset_detail_page=PageName.ZAPRET2_PRESET_DETAIL,
        profile_detail_page=PageName.ZAPRET2_PROFILE_DETAIL,
    )


def resolve_zapret1_navigation_pages() -> Z1NavigationPages:
    return Z1NavigationPages(
        control_page=PageName.ZAPRET1_MODE_CONTROL,
        profiles_page=PageName.ZAPRET1_MODE,
        user_presets_page=PageName.ZAPRET1_USER_PRESETS,
        preset_detail_page=PageName.ZAPRET1_PRESET_DETAIL,
        profile_detail_page=PageName.ZAPRET1_PROFILE_DETAIL,
    )


def resolve_control_page_for_method(method: str | None) -> PageName:
    normalized = str(method or "").strip().lower()
    if normalized == "orchestra":
        return PageName.ORCHESTRA
    if normalized == "zapret2_mode":
        return resolve_zapret2_navigation_pages().control_page
    if normalized == "zapret1_mode":
        return resolve_zapret1_navigation_pages().control_page
    return PageName.CONTROL


def resolve_profiles_page_for_method(method: str | None) -> PageName | None:
    normalized = str(method or "").strip().lower()
    if normalized == "zapret2_mode":
        return resolve_zapret2_navigation_pages().profiles_page
    if normalized == "zapret1_mode":
        return resolve_zapret1_navigation_pages().profiles_page
    return None


def resolve_user_presets_page_for_method(method: str | None) -> PageName | None:
    normalized = str(method or "").strip().lower()
    if normalized == "zapret2_mode":
        return resolve_zapret2_navigation_pages().user_presets_page
    if normalized == "zapret1_mode":
        return resolve_zapret1_navigation_pages().user_presets_page
    return None


def resolve_preset_detail_page_for_method(method: str | None) -> PageName | None:
    normalized = str(method or "").strip().lower()
    if normalized == "zapret2_mode":
        return resolve_zapret2_navigation_pages().preset_detail_page
    if normalized == "zapret1_mode":
        return resolve_zapret1_navigation_pages().preset_detail_page
    return None


def resolve_profile_detail_page_for_method(method: str | None) -> PageName | None:
    normalized = str(method or "").strip().lower()
    if normalized == "zapret2_mode":
        return resolve_zapret2_navigation_pages().profile_detail_page
    if normalized == "zapret1_mode":
        return resolve_zapret1_navigation_pages().profile_detail_page
    return None


def resolve_profile_detail_back_page_for_method(method: str | None) -> PageName:
    normalized = str(method or "").strip().lower()
    if normalized == "zapret2_mode":
        return resolve_zapret2_navigation_pages().profiles_page
    if normalized == "zapret1_mode":
        return resolve_zapret1_navigation_pages().profiles_page
    if normalized == "orchestra":
        return PageName.ORCHESTRA
    return PageName.CONTROL


def resolve_preset_detail_back_page_for_method(method: str | None) -> PageName | None:
    normalized = str(method or "").strip().lower()
    if normalized == "zapret2_mode":
        return resolve_zapret2_navigation_pages().user_presets_page
    if normalized == "zapret1_mode":
        return resolve_zapret1_navigation_pages().user_presets_page
    return None


def resolve_preset_detail_root_page_for_method(method: str | None) -> PageName:
    normalized = str(method or "").strip().lower()
    if normalized == "zapret2_mode":
        return resolve_zapret2_navigation_pages().control_page
    if normalized == "zapret1_mode":
        return resolve_zapret1_navigation_pages().control_page
    return PageName.CONTROL


def resolve_profile_detail_root_page_for_method(method: str | None) -> PageName:
    normalized = str(method or "").strip().lower()
    if normalized == "zapret2_mode":
        return resolve_zapret2_navigation_pages().control_page
    if normalized == "zapret1_mode":
        return resolve_zapret1_navigation_pages().control_page
    if normalized == "orchestra":
        return PageName.ORCHESTRA
    return PageName.CONTROL


def get_profile_detail_pages() -> tuple[PageName, ...]:
    return (
        resolve_zapret2_navigation_pages().profile_detail_page,
        resolve_zapret1_navigation_pages().profile_detail_page,
    )
