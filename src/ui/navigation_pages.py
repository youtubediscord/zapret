from __future__ import annotations

from dataclasses import dataclass

from settings.mode import (
    ZAPRET1_MODE,
    ZAPRET2_MODE,
    is_orchestra_launch_method,
    normalize_launch_method,
)
from app.page_names import PageName


@dataclass(frozen=True)
class Winws2NavigationPages:
    # У Zapret 2 есть две соседние ветки из control page:
    # user_presets_page -> выбор/активация preset-а и raw-редактор preset-а;
    # preset_setup_page -> настройка выбранного preset-а через profiles.
    control_page: PageName
    preset_setup_page: PageName
    user_presets_page: PageName
    preset_raw_editor_page: PageName
    profile_setup_page: PageName


@dataclass(frozen=True)
class Winws1NavigationPages:
    # У Zapret 1 тот же верхний путь, отличается только strategy внутри profile.
    control_page: PageName
    preset_setup_page: PageName
    user_presets_page: PageName
    preset_raw_editor_page: PageName
    profile_setup_page: PageName


def resolve_zapret2_navigation_pages() -> Winws2NavigationPages:
    return Winws2NavigationPages(
        control_page=PageName.ZAPRET2_MODE_CONTROL,
        preset_setup_page=PageName.ZAPRET2_PRESET_SETUP,
        user_presets_page=PageName.ZAPRET2_USER_PRESETS,
        preset_raw_editor_page=PageName.ZAPRET2_PRESET_RAW_EDITOR,
        profile_setup_page=PageName.ZAPRET2_PROFILE_SETUP,
    )


def resolve_zapret1_navigation_pages() -> Winws1NavigationPages:
    return Winws1NavigationPages(
        control_page=PageName.ZAPRET1_MODE_CONTROL,
        preset_setup_page=PageName.ZAPRET1_PRESET_SETUP,
        user_presets_page=PageName.ZAPRET1_USER_PRESETS,
        preset_raw_editor_page=PageName.ZAPRET1_PRESET_RAW_EDITOR,
        profile_setup_page=PageName.ZAPRET1_PROFILE_SETUP,
    )


_NAVIGATION_PAGES_BY_METHOD = {
    ZAPRET2_MODE: resolve_zapret2_navigation_pages,
    ZAPRET1_MODE: resolve_zapret1_navigation_pages,
}


def _normalize_navigation_method(method: str | None) -> str:
    return normalize_launch_method(method, default="")


def _resolve_mode_navigation_pages(method: str | None) -> Winws2NavigationPages | Winws1NavigationPages | None:
    normalized = _normalize_navigation_method(method)
    resolver = _NAVIGATION_PAGES_BY_METHOD.get(normalized)
    return resolver() if resolver is not None else None


def resolve_control_page_for_method(method: str | None) -> PageName:
    normalized = _normalize_navigation_method(method)
    if is_orchestra_launch_method(normalized):
        return PageName.ORCHESTRA
    pages = _resolve_mode_navigation_pages(normalized)
    if pages is not None:
        return pages.control_page
    return resolve_zapret2_navigation_pages().control_page


def resolve_preset_setup_page_for_method(method: str | None) -> PageName | None:
    pages = _resolve_mode_navigation_pages(method)
    return pages.preset_setup_page if pages is not None else None


def resolve_user_presets_page_for_method(method: str | None) -> PageName | None:
    pages = _resolve_mode_navigation_pages(method)
    return pages.user_presets_page if pages is not None else None


def resolve_preset_raw_editor_page_for_method(method: str | None) -> PageName | None:
    pages = _resolve_mode_navigation_pages(method)
    return pages.preset_raw_editor_page if pages is not None else None


def resolve_profile_setup_page_for_method(method: str | None) -> PageName | None:
    pages = _resolve_mode_navigation_pages(method)
    return pages.profile_setup_page if pages is not None else None


def resolve_profile_setup_back_page_for_method(method: str | None) -> PageName:
    normalized = _normalize_navigation_method(method)
    pages = _resolve_mode_navigation_pages(normalized)
    if pages is not None:
        return pages.preset_setup_page
    if is_orchestra_launch_method(normalized):
        return PageName.ORCHESTRA
    return resolve_zapret2_navigation_pages().control_page


def resolve_preset_raw_editor_back_page_for_method(method: str | None) -> PageName | None:
    pages = _resolve_mode_navigation_pages(method)
    return pages.user_presets_page if pages is not None else None


def resolve_preset_raw_editor_root_page_for_method(method: str | None) -> PageName:
    pages = _resolve_mode_navigation_pages(method)
    if pages is not None:
        return pages.control_page
    return resolve_zapret2_navigation_pages().control_page


def resolve_profile_setup_root_page_for_method(method: str | None) -> PageName:
    normalized = _normalize_navigation_method(method)
    pages = _resolve_mode_navigation_pages(normalized)
    if pages is not None:
        return pages.control_page
    if is_orchestra_launch_method(normalized):
        return PageName.ORCHESTRA
    return resolve_zapret2_navigation_pages().control_page


def get_profile_setup_pages() -> tuple[PageName, ...]:
    return (
        resolve_zapret2_navigation_pages().profile_setup_page,
        resolve_zapret1_navigation_pages().profile_setup_page,
    )
