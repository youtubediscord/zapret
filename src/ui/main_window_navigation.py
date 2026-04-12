from __future__ import annotations

from ui.main_window_pages import get_loaded_page
from ui.router import (
    resolve_control_page_for_method,
    resolve_zapret1_navigation_pages,
    resolve_zapret2_navigation_pages,
)
from ui.page_names import PageName


def refresh_page_if_possible(window, page_name: PageName) -> None:
    page = window._ensure_page(page_name)
    if page is None:
        return
    _call_page_method(page, "refresh_presets_view_if_possible")


def _call_page_method(page, method_name: str, *args) -> bool:
    if page is None:
        return False
    handler = getattr(page, method_name, None)
    if not callable(handler):
        return False
    try:
        handler(*args)
        return True
    except Exception:
        return False


def _refresh_or_show_page_after_refresh_if_possible(
    window,
    page_name: PageName,
    *,
    show_page: bool,
) -> None:
    refresh_page_if_possible(window, page_name)
    if show_page:
        window.show_page(page_name)

def _get_current_launch_method(*, default: str = "") -> str:
    try:
        from strategy_menu import get_strategy_launch_method

        return str(get_strategy_launch_method() or "").strip().lower()
    except Exception:
        return str(default or "").strip().lower()

def _resolve_zapret2_user_presets_page(method: str | None) -> PageName:
    return resolve_zapret2_navigation_pages(method).user_presets_page


def _resolve_zapret2_preset_detail_page(method: str | None) -> PageName:
    return resolve_zapret2_navigation_pages(method).preset_detail_page


def _show_static_page(window, page_name: PageName) -> None:
    window.show_page(page_name)


def _get_strategies_context_pages(window) -> set:
    strategies_context_pages = set()
    z2_direct = resolve_zapret2_navigation_pages("direct_zapret2")
    for page_name in (
        PageName.DPI_SETTINGS,
        z2_direct.user_presets_page,
        z2_direct.strategies_page,
        PageName.ZAPRET1_DIRECT_CONTROL,
        PageName.ZAPRET1_DIRECT,
        PageName.ZAPRET1_USER_PRESETS,
        z2_direct.strategy_detail_page,
    ):
        page = get_loaded_page(window, page_name)
        if page is not None:
            strategies_context_pages.add(page)
    return strategies_context_pages


def _get_remembered_z2_detail_target(window) -> tuple[str | None, bool]:
    last_key = getattr(window, "_direct_zapret2_last_opened_target_key", None)
    want_restore = bool(getattr(window, "_direct_zapret2_restore_detail_on_open", False))
    normalized_key = str(last_key or "").strip() or None
    return normalized_key, want_restore


def _remember_z2_detail_target(window, target_key: str) -> None:
    try:
        window._direct_zapret2_last_opened_target_key = str(target_key or "").strip() or None
        window._direct_zapret2_restore_detail_on_open = True
    except Exception:
        pass


def _clear_remembered_z2_detail_target(window) -> None:
    try:
        window._direct_zapret2_last_opened_target_key = None
        window._direct_zapret2_restore_detail_on_open = False
    except Exception:
        pass


def _resolve_navigation_target_for_strategies(
    window,
    method: str | None,
    *,
    allow_restore_z2_detail: bool,
) -> PageName:
    normalized = str(method or "").strip().lower()
    target_page = resolve_control_page_for_method(normalized)

    if normalized != "direct_zapret2" or not allow_restore_z2_detail:
        return target_page

    z2_direct = resolve_zapret2_navigation_pages("direct_zapret2")
    last_key, want_restore = _get_remembered_z2_detail_target(window)
    if not (want_restore and last_key):
        return target_page

    try:
        from core.presets.direct_facade import DirectPresetFacade

        facade = DirectPresetFacade.from_launch_method("direct_zapret2", app_context=window.app_context)
        if facade.get_target_ui_item(last_key) and open_zapret2_strategy_detail(
            window,
            last_key,
            remember=False,
            show_page=False,
        ):
            return z2_direct.strategy_detail_page
    except Exception:
        pass

    _clear_remembered_z2_detail_target(window)
    return z2_direct.control_page


def _open_preset_detail_page(window, page_name: PageName, preset_name: str) -> None:
    page = window._ensure_page(page_name)
    if page is None:
        return
    _call_page_method(page, "set_preset_file_name", preset_name)
    window.show_page(page_name)


