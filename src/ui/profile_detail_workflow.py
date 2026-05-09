from __future__ import annotations

from log.log import log


from ui.page_method_dispatch import dispatch_detail_page_result
from ui.page_contracts import PageMethodName
from ui.navigation_pages import resolve_profile_detail_back_page_for_method
from ui.page_names import PageName
from ui.workflows.mode import (
    open_zapret1_profile_detail,
    open_zapret2_profile_detail,
)
from ui.window_adapter import show_page


def open_profile_detail_with_logging(
    window,
    profile_key: str,
    *,
    opener,
    error_prefix: str,
) -> bool:
    try:
        return bool(opener(window, profile_key))
    except Exception as e:
        log(f"{error_prefix}: {e}", "ERROR")
        return False


def on_open_profile_detail(window, profile_key: str, current_strategy_id: str) -> None:
    _ = current_strategy_id
    open_profile_detail_with_logging(
        window,
        profile_key,
        opener=lambda w, key: open_zapret2_profile_detail(w, key, allow_internal=True),
        error_prefix="Error opening profile detail",
    )


def on_open_z1_profile_detail(window, profile_key: str, current_strategy_id: str) -> None:
    _ = current_strategy_id
    open_profile_detail_with_logging(
        window,
        profile_key,
        opener=lambda w, key: open_zapret1_profile_detail(w, key, allow_internal=True),
        error_prefix="Error opening Zapret 1 profile detail",
    )


def on_profile_detail_back(window) -> None:
    from settings.dpi.strategy_settings import get_strategy_launch_method

    method = get_strategy_launch_method()
    show_page(window, resolve_profile_detail_back_page_for_method(method))


def on_profile_detail_selected(window, profile_key: str, strategy_id: str) -> bool:
    return dispatch_detail_page_result(
        window,
        PageName.ZAPRET2_MODE,
        PageMethodName.APPLY_STRATEGY_SELECTION,
        profile_key,
        strategy_id,
        log_message=f"Strategy selected from profile detail: {profile_key} = {strategy_id}",
    )


def on_z1_profile_detail_selected(window, profile_key: str, strategy_id: str) -> bool:
    return dispatch_detail_page_result(
        window,
        PageName.ZAPRET1_MODE,
        PageMethodName.APPLY_STRATEGY_SELECTION,
        profile_key,
        strategy_id,
        log_message=f"Zapret 1 strategy selected from profile detail: {profile_key} = {strategy_id}",
    )
