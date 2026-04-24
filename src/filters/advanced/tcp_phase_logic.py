from __future__ import annotations

import re


def extract_desync_techniques_from_text(args_text: str) -> list[str]:
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
    plan_factory,
):
    normalized_target = str(target_key or "").strip()
    phase = str(active_phase_key or "").strip().lower()
    sid = str(strategy_id or "").strip()
    updated_selected_ids = dict(selected_ids or {})
    updated_custom_args = dict(custom_args or {})

    if not tcp_phase_mode or not normalized_target or not phase or not sid or not is_visible:
        return plan_factory(
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
            techniques = extract_desync_techniques_from_text(str((strategy_args_by_id or {}).get(sel_id, "") or ""))
            if any(tech in embedded_fake_techniques for tech in techniques):
                embedded_fake = True
                break
        if embedded_fake:
            break

    if not embedded_fake:
        for key, chunk in updated_custom_args.items():
            if str(key or "").strip().lower() == "fake":
                continue
            techniques = extract_desync_techniques_from_text(str(chunk or ""))
            if any(tech in embedded_fake_techniques for tech in techniques):
                embedded_fake = True
                break

    return plan_factory(
        should_apply=True,
        selected_ids=updated_selected_ids,
        custom_args=updated_custom_args,
        hide_fake_phase=embedded_fake,
        should_select_strategy=bool(selected_strategy_to_highlight),
        selected_strategy_id=selected_strategy_to_highlight,
        should_clear_active_strategy=should_clear_active,
        should_save=True,
    )