def open_zapret2_strategy_detail(
    window,
    target_key: str,
    *,
    remember: bool = True,
    show_page: bool = True,
) -> bool:
    detail_page = window._ensure_page(PageName.ZAPRET2_STRATEGY_DETAIL)
    if detail_page is None:
        return False

    if not _call_page_method(detail_page, "show_target", target_key):
        return False

    if show_page:
        window.show_page(PageName.ZAPRET2_STRATEGY_DETAIL)

    if remember:
        _remember_z2_detail_target(window, target_key)

    return True


def open_zapret1_strategy_detail(window, target_key: str) -> bool:
    detail_page = window._ensure_page(PageName.ZAPRET1_STRATEGY_DETAIL)
    if detail_page is None:
        return False

    try:
        from core.presets.direct_facade import DirectPresetFacade

        def _reload_dpi() -> None:
            try:
                from direct_launch.flow.apply_policy import request_direct_runtime_content_apply

                request_direct_runtime_content_apply(
                    window,
                    launch_method="direct_zapret1",
                    reason="target_settings_changed",
                    target_key=target_key,
                )
            except Exception:
                pass

        manager = DirectPresetFacade.from_launch_method(
            "direct_zapret1",
            app_context=window.app_context,
            on_dpi_reload_needed=_reload_dpi,
        )
    except Exception:
        return False

    if not _call_page_method(detail_page, "show_target", target_key, manager):
        return False

    window.show_page(PageName.ZAPRET1_STRATEGY_DETAIL)
    return True


def show_active_zapret2_user_presets_page(window) -> None:
    method = _get_current_launch_method()
    _refresh_or_show_page_after_refresh_if_possible(
        window,
        _resolve_zapret2_user_presets_page(method),
        show_page=True,
    )


def show_zapret1_user_presets_page(window) -> None:
    _refresh_or_show_page_after_refresh_if_possible(
        window,
        resolve_zapret1_navigation_pages().user_presets_page,
        show_page=True,
    )


def refresh_active_zapret2_user_presets_page(window) -> None:
    method = _get_current_launch_method()
    _refresh_or_show_page_after_refresh_if_possible(
        window,
        _resolve_zapret2_user_presets_page(method),
        show_page=False,
    )


def refresh_zapret1_user_presets_page(window) -> None:
    _refresh_or_show_page_after_refresh_if_possible(
        window,
        resolve_zapret1_navigation_pages().user_presets_page,
        show_page=False,
    )


def open_zapret2_preset_detail(window, preset_name: str) -> None:
    method = _get_current_launch_method()
    _open_preset_detail_page(window, _resolve_zapret2_preset_detail_page(method), preset_name)


def open_zapret1_preset_detail(window, preset_name: str) -> None:
    _open_preset_detail_page(window, resolve_zapret1_navigation_pages().preset_detail_page, preset_name)


def redirect_to_strategies_page_for_method(window, method: str) -> None:
    current = None
    try:
        current = window.stackedWidget.currentWidget() if hasattr(window, "stackedWidget") else None
    except Exception:
        current = None

    strategies_context_pages = _get_strategies_context_pages(window)

    if current is not None and current not in strategies_context_pages:
        return

    window.show_page(
        _resolve_navigation_target_for_strategies(
            window,
            method,
            allow_restore_z2_detail=False,
        )
    )


def show_autostart_page(window) -> None:
    _show_static_page(window, PageName.AUTOSTART)


def show_hosts_page(window) -> None:
    _show_static_page(window, PageName.HOSTS)


def show_servers_page(window) -> None:
    _show_static_page(window, PageName.SERVERS)


def show_active_zapret2_control_page(window) -> None:
    method = _get_current_launch_method(default="direct_zapret2")
    window.show_page(resolve_zapret2_navigation_pages(method).control_page)


def navigate_to_control(window) -> None:
    method = _get_current_launch_method()
    window.show_page(resolve_control_page_for_method(method))


def navigate_to_strategies(window) -> None:
    method = _get_current_launch_method(default="direct_zapret2")
    target_page = _resolve_navigation_target_for_strategies(
        window,
        method,
        allow_restore_z2_detail=True,
    )
    window.show_page(target_page)
