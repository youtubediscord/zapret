from __future__ import annotations

from dataclasses import dataclass
from typing import Any


def _holiday_effects_allowed() -> bool:
    try:
        from settings.appearance import peek_warmed_animations_enabled

        return bool(peek_warmed_animations_enabled())
    except Exception:
        return False


@dataclass(frozen=True, slots=True)
class WindowStateActions:
    window: Any
    ui_state_store: Any

    def set_garland_enabled(self, enabled: bool) -> None:
        try:
            from ui.window_appearance_state import apply_garland_enabled

            effects_allowed = _holiday_effects_allowed()
            effective_enabled = bool(enabled) and effects_allowed
            snapshot = self.ui_state_store.snapshot()
            self.ui_state_store.set_holiday_overlays(effective_enabled, bool(snapshot.snowflakes_enabled) and effects_allowed)
            apply_garland_enabled(self.window, effective_enabled)
        except Exception as exc:
            from log.log import log

            log(f"❌ Ошибка переключения гирлянды: {exc}", "ERROR")

    def set_snowflakes_enabled(self, enabled: bool) -> None:
        try:
            from ui.window_appearance_state import apply_snowflakes_enabled

            effects_allowed = _holiday_effects_allowed()
            effective_enabled = bool(enabled) and effects_allowed
            snapshot = self.ui_state_store.snapshot()
            self.ui_state_store.set_holiday_overlays(bool(snapshot.garland_enabled) and effects_allowed, effective_enabled)
            apply_snowflakes_enabled(self.window, effective_enabled)
        except Exception as exc:
            from log.log import log

            log(f"❌ Ошибка переключения снежинок: {exc}", "ERROR")

    def set_window_opacity(self, value: int) -> None:
        try:
            from ui.window_appearance_state import apply_window_opacity_value

            self.ui_state_store.set_window_opacity_value(value)
            apply_window_opacity_value(self.window, value)
        except Exception as exc:
            from log.log import log

            log(f"❌ Ошибка при установке прозрачности окна: {exc}", "ERROR")


__all__ = ["WindowStateActions"]
