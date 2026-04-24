from __future__ import annotations

from ui.navigation_targets import (
    resolve_zapret1_navigation_pages,
    resolve_zapret2_navigation_pages,
)
from ui.page_contracts import PageMethodName
from ui.page_names import PageName
from ui.window_adapter import ensure_page, get_loaded_page, show_page
from ui.workflows.common import (
    call_page_method,
    get_current_launch_method,
    open_preset_detail_page,
)


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
        page = get_loaded_page(window, page_name)
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
    detail_page = ensure_page(window, PageName.ZAPRET2_STRATEGY_DETAIL)
    if detail_page is None:
        return False

    handler = getattr(detail_page, PageMethodName.SHOW_TARGET, None)
    if not callable(handler):
        return False

    handler(target_key)

    if show_page_after_open:
        if not show_page(window, PageName.ZAPRET2_STRATEGY_DETAIL, allow_internal=allow_internal):
            return False

    if remember:
        remember_z2_detail_target(window, target_key)

    return True


def open_zapret1_strategy_detail(
    window,
    target_key: str,
    *,
    allow_internal: bool = False,
) -> bool:
    detail_page = ensure_page(window, PageName.ZAPRET1_STRATEGY_DETAIL)
    if detail_page is None:
        return False

    try:
        from direct_preset.facade import DirectPresetFacade

        def _reload_dpi() -> None:
            try:
                from winws_runtime.flow.apply_policy import request_direct_runtime_content_apply

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

    show_page(window, PageName.ZAPRET1_STRATEGY_DETAIL, allow_internal=allow_internal)
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
        from direct_preset.facade import DirectPresetFacade

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


def redirect_to_strategies_page_for_method(window, method: str) -> None:
    current = None
    try:
        current = window.stackedWidget.currentWidget() if hasattr(window, "stackedWidget") else None
    except Exception:
        current = None

    strategies_context_pages = get_strategies_context_pages(window)

    if current is not None and current not in strategies_context_pages:
        return

    show_page(
        window,
        resolve_navigation_target_for_strategies(
            window,
            method,
            allow_restore_z2_detail=False,
        ),
        allow_internal=True,
    )


def show_active_zapret2_control_page(window, *, allow_internal: bool) -> None:
    method = get_current_launch_method(default="direct_zapret2")
    show_page(
        window,
        resolve_zapret2_navigation_pages(method).control_page,
        allow_internal=allow_internal,
    )


__all__ = [
    "clear_remembered_z2_detail_target",
    "get_remembered_z2_detail_target",
    "get_strategies_context_pages",
    "open_zapret1_preset_detail",
    "open_zapret1_strategy_detail",
    "open_zapret2_preset_detail_for_method",
    "open_zapret2_strategy_detail",
    "remember_z2_detail_target",
    "redirect_to_strategies_page_for_method",
    "resolve_navigation_target_for_strategies",
    "resolve_zapret2_preset_detail_page",
    "show_active_zapret2_control_page",
]
