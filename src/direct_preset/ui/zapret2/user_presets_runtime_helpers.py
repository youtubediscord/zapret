"""Runtime/list helper'ы для страницы пользовательских пресетов Zapret 2."""

from __future__ import annotations

import time


def schedule_preset_search(*, preset_search_timer, refresh_presets_view_from_cache_fn) -> None:
    try:
        preset_search_timer.start(180)
    except Exception:
        refresh_presets_view_from_cache_fn()


def apply_preset_search(
    *,
    is_visible: bool,
    runtime_service,
    refresh_presets_view_from_cache_fn,
) -> None:
    if not is_visible:
        runtime_service.set_ui_dirty(True)
        return
    refresh_presets_view_from_cache_fn()


def update_presets_view_height(
    *,
    presets_model,
    presets_list,
    viewport,
    layout,
) -> None:
    if not presets_model or presets_list is None:
        return

    viewport_height = viewport.height()
    if viewport_height <= 0:
        return

    top = max(0, presets_list.geometry().top())
    bottom_margin = layout.contentsMargins().bottom()
    target_height = max(220, viewport_height - top - bottom_margin)

    if presets_list.minimumHeight() != target_height:
        presets_list.setMinimumHeight(target_height)
    if presets_list.maximumHeight() != target_height:
        presets_list.setMaximumHeight(target_height)


def rebuild_presets_rows(
    *,
    runtime_service,
    listing_api,
    presets_delegate,
    presets_model,
    presets_list,
    get_selected_source_preset_file_name_light_fn,
    ui_language: str,
    schedule_layout_resync_fn,
    update_presets_view_height_fn,
    log_fn,
    all_presets: dict[str, dict[str, object]],
    started_at: float | None = None,
) -> None:
    try:
        view_state = runtime_service.capture_presets_view_state() if presets_list is not None else {}
        active_file_name = get_selected_source_preset_file_name_light_fn()
        plan = listing_api.build_preset_rows_plan(
            all_presets=all_presets,
            query=runtime_service.current_search_query(),
            active_file_name=active_file_name,
            language=ui_language,
        )

        if presets_delegate:
            presets_delegate.reset_interaction_state()
        if presets_model:
            presets_model.set_rows(plan.rows)
        runtime_service.ensure_preset_list_current_index()
        if view_state:
            runtime_service.restore_presets_view_state(view_state)
        update_presets_view_height_fn()
        schedule_layout_resync_fn()
        if started_at is not None:
            elapsed_ms = int((time.perf_counter() - started_at) * 1000)
            log_fn(
                f"Z2UserPresetsPage: lightweight list reload {elapsed_ms}ms ({plan.total_presets} presets)",
                "DEBUG",
            )

    except Exception as exc:
        log_fn(f"Ошибка загрузки пресетов: {exc}", "ERROR")
