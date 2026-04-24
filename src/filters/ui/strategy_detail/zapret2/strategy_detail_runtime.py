from __future__ import annotations

import time as _time
from collections.abc import Callable

from PyQt6.QtCore import QEvent, QTimer
from PyQt6.QtWidgets import QApplication

from direct_preset.runtime import DirectTargetDetailSnapshotWorker
from log.log import log
from ui.theme import get_theme_tokens, get_themed_qta_icon

from filters.strategy_detail.zapret2.payload_logic import (
    build_payload_loaded_plan,
    build_preset_refresh_plan,
    build_target_payload_apply_plan,
    build_target_payload_request_plan,
)
from filters.strategy_detail.zapret2.target_payload_workflow import (
    apply_preset_refresh,
    handle_loaded_payload,
    start_target_payload_request,
)
from filters.ui.strategy_detail.zapret2.apply import apply_target_payload_header_state
from filters.ui.strategy_detail.zapret2.common import log_z2_detail_metric as _log_z2_detail_metric
from filters.ui.strategy_detail.zapret2.target_payload_apply import (
    apply_payload_reuse_plan,
    finalize_target_payload_apply_ui,
    prepare_target_payload_apply_ui,
)
from filters.ui.strategy_detail.shared_detail_header import build_detail_header_text_state


def after_content_built(page) -> None:
    page._content_built = True

    # Close hover/pinned preview when the main window hides/deactivates (e.g. tray).
    QTimer.singleShot(0, lambda: (not page._cleanup_in_progress) and install_host_window_event_filter(page))

    apply_pending_target_request_if_ready(page)


def install_host_window_event_filter(page) -> None:
    if page._cleanup_in_progress:
        return
    try:
        window = page.window()
    except Exception:
        window = None
    if not window or window is page._host_window:
        return
    page._host_window = window
    try:
        window.installEventFilter(page)
    except Exception:
        pass


def handle_host_window_event_filter(page, obj, event, *, super_handler: Callable[[], object]):
    try:
        if obj is page._host_window and event is not None:
            event_type = event.type()
            if event_type in (
                QEvent.Type.Hide,
                QEvent.Type.Close,
                QEvent.Type.WindowDeactivate,
                QEvent.Type.WindowStateChange,
            ):
                # Don't close if focus went to the preview dialog itself.
                if event_type == QEvent.Type.WindowDeactivate and page._preview_dialog is not None:
                    try:
                        active = QApplication.activeWindow()
                        if active is not None and active is page._preview_dialog:
                            return super_handler()
                    except Exception:
                        pass
                page._close_preview_dialog(force=True)
                close_filter_combo_popup(page)
    except Exception:
        pass
    return super_handler()


def close_filter_combo_popup(page) -> None:
    """Close the technique filter ComboBox dropdown if it is open."""
    try:
        combo = getattr(page, "_filter_combo", None)
        if combo is not None and hasattr(combo, "_closeComboMenu"):
            combo._closeComboMenu()
    except Exception:
        pass


def apply_page_theme(page, tokens=None, force: bool = False) -> None:
    try:
        tokens = tokens or get_theme_tokens()
    except Exception:
        return

    key = (
        str(tokens.theme_name),
        str(tokens.fg),
        str(tokens.fg_muted),
        str(tokens.fg_faint),
        str(tokens.accent_hex),
    )
    if not force and key == page._last_theme_overrides_key:
        return
    page._last_theme_overrides_key = key

    try:
        detail_text_color = tokens.fg_muted if tokens.is_light else tokens.fg
        if getattr(page, "_subtitle_strategy", None) is not None:
            subtitle_style = f"background: transparent; padding-left: 10px; color: {detail_text_color};"
            if page._subtitle_strategy.styleSheet() != subtitle_style:
                page._subtitle_strategy.setStyleSheet(subtitle_style)
    except Exception:
        pass

    try:
        if getattr(page, "_parent_link", None) is not None:
            parent_color = str(tokens.fg_muted)
            if parent_color != page._last_parent_link_icon_color:
                page._parent_link.setIcon(get_themed_qta_icon("fa5s.chevron-left", color=parent_color))
                page._last_parent_link_icon_color = parent_color
    except Exception:
        pass

    try:
        if not getattr(page, "_HAS_FLUENT", False) and getattr(page, "_edit_args_btn", None) is not None:
            edit_color = str(tokens.fg_faint)
            if edit_color != page._last_edit_args_icon_color:
                page._edit_args_btn.setIcon(get_themed_qta_icon("fa5s.edit", color=edit_color))
                page._last_edit_args_icon_color = edit_color
    except Exception:
        pass

    try:
        page._update_sort_button_ui()
    except Exception:
        pass


