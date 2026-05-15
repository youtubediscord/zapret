from __future__ import annotations

from dataclasses import dataclass

from log.log import log
from settings.mode import is_orchestra_launch_method, is_preset_launch_method


@dataclass(frozen=True, slots=True)
class ProfileStrategyDisplayState:
    summary: str
    active_count: int

    @property
    def tooltip(self) -> str:
        if self.active_count <= 0 or not self.summary:
            return ""
        return self.summary.replace(" • ", "\n").replace(" +", "\n+")


def resolve_profile_strategy_display_state(
    *,
    method: str,
    profile_feature,
    max_items: int = 2,
) -> ProfileStrategyDisplayState:
    """Готовит краткое имя активных profile для UI.

    UI не должен сам читать profile-ы и решать, что показывать на control page.
    Здесь остаётся только бизнес-смысл: выбранный preset -> enabled profiles ->
    краткое отображение.
    """
    if not is_preset_launch_method(method):
        return ProfileStrategyDisplayState(summary="Профили", active_count=0)

    try:
        payload = profile_feature.list_profiles(method)
        active_names = [
            item.display_name
            for item in payload.items
            if item.in_preset and item.enabled and item.strategy_id != "none"
        ]
    except Exception:
        return ProfileStrategyDisplayState(summary="Профили", active_count=0)

    if not active_names:
        return ProfileStrategyDisplayState(summary="Не выбрана", active_count=0)
    if len(active_names) <= max_items:
        return ProfileStrategyDisplayState(
            summary=" • ".join(active_names),
            active_count=len(active_names),
        )
    return ProfileStrategyDisplayState(
        summary=" • ".join(active_names[:max_items]) + f" +{len(active_names) - max_items} ещё",
        active_count=len(active_names),
    )


def refresh_profile_strategy_summary_in_store(
    *,
    method: str,
    profile_feature,
    ui_state_store,
) -> None:
    """Обновляет summary profiles после смены source preset."""
    try:
        state = resolve_profile_strategy_display_state(
            method=method,
            profile_feature=profile_feature,
        )
        if ui_state_store is not None and state.summary:
            ui_state_store.set_current_strategy_summary(state.summary)
    except Exception as e:
        log(f"Ошибка обновления display стратегии после смены пресета: {e}", "DEBUG")


def refresh_launch_summary_in_store(
    *,
    method: str,
    profile_feature,
    ui_state_store,
) -> None:
    """Обновляет краткое отображение текущего launch-режима.

    Это display-слой, а не runtime: он решает, какой текст показать в UI,
    когда уже известен текущий способ запуска.
    """
    normalized_method = str(method or "").strip().lower()
    if is_orchestra_launch_method(normalized_method):
        if ui_state_store is not None:
            ui_state_store.set_current_strategy_summary("Оркестр")
        return

    refresh_profile_strategy_summary_in_store(
        method=normalized_method,
        profile_feature=profile_feature,
        ui_state_store=ui_state_store,
    )


__all__ = [
    "ProfileStrategyDisplayState",
    "refresh_launch_summary_in_store",
    "refresh_profile_strategy_summary_in_store",
    "resolve_profile_strategy_display_state",
]
