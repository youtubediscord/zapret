from __future__ import annotations

from dataclasses import dataclass


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


def resolve_sort_mode(mode: str | None) -> str:
    mode_value = str(mode or "default").strip().lower() or "default"
    if mode_value in {"default", "name_asc", "name_desc"}:
        return mode_value
    return "default"


def build_sort_label(*, mode: str | None, tr) -> str:
    mode_value = resolve_sort_mode(mode)
    if mode_value == "name_asc":
        return tr("page.z2_strategy_detail.sort.name_asc", "По имени (А-Я)")
    if mode_value == "name_desc":
        return tr("page.z2_strategy_detail.sort.name_desc", "По имени (Я-А)")
    return tr("page.z2_strategy_detail.sort.default", "По умолчанию")


def build_sort_tooltip(*, mode: str | None, tr) -> str:
    label = build_sort_label(mode=mode, tr=tr)
    return tr("page.z2_strategy_detail.sort.tooltip", "Сортировка: {label}", label=label)


def build_sort_options(*, tr) -> list[StrategyDetailSortOption]:
    return [
        StrategyDetailSortOption("default", tr("page.z2_strategy_detail.sort.default", "По умолчанию")),
        StrategyDetailSortOption("name_asc", tr("page.z2_strategy_detail.sort.name_asc", "По имени (А-Я)")),
        StrategyDetailSortOption("name_desc", tr("page.z2_strategy_detail.sort.name_desc", "По имени (Я-А)")),
    ]


def build_technique_filter_plan(
    *,
    active_filters: set[str],
    technique_filters: list[tuple[str, str]],
) -> StrategyDetailTechniqueFilterPlan:
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


def build_sort_change_plan(
    *,
    requested_mode: str,
    current_mode: str,
    target_key: str,
) -> StrategyDetailSortChangePlan:
    normalized_requested = resolve_sort_mode(requested_mode)
    normalized_current = resolve_sort_mode(current_mode)
    return StrategyDetailSortChangePlan(
        normalized_mode=normalized_requested,
        should_apply=normalized_requested != normalized_current,
        should_persist=bool(str(target_key or "").strip()) and normalized_requested != normalized_current,
    )


def build_sort_apply_plan(
    *,
    sort_mode: str,
    selected_strategy_id: str,
    current_strategy_id: str,
    has_selected_strategy: bool,
) -> StrategyDetailSortApplyPlan:
    selected = str(selected_strategy_id or current_strategy_id or "none").strip() or "none"
    return StrategyDetailSortApplyPlan(
        normalized_mode=resolve_sort_mode(sort_mode),
        selected_strategy_id=selected,
        should_restore_selected_strategy=bool(selected) and has_selected_strategy,
    )


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
