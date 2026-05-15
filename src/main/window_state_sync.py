from __future__ import annotations

from log.log import log

from ui.window_appearance_state import on_animations_changed
from app.initial_ui_state import build_initial_ui_state
from app.state_store import AppUiState


class WindowStateSyncMixin:
    @property
    def _ui_state_store(self):
        return self.app_runtime.state.ui

    def ensure_holiday_effects_manager(self):
        effects = self.visual_state.holiday_effects
        if effects is not None:
            return effects

        try:
            from ui.holiday_effects import HolidayEffectsManager

            effects = HolidayEffectsManager(self)
            self.visual_state.holiday_effects = effects
            return effects
        except Exception as e:
            log(f"❌ Ошибка создания праздничных эффектов: {e}", "DEBUG")
            return None

    @staticmethod
    def _build_initial_ui_state() -> AppUiState:
        return build_initial_ui_state()

    def set_garland_enabled(self, enabled: bool) -> None:
        """Enable/disable top garland overlay in FluentWindow shell."""
        try:
            ui_state_store = self._ui_state_store
            snapshot = ui_state_store.snapshot()
            ui_state_store.set_holiday_overlays(bool(enabled), snapshot.snowflakes_enabled)

            effects = self.ensure_holiday_effects_manager()
            if effects is None:
                return
            effects.set_garland_enabled(bool(enabled))
        except Exception as e:
            log(f"❌ Ошибка переключения гирлянды: {e}", "ERROR")

    def set_snowflakes_enabled(self, enabled: bool) -> None:
        """Enable/disable snow overlay in FluentWindow shell."""
        try:
            ui_state_store = self._ui_state_store
            snapshot = ui_state_store.snapshot()
            ui_state_store.set_holiday_overlays(snapshot.garland_enabled, bool(enabled))

            effects = self.ensure_holiday_effects_manager()
            if effects is None:
                return
            effects.set_snowflakes_enabled(bool(enabled))
        except Exception as e:
            log(f"❌ Ошибка переключения снежинок: {e}", "ERROR")

    def set_window_opacity(self, value: int) -> None:
        """Устанавливает прозрачность фона окна (0–100%).

        Win11: при включённой Mica обновляет её тинт.
        В обычном статичном фоне просто пересобирает фон окна.
        """
        try:
            self._ui_state_store.set_window_opacity_value(value)

            from settings.appearance import load_background_preset

            if load_background_preset().preset != "standard":
                log("Transparent effect проигнорирован (не standard пресет)", "DEBUG")
                return

            from settings.appearance import load_mica_enabled
            from ui.theme import apply_aero_effect, apply_window_background

            if load_mica_enabled().enabled:
                apply_aero_effect(self, value)
            else:
                apply_window_background(self)
            log(f"Прозрачность обновлена: {value}%", "DEBUG")
        except Exception as e:
            log(f"❌ Ошибка при установке прозрачности окна: {e}", "ERROR")

    def init_holiday_effects_from_settings(self, *, effects_allowed: bool) -> None:
        """Загружает состояние гирлянды и снежинок из реестра при старте."""
        try:
            from settings.appearance import (
                load_animations_enabled,
                load_premium_effects,
                load_window_opacity,
            )

            premium_effects = load_premium_effects()
            garland_saved = premium_effects.garland_enabled
            snowflakes_saved = premium_effects.snowflakes_enabled
            log(f"🎄 Инициализация: гирлянда={garland_saved}, снежинки={snowflakes_saved}", "DEBUG")

            should_enable_garland = bool(effects_allowed) and garland_saved
            self.set_garland_enabled(should_enable_garland)

            should_enable_snowflakes = bool(effects_allowed) and snowflakes_saved
            self.set_snowflakes_enabled(should_enable_snowflakes)

            opacity_saved = load_window_opacity().value
            log(f"🔮 Инициализация: opacity={opacity_saved}%", "DEBUG")
            self.set_window_opacity(opacity_saved)

            if not load_animations_enabled().enabled:
                on_animations_changed(self, False)

        except Exception as e:
            log(f"❌ Ошибка загрузки состояния декораций: {e}", "ERROR")
            import traceback

            log(traceback.format_exc(), "DEBUG")