def handle_hide_event(page, event, *, super_handler: Callable[[], object]):
    # Ensure floating preview/tool windows do not keep intercepting mouse events
    # after navigation away from this page.
    try:
        save_scroll_state(page)
    except Exception:
        pass
    try:
        page._close_preview_dialog(force=True)
    except Exception:
        pass
    try:
        close_filter_combo_popup(page)
    except Exception:
        pass
    try:
        page._stop_loading()
    except Exception:
        pass
    page._preset_refresh_runtime.mark_pending()
    try:
        page._strategies_load_runtime.reset(delete_later=False)
    except Exception:
        pass
    return super_handler()


def handle_page_activated(page) -> None:
    apply_pending_target_request_if_ready(page)
    if page._preset_refresh_runtime.consume_pending():
        page.refresh_from_preset_switch()


def refresh_scroll_range(page) -> None:
    # Ensure QScrollArea recomputes range after dynamic content growth.
    try:
        if page.layout is not None:
            page.layout.invalidate()
            page.layout.activate()
    except Exception:
        pass


def apply_pending_target_request_if_ready(page) -> None:
    if page._cleanup_in_progress:
        return
    pending_target_key = page._target_payload_runtime.take_pending_target_if_ready(
        is_visible=page.isVisible(),
        content_built=bool(getattr(page, "_content_built", False)),
    )
    if not pending_target_key:
        return

    try:
        page._request_target_payload(pending_target_key, refresh=False, reason="show_target")
    except Exception:
        page._target_payload_runtime.restore_pending_target(pending_target_key)
    try:
        if hasattr(page, "content") and page.content is not None:
            page.content.updateGeometry()
            page.content.adjustSize()
    except Exception:
        pass
    try:
        page.updateGeometry()
        page.viewport().update()
    except Exception:
        pass


def save_scroll_state(page, target_key: str | None = None) -> None:
    key = str(target_key or page._target_key or "").strip()
    if not key:
        return

    try:
        bar = page.verticalScrollBar()
        page._page_scroll_by_target[key] = int(bar.value())
    except Exception:
        pass

    try:
        if page._strategies_tree:
            tree_bar = page._strategies_tree.verticalScrollBar()
            page._tree_scroll_by_target[key] = int(tree_bar.value())
    except Exception:
        pass


def restore_scroll_state(page, target_key: str | None = None, defer: bool = False) -> None:
    key = str(target_key or page._target_key or "").strip()
    if not key:
        return

    def _apply() -> None:
        if page._cleanup_in_progress:
            return
        try:
            page_bar = page.verticalScrollBar()
            saved_page = page._page_scroll_by_target.get(key)
            if saved_page is None:
                page_bar.setValue(page_bar.minimum())
            else:
                page_bar.setValue(max(page_bar.minimum(), min(int(saved_page), page_bar.maximum())))
        except Exception:
            pass

        try:
            if not page._strategies_tree:
                return
            tree_bar = page._strategies_tree.verticalScrollBar()
            saved_tree = page._tree_scroll_by_target.get(key)
            if saved_tree is None:
                return
            tree_bar.setValue(max(tree_bar.minimum(), min(int(saved_tree), tree_bar.maximum())))
        except Exception:
            pass

    if defer:
        QTimer.singleShot(0, lambda: (not page._cleanup_in_progress) and _apply())
        QTimer.singleShot(40, lambda: (not page._cleanup_in_progress) and _apply())
    else:
        _apply()


def prepare_target_payload_request_ui(page, target_key: str) -> None:
    normalized_key = str(target_key or "").strip().lower()
    page._target_key = normalized_key
    page._stop_loading()
    page.show_loading()
    page._success_icon.hide()
    page._target_payload = None
    preview_target_info = None
    try:
        preview_target_info = page._direct_facade.get_target_ui_item(normalized_key)
    except Exception:
        preview_target_info = None
    page._target_info = preview_target_info
    try:
        page._settings_host.setVisible(False)
    except Exception:
        pass
    try:
        page._toolbar_frame.setVisible(False)
    except Exception:
        pass
    try:
        page._strategies_block.setVisible(False)
    except Exception:
        pass
    try:
        header_state = build_detail_header_text_state(
            target_info=preview_target_info,
            target_key=normalized_key,
            tr=page._tr,
            ports_text_key="page.z2_strategy_detail.subtitle.ports",
            ports_text_default="порты: {ports}",
            empty_title="",
            empty_detail=page._tr("page.z2_strategy_detail.header.category_fallback", "Target"),
        )
        apply_target_payload_header_state(
            page._title,
            page._subtitle,
            page._breadcrumb,
            title_text=header_state.title_text,
            subtitle_text=header_state.subtitle_text,
            detail_text=header_state.detail_text,
            control_text=page._tr("page.z2_strategy_detail.breadcrumb.control", "Управление"),
            strategies_text=page._tr("page.z2_strategy_detail.breadcrumb.strategies", "Стратегии DPI"),
        )
    except Exception:
        pass
    try:
        page._update_selected_strategy_header("none")
    except Exception:
        pass


