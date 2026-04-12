from __future__ import annotations

from ui.navigation_targets import (
    resolve_control_page_for_method,
    resolve_zapret1_navigation_pages,
    resolve_zapret2_navigation_pages,
)
from ui.page_contracts import PageMethodName
from ui.page_names import PageName
from ui.window_adapter import ensure_window_adapter
from ui.workflows.common import (
    call_page_method,
    get_current_launch_method,
    open_preset_detail_page,
    refresh_or_show_page_after_refresh_if_possible,
)


def resolve_zapret2_user_presets_page(method: str | None) -> PageName:
    return resolve_zapret2_navigation_pages(method).user_presets_page


def resolve_zapret2_preset_detail_page(method: str | None) -> PageName:
    return resolve_zapret2_navigation_pages(method).preset_detail_page


def get_strategies_context_pages(window) -> set:
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
        page = ensure_window_adapter(window).get_loaded_page(page_name)
        if page is not None:
            strategies_context_pages.add(page)
    return strategies_context_pages


def get_remembered_z2_detail_target(window) -> tuple[str | None, bool]:
    last_key = getattr(window, "_direct_zapret2_last_opened_target_key", None)
    want_restore = bool(getattr(window, "_direct_zapret2_restore_detail_on_open", False))
    normalized_key = str(last_key or "").strip() or None
    return normalized_key, want_restore


def remember_z2_detail_target(window, target_key: str) -> None:
    try:
        window._direct_zapret2_last_opened_target_key = str(target_key or "").strip() or None
        window._direct_zapret2_restore_detail_on_open = True
    except Exception:
        pass


def clear_remembered_z2_detail_target(window) -> None:
    try:
        window._direct_zapret2_last_opened_target_key = None
        window._direct_zapret2_restore_detail_on_open = False
    except Exception:
        pass


def open_zapret2_strategy_detail(
    window,
    target_key: str,
    *,
    remember: bool = True,
    show_page_after_open: bool = True,
    allow_internal: bool = False,
) -> bool:
    detail_page = ensure_window_adapter(window).ensure_page(PageName.ZAPRET2_STRATEGY_DETAIL)
    if detail_page is None:
        return False

    if not call_page_method(detail_page, PageMethodName.SHOW_TARGET, target_key):
        return False

    if show_page_after_open:
        ensure_window_adapter(window).show_page(PageName.ZAPRET2_STRATEGY_DETAIL, allow_internal=allow_internal)

    if remember:
        remember_z2_detail_target(window, target_key)

    return True


def open_zapret1_strategy_detail(
    window,
    target_key: str,
    *,
    allow_internal: bool = False,
) -> bool:
    detail_page = ensure_window_adapter(window).ensure_page(PageName.ZAPRET1_STRATEGY_DETAIL)
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

    if not call_page_method(detail_page, PageMethodName.SHOW_TARGET, target_key, manager):
        return False

    ensure_window_adapter(window).show_page(PageName.ZAPRET1_STRATEGY_DETAIL, allow_internal=allow_internal)
    return True


def resolve_navigation_target_for_strategies(
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
    last_key, want_restore = get_remembered_z2_detail_target(window)
    if not (want_restore and last_key):
        return target_page

    try:
        from core.presets.direct_facade import DirectPresetFacade

        facade = DirectPresetFacade.from_launch_method("direct_zapret2", app_context=window.app_context)
        if facade.get_target_ui_item(last_key) and open_zapret2_strategy_detail(
            window,
            last_key,
            remember=False,
            show_page_after_open=False,
            allow_internal=True,
        ):
            return z2_direct.strategy_detail_page
    except Exception:
        pass

    clear_remembered_z2_detail_target(window)
    return z2_direct.control_page


def open_zapret2_preset_detail(window, method: str | None, preset_name: str, *, allow_internal: bool) -> None:
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


def show_active_zapret2_user_presets_page(window, *, allow_internal: bool) -> None:
    method = get_current_launch_method()
    refresh_or_show_page_after_refresh_if_possible(
        window,
        resolve_zapret2_user_presets_page(method),
        show_page_after_refresh=True,
        allow_internal=allow_internal,
    )


def show_zapret1_user_presets_page(window, *, allow_internal: bool) -> None:
    refresh_or_show_page_after_refresh_if_possible(
        window,
        resolve_zapret1_navigation_pages().user_presets_page,
        show_page_after_refresh=True,
        allow_internal=allow_internal,
    )


def refresh_active_zapret2_user_presets_page(window, *, allow_internal: bool) -> None:
    method = get_current_launch_method()
    refresh_or_show_page_after_refresh_if_possible(
        window,
        resolve_zapret2_user_presets_page(method),
        show_page_after_refresh=False,
        allow_internal=allow_internal,
    )


def refresh_zapret1_user_presets_page(window, *, allow_internal: bool) -> None:
    refresh_or_show_page_after_refresh_if_possible(
        window,
        resolve_zapret1_navigation_pages().user_presets_page,
        show_page_after_refresh=False,
        allow_internal=allow_internal,
    )


def show_active_zapret2_control_page(window, *, allow_internal: bool) -> None:
    method = get_current_launch_method(default="direct_zapret2")
    ensure_window_adapter(window).show_page(
        resolve_zapret2_navigation_pages(method).control_page,
        allow_internal=allow_internal,
    )


def navigate_to_control(window, *, allow_internal: bool) -> None:
    method = get_current_launch_method()
    ensure_window_adapter(window).show_page(
        resolve_control_page_for_method(method),
        allow_internal=allow_internal,
    )


def navigate_to_strategies(window, *, allow_internal: bool) -> None:
    method = get_current_launch_method(default="direct_zapret2")
    target_page = resolve_navigation_target_for_strategies(
        window,
        method,
        allow_restore_z2_detail=True,
    )
    ensure_window_adapter(window).show_page(target_page, allow_internal=allow_internal)


__all__ = [
    "clear_remembered_z2_detail_target",
    "get_remembered_z2_detail_target",
    "get_strategies_context_pages",
    "navigate_to_control",
    "navigate_to_strategies",
    "open_zapret1_preset_detail",
    "open_zapret1_strategy_detail",
    "open_zapret2_preset_detail",
    "open_zapret2_strategy_detail",
    "refresh_active_zapret2_user_presets_page",
    "refresh_zapret1_user_presets_page",
    "remember_z2_detail_target",
    "resolve_navigation_target_for_strategies",
    "resolve_zapret2_preset_detail_page",
    "resolve_zapret2_user_presets_page",
    "show_active_zapret2_control_page",
    "show_active_zapret2_user_presets_page",
    "show_zapret1_user_presets_page",
]
