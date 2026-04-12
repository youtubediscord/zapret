from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(slots=True)
class StrategyDetailSortOption:
    mode: str
    label: str


@dataclass(slots=True)
class StrategyDetailTechniqueFilterPlan:
    target_index: int


@dataclass(slots=True)
class StrategyDetailSummaryPlan:
    text: str


@dataclass(slots=True)
class StrategyDetailPresetActionResult:
    ok: bool
    log_level: str
    log_message: str
    infobar_level: str | None
    infobar_title: str
    infobar_content: str
    structure_changed: bool
    switched_file_name: str | None = None


@dataclass(slots=True)
class StrategyDetailResetPlan:
    ok: bool
    log_level: str
    log_message: str
    should_reload_payload: bool
    should_apply_syndata_settings: bool
    should_refresh_filter_mode: bool
    should_refresh_strategy_selection: bool
    should_show_loading: bool
    should_refresh_args_editor: bool
    should_refresh_target_enabled_ui: bool


@dataclass(slots=True)
class StrategyDetailRowClickPlan:
    selected_strategy_id: str
    remembered_last_enabled_strategy_id: str | None
    should_hide_args_editor: bool
    loading_state: str
    target_enabled: bool
    should_emit_strategy_selected: bool
    suppress_next_preset_refresh: bool


@dataclass(slots=True)
class StrategyDetailLoadingStatePlan:
    action: str


@dataclass(slots=True)
class StrategyDetailTargetRequestPlan:
    should_request: bool
    normalized_target_key: str
    token_reason: str


class StrategyDetailTargetPayloadRuntime:
    def __init__(self) -> None:
        self.pending_target_key: str | None = None
        self.worker = None
        self.request_id = 0
        self.request_started_at = None

    def current_or_pending_target_key(self, current_target_key: str | None) -> str:
        return str(self.pending_target_key or current_target_key or "").strip().lower()

    def remember_pending_target(self, target_key: str | None) -> None:
        normalized_key = str(target_key or "").strip().lower()
        self.pending_target_key = normalized_key or None

    def clear_pending_target(self) -> None:
        self.pending_target_key = None

    def take_pending_target_if_ready(self, *, is_visible: bool, content_built: bool) -> str | None:
        pending_target_key = str(self.pending_target_key or "").strip().lower()
        if not pending_target_key:
            return None
        if not is_visible or not content_built:
            return None
        self.pending_target_key = None
        return pending_target_key

    def restore_pending_target(self, target_key: str | None) -> None:
        self.remember_pending_target(target_key)

    def current_request_id(self) -> int:
        return int(self.request_id)

    def register_request(self, *, request_id: int, started_at, worker) -> None:
        self.request_id = int(request_id)
        self.request_started_at = started_at
        self.worker = worker


@dataclass(slots=True)
class StrategyDetailPayloadLoadedPlan:
    action: str
    normalized_target_key: str
    log_level: str | None = None
    log_message: str = ""


@dataclass(slots=True)
class StrategyDetailPayloadApplyPlan:
    policy: object
    current_strategy_id: str
    selected_strategy_id: str
    target_enabled: bool
    should_reuse_list: bool
    title_text: str
    subtitle_text: str


@dataclass(slots=True)
class StrategyDetailPresetRefreshPlan:
    should_mark_pending: bool
    should_request_refresh: bool


class StrategyDetailPresetRefreshRuntime:
    def __init__(self) -> None:
        self.pending = False
        self.suppress_next = False

    def mark_pending(self) -> None:
        self.pending = True

    def clear_pending(self) -> None:
        self.pending = False

    def consume_pending(self) -> bool:
        if not self.pending:
            return False
        self.pending = False
        return True

    def mark_suppressed(self) -> None:
        self.suppress_next = True

    def set_suppressed(self, enabled: bool) -> None:
        self.suppress_next = bool(enabled)

    def consume_suppressed(self) -> bool:
        if not self.suppress_next:
            return False
        self.suppress_next = False
        return True


class StrategyDetailStrategiesLoadRuntime:
    def __init__(self) -> None:
        self.timer = None
        self.generation = 0
        self.pending_items: list[StrategyDetailPendingStrategyItem] = []
        self.pending_index = 0

    def bump_generation(self) -> int:
        self.generation += 1
        return int(self.generation)

    def stop_timer(self, *, delete_later: bool) -> None:
        timer = self.timer
        if timer is None:
            return
        try:
            timer.stop()
        except Exception:
            pass
        if delete_later:
            try:
                timer.deleteLater()
            except Exception:
                pass
            self.timer = None

    def reset(self, *, delete_later: bool) -> None:
        self.bump_generation()
        self.stop_timer(delete_later=delete_later)
        self.pending_items = []
        self.pending_index = 0

    def set_pending_items(self, items: list[StrategyDetailPendingStrategyItem]) -> None:
        self.pending_items = list(items or [])
        self.pending_index = 0

    def ensure_timer(self, *, parent, timeout_callback):
        if self.timer is not None:
            return self.timer
        from PyQt6.QtCore import QTimer

        timer = QTimer(parent)
        timer.timeout.connect(timeout_callback)
        self.timer = timer
        return timer

    def total_items(self) -> int:
        return len(self.pending_items or [])

    def start_index(self) -> int:
        return int(self.pending_index or 0)

    def item_at(self, index: int) -> StrategyDetailPendingStrategyItem:
        return self.pending_items[index]

    def advance_to(self, index: int) -> None:
        self.pending_index = int(index)


@dataclass(slots=True)
class StrategyDetailPendingStrategyItem:
    strategy_id: str
    name: str
    arg_text: str
    is_custom: bool = False


@dataclass(slots=True)
class StrategyDetailStrategiesLoadPlan:
    resolved_policy: object
    strategies_data_by_id: dict[str, dict[str, str]]
    default_strategy_order: list[str]
    loaded_strategy_type: str
    loaded_strategy_set: str
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


@dataclass(slots=True)
class StrategyDetailWorkingMarkUpdate:
    strategy_id: str
    state: object


@dataclass(slots=True)
class StrategyDetailWorkingMarksPlan:
    updates: list[StrategyDetailWorkingMarkUpdate]


@dataclass(slots=True)
class StrategyDetailPreviewDataPlan:
    ok: bool
    data: dict[str, object]


@dataclass(slots=True)
class StrategyDetailMarkResult:
    ok: bool
    resulting_mark_state: object
    resulting_rating: str | None
    should_update_tree_state: bool
    should_emit_signal: bool


@dataclass(slots=True)
class StrategyDetailFavoriteToggleResult:
    ok: bool
    updated_favorite_ids: set[str]