def request_target_payload(page, target_key: str, *, refresh: bool, reason: str) -> None:
    request = start_target_payload_request(
        target_key=target_key,
        reason=reason,
        refresh=refresh,
        current_request_id=page._target_payload_runtime.current_request_id(),
        build_request_plan_fn=build_target_payload_request_plan,
        issue_page_load_token_fn=page.issue_page_load_token,
        snapshot_service=page._require_app_context().direct_ui_snapshot_service,
        prepare_request_fn=lambda normalized_key: prepare_target_payload_request_ui(page, normalized_key),
        now_fn=_time.perf_counter,
        worker_cls=DirectTargetDetailSnapshotWorker,
        worker_kwargs={
            "direct_mode_override": page._current_direct_mode(),
        },
        parent=page,
        on_loaded_callback=page._on_target_payload_loaded,
    )
    if request is None:
        return

    request_id, started_at, worker = request
    page._target_payload_runtime.register_request(
        request_id=request_id,
        started_at=started_at,
        worker=worker,
    )
    worker.start()


def on_target_payload_loaded(page, request_id: int, snapshot, token: int, *, reason: str) -> None:
    handle_loaded_payload(
        request_id=request_id,
        snapshot=snapshot,
        token=token,
        reason=reason,
        current_request_id=page._target_payload_runtime.current_request_id(),
        fallback_target_key=page._target_key,
        token_is_current_fn=page.is_page_load_token_current,
        build_loaded_plan_fn=build_payload_loaded_plan,
        stop_loading_fn=page._stop_loading,
        hide_success_icon_fn=lambda: page._success_icon.hide(),
        log_fn=log,
        apply_payload_fn=page._apply_target_payload,
        started_at=page._target_payload_runtime.request_started_at,
    )


