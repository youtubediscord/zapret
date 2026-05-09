from __future__ import annotations

from ui.navigation_pages import (
    resolve_control_page_for_method,
    resolve_profiles_page_for_method,
    resolve_zapret1_navigation_pages,
    resolve_zapret2_navigation_pages,
)
from ui.page_contracts import PageMethodName
from ui.page_names import PageName
from ui.window_adapter import ensure_page, get_loaded_page, show_page
from ui.workflows.common import (
    get_current_launch_method,
    open_preset_detail_page,
)


def resolve_zapret2_preset_detail_page(method: str | None) -> PageName:
    return resolve_zapret2_navigation_pages().preset_detail_page


def get_mode_context_pages(window) -> set:
    mode_context_pages = set()
    z2_pages = resolve_zapret2_navigation_pages()
    for page_name in (
        PageName.DPI_SETTINGS,
        z2_pages.user_presets_page,
        z2_pages.profiles_page,
        PageName.ZAPRET1_MODE_CONTROL,
        PageName.ZAPRET1_MODE,
        PageName.ZAPRET1_USER_PRESETS,
        PageName.ZAPRET1_PROFILE_DETAIL,
        z2_pages.profile_detail_page,
    ):
        page = get_loaded_page(window, page_name)
        if page is not None:
            mode_context_pages.add(page)
    return mode_context_pages


def get_remembered_z2_detail_profile(window) -> tuple[str | None, bool]:
    last_key = getattr(window, "_zapret2_mode_last_opened_profile_key", None)
    want_restore = bool(getattr(window, "_zapret2_mode_restore_profile_detail_on_open", False))
    normalized_key = str(last_key or "").strip() or None
    return normalized_key, want_restore


def remember_z2_detail_profile(window, profile_key: str) -> None:
    try:
        window._zapret2_mode_last_opened_profile_key = str(profile_key or "").strip() or None
        window._zapret2_mode_restore_profile_detail_on_open = True
    except Exception:
        pass


def clear_remembered_z2_detail_profile(window) -> None:
    try:
        window._zapret2_mode_last_opened_profile_key = None
        window._zapret2_mode_restore_profile_detail_on_open = False
    except Exception:
        pass


def open_zapret2_profile_detail(
    window,
    profile_key: str,
    *,
    remember: bool = True,
    show_page_after_open: bool = True,
    allow_internal: bool = False,
) -> bool:
    detail_page = ensure_page(window, PageName.ZAPRET2_PROFILE_DETAIL)
    if detail_page is None:
        return False

    handler = getattr(detail_page, PageMethodName.SHOW_PROFILE, None)
    if not callable(handler):
        return False

    handler(profile_key)

    if show_page_after_open:
        if not show_page(window, PageName.ZAPRET2_PROFILE_DETAIL, allow_internal=allow_internal):
            return False

    if remember:
        remember_z2_detail_profile(window, profile_key)

    return True


def open_zapret1_profile_detail(
    window,
    profile_key: str,
    *,
    allow_internal: bool = False,
) -> bool:
    detail_page = ensure_page(window, PageName.ZAPRET1_PROFILE_DETAIL)
    if detail_page is None:
        return False

    handler = getattr(detail_page, PageMethodName.SHOW_PROFILE, None)
    if not callable(handler):
        return False

    handler(profile_key)

    show_page(window, PageName.ZAPRET1_PROFILE_DETAIL, allow_internal=allow_internal)
    return True


def resolve_navigation_page_for_profiles(
    window,
    method: str | None,
    *,
    allow_restore_z2_detail: bool,
) -> PageName:
    normalized = str(method or "").strip().lower()
    page_name = resolve_profiles_page_for_method(normalized)
    if page_name is None:
        return resolve_control_page_for_method(normalized)

    if normalized != "zapret2_mode" or not allow_restore_z2_detail:
        return page_name

    z2_pages = resolve_zapret2_navigation_pages()
    last_key, want_restore = get_remembered_z2_detail_profile(window)
    if not (want_restore and last_key):
        return page_name

    try:
        if open_zapret2_profile_detail(
            window,
            last_key,
            remember=False,
            show_page_after_open=False,
            allow_internal=True,
        ):
            return z2_pages.profile_detail_page
    except Exception:
        pass

    clear_remembered_z2_detail_profile(window)
    return z2_pages.profiles_page


def open_zapret2_preset_detail_for_method(
    window,
    method: str | None,
    preset_name: str,
    *,
    allow_internal: bool,
) -> None:
    open_preset_detail_page(
        window,
        resolve_zapret2_preset_detail_page(method),
        preset_name,
        allow_internal=allow_internal,
    )


def open_zapret1_preset_detail(window, preset_name: str, *, allow_internal: bool) -> None:
    open_preset_detail_page(
        window,
        resolve_zapret1_navigation_pages().preset_detail_page,
        preset_name,
        allow_internal=allow_internal,
    )


def redirect_to_profiles_page_for_method(window, method: str) -> None:
    current = None
    try:
        current = window.stackedWidget.currentWidget() if hasattr(window, "stackedWidget") else None
    except Exception:
        current = None

    mode_context_pages = get_mode_context_pages(window)

    if current is not None and current not in mode_context_pages:
        return

    show_page(
        window,
        resolve_navigation_page_for_profiles(
            window,
            method,
            allow_restore_z2_detail=False,
        ),
        allow_internal=True,
    )


def show_active_mode_control_page(window, *, allow_internal: bool) -> None:
    method = get_current_launch_method(default="zapret2_mode")
    show_page(
        window,
        resolve_zapret2_navigation_pages().control_page,
        allow_internal=allow_internal,
    )


__all__ = [
    "clear_remembered_z2_detail_profile",
    "get_remembered_z2_detail_profile",
    "get_mode_context_pages",
    "open_zapret1_preset_detail",
    "open_zapret1_profile_detail",
    "open_zapret2_profile_detail",
    "open_zapret2_preset_detail_for_method",
    "redirect_to_profiles_page_for_method",
    "resolve_navigation_page_for_profiles",
    "resolve_zapret2_preset_detail_page",
    "show_active_mode_control_page",
]