@dataclass(slots=True)
class StrategyDetailSortChangePlan:
    normalized_mode: str
    should_apply: bool
    should_persist: bool


@dataclass(slots=True)
class StrategyDetailSortApplyPlan:
    normalized_mode: str
    selected_strategy_id: str
    should_restore_selected_strategy: bool


@dataclass(slots=True)
class StrategyDetailPhaseSelectionPlan:
    selected_strategy_id: str
    should_select_strategy: bool
    should_clear_active: bool


@dataclass(slots=True)
class StrategyDetailFilterApplyPlan:
    search_text: str
    active_filters: set[str]
    phase_key: str | None
    use_phase_filter: bool
    selected_strategy_id: str
    should_restore_selected_strategy: bool
    should_sync_phase_selection: bool


@dataclass(slots=True)
class StrategyDetailPhaseTabPlan:
    normalized_phase_key: str
    should_apply: bool
    should_persist: bool
    should_sync_phase_selection: bool


@dataclass(slots=True)
class StrategyDetailSyndataTimerPlan:
    should_schedule: bool
    pending_target_key: str | None
    delay_ms: int


@dataclass(slots=True)
class StrategyDetailSyndataPersistPlan:
    should_save: bool
    normalized_target_key: str
    payload: dict[str, object]


@dataclass(slots=True)
class StrategyDetailArgsEditorStatePlan:
    enabled: bool
    should_hide_editor: bool


@dataclass(slots=True)
class StrategyDetailArgsEditorOpenPlan:
    should_open: bool
    initial_text: str


@dataclass(slots=True)
class StrategyDetailArgsApplyPlan:
    should_apply: bool
    normalized_text: str
    args_lines: list[str]


@dataclass(slots=True)
class StrategyDetailArgsApplyResultPlan:
    selected_strategy_id: str
    current_strategy_id: str
    should_show_loading: bool
    should_emit_args_changed: bool


@dataclass(slots=True)
class StrategyDetailTcpPhaseStatePlan:
    selected_ids: dict[str, str]
    custom_args: dict[str, str]
    hide_fake_phase: bool


@dataclass(slots=True)
class StrategyDetailTcpPhaseMarkerPlan:
    labels_by_phase: dict[str, str]


@dataclass(slots=True)
class StrategyDetailTcpPhaseTabsVisibilityPlan:
    hide_fake_phase: bool
    fallback_phase_key: str | None
    should_reapply_filters: bool


@dataclass(slots=True)
class StrategyDetailActivePhaseChipPlan:
    should_apply: bool
    final_phase_key: str | None


@dataclass(slots=True)
class StrategyDetailDefaultTcpPhaseTabPlan:
    preferred_phase_key: str


@dataclass(slots=True)
class StrategyDetailTcpPhaseSaveResultPlan:
    selected_strategy_id: str
    current_strategy_id: str
    target_enabled: bool
    should_refresh_args_editor: bool
    should_show_loading: bool
    should_hide_loading: bool
    should_update_header: bool
    should_update_markers: bool
    should_emit_selection: bool


@dataclass(slots=True)
class StrategyDetailTcpPhaseRowClickPlan:
    should_apply: bool
    selected_ids: dict[str, str]
    custom_args: dict[str, str]
    hide_fake_phase: bool
    should_select_strategy: bool
    selected_strategy_id: str | None
    should_clear_active_strategy: bool
    should_save: bool


