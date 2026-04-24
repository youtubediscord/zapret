from __future__ import annotations

import time as _time

from PyQt6.QtCore import QTimer

from log.log import log

from filters.strategy_detail.zapret2.controller import StrategyDetailPageController
from filters.strategy_detail.zapret2.strategies_logic import (
    build_batch_update_plan,
    build_strategies_load_plan,
    build_tree_completion_plan,
    extract_pending_item_args,
)
from filters.ui.strategy_detail.zapret2.common import log_z2_detail_metric as _log_z2_detail_metric


def clear_strategies(page) -> None:
    """Очищает список стратегий."""
    page._strategies_load_runtime.reset(delete_later=True)

    if page._strategies_tree:
        page._strategies_tree.clear_strategies()
    page._strategies_data_by_id = {}
    page._loaded_strategy_type = None
    page._loaded_direct_mode = None
    page._loaded_tcp_phase_mode = False
    page._default_strategy_order = []
    page._strategies_loaded_fully = False
    page._update_strategies_summary()


def is_dpi_running_now(page) -> bool:
    """Смотрит на канонический runtime-state вместо локальных догадок."""
    app_runtime_state = getattr(page.parent_app, "app_runtime_state", None)
    if app_runtime_state is None:
        return False
    try:
        return bool(app_runtime_state.is_launch_running())
    except Exception:
        return False


def load_strategies(page, policy=None, *, info_bar_cls=None) -> None:
    """Загружает стратегии для текущего target'а."""
    if page._cleanup_in_progress:
        return
    started_at = _time.perf_counter()
    try:
        payload = page._target_payload or page._load_target_payload_sync(page._target_key, refresh=False)
        if payload is not None:
            page._target_payload = payload
            target_info = payload.target_item or page._target_info
        else:
            target_info = page._target_info
        if target_info:
            log(f"StrategyDetailPage: target {page._target_key}, strategy_type={target_info.strategy_type}", "DEBUG")
        else:
            log(f"StrategyDetailPage: target {page._target_key} не найден в target metadata service!", "ERROR")
            return

        retry_count = int(getattr(page, "_retry_count", 0) or 0)
        plan = build_strategies_load_plan(
            target_info=target_info,
            payload=payload,
            policy=policy,
            retry_count=retry_count,
            launch_running=is_dpi_running_now(page),
            is_visible=page.isVisible(),
            custom_strategy_id=page.CUSTOM_STRATEGY_ID,
            direct_mode_override=page._current_direct_mode(),
            tr=page._tr,
        )
        page._detail_mode_policy = plan.resolved_policy

        log(
            f"StrategyDetailPage: загружено {len(plan.strategies_data_by_id)} стратегий для {page._target_key}",
            "DEBUG",
        )

        page._strategies_data_by_id = dict(plan.strategies_data_by_id or {})
        page._default_strategy_order = list(plan.default_strategy_order)
        page._loaded_strategy_type = plan.loaded_strategy_type
        page._loaded_direct_mode = plan.loaded_direct_mode
        page._loaded_tcp_phase_mode = plan.loaded_tcp_phase_mode

        if plan.is_empty:
            try:
                page._strategies_tree.clear_strategies()
            except Exception:
                pass
            page._update_strategies_summary()
            log(f"StrategyDetailPage: список стратегий пуст для {page._target_key}", "INFO")
            page._stop_loading()
            page._retry_count = plan.next_retry_count

            if plan.should_schedule_retry:
                QTimer.singleShot(1000, lambda: (not page._cleanup_in_progress) and page._load_strategies())
            elif plan.should_suppress_warning:
                log(
                    f"StrategyDetailPage: suppress 'no strategies' warning while DPI is stopped ({page._target_key})",
                    "DEBUG",
                )
            elif plan.should_show_warning and info_bar_cls:
                info_bar_cls.warning(
                    title=plan.warning_title,
                    content=plan.warning_content,
                    parent=page.window(),
                )
            return

        page._retry_count = plan.next_retry_count
        page._strategies_load_runtime.set_pending_items(list(plan.pending_items))
        page._strategies_loaded_fully = False

        page._strategies_load_runtime.bump_generation()
        timer = page._strategies_load_runtime.ensure_timer(
            parent=page,
            timeout_callback=page._load_next_strategies_batch,
        )
        timer.start(5)
        _log_z2_detail_metric(
            "_load_strategies.total",
            (_time.perf_counter() - started_at) * 1000,
            extra=f"target={page._target_key}, strategies={len(plan.strategies_data_by_id)}, tcp_phase={'yes' if plan.loaded_tcp_phase_mode else 'no'}",
        )

    except Exception as e:
        log(f"StrategyDetailPage.error loading strategies: {e}", "ERROR")
        page._stop_loading()