def apply_target_payload(page, normalized_key: str, payload, *, reason: str, started_at: float | None = None) -> None:
    started = started_at if started_at is not None else _time.perf_counter()
    log(f"StrategyDetailPage.show_target: {normalized_key}", "DEBUG")
    page._target_key = normalized_key
    page._target_payload = payload
    target_info = payload.target_item
    apply_plan = build_target_payload_apply_plan(
        payload=payload,
        has_strategy_rows=bool(page._strategies_tree and page._strategies_tree.has_rows()),
        loaded_strategy_type=page._loaded_strategy_type,
        loaded_direct_mode=page._loaded_direct_mode,
        loaded_tcp_phase_mode=page._loaded_tcp_phase_mode,
        direct_mode_override=page._current_direct_mode(),
        tr=page._tr,
    )
    policy = apply_plan.policy
    page._target_info = target_info
    page._current_strategy_id = apply_plan.current_strategy_id
    page._selected_strategy_id = apply_plan.selected_strategy_id
    page._favorite_strategy_ids = prepare_target_payload_apply_ui(
        normalized_key=normalized_key,
        feedback_store=page._feedback_store,
        close_preview_fn=page._close_preview_dialog,
        settings_host=page._settings_host,
        toolbar_frame=page._toolbar_frame,
        title_label=page._title,
        subtitle_label=page._subtitle,
        breadcrumb=page._breadcrumb,
        apply_plan=apply_plan,
        detail_text=target_info.full_name,
        control_text=page._tr("page.z2_strategy_detail.breadcrumb.control", "Управление"),
        strategies_text=page._tr("page.z2_strategy_detail.breadcrumb.strategies", "Стратегии DPI"),
        apply_header_state_fn=apply_target_payload_header_state,
    )
    page._update_selected_strategy_header(page._selected_strategy_id)

    page._apply_phase_mode_policy(policy)
    reuse_list = apply_plan.should_reuse_list

    apply_payload_reuse_plan(
        reuse_list=reuse_list,
        clear_strategies_fn=page._clear_strategies,
        load_strategies_fn=page._load_strategies,
        policy=policy,
        strategies_tree=page._strategies_tree,
        favorite_ids=page._favorite_strategy_ids,
        refresh_working_marks_fn=page._refresh_working_marks_for_target,
        current_strategy_id=page._current_strategy_id,
        restore_scroll_state_fn=page._restore_scroll_state,
        normalized_key=normalized_key,
    )

    is_enabled = apply_plan.target_enabled
    page._update_status_icon(is_enabled)

    if page._tcp_phase_mode:
        page._load_tcp_phase_state_from_preset()
        page._apply_tcp_phase_tabs_visibility()
        preferred = None
        try:
            preferred = (page._last_active_phase_key_by_target or {}).get(normalized_key)
        except Exception:
            preferred = None
        if not preferred:
            preferred = page._load_target_last_tcp_phase_tab(normalized_key)
            if preferred:
                try:
                    page._last_active_phase_key_by_target[normalized_key] = preferred
                except Exception:
                    pass
        if preferred:
            page._set_active_phase_chip(preferred)
        else:
            page._select_default_tcp_phase_tab()

    finalize_target_payload_apply_ui(
        policy=policy,
        normalized_key=normalized_key,
        load_target_filter_mode_fn=page._load_target_filter_mode,
        filter_mode_selector=page._filter_mode_selector,
        apply_target_mode_visibility_fn=page._apply_target_mode_visibility,
        search_input=page._search_input,
        active_filters=page._active_filters,
        load_target_sort_fn=page._load_target_sort,
        set_sort_mode_fn=lambda mode: setattr(page, "_sort_mode", mode),
        update_technique_filter_ui_fn=page._update_technique_filter_ui,
        apply_sort_fn=page._apply_sort,
        apply_filters_fn=page._apply_filters,
        load_syndata_settings_fn=page._load_syndata_settings,
        apply_syndata_settings_fn=page._apply_syndata_settings,
        refresh_args_editor_state_fn=page._refresh_args_editor_state,
        set_target_enabled_ui_fn=page._set_target_enabled_ui,
        target_enabled=is_enabled,
        stop_loading_fn=page._stop_loading,
        hide_success_icon_fn=lambda: page._success_icon.hide(),
        log_metric_fn=lambda marker, metric_started_at, extra: _log_z2_detail_metric(
            marker,
            (_time.perf_counter() - metric_started_at) * 1000,
            extra=f"{extra}, reuse_list={'yes' if reuse_list else 'no'}",
        ),
        started_at=started,
        reason=reason,
        tcp_phase_mode=bool(page._tcp_phase_mode),
    )

    log(f"StrategyDetailPage: показан target {page._target_key}, sort_mode={page._sort_mode}", "DEBUG")


def show_target(page, target_key: str) -> None:
    """Открывает detail page для target из текущего source preset."""
    normalized_target_key = str(target_key or "").strip().lower()
    if not normalized_target_key:
        return

    prev_key = page._target_payload_runtime.current_or_pending_target_key(page._target_key)
    try:
        pending_key = str(page._pending_syndata_target_key or "").strip()
    except Exception:
        pending_key = ""
    if pending_key and pending_key != normalized_target_key:
        page._flush_syndata_settings_save()
    if prev_key:
        page._save_scroll_state(prev_key)

    # Канонический shell detail-страницы строится в конструкторе.
    # Поэтому для обычного перехода нам не нужно ждать фактической видимости
    # страницы: если shell уже построен, payload можно запросить сразу.
    # В pending-режиме остаётся только действительно неготовая страница.
    if not bool(getattr(page, "_content_built", False)):
        page._target_payload_runtime.remember_pending_target(normalized_target_key)
        return

    page._target_payload_runtime.clear_pending_target()
    request_target_payload(page, normalized_target_key, refresh=False, reason="show_target")


def refresh_from_preset_switch(page) -> None:
    """
    Асинхронно перечитывает активный пресет и обновляет текущий target (если открыт).
    Вызывается из MainWindow после активации пресета.
    """
    if page._cleanup_in_progress:
        return
    if not page.isVisible():
        page._preset_refresh_runtime.mark_pending()
        return
    try:
        page._preset_refresh_runtime.clear_pending()
        QTimer.singleShot(0, lambda: (not page._cleanup_in_progress) and apply_preset_refresh_now(page))
    except Exception:
        try:
            apply_preset_refresh_now(page)
        except Exception:
            pass


def apply_preset_refresh_now(page) -> None:
    if page._cleanup_in_progress:
        return
    apply_preset_refresh(
        is_visible=page.isVisible(),
        target_key=page._target_key,
        build_preset_refresh_plan_fn=build_preset_refresh_plan,
        mark_pending_fn=page._preset_refresh_runtime.mark_pending,
        request_payload_fn=page._request_target_payload,
    )
