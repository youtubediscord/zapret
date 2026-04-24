from __future__ import annotations

from filters.strategy_detail.shared_filter_mode import load_target_filter_mode, target_supports_filter_switch
from filters.ui.strategy_detail.zapret1.display_logic import (
    apply_strategy_detail_v1_language,
    default_strategy_id_v1,
    normalize_search_text,
    normalize_target_info_v1,
    refresh_args_preview,
    resolve_sort_mode_change,
    sorted_strategy_items_v1,
    strategy_display_name_v1,
    sync_target_controls,
    update_header_labels,
    update_selected_label,
)
from filters.ui.strategy_detail.zapret1.feedback_helpers import (
    hide_success_feedback_v1,
    show_loading_feedback_v1,
    show_success_feedback_v1,
)
from filters.ui.strategy_detail.zapret1.filtering_ui import (
    apply_search_filter_v1,
    apply_sort_mode_v1,
)
from filters.ui.strategy_detail.zapret1.selection_logic import (
    handle_enable_toggle_v1,
    handle_filter_mode_change_v1,
    handle_strategy_selection_v1,
)
from log.log import log


def load_target_filter_mode_runtime_v1(page, target_key: str) -> str:
    return load_target_filter_mode(
        direct_facade=page._direct_facade,
        target_key=target_key,
        current_payload=getattr(page, "_target_payload", None),
    )


def on_filter_mode_changed_runtime_v1(page, new_mode: str) -> None:
    handle_filter_mode_change_v1(
        direct_facade=page._direct_facade,
        target_key=page._target_key,
        new_mode=new_mode,
        tr_fn=page._tr,
        info_bar_cls=page._info_bar_cls,
        has_fluent=page._HAS_FLUENT,
        parent_window=page.window(),
        log_fn=log,
        sync_target_controls_fn=page._sync_target_controls,
    )


def default_strategy_id_runtime_v1(page) -> str:
    return default_strategy_id_v1(page._strategies, page._sort_mode)


def on_enable_toggled_runtime_v1(page, enabled: bool) -> None:
    handle_enable_toggle_v1(
        direct_facade=page._direct_facade,
        target_key=page._target_key,
        enabled=enabled,
        last_enabled_strategy_id=page._last_enabled_strategy_id,
        default_strategy_id_fn=page._default_strategy_id,
        enable_toggle=page._enable_toggle,
        sync_target_controls_fn=page._sync_target_controls,
        select_strategy_fn=page._on_strategy_selected,
        current_strategy_id=page._current_strategy_id,
        set_last_enabled_strategy_id_fn=lambda value: setattr(page, "_last_enabled_strategy_id", value),
    )


def on_strategy_selected_runtime_v1(page, strategy_id: str) -> None:
    handle_strategy_selection_v1(
        direct_facade=page._direct_facade,
        target_key=page._target_key,
        strategy_id=strategy_id,
        show_loading_fn=page.show_loading,
        set_current_strategy_id_fn=lambda value: setattr(page, "_current_strategy_id", value),
        set_last_enabled_strategy_id_fn=lambda value: setattr(page, "_last_enabled_strategy_id", value),
        update_selected_label_fn=page._update_selected_label,
        refresh_args_preview_fn=page._refresh_args_preview,
        sync_target_controls_fn=page._sync_target_controls,
        apply_tree_selected_strategy_state_fn=page._apply_tree_selected_strategy_state_fn,
        tree=page._tree,
        emit_strategy_selected_fn=page.strategy_selected.emit,
        log_fn=log,
        has_fluent=page._HAS_FLUENT,
        info_bar_cls=page._info_bar_cls,
        tr_fn=page._tr,
        strategy_display_name_fn=page._strategy_display_name,
        parent_window=page.window(),
        show_success_fn=page.show_success,
        reload_target_fn=page._reload_target,
    )


def strategy_display_name_runtime_v1(page, strategy_id: str) -> str:
    return strategy_display_name_v1(strategy_id, page._strategies, page._tr)


def refresh_args_preview_runtime_v1(page) -> None:
    refresh_args_preview(
        args_preview_label=page._args_preview_label,
        tr_fn=page._tr,
        get_current_args_fn=page._get_current_args,
    )


def get_current_args_runtime_v1(page) -> str:
    if not page._direct_facade or not page._target_key:
        return ""
    payload = getattr(page, "_target_payload", None)
    if payload is not None and str(getattr(payload, "target_key", "") or "") == page._target_key:
        return str(getattr(payload, "raw_args_text", "") or "").strip()
    payload = page._load_target_payload_sync(page._target_key, refresh=False)
    if payload is not None:
        return str(getattr(payload, "raw_args_text", "") or "").strip()
    return ""


def update_header_labels_runtime_v1(page) -> None:
    update_header_labels(
        title_label=page._title_label,
        desc_label=page._desc_label,
        subtitle_label=page._subtitle_label,
        tr_fn=page._tr,
        target_info=page._target_info,
        target_key=page._target_key,
        update_selected_label_fn=page._update_selected_label,
    )


def update_selected_label_runtime_v1(page) -> None:
    update_selected_label(
        selected_label=page._selected_label,
        tr_fn=page._tr,
        current_strategy_id=page._current_strategy_id,
        strategy_display_name_fn=page._strategy_display_name,
    )


def on_search_text_changed_runtime_v1(page, text: str) -> None:
    page._search_text = normalize_search_text(text)
    page._apply_search_filter()


def on_sort_combo_changed_runtime_v1(page, *_args) -> None:
    mode = resolve_sort_mode_change(
        sort_combo=page._sort_combo,
        current_sort_mode=page._sort_mode,
    )
    if mode is None:
        return
    page._sort_mode = mode
    page._rebuild_tree_rows()


def apply_sort_mode_runtime_v1(page) -> None:
    apply_sort_mode_v1(
        tree=page._tree,
        sort_mode=page._sort_mode,
    )


def apply_search_filter_runtime_v1(page) -> None:
    apply_search_filter_v1(
        tree=page._tree,
        search_text=page._search_text,
    )


def target_supports_filter_switch_runtime_v1(page) -> bool:
    return target_supports_filter_switch(page._target_info)


def sync_target_controls_runtime_v1(page) -> None:
    sync_target_controls(
        enable_toggle=page._enable_toggle,
        edit_args_btn=page._edit_args_btn,
        filter_mode_frame=page._filter_mode_frame,
        filter_mode_selector=page._filter_mode_selector,
        current_strategy_id=page._current_strategy_id,
        target_key=page._target_key,
        target_info=page._target_info,
        load_target_filter_mode_fn=page._load_target_filter_mode,
    )


def show_loading_runtime_v1(page) -> None:
    show_loading_feedback_v1(
        cleanup_in_progress=page._cleanup_in_progress,
        spinner=page._spinner,
        success_icon=page._success_icon,
    )


def show_success_runtime_v1(page) -> None:
    try:
        from ui.theme import get_cached_qta_pixmap

        success_pixmap = get_cached_qta_pixmap("fa5s.check-circle", color="#6ccb5f", size=16)
    except Exception:
        success_pixmap = None

    show_success_feedback_v1(
        cleanup_in_progress=page._cleanup_in_progress,
        spinner=page._spinner,
        success_icon=page._success_icon,
        success_timer=page._success_timer,
        success_pixmap=success_pixmap,
    )


def hide_success_runtime_v1(page) -> None:
    hide_success_feedback_v1(
        cleanup_in_progress=page._cleanup_in_progress,
        spinner=page._spinner,
        success_icon=page._success_icon,
    )