def add_strategy_row(page, strategy_id: str, name: str, args: list[str] | None = None) -> None:
    if not page._strategies_tree:
        return

    args_list = [str(a).strip() for a in (args or []) if str(a).strip()]
    is_favorite = (strategy_id != "none") and (strategy_id in page._favorite_strategy_ids)
    is_working = None
    if page._target_key and strategy_id not in ("none", page.CUSTOM_STRATEGY_ID):
        try:
            is_working = page._feedback_store.get_mark(page._target_key, strategy_id)
        except Exception:
            is_working = None

    try:
        page._strategies_tree.add_strategy(
            page.StrategyTreeRow(
                strategy_id=strategy_id,
                name=name,
                args=args_list,
                is_favorite=is_favorite,
                is_working=is_working,
            )
        )
    except Exception as e:
        log(f"Strategy row add failed for {strategy_id}: {e}", "DEBUG")


def load_next_strategies_batch(page) -> None:
    """Lazily appends strategies to the tree in small UI-friendly chunks."""
    if not page._strategies_tree:
        return

    runtime = page._strategies_load_runtime
    total = runtime.total_items()
    start = runtime.start_index()
    initial_plan = build_batch_update_plan(
        total=total,
        start=start,
        end=start,
        search_active=False,
        has_active_filters=bool(page._active_filters),
        tcp_phase_mode=bool(page._tcp_phase_mode),
    )
    if initial_plan.is_complete:
        if initial_plan.should_stop_timer:
            runtime.stop_timer(delete_later=False)
        if initial_plan.should_mark_loaded_fully:
            page._strategies_loaded_fully = True
        return

    chunk_size = 32
    end = min(start + chunk_size, total)
    batch_started_at = _time.perf_counter()

    try:
        page._strategies_tree.begin_bulk_update()
        for index in range(start, end):
            item = runtime.item_at(index)
            strategy_id = str(getattr(item, "strategy_id", "") or "").strip()
            if not strategy_id:
                continue
            name = str(getattr(item, "name", "") or strategy_id).strip() or strategy_id
            args_list = extract_pending_item_args(
                strategy_id=strategy_id,
                strategy_data=page._strategies_data_by_id.get(strategy_id, {}),
                pending_item=item,
            )
            add_strategy_row(page, strategy_id, name, args_list)
    finally:
        try:
            page._strategies_tree.end_bulk_update()
        except Exception:
            pass

    runtime.advance_to(end)
    try:
        _log_z2_detail_metric(
            "_load_next_strategies_batch",
            (_time.perf_counter() - batch_started_at) * 1000,
            extra=f"target={page._target_key}, rows={end - start}, progress={end}/{total}",
        )
    except Exception:
        pass

    try:
        search_active = bool(page._search_input and page._search_input.text().strip())
    except Exception:
        search_active = False
    plan = build_batch_update_plan(
        total=total,
        start=start,
        end=end,
        search_active=search_active,
        has_active_filters=bool(page._active_filters),
        tcp_phase_mode=bool(page._tcp_phase_mode),
    )
    if plan.should_apply_filters:
        page._apply_filters()
    elif plan.should_update_summary:
        page._update_strategies_summary()

    if not plan.is_complete:
        return

    if plan.should_stop_timer:
        runtime.stop_timer(delete_later=False)

    if plan.should_mark_loaded_fully:
        page._strategies_loaded_fully = True

    completion_plan = build_tree_completion_plan(
        tcp_phase_mode=bool(page._tcp_phase_mode),
        current_strategy_id=page._current_strategy_id,
        has_current_strategy=bool(page._strategies_tree.has_strategy(page._current_strategy_id)),
        has_none_strategy=bool(page._strategies_tree.has_strategy("none")),
    )
    if completion_plan.should_refresh_working_marks:
        page._refresh_working_marks_for_target()
    if completion_plan.should_apply_sort:
        page._apply_sort()

    if completion_plan.should_sync_tcp_phase_selection:
        page._sync_tree_selection_to_active_phase()
    else:
        if completion_plan.should_select_current_strategy:
            page._strategies_tree.set_selected_strategy(completion_plan.selected_strategy_id)
        elif completion_plan.should_select_none_fallback:
            page._strategies_tree.set_selected_strategy("none")

    if completion_plan.should_refresh_scroll_range:
        page._refresh_scroll_range()
    if completion_plan.should_update_summary:
        page._update_strategies_summary()
    if completion_plan.should_restore_scroll_state:
        page._restore_scroll_state(page._target_key, defer=True)
