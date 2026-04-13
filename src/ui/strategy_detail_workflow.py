from __future__ import annotations

from log.log import log


from ui.page_method_dispatch import dispatch_detail_page_result
from ui.page_contracts import PageMethodName
from ui.navigation_targets import resolve_strategy_detail_back_page_for_method
from ui.page_names import PageName
from ui.workflows.direct import (
    open_zapret1_strategy_detail,
    open_zapret2_strategy_detail,
)
from ui.window_adapter import show_page


def open_strategy_detail_with_logging(
    window,
    target_key: str,
    *,
    opener,
    error_prefix: str,
) -> bool:
    try:
        return bool(opener(window, target_key))
    except Exception as e:
        log(f"{error_prefix}: {e}", "ERROR")
        return False


def on_open_target_detail(window, target_key: str, current_strategy_id: str) -> None:
    _ = current_strategy_id
    open_strategy_detail_with_logging(
        window,
        target_key,
        opener=lambda w, key: open_zapret2_strategy_detail(w, key, allow_internal=True),
        error_prefix="Error opening target detail",
    )


def on_strategy_detail_back(window) -> None:
    from settings.dpi.strategy_settings import get_strategy_launch_method

    method = get_strategy_launch_method()
    show_page(window, resolve_strategy_detail_back_page_for_method(method))


def on_strategy_detail_selected(window, target_key: str, strategy_id: str) -> bool:
    return dispatch_detail_page_result(
        window,
        PageName.ZAPRET2_DIRECT,
        PageMethodName.APPLY_STRATEGY_SELECTION,
        target_key,
        strategy_id,
        log_message=f"Strategy selected from detail: {target_key} = {strategy_id}",
    )


def on_strategy_detail_filter_mode_changed(window, target_key: str, filter_mode: str) -> bool:
    return dispatch_detail_page_result(
        window,
        PageName.ZAPRET2_DIRECT,
        PageMethodName.APPLY_FILTER_MODE_CHANGE,
        target_key,
        filter_mode,
    )


def open_zapret1_target_detail(window, target_key: str, target_info: dict) -> None:
    _ = target_info
    open_strategy_detail_with_logging(
        window,
        target_key,
        opener=lambda w, key: open_zapret1_strategy_detail(w, key),
        error_prefix="Error opening V1 target detail",
    )


def on_z1_strategy_detail_selected(window, target_key: str, strategy_id: str) -> bool:
    _ = target_key
    _ = strategy_id
    return dispatch_detail_page_result(
        window,
        PageName.ZAPRET1_DIRECT,
        PageMethodName.REFRESH_STRATEGY_LIST_STATE,
        log_message=f"V1 strategy detail selected: {target_key} = {strategy_id}",
        delay_ms=100,
    )
