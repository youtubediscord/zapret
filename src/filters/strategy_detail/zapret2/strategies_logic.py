from __future__ import annotations

from dataclasses import dataclass

from direct_preset.modes import resolve_direct_mode_logic
from filters.strategy_detail.zapret2.runtime_state import StrategyDetailPendingStrategyItem


@dataclass(slots=True)
class StrategyDetailStrategiesLoadPlan:
    resolved_policy: object
    strategies_data_by_id: dict[str, dict[str, str]]
    default_strategy_order: list[str]
    loaded_strategy_type: str
    loaded_direct_mode: str
    loaded_tcp_phase_mode: bool
    pending_items: list[StrategyDetailPendingStrategyItem]
    is_empty: bool
    next_retry_count: int
    should_schedule_retry: bool
    should_show_warning: bool
    should_suppress_warning: bool
    warning_title: str
    warning_content: str


@dataclass(slots=True)
class StrategyDetailBatchUpdatePlan:
    should_stop_timer: bool
    should_mark_loaded_fully: bool
    should_apply_filters: bool
    should_update_summary: bool
    is_complete: bool


@dataclass(slots=True)
class StrategyDetailTreeCompletionPlan:
    should_sync_tcp_phase_selection: bool
    selected_strategy_id: str
    should_select_current_strategy: bool
    should_select_none_fallback: bool
    should_refresh_working_marks: bool
    should_apply_sort: bool
    should_refresh_scroll_range: bool
    should_update_summary: bool
    should_restore_scroll_state: bool


def build_strategies_load_plan(
    *,
    target_info,
    payload,
    policy,
    retry_count: int,
    launch_running: bool,
    is_visible: bool,
    custom_strategy_id: str,
    direct_mode_override: str | None,
    tr,
) -> StrategyDetailStrategiesLoadPlan:
    from filters.strategy_detail.zapret2.mode_policy import build_strategy_detail_mode_policy

    resolved_policy = policy or build_strategy_detail_mode_policy(
        target_info,
        direct_mode=direct_mode_override,
        is_circular_preset=bool(getattr(payload, "is_circular_preset", False)),
    )
    mode_logic = resolve_direct_mode_logic("winws2", resolved_policy.direct_mode)

    strategies = dict(getattr(payload, "strategy_entries", {}) or {}) if payload is not None else {}
    pending_items: list[StrategyDetailPendingStrategyItem] = []
    is_empty = not strategies
    next_retry_count = 0
    should_schedule_retry = False
    should_show_warning = False
    should_suppress_warning = False
    warning_title = ""
    warning_content = ""

    if is_empty:
        if int(retry_count or 0) < 3:
            should_schedule_retry = True
            next_retry_count = int(retry_count or 0) + 1
        else:
            next_retry_count = 0
            if (not launch_running) or (not is_visible):
                should_suppress_warning = True
            else:
                should_show_warning = True
                warning_title = tr("page.z2_strategy_detail.infobar.no_strategies.title", "Нет стратегий")
                warning_content = tr(
                    "page.z2_strategy_detail.infobar.no_strategies.content",
                    "Для target'а '{category}' не найдено стратегий.",
                    category=str(getattr(payload, "target_key", "") or getattr(target_info, "key", "") or ""),
                )
    else:
        if mode_logic is None:
            pending_items = []
        else:
            pending_items = list(
                mode_logic.build_pending_strategy_items(
                    strategies=strategies,
                    item_factory=StrategyDetailPendingStrategyItem,
                    tr=tr,
                    custom_strategy_id=custom_strategy_id,
                )
            )

    return StrategyDetailStrategiesLoadPlan(
        resolved_policy=resolved_policy,
        strategies_data_by_id=dict(strategies or {}),
        default_strategy_order=list(strategies.keys()),
        loaded_strategy_type=resolved_policy.strategy_type,
        loaded_direct_mode=resolved_policy.direct_mode,
        loaded_tcp_phase_mode=resolved_policy.tcp_phase_mode,
        pending_items=pending_items,
        is_empty=is_empty,
        next_retry_count=next_retry_count,
        should_schedule_retry=should_schedule_retry,
        should_show_warning=should_show_warning,
        should_suppress_warning=should_suppress_warning,
        warning_title=warning_title,
        warning_content=warning_content,
    )


def extract_pending_item_args(
    *,
    strategy_id: str,
    strategy_data: dict | None,
    pending_item: StrategyDetailPendingStrategyItem,
) -> list[str]:
    source = None
    data = dict(strategy_data or {})

    if data:
        source = data.get("args")
        if source in (None, "", []):
            source = data.get("arg_str")

    if source in (None, "", []):
        source = pending_item.arg_text

    if isinstance(source, (list, tuple)):
        return [str(v).strip() for v in source if str(v).strip()]

    text = str(source or "").strip()
    if not text:
        return []
    if "\n" in text:
        return [ln.strip() for ln in text.splitlines() if ln.strip()]
    if text.startswith("--"):
        return [part.strip() for part in text.split() if part.strip()]
    return [text]


def build_batch_update_plan(
    *,
    total: int,
    start: int,
    end: int,
    search_active: bool,
    has_active_filters: bool,
    tcp_phase_mode: bool,
) -> StrategyDetailBatchUpdatePlan:
    if total <= 0 or start >= total:
        return StrategyDetailBatchUpdatePlan(
            should_stop_timer=True,
            should_mark_loaded_fully=True,
            should_apply_filters=False,
            should_update_summary=False,
            is_complete=True,
        )

    is_complete = end >= total
    should_apply_filters = bool(search_active or has_active_filters or tcp_phase_mode)
    return StrategyDetailBatchUpdatePlan(
        should_stop_timer=is_complete,
        should_mark_loaded_fully=is_complete,
        should_apply_filters=should_apply_filters,
        should_update_summary=not should_apply_filters,
        is_complete=is_complete,
    )


def build_tree_completion_plan(
    *,
    tcp_phase_mode: bool,
    current_strategy_id: str,
    has_current_strategy: bool,
    has_none_strategy: bool,
) -> StrategyDetailTreeCompletionPlan:
    normalized_current = str(current_strategy_id or "none").strip() or "none"
    return StrategyDetailTreeCompletionPlan(
        should_sync_tcp_phase_selection=bool(tcp_phase_mode),
        selected_strategy_id=normalized_current,
        should_select_current_strategy=(not tcp_phase_mode) and has_current_strategy,
        should_select_none_fallback=(not tcp_phase_mode) and (not has_current_strategy) and has_none_strategy,
        should_refresh_working_marks=True,
        should_apply_sort=True,
        should_refresh_scroll_range=True,
        should_update_summary=True,
        should_restore_scroll_state=True,
    )
