"""Selection persistence/plan helper'ы для страницы деталей стратегии Zapret 1."""

from __future__ import annotations

from dataclasses import dataclass

from filters.strategy_detail.shared_filter_mode import save_target_filter_mode


@dataclass(frozen=True, slots=True)
class EnableTogglePlanV1:
    should_select_strategy: bool
    strategy_id: str
    remember_last_enabled_strategy_id: str | None
    should_restore_toggle_off: bool


def save_filter_mode_v1(direct_facade, *, target_key: str, mode: str) -> bool:
    return save_target_filter_mode(
        direct_facade,
        target_key=target_key,
        mode=mode,
    )


def resolve_enable_toggle_plan_v1(
    *,
    enabled: bool,
    last_enabled_strategy_id: str,
    default_strategy_id: str,
    current_strategy_id: str,
) -> EnableTogglePlanV1:
    if enabled:
        strategy_id = str(last_enabled_strategy_id or "").strip()
        if not strategy_id or strategy_id == "none":
            strategy_id = str(default_strategy_id or "").strip() or "none"
        if strategy_id == "none":
            return EnableTogglePlanV1(
                should_select_strategy=False,
                strategy_id="none",
                remember_last_enabled_strategy_id=None,
                should_restore_toggle_off=True,
            )
        return EnableTogglePlanV1(
            should_select_strategy=True,
            strategy_id=strategy_id,
            remember_last_enabled_strategy_id=None,
            should_restore_toggle_off=False,
        )

    remembered = None
    if current_strategy_id and current_strategy_id != "none":
        remembered = str(current_strategy_id).strip()
    return EnableTogglePlanV1(
        should_select_strategy=True,
        strategy_id="none",
        remember_last_enabled_strategy_id=remembered,
        should_restore_toggle_off=False,
    )


def persist_strategy_selection_v1(direct_facade, *, target_key: str, strategy_id: str) -> str:
    sid = (strategy_id or "none").strip() or "none"
    ok = direct_facade.set_strategy_selection(
        target_key,
        sid,
        save_and_sync=True,
    )
    if ok is False:
        raise RuntimeError("Не удалось сохранить выбор стратегии")
    return sid