class StrategyDetailPageController:
    @staticmethod
    def create_target_payload_runtime() -> StrategyDetailTargetPayloadRuntime:
        return StrategyDetailTargetPayloadRuntime()

    @staticmethod
    def create_preset_refresh_runtime() -> StrategyDetailPresetRefreshRuntime:
        return StrategyDetailPresetRefreshRuntime()

    @staticmethod
    def create_strategies_load_runtime() -> StrategyDetailStrategiesLoadRuntime:
        return StrategyDetailStrategiesLoadRuntime()

    @staticmethod
    def create_preset(facade, *, name: str) -> StrategyDetailPresetActionResult:
        facade.create(name, from_current=True)
        return StrategyDetailPresetActionResult(
            ok=True,
            log_level="INFO",
            log_message=f"Создан пресет '{name}'",
            infobar_level="success",
            infobar_title="Пресет создан",
            infobar_content=f"Пресет '{name}' создан на основе текущих настроек.",
            structure_changed=True,
        )

    @staticmethod
    def build_missing_active_preset_result() -> StrategyDetailPresetActionResult:
        return StrategyDetailPresetActionResult(
            ok=False,
            log_level="WARNING",
            log_message="Выбранный source-пресет не найден",
            infobar_level="warning",
            infobar_title="Нет выбранного source-пресета",
            infobar_content="Выбранный source-пресет не найден.",
            structure_changed=False,
        )

    @staticmethod
    def rename_preset(facade, *, old_file_name: str, old_name: str, new_name: str) -> StrategyDetailPresetActionResult:
        updated = facade.rename_by_file_name(old_file_name, new_name)
        switched_file_name = updated.file_name if facade.is_selected_file_name(updated.file_name) else None
        if switched_file_name:
            facade.notify_preset_identity_changed(updated.file_name)

        return StrategyDetailPresetActionResult(
            ok=True,
            log_level="INFO",
            log_message=f"Пресет '{old_name}' переименован в '{new_name}'",
            infobar_level="success",
            infobar_title="Переименован",
            infobar_content=f"Пресет переименован: '{old_name}' -> '{new_name}'.",
            structure_changed=True,
            switched_file_name=switched_file_name,
        )

    @staticmethod
    def save_target_filter_mode(facade, *, target_key: str, mode: str) -> None:
        facade.update_target_filter_mode(target_key, mode, save_and_sync=True)

    @staticmethod
    def load_target_filter_mode(facade, *, payload, target_key: str) -> str:
        if payload is not None and str(getattr(payload, "target_key", "") or "") == str(target_key or "").strip().lower():
            return str(getattr(payload, "filter_mode", "") or "hostlist")
        return facade.get_target_filter_mode(target_key)

    @staticmethod
    def save_target_sort(facade, *, target_key: str, sort_order: str) -> None:
        normalized = StrategyDetailPageController.resolve_sort_mode(sort_order)
        facade.update_target_sort_order(target_key, normalized, save_and_sync=True)

    @staticmethod
    def load_target_sort(facade, *, target_key: str) -> str:
        return StrategyDetailPageController.resolve_sort_mode(facade.get_target_sort_order(target_key))

    @staticmethod
    def build_reset_settings_plan(*, target_key: str, success: bool) -> StrategyDetailResetPlan:
        if success:
            return StrategyDetailResetPlan(
                ok=True,
                log_level="INFO",
                log_message=f"Настройки target'а {target_key} сброшены",
                should_reload_payload=True,
                should_apply_syndata_settings=True,
                should_refresh_filter_mode=True,
                should_refresh_strategy_selection=True,
                should_show_loading=True,
                should_refresh_args_editor=True,
                should_refresh_target_enabled_ui=True,
            )
        return StrategyDetailResetPlan(
            ok=False,
            log_level="WARNING",
            log_message=f"Не удалось сбросить настройки target'а {target_key}",
            should_reload_payload=False,
            should_apply_syndata_settings=False,
            should_refresh_filter_mode=False,
            should_refresh_strategy_selection=False,
            should_show_loading=False,
            should_refresh_args_editor=False,
            should_refresh_target_enabled_ui=False,
        )

    @staticmethod
    def build_row_click_plan(
        *,
        strategy_id: str,
        prev_strategy_id: str,
        has_target_key: bool,
    ) -> StrategyDetailRowClickPlan:
        normalized_id = str(strategy_id or "none").strip() or "none"
        normalized_prev = str(prev_strategy_id or "").strip()
        remembered_last_enabled = None
        if normalized_id == "none" and normalized_prev and normalized_prev != "none":
            remembered_last_enabled = normalized_prev

        return StrategyDetailRowClickPlan(
            selected_strategy_id=normalized_id,
            remembered_last_enabled_strategy_id=remembered_last_enabled,
            should_hide_args_editor=normalized_prev != normalized_id,
            loading_state="show" if normalized_id != "none" else "stop",
            target_enabled=normalized_id != "none",
            should_emit_strategy_selected=bool(has_target_key),
            suppress_next_preset_refresh=bool(has_target_key),
        )

    @staticmethod
    def build_status_icon_plan(*, active: bool) -> StrategyDetailLoadingStatePlan:
        return StrategyDetailLoadingStatePlan(action="success" if active else "hide")

    @staticmethod
    def build_apply_feedback_timeout_plan(
        *,
        waiting_for_process_start: bool,
        selected_strategy_id: str,
    ) -> StrategyDetailLoadingStatePlan:
        if not waiting_for_process_start:
            return StrategyDetailLoadingStatePlan(action="noop")
        if (selected_strategy_id or "none") != "none":
            return StrategyDetailLoadingStatePlan(action="success")
        return StrategyDetailLoadingStatePlan(action="hide")

    @staticmethod
    def build_target_payload_request_plan(
        *,
        target_key: str,
        reason: str,
    ) -> StrategyDetailTargetRequestPlan:
        normalized_key = str(target_key or "").strip().lower()
        should_request = bool(normalized_key)
        token_reason = f"{reason}:{normalized_key}" if should_request else str(reason or "").strip()
        return StrategyDetailTargetRequestPlan(
            should_request=should_request,
            normalized_target_key=normalized_key,
            token_reason=token_reason,
        )

    @staticmethod
    def build_payload_loaded_plan(
        *,
        request_id: int,
        current_request_id: int,
        token_is_current: bool,
        snapshot,
        fallback_target_key: str,
    ) -> StrategyDetailPayloadLoadedPlan:
        if request_id != current_request_id:
            return StrategyDetailPayloadLoadedPlan(action="ignore", normalized_target_key="")
        if not token_is_current:
            return StrategyDetailPayloadLoadedPlan(action="ignore", normalized_target_key="")

        normalized_key = str(
            getattr(snapshot, "target_key", "") or fallback_target_key or ""
        ).strip().lower()
        payload = getattr(snapshot, "payload", None)
        if payload is None or getattr(payload, "target_item", None) is None:
            return StrategyDetailPayloadLoadedPlan(
                action="missing",
                normalized_target_key=normalized_key,
                log_level="WARNING",
                log_message=f"StrategyDetailPage.show_target: target '{normalized_key}' не найден",
            )

        return StrategyDetailPayloadLoadedPlan(
            action="apply",
            normalized_target_key=normalized_key,
        )

    @staticmethod
    def build_target_payload_apply_plan(
        *,
        payload,
        has_strategy_rows: bool,
        loaded_strategy_type: str | None,
        loaded_strategy_set: str | None,
        loaded_tcp_phase_mode: bool,
        tr,
    ) -> StrategyDetailPayloadApplyPlan:
        from preset_zapret2.ui.strategy_detail.mode_policy import build_strategy_detail_mode_policy

        target_info = getattr(payload, "target_item", None)
        policy = build_strategy_detail_mode_policy(
            target_info,
            is_circular_preset=bool(getattr(payload, "is_circular_preset", False)),
        )
        details = getattr(payload, "details", None)
        current_strategy_id = str(getattr(details, "current_strategy", "none") or "none").strip() or "none"
        protocol = str(getattr(target_info, "protocol", "") or "").strip()
        ports = str(getattr(target_info, "ports", "") or "").strip()

        return StrategyDetailPayloadApplyPlan(
            policy=policy,
            current_strategy_id=current_strategy_id,
            selected_strategy_id=current_strategy_id,
            target_enabled=current_strategy_id != "none",
            should_reuse_list=(
                bool(has_strategy_rows)
                and loaded_strategy_type == policy.strategy_type
                and loaded_strategy_set == policy.strategy_set
                and bool(loaded_tcp_phase_mode) == bool(policy.tcp_phase_mode)
            ),
            title_text=str(getattr(target_info, "full_name", "") or "").strip(),
            subtitle_text=(
                f"{protocol}  |  "
                f"{tr('page.z2_strategy_detail.subtitle.ports', 'порты: {ports}', ports=ports)}"
            ),
        )

    @staticmethod
    def build_preset_refresh_plan(
        *,
        is_visible: bool,
        target_key: str,
    ) -> StrategyDetailPresetRefreshPlan:
        if not is_visible:
            return StrategyDetailPresetRefreshPlan(
                should_mark_pending=True,
                should_request_refresh=False,
            )
        if not str(target_key or "").strip():
            return StrategyDetailPresetRefreshPlan(
                should_mark_pending=False,
                should_request_refresh=False,
            )
        return StrategyDetailPresetRefreshPlan(
            should_mark_pending=False,
            should_request_refresh=True,
        )

    @staticmethod
    def build_strategies_load_plan(
        *,
        target_info,
        payload,
        policy,
        retry_count: int,
        dpi_running: bool,
        is_visible: bool,
        custom_strategy_id: str,
        tr,
    ) -> StrategyDetailStrategiesLoadPlan:
        from preset_zapret2.ui.strategy_detail.mode_policy import build_strategy_detail_mode_policy

        resolved_policy = policy or build_strategy_detail_mode_policy(
            target_info,
            is_circular_preset=bool(getattr(payload, "is_circular_preset", False)),
        )
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
                if (not dpi_running) or (not is_visible):
                    should_suppress_warning = True
                else:
                    should_show_warning = True
                    warning_title = tr("page.z2_strategy_detail.infobar.no_strategies.title", "Нет стратегий")
                    warning_content = tr(
                        "page.z2_strategy_detail.infobar.no_strategies.content",
                        "Для target'а '{category}' не найдено стратегий.",
                        category=str(getattr(payload, "target_key", "") or getattr(target_info, "key", "") or ""),
                    )
        elif resolved_policy.tcp_phase_mode:
            pending_items.append(
                StrategyDetailPendingStrategyItem(
                    strategy_id="none",
                    name=tr("page.z2_strategy_detail.tree.phase.none.name", "(без изменений)"),
                    arg_text="--new",
                    is_custom=False,
                )
            )
            pending_items.append(
                StrategyDetailPendingStrategyItem(
                    strategy_id=custom_strategy_id,
                    name=tr("page.z2_strategy_detail.tree.phase.custom.name", "Пользовательские аргументы (custom)"),
                    arg_text="...",
                    is_custom=True,
                )
            )
            for sid, data in strategies.items():
                pending_items.append(
                    StrategyDetailPendingStrategyItem(
                        strategy_id=str(sid or "").strip(),
                        name=str(data.get("name", sid)).strip() or str(sid or "").strip(),
                        arg_text=str(data.get("arg_str", "") or ""),
                        is_custom=False,
                    )
                )
        else:
            pending_items.append(
                StrategyDetailPendingStrategyItem(
                    strategy_id="none",
                    name=tr("page.z2_strategy_detail.tree.disabled.name", "Выключено (без DPI-обхода)"),
                    arg_text="",
                    is_custom=False,
                )
            )
            for sid, data in strategies.items():
                normalized_sid = str(sid or "").strip()
                pending_items.append(
                    StrategyDetailPendingStrategyItem(
                        strategy_id=normalized_sid,
                        name=str(data.get("name", sid) or normalized_sid),
                        arg_text=str(data.get("arg_str", "") or ""),
                        is_custom=False,
                    )
                )

        return StrategyDetailStrategiesLoadPlan(
            resolved_policy=resolved_policy,
            strategies_data_by_id=dict(strategies or {}),
            default_strategy_order=list(strategies.keys()),
            loaded_strategy_type=resolved_policy.strategy_type,
            loaded_strategy_set=resolved_policy.strategy_set,
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

    @staticmethod
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

    @staticmethod
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

    @staticmethod
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

    @staticmethod
    def build_working_marks_plan(
        *,
        target_key: str,
        strategy_ids: list[str],
        custom_strategy_id: str,
        mark_getter,
    ) -> StrategyDetailWorkingMarksPlan:
        if not str(target_key or "").strip():
            return StrategyDetailWorkingMarksPlan(updates=[])

        updates: list[StrategyDetailWorkingMarkUpdate] = []
        for strategy_id in strategy_ids:
            normalized = str(strategy_id or "").strip()
            if not normalized or normalized in ("none", custom_strategy_id):
                continue
            try:
                state = mark_getter(normalized)
            except Exception:
                continue
            updates.append(StrategyDetailWorkingMarkUpdate(strategy_id=normalized, state=state))
        return StrategyDetailWorkingMarksPlan(updates=updates)

    @staticmethod
    def build_preview_strategy_data(
        *,
        strategy_id: str,
        strategy_data: dict | None,
    ) -> StrategyDetailPreviewDataPlan:
        normalized_id = str(strategy_id or "").strip()
        data = dict(strategy_data or {})
        if "name" not in data:
            data["name"] = normalized_id

        args = data.get("args", [])
        if isinstance(args, str):
            args_text = args
        elif isinstance(args, (list, tuple)):
            args_text = "\n".join([str(a) for a in args if a is not None]).strip()
        else:
            args_text = ""
        data["args"] = args_text
        return StrategyDetailPreviewDataPlan(
            ok=bool(normalized_id),
            data=data,
        )

    @staticmethod
    def resolve_strategy_mark_rating(mark_state: object) -> str | None:
        if mark_state is True:
            return "working"
        if mark_state is False:
            return "broken"
        return None

    @staticmethod
    def get_preview_rating(mark_store, *, strategy_id: str, target_key: str) -> str | None:
        normalized_target = str(target_key or "").strip()
        normalized_strategy = str(strategy_id or "").strip()
        if not normalized_target or not normalized_strategy or normalized_strategy == "none":
            return None
        try:
            mark_state = mark_store.get_mark(normalized_target, normalized_strategy)
        except Exception:
            return None
        return StrategyDetailPageController.resolve_strategy_mark_rating(mark_state)

    @staticmethod
    def toggle_preview_rating(
        mark_store,
        *,
        strategy_id: str,
        rating: str,
        target_key: str,
    ) -> StrategyDetailMarkResult:
        normalized_target = str(target_key or "").strip()
        normalized_strategy = str(strategy_id or "").strip()
        if not normalized_target or not normalized_strategy or normalized_strategy == "none":
            return StrategyDetailMarkResult(
                ok=False,
                resulting_mark_state=None,
                resulting_rating=None,
                should_update_tree_state=False,
                should_emit_signal=False,
            )

        try:
            current = mark_store.get_mark(normalized_target, normalized_strategy)
        except Exception:
            current = None

        normalized_rating = str(rating or "").strip().lower()
        if normalized_rating == "working":
            new_state = None if current is True else True
        elif normalized_rating == "broken":
            new_state = None if current is False else False
        else:
            new_state = None

        try:
            mark_store.set_mark(normalized_target, normalized_strategy, new_state)
        except Exception:
            return StrategyDetailMarkResult(
                ok=False,
                resulting_mark_state=current,
                resulting_rating=StrategyDetailPageController.resolve_strategy_mark_rating(current),
                should_update_tree_state=False,
                should_emit_signal=False,
            )

        return StrategyDetailMarkResult(
            ok=True,
            resulting_mark_state=new_state,
            resulting_rating=StrategyDetailPageController.resolve_strategy_mark_rating(new_state),
            should_update_tree_state=True,
            should_emit_signal=False,
        )

    @staticmethod
    def save_strategy_mark(
        mark_store,
        *,
        strategy_id: str,
        is_working,
        target_key: str,
    ) -> StrategyDetailMarkResult:
        normalized_target = str(target_key or "").strip()
        normalized_strategy = str(strategy_id or "").strip()
        if not normalized_target or not normalized_strategy or normalized_strategy == "none":
            return StrategyDetailMarkResult(
                ok=False,
                resulting_mark_state=None,
                resulting_rating=None,
                should_update_tree_state=False,
                should_emit_signal=False,
            )

        try:
            mark_store.set_mark(normalized_target, normalized_strategy, is_working)
        except Exception:
            return StrategyDetailMarkResult(
                ok=False,
                resulting_mark_state=None,
                resulting_rating=None,
                should_update_tree_state=False,
                should_emit_signal=False,
            )

        return StrategyDetailMarkResult(
            ok=True,
            resulting_mark_state=is_working,
            resulting_rating=StrategyDetailPageController.resolve_strategy_mark_rating(is_working),
            should_update_tree_state=True,
            should_emit_signal=True,
        )

    @staticmethod
    def toggle_favorite(
        favorites_store,
        *,
        strategy_id: str,
        is_favorite: bool,
        target_key: str,
        favorite_ids: set[str],
    ) -> StrategyDetailFavoriteToggleResult:
        normalized_target = str(target_key or "").strip()
        normalized_strategy = str(strategy_id or "").strip()
        current_ids = set(favorite_ids or set())
        if not normalized_target or not normalized_strategy:
            return StrategyDetailFavoriteToggleResult(
                ok=False,
                updated_favorite_ids=current_ids,
            )

        try:
            favorites_store.set_favorite(normalized_target, normalized_strategy, is_favorite)
        except Exception:
            return StrategyDetailFavoriteToggleResult(
                ok=False,
                updated_favorite_ids=current_ids,
            )

        if is_favorite:
            current_ids.add(normalized_strategy)
        else:
            current_ids.discard(normalized_strategy)

        return StrategyDetailFavoriteToggleResult(
            ok=True,
            updated_favorite_ids=current_ids,
        )

    @staticmethod
    def build_sort_change_plan(
        *,
        requested_mode: str,
        current_mode: str,
        target_key: str,
    ) -> StrategyDetailSortChangePlan:
        normalized_requested = StrategyDetailPageController.resolve_sort_mode(requested_mode)
        normalized_current = StrategyDetailPageController.resolve_sort_mode(current_mode)
        return StrategyDetailSortChangePlan(
            normalized_mode=normalized_requested,
            should_apply=normalized_requested != normalized_current,
            should_persist=bool(str(target_key or "").strip()) and normalized_requested != normalized_current,
        )

    @staticmethod
    def build_sort_apply_plan(
        *,
        sort_mode: str,
        selected_strategy_id: str,
        current_strategy_id: str,
        has_selected_strategy: bool,
    ) -> StrategyDetailSortApplyPlan:
        selected = str(selected_strategy_id or current_strategy_id or "none").strip() or "none"
        return StrategyDetailSortApplyPlan(
            normalized_mode=StrategyDetailPageController.resolve_sort_mode(sort_mode),
            selected_strategy_id=selected,
            should_restore_selected_strategy=bool(selected) and has_selected_strategy,
        )

    @staticmethod
    def build_phase_selection_plan(
        *,
        tcp_phase_mode: bool,
        active_phase_key: str,
        phase_selected_strategy_id: str,
        custom_strategy_id: str,
        has_strategy: bool,
        is_visible: bool,
    ) -> StrategyDetailPhaseSelectionPlan:
        if not tcp_phase_mode:
            return StrategyDetailPhaseSelectionPlan(
                selected_strategy_id="",
                should_select_strategy=False,
                should_clear_active=False,
            )

        phase = str(active_phase_key or "").strip().lower()
        if not phase:
            return StrategyDetailPhaseSelectionPlan(
                selected_strategy_id="",
                should_select_strategy=False,
                should_clear_active=True,
            )

        sid = str(phase_selected_strategy_id or "").strip()
        if sid and sid != custom_strategy_id and has_strategy and is_visible:
            return StrategyDetailPhaseSelectionPlan(
                selected_strategy_id=sid,
                should_select_strategy=True,
                should_clear_active=False,
            )

        return StrategyDetailPhaseSelectionPlan(
            selected_strategy_id=sid,
            should_select_strategy=False,
            should_clear_active=True,
        )

    @staticmethod
    def build_filter_apply_plan(
        *,
        tcp_phase_mode: bool,
        active_phase_key: str,
        search_text: str,
        active_filters: set[str],
        selected_strategy_id: str,
        current_strategy_id: str,
        has_selected_strategy: bool,
        is_selected_visible: bool,
    ) -> StrategyDetailFilterApplyPlan:
        selected = str(selected_strategy_id or current_strategy_id or "none").strip() or "none"
        if tcp_phase_mode:
            return StrategyDetailFilterApplyPlan(
                search_text=str(search_text or ""),
                active_filters=set(),
                phase_key=str(active_phase_key or "").strip().lower() or None,
                use_phase_filter=True,
                selected_strategy_id=selected,
                should_restore_selected_strategy=False,
                should_sync_phase_selection=True,
            )

        return StrategyDetailFilterApplyPlan(
            search_text=str(search_text or ""),
            active_filters={str(v or "").strip().lower() for v in (active_filters or set()) if str(v or "").strip()},
            phase_key=None,
            use_phase_filter=False,
            selected_strategy_id=selected,
            should_restore_selected_strategy=bool(selected) and has_selected_strategy and is_selected_visible,
            should_sync_phase_selection=False,
        )

    @staticmethod
    def build_phase_tab_change_plan(
        *,
        tcp_phase_mode: bool,
        phase_key: str,
        target_key: str,
    ) -> StrategyDetailPhaseTabPlan:
        normalized_phase = str(phase_key or "").strip().lower()
        should_apply = bool(tcp_phase_mode and normalized_phase)
        return StrategyDetailPhaseTabPlan(
            normalized_phase_key=normalized_phase,
            should_apply=should_apply,
            should_persist=should_apply and bool(str(target_key or "").strip()),
            should_sync_phase_selection=should_apply,
        )

    @staticmethod
    def build_phase_tab_reclick_plan(
        *,
        tcp_phase_mode: bool,
        clicked_key: str,
        active_phase_key: str,
    ) -> StrategyDetailPhaseTabPlan:
        normalized_clicked = str(clicked_key or "").strip().lower()
        normalized_active = str(active_phase_key or "").strip().lower()
        should_apply = bool(tcp_phase_mode and normalized_clicked and normalized_clicked == normalized_active)
        return StrategyDetailPhaseTabPlan(
            normalized_phase_key=normalized_clicked,
            should_apply=should_apply,
            should_persist=False,
            should_sync_phase_selection=should_apply,
        )

    @staticmethod
    def build_syndata_timer_plan(
        *,
        target_key: str,
        delay_ms: int,
    ) -> StrategyDetailSyndataTimerPlan:
        normalized_target = str(target_key or "").strip().lower()
        return StrategyDetailSyndataTimerPlan(
            should_schedule=bool(normalized_target),
            pending_target_key=normalized_target or None,
            delay_ms=max(0, int(delay_ms)),
        )

    @staticmethod
    def build_syndata_persist_plan(
        *,
        target_key: str,
        pending_target_key: str | None,
        payload: dict[str, object],
    ) -> StrategyDetailSyndataPersistPlan:
        normalized_target = str(target_key or "").strip().lower()
        normalized_pending = str(pending_target_key or "").strip().lower()
        should_save = bool(normalized_target) and (not normalized_pending or normalized_pending == normalized_target)
        return StrategyDetailSyndataPersistPlan(
            should_save=should_save,
            normalized_target_key=normalized_target,
            payload=dict(payload or {}),
        )

    @staticmethod
    def build_target_settings_payload(*, details, protocol: str | None) -> dict[str, object]:
        if details is None:
            fallback = {
                "enabled": False,
                "blob": "tls_google",
                "tls_mod": "none",
                "autottl_delta": 0,
                "autottl_min": 3,
                "autottl_max": 20,
                "out_range": 8,
                "out_range_mode": "d",
                "tcp_flags_unset": "none",
                "send_enabled": False,
                "send_repeats": 2,
                "send_ip_ttl": 0,
                "send_ip6_ttl": 0,
                "send_ip_id": "none",
                "send_badsum": False,
            }
            from preset_zapret2.ui.strategy_detail.mode_policy import is_udp_like_protocol

            if is_udp_like_protocol(protocol):
                fallback["enabled"] = False
                fallback["send_enabled"] = False
            return fallback

        out_range = details.out_range_settings
        send = details.send_settings
        syndata = details.syndata_settings
        out_range_enabled = bool(out_range.enabled and int(out_range.value or 0) > 0)
        return {
            "enabled": bool(syndata.enabled),
            "blob": str(syndata.blob or "tls_google"),
            "tls_mod": str(syndata.tls_mod or "none"),
            "autottl_delta": int(syndata.autottl_delta or 0),
            "autottl_min": int(syndata.autottl_min or 3),
            "autottl_max": int(syndata.autottl_max or 20),
            "out_range": int(out_range.value or 8) if out_range_enabled else 8,
            "out_range_mode": str((out_range.mode if out_range_enabled else "d") or "d"),
            "tcp_flags_unset": str(syndata.tcp_flags_unset or "none"),
            "send_enabled": bool(send.enabled),
            "send_repeats": int(send.repeats or 0),
            "send_ip_ttl": int(send.ip_ttl or 0),
            "send_ip6_ttl": int(send.ip6_ttl or 0),
            "send_ip_id": str(send.ip_id or "none"),
            "send_badsum": bool(send.badsum),
        }

    @staticmethod
    def build_args_editor_state_plan(
        *,
        target_key: str,
        selected_strategy_id: str,
    ) -> StrategyDetailArgsEditorStatePlan:
        enabled = bool(str(target_key or "").strip()) and (str(selected_strategy_id or "none").strip() or "none") != "none"
        return StrategyDetailArgsEditorStatePlan(
            enabled=enabled,
            should_hide_editor=not enabled,
        )

    @staticmethod
    def build_args_editor_open_plan(
        facade,
        *,
        payload,
        target_key: str,
        selected_strategy_id: str,
    ) -> StrategyDetailArgsEditorOpenPlan:
        state_plan = StrategyDetailPageController.build_args_editor_state_plan(
            target_key=target_key,
            selected_strategy_id=selected_strategy_id,
        )
        if not state_plan.enabled:
            return StrategyDetailArgsEditorOpenPlan(
                should_open=False,
                initial_text="",
            )

        normalized_target = str(target_key or "").strip().lower()
        if payload is not None and str(getattr(payload, "target_key", "") or "").strip().lower() == normalized_target:
            return StrategyDetailArgsEditorOpenPlan(
                should_open=True,
                initial_text=str(getattr(payload, "raw_args_text", "") or ""),
            )
        try:
            return StrategyDetailArgsEditorOpenPlan(
                should_open=True,
                initial_text=str(facade.get_target_raw_args_text(normalized_target) or ""),
            )
        except Exception:
            return StrategyDetailArgsEditorOpenPlan(
                should_open=True,
                initial_text="",
            )

    @staticmethod
    def build_args_apply_plan(
        *,
        target_key: str,
        selected_strategy_id: str,
        raw_text: str,
    ) -> StrategyDetailArgsApplyPlan:
        state_plan = StrategyDetailPageController.build_args_editor_state_plan(
            target_key=target_key,
            selected_strategy_id=selected_strategy_id,
        )
        lines = [line.strip() for line in str(raw_text or "").splitlines() if line.strip()]
        return StrategyDetailArgsApplyPlan(
            should_apply=state_plan.enabled,
            normalized_text="\n".join(lines),
            args_lines=lines,
        )

    @staticmethod
    def build_args_apply_result_plan(*, payload) -> StrategyDetailArgsApplyResultPlan:
        current_strategy_id = (
            str(getattr(getattr(payload, "details", None), "current_strategy", "none") or "none").strip() or "none"
        )
        return StrategyDetailArgsApplyResultPlan(
            selected_strategy_id=current_strategy_id,
            current_strategy_id=current_strategy_id,
            should_show_loading=current_strategy_id != "none",
            should_emit_args_changed=True,
        )

    @staticmethod
    def build_tcp_phase_state_plan(
        *,
        phase_chunks: dict[str, str],
        phase_lookup: dict[str, dict[str, str]],
        phase_order: list[str],
        hide_fake_phase: bool,
        fake_disabled_strategy_id: str,
        custom_strategy_id: str,
    ) -> StrategyDetailTcpPhaseStatePlan:
        selected_ids: dict[str, str] = {}
        custom_args: dict[str, str] = {}

        if "fake" not in phase_chunks:
            selected_ids["fake"] = fake_disabled_strategy_id

        for phase_key in phase_order:
            chunk = str((phase_chunks or {}).get(phase_key, "") or "").strip()
            if not chunk:
                continue
            found = str(((phase_lookup or {}).get(phase_key, {}) or {}).get(chunk, "") or "").strip()
            if found:
                selected_ids[phase_key] = found
            else:
                selected_ids[phase_key] = custom_strategy_id
                custom_args[phase_key] = chunk

        return StrategyDetailTcpPhaseStatePlan(
            selected_ids=selected_ids,
            custom_args=custom_args,
            hide_fake_phase=bool(hide_fake_phase),
        )

    @staticmethod
    def build_tcp_phase_marker_plan(
        *,
        phase_label_map: dict[str, str],
        selected_ids: dict[str, str],
        custom_args: dict[str, str],
        fake_disabled_strategy_id: str,
        custom_strategy_id: str,
    ) -> StrategyDetailTcpPhaseMarkerPlan:
        labels_by_phase: dict[str, str] = {}
        for phase_key, label in (phase_label_map or {}).items():
            sid = str((selected_ids or {}).get(phase_key, "") or "").strip()
            is_active = False
            if sid and sid != "none":
                if phase_key == "fake" and sid == fake_disabled_strategy_id:
                    is_active = False
                elif sid == custom_strategy_id:
                    chunk = "\n".join(
                        [ln.strip() for ln in str((custom_args or {}).get(phase_key, "") or "").splitlines() if ln.strip()]
                    ).strip()
                    is_active = bool(chunk)
                else:
                    is_active = True
            labels_by_phase[phase_key] = f"● {label}" if is_active else label
        return StrategyDetailTcpPhaseMarkerPlan(labels_by_phase=labels_by_phase)

    @staticmethod
    def build_tcp_phase_tabs_visibility_plan(
        *,
        hide_fake_phase: bool,
        active_phase_key: str,
    ) -> StrategyDetailTcpPhaseTabsVisibilityPlan:
        normalized_active = str(active_phase_key or "").strip().lower()
        fallback = "multisplit" if hide_fake_phase and normalized_active == "fake" else None
        return StrategyDetailTcpPhaseTabsVisibilityPlan(
            hide_fake_phase=bool(hide_fake_phase),
            fallback_phase_key=fallback,
            should_reapply_filters=bool(fallback),
        )

    @staticmethod
    def build_active_phase_chip_plan(
        *,
        requested_phase_key: str,
        available_phase_keys: set[str],
        visible_phase_keys: set[str],
    ) -> StrategyDetailActivePhaseChipPlan:
        key = str(requested_phase_key or "").strip().lower()
        if not key or key not in (available_phase_keys or set()):
            return StrategyDetailActivePhaseChipPlan(
                should_apply=False,
                final_phase_key=None,
            )

        final_key = key if key in (visible_phase_keys or set()) else "multisplit"
        if final_key not in (available_phase_keys or set()):
            return StrategyDetailActivePhaseChipPlan(
                should_apply=False,
                final_phase_key=None,
            )
        return StrategyDetailActivePhaseChipPlan(
            should_apply=True,
            final_phase_key=final_key,
        )

    @staticmethod
    def build_default_tcp_phase_tab_plan(
        *,
        selected_ids: dict[str, str],
        hide_fake_phase: bool,
        phase_priority: list[str],
    ) -> StrategyDetailDefaultTcpPhaseTabPlan:
        preferred = None
        for phase_key in phase_priority:
            sid = str((selected_ids or {}).get(phase_key, "") or "").strip()
            if sid:
                preferred = phase_key
                break
        if not preferred:
            preferred = "multisplit"
        if hide_fake_phase and preferred == "fake":
            preferred = "multisplit"
        return StrategyDetailDefaultTcpPhaseTabPlan(preferred_phase_key=preferred)

    @staticmethod
    def build_tcp_phase_args_text(
        *,
        selected_ids: dict[str, str],
        custom_args: dict[str, str],
        hide_fake_phase: bool,
        phase_order: list[str],
        strategy_args_by_id: dict[str, str],
        fake_disabled_strategy_id: str,
        custom_strategy_id: str,
    ) -> str:
        out_lines: list[str] = []
        for phase in phase_order:
            if phase == "fake" and hide_fake_phase:
                continue

            sid = str((selected_ids or {}).get(phase, "") or "").strip()
            if not sid or sid == "none":
                continue
            if phase == "fake" and sid == fake_disabled_strategy_id:
                continue

            if sid == custom_strategy_id:
                chunk = "\n".join(
                    [ln.strip() for ln in str((custom_args or {}).get(phase, "") or "").splitlines() if ln.strip()]
                ).strip()
            else:
                chunk = "\n".join(
                    [ln.strip() for ln in str((strategy_args_by_id or {}).get(sid, "") or "").splitlines() if ln.strip()]
                ).strip()
            if not chunk:
                continue
            for raw in chunk.splitlines():
                line = raw.strip()
                if line:
                    out_lines.append(line)
        return "\n".join(out_lines).strip()

    @staticmethod
    def build_tcp_phase_save_result_plan(
        *,
        payload,
        show_loading: bool,
    ) -> StrategyDetailTcpPhaseSaveResultPlan:
        current_strategy_id = (
            str(getattr(getattr(payload, "details", None), "current_strategy", "none") or "none").strip() or "none"
        )
        return StrategyDetailTcpPhaseSaveResultPlan(
            selected_strategy_id=current_strategy_id,
            current_strategy_id=current_strategy_id,
            target_enabled=current_strategy_id != "none",
            should_refresh_args_editor=True,
            should_show_loading=bool(show_loading and current_strategy_id != "none"),
            should_hide_loading=current_strategy_id == "none",
            should_update_header=True,
            should_update_markers=True,
            should_emit_selection=True,
        )

    @staticmethod
    def _extract_desync_techniques_from_text(args_text: str) -> list[str]:
        techniques: list[str] = []
        for raw in str(args_text or "").splitlines():
            line = raw.strip()
            if not line or not line.startswith("--"):
                continue
            match = re.match(r"^--(?:lua-desync|dpi-desync)=([a-zA-Z0-9_-]+)", line)
            if not match:
                continue
            technique = str(match.group(1) or "").strip().lower()
            if technique:
                techniques.append(technique)
        return techniques

    @staticmethod
    def build_tcp_phase_row_click_plan(
        *,
        tcp_phase_mode: bool,
        target_key: str,
        active_phase_key: str,
        strategy_id: str,
        is_visible: bool,
        selected_ids: dict[str, str],
        custom_args: dict[str, str],
        strategy_args_by_id: dict[str, str],
        phase_order: list[str],
        embedded_fake_techniques: set[str],
        custom_strategy_id: str,
        fake_disabled_strategy_id: str,
    ) -> StrategyDetailTcpPhaseRowClickPlan:
        normalized_target = str(target_key or "").strip()
        phase = str(active_phase_key or "").strip().lower()
        sid = str(strategy_id or "").strip()
        updated_selected_ids = dict(selected_ids or {})
        updated_custom_args = dict(custom_args or {})

        if not tcp_phase_mode or not normalized_target or not phase or not sid or not is_visible:
            return StrategyDetailTcpPhaseRowClickPlan(
                should_apply=False,
                selected_ids=updated_selected_ids,
                custom_args=updated_custom_args,
                hide_fake_phase=False,
                should_select_strategy=False,
                selected_strategy_id=None,
                should_clear_active_strategy=False,
                should_save=False,
            )

        should_clear_active = False
        selected_strategy_to_highlight: str | None = None

        if phase == "fake":
            current = str(updated_selected_ids.get("fake", "") or "").strip()
            if current and current == sid:
                updated_selected_ids["fake"] = fake_disabled_strategy_id
                updated_custom_args.pop("fake", None)
                should_clear_active = True
            else:
                updated_selected_ids["fake"] = sid
                updated_custom_args.pop("fake", None)
                selected_strategy_to_highlight = sid
        else:
            current = str(updated_selected_ids.get(phase, "") or "").strip()
            if current == sid:
                updated_selected_ids.pop(phase, None)
                updated_custom_args.pop(phase, None)
                should_clear_active = True
            else:
                updated_selected_ids[phase] = sid
                updated_custom_args.pop(phase, None)
                selected_strategy_to_highlight = sid

        embedded_fake = False
        for key in phase_order:
            if key == "fake":
                continue
            sel_id = str(updated_selected_ids.get(key, "") or "").strip()
            if sel_id and sel_id not in (custom_strategy_id, fake_disabled_strategy_id):
                techniques = StrategyDetailPageController._extract_desync_techniques_from_text(
                    str((strategy_args_by_id or {}).get(sel_id, "") or "")
                )
                if any(tech in embedded_fake_techniques for tech in techniques):
                    embedded_fake = True
                    break
            if embedded_fake:
                break
        if not embedded_fake:
            for key, chunk in updated_custom_args.items():
                if str(key or "").strip().lower() == "fake":
                    continue
                techniques = StrategyDetailPageController._extract_desync_techniques_from_text(str(chunk or ""))
                if any(tech in embedded_fake_techniques for tech in techniques):
                    embedded_fake = True
                    break

        return StrategyDetailTcpPhaseRowClickPlan(
            should_apply=True,
            selected_ids=updated_selected_ids,
            custom_args=updated_custom_args,
            hide_fake_phase=embedded_fake,
            should_select_strategy=bool(selected_strategy_to_highlight),
            selected_strategy_id=selected_strategy_to_highlight,
            should_clear_active_strategy=should_clear_active,
            should_save=True,
        )

    @staticmethod
    def resolve_sort_mode(mode: str | None) -> str:
        mode_value = str(mode or "default").strip().lower() or "default"
        if mode_value in {"default", "name_asc", "name_desc"}:
            return mode_value
        return "default"

    @staticmethod
    def build_sort_label(*, mode: str | None, tr) -> str:
        mode_value = StrategyDetailPageController.resolve_sort_mode(mode)
        if mode_value == "name_asc":
            return tr("page.z2_strategy_detail.sort.name_asc", "По имени (А-Я)")
        if mode_value == "name_desc":
            return tr("page.z2_strategy_detail.sort.name_desc", "По имени (Я-А)")
        return tr("page.z2_strategy_detail.sort.default", "По умолчанию")

    @staticmethod
    def build_sort_tooltip(*, mode: str | None, tr) -> str:
        label = StrategyDetailPageController.build_sort_label(mode=mode, tr=tr)
        return tr("page.z2_strategy_detail.sort.tooltip", "Сортировка: {label}", label=label)

    @staticmethod
    def build_sort_options(*, tr) -> list[StrategyDetailSortOption]:
        return [
            StrategyDetailSortOption("default", tr("page.z2_strategy_detail.sort.default", "По умолчанию")),
            StrategyDetailSortOption("name_asc", tr("page.z2_strategy_detail.sort.name_asc", "По имени (А-Я)")),
            StrategyDetailSortOption("name_desc", tr("page.z2_strategy_detail.sort.name_desc", "По имени (Я-А)")),
        ]

    @staticmethod
    def build_technique_filter_plan(*, active_filters: set[str], technique_filters: list[tuple[str, str]]) -> StrategyDetailTechniqueFilterPlan:
        active = {str(t or "").strip().lower() for t in (active_filters or set()) if str(t or "").strip()}
        if not active:
            return StrategyDetailTechniqueFilterPlan(target_index=0)

        technique = next(iter(active))
        target_idx = 0
        for i, (_label, key) in enumerate(technique_filters, start=1):
            if key == technique:
                target_idx = i
                break
        return StrategyDetailTechniqueFilterPlan(target_index=target_idx)

    @staticmethod
    def build_strategies_summary(
        *,
        total: int,
        visible: int,
        tcp_phase_mode: bool,
        active_phase_key: str | None,
        active_filters: set[str],
        search_active: bool,
        technique_filters: list[tuple[str, str]],
        tr,
    ) -> StrategyDetailSummaryPlan:
        if total <= 0:
            return StrategyDetailSummaryPlan(
                text=tr(
                    "page.z2_strategy_detail.tree.summary.empty",
                    "Список пока пуст. Стратегии появятся после загрузки target-а.",
                )
            )

        text = tr(
            "page.z2_strategy_detail.tree.summary.counts",
            "Показано {visible} из {total}",
            visible=visible,
            total=total,
        )
        suffix: list[str] = []

        if tcp_phase_mode and active_phase_key:
            suffix.append(
                tr(
                    "page.z2_strategy_detail.tree.summary.phase",
                    "фаза: {phase}",
                    phase=str(active_phase_key).upper(),
                )
            )
        elif active_filters:
            active_key = next(iter(active_filters), "")
            active_label = ""
            for label_text, key in technique_filters:
                if key == active_key:
                    active_label = label_text
                    break
            if active_label:
                suffix.append(
                    tr(
                        "page.z2_strategy_detail.tree.summary.technique",
                        "техника: {technique}",
                        technique=active_label,
                    )
                )

        if search_active:
            suffix.append(tr("page.z2_strategy_detail.tree.summary.search", "поиск активен"))

        if suffix:
            text = f"{text} | {' | '.join(suffix)}"
        return StrategyDetailSummaryPlan(text=text)
