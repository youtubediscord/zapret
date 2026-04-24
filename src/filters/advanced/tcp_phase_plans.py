from __future__ import annotations

from dataclasses import dataclass

from direct_preset.modes import resolve_direct_mode_logic


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


def extract_desync_techniques_from_text(args_text: str) -> list[str]:
    mode_logic = resolve_direct_mode_logic("winws2", "advanced")
    if mode_logic is None:
        return []
    return list(mode_logic.extract_desync_techniques_from_text(args_text))


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
    mode_logic = resolve_direct_mode_logic("winws2", "advanced")
    if mode_logic is None:
        return StrategyDetailTcpPhaseRowClickPlan(
            should_apply=False,
            selected_ids=dict(selected_ids or {}),
            custom_args=dict(custom_args or {}),
            hide_fake_phase=False,
            should_select_strategy=False,
            selected_strategy_id=None,
            should_clear_active_strategy=False,
            should_save=False,
        )

    return mode_logic.build_tcp_phase_row_click_plan(
        tcp_phase_mode=tcp_phase_mode,
        target_key=target_key,
        active_phase_key=active_phase_key,
        strategy_id=strategy_id,
        is_visible=is_visible,
        selected_ids=selected_ids,
        custom_args=custom_args,
        strategy_args_by_id=strategy_args_by_id,
        phase_order=phase_order,
        embedded_fake_techniques=embedded_fake_techniques,
        custom_strategy_id=custom_strategy_id,
        fake_disabled_strategy_id=fake_disabled_strategy_id,
        plan_factory=StrategyDetailTcpPhaseRowClickPlan,
    )
