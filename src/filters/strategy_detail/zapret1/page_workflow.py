"""Page-level workflow helper'ы для стратегии Zapret 1."""

from __future__ import annotations


def rebuild_breadcrumb_v1(
    *,
    breadcrumb,
    tr_fn,
    target_info: dict,
    target_key: str,
) -> None:
    if breadcrumb is None:
        return

    target_title = target_info.get("full_name", target_key) if target_key else "Target"
    breadcrumb.blockSignals(True)
    try:
        breadcrumb.clear()
        breadcrumb.addItem(
            "control",
            tr_fn("page.z1_strategy_detail.breadcrumb.control", "Управление"),
        )
        breadcrumb.addItem(
            "strategies",
            tr_fn("page.z1_strategy_detail.breadcrumb.strategies", "Прямой запуск Zapret 1"),
        )
        breadcrumb.addItem("detail", target_title)
    finally:
        breadcrumb.blockSignals(False)


def handle_breadcrumb_changed_v1(
    *,
    key: str,
    rebuild_breadcrumb_fn,
    emit_back_fn,
    emit_navigate_to_control_fn,
) -> None:
    rebuild_breadcrumb_fn()
    if key == "strategies":
        emit_back_fn()
    elif key == "control":
        emit_navigate_to_control_fn()


def show_target_v1(
    *,
    cleanup_in_progress: bool,
    target_key: str,
    direct_facade,
    current_direct_facade,
    require_app_context_fn,
    is_visible: bool,
    set_direct_facade_fn,
    set_pending_target_key_fn,
    request_target_payload_fn,
) -> None:
    if cleanup_in_progress:
        return

    normalized_target_key = str(target_key or "").strip().lower()
    if not normalized_target_key:
        return

    if direct_facade is not None:
        set_direct_facade_fn(direct_facade)
    elif current_direct_facade is None:
        try:
            from core.presets.direct_facade import DirectPresetFacade

            resolved = DirectPresetFacade.from_launch_method(
                "direct_zapret1",
                app_context=require_app_context_fn(),
            )
        except Exception:
            resolved = None
        set_direct_facade_fn(resolved)

    if not is_visible:
        set_pending_target_key_fn(normalized_target_key)
        return

    set_pending_target_key_fn("")
    request_target_payload_fn(normalized_target_key, refresh=False, reason="show_target")


def activate_page_v1(
    *,
    cleanup_in_progress: bool,
    pending_target_key: str,
    target_key: str,
    preset_refresh_pending: bool,
    set_pending_target_key_fn,
    clear_preset_refresh_pending_fn,
    request_target_payload_fn,
    rebuild_breadcrumb_fn,
    single_shot_fn,
    refresh_from_preset_switch_fn,
) -> None:
    if cleanup_in_progress:
        return

    normalized_pending_target_key = str(pending_target_key or "").strip().lower()
    if normalized_pending_target_key:
        set_pending_target_key_fn("")
        request_target_payload_fn(normalized_pending_target_key, refresh=False, reason="show_target")
        return

    rebuild_breadcrumb_fn()
    if target_key and preset_refresh_pending:
        clear_preset_refresh_pending_fn()
        single_shot_fn(0, refresh_from_preset_switch_fn)


def reload_target_v1(
    *,
    target_key: str,
    refresh_btn,
    request_target_payload_fn,
    on_error_fallback_fn,
    log_fn,
) -> None:
    if not target_key:
        return

    if refresh_btn:
        refresh_btn.set_loading(True)

    try:
        request_target_payload_fn(target_key, refresh=True, reason="reload")
    except Exception as exc:
        log_fn(f"Zapret1StrategyDetailPage: cannot load strategies: {exc}", "ERROR")
        on_error_fallback_fn()


def bind_ui_state_store_v1(
    *,
    current_store,
    store,
    current_unsubscribe,
    set_store_fn,
    set_unsubscribe_fn,
    on_ui_state_changed,
) -> None:
    if current_store is store:
        return

    if callable(current_unsubscribe):
        try:
            current_unsubscribe()
        except Exception:
            pass

    set_store_fn(store)
    unsubscribe = store.subscribe(
        on_ui_state_changed,
        fields={"active_preset_revision", "preset_content_revision"},
        emit_initial=False,
    )
    set_unsubscribe_fn(unsubscribe)


def handle_ui_state_changed_v1(
    *,
    cleanup_in_progress: bool,
    changed_fields: frozenset[str],
    refresh_from_preset_switch_fn,
) -> None:
    if cleanup_in_progress:
        return
    if "active_preset_revision" in changed_fields or "preset_content_revision" in changed_fields:
        refresh_from_preset_switch_fn()


def cleanup_page_v1(
    *,
    set_cleanup_in_progress_fn,
    set_pending_target_key_fn,
    clear_preset_refresh_pending_fn,
    increment_request_id_fn,
    success_timer,
    current_unsubscribe,
    set_unsubscribe_fn,
    set_store_fn,
) -> None:
    set_cleanup_in_progress_fn(True)
    set_pending_target_key_fn("")
    clear_preset_refresh_pending_fn()
    increment_request_id_fn()
    success_timer.stop()

    if callable(current_unsubscribe):
        try:
            current_unsubscribe()
        except Exception:
            pass
    set_unsubscribe_fn(None)
    set_store_fn(None)
