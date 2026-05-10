from __future__ import annotations

import os

from log.log import log

from main.runtime_state import startup_elapsed_ms
from ui.window_appearance_state import on_animations_changed
from ui.state.main_window_state import AppUiState


class WindowStateSyncMixin:
    def _ensure_holiday_effects_manager(self):
        effects = getattr(self, "_holiday_effects", None)
        if effects is not None:
            return effects

        try:
            from ui.holiday_effects import HolidayEffectsManager

            effects = HolidayEffectsManager(self)
            self._holiday_effects = effects
            return effects
        except Exception as e:
            log(f"❌ Ошибка создания праздничных эффектов: {e}", "DEBUG")
            return None

    @staticmethod
    def _build_initial_ui_state() -> AppUiState:
        """Честное стартовое состояние UI до реальной синхронизации runtime-слоёв.

        Здесь важно не смешивать два разных механизма:
        - `is_auto_dpi_enabled()` — запуск DPI после старта уже открытого GUI;
        - `AppUiState.autostart_enabled` — сохранённое в settings.json состояние
          автозапуска самого GUI-приложения.

        На старте не опрашиваем Task Scheduler: это тяжёлая Windows-проверка.
        UI показывает сохранённый выбор пользователя, а реальная задача Windows
        меняется только при явном включении или отключении автозапуска.
        """
        try:
            from program_settings.public import is_auto_dpi_enabled
            from settings.store import get_gui_autostart_enabled
            from winws_runtime.public import LaunchRuntimeService

            from settings.dpi.strategy_settings import get_strategy_launch_method
            from settings.mode import ALL_LAUNCH_METHODS, normalize_launch_method

            dpi_autostart_enabled = bool(is_auto_dpi_enabled())
            gui_autostart_enabled = bool(get_gui_autostart_enabled())
            launch_method = normalize_launch_method(get_strategy_launch_method(), default="")

            return LaunchRuntimeService.build_initial_ui_state(
                launch_method=launch_method,
                dpi_autostart_enabled=dpi_autostart_enabled,
                gui_autostart_enabled=gui_autostart_enabled,
                launch_supported=launch_method in ALL_LAUNCH_METHODS,
            )
        except Exception:
            return AppUiState()

    def _apply_runner_failure_update(self, payload: object) -> None:
        if not isinstance(payload, dict):
            return

        launch_method = str(payload.get("launch_method") or "").strip().lower()
        if not is_preset_launch_method(launch_method):
            return

        snapshot = self.launch_runtime_service.snapshot()
        current_method = str(snapshot.launch_method or "").strip().lower()
        if current_method and current_method != launch_method and snapshot.phase in {"starting", "running", "autostart_pending"}:
            return

        error_text = str(payload.get("error") or "").strip()

        self.launch_runtime_service.mark_start_failed(
            error_text or "Запуск завершился ошибкой",
        )

    def _apply_active_preset_content_changed(self, path: str) -> None:
        normalized_path = os.path.normcase(str(path or "").strip())
        if not normalized_path:
            return

        now_ms = startup_elapsed_ms()
        if (
            normalized_path == str(self._last_active_preset_content_path or "")
            and max(0, now_ms - int(self._last_active_preset_content_ms or 0)) < 500
        ):
            return

        self._last_active_preset_content_path = normalized_path
        self._last_active_preset_content_ms = now_ms

        try:
            self.ui_state_store.bump_preset_content_revision()
        except Exception:
            pass

    def set_garland_enabled(self, enabled: bool) -> None:
        """Enable/disable top garland overlay in FluentWindow shell."""
        try:
            snapshot = self.ui_state_store.snapshot()
            self.ui_state_store.set_holiday_overlays(bool(enabled), snapshot.snowflakes_enabled)

            effects = self._ensure_holiday_effects_manager()
            if effects is None:
                return
            effects.set_garland_enabled(bool(enabled))
        except Exception as e:
            log(f"❌ Ошибка переключения гирлянды: {e}", "ERROR")

    def set_snowflakes_enabled(self, enabled: bool) -> None:
        """Enable/disable snow overlay in FluentWindow shell."""
        try:
            snapshot = self.ui_state_store.snapshot()
            self.ui_state_store.set_holiday_overlays(snapshot.garland_enabled, bool(enabled))

            effects = self._ensure_holiday_effects_manager()
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
            self.ui_state_store.set_window_opacity_value(value)

            from settings.store import get_background_preset

            if get_background_preset() != "standard":
                log("Transparent effect проигнорирован (не standard пресет)", "DEBUG")
                return

            from settings.store import get_mica_enabled
            from ui.theme import apply_aero_effect, apply_window_background

            if get_mica_enabled():
                apply_aero_effect(self, value)
            else:
                apply_window_background(self)
            log(f"Прозрачность обновлена: {value}%", "DEBUG")
        except Exception as e:
            log(f"❌ Ошибка при установке прозрачности окна: {e}", "ERROR")

    def _init_garland_from_registry(self) -> None:
        """Загружает состояние гирлянды и снежинок из реестра при старте."""
        try:
            from settings.store import get_animations_enabled, get_garland_enabled, get_snowflakes_enabled, get_window_opacity

            garland_saved = get_garland_enabled()
            snowflakes_saved = get_snowflakes_enabled()
            log(f"🎄 Инициализация: гирлянда={garland_saved}, снежинки={snowflakes_saved}", "DEBUG")

            try:
                from donater.public import get_premium_state

                premium_state = get_premium_state(use_cache=True)
                is_premium = bool(premium_state.is_premium)
                log(f"🎄 Премиум статус: {is_premium}", "DEBUG")
            except Exception as e:
                is_premium = False
                log(f"🎄 Ошибка проверки премиума: {e}", "DEBUG")

            should_enable_garland = is_premium and garland_saved
            self.set_garland_enabled(should_enable_garland)

            should_enable_snowflakes = is_premium and snowflakes_saved
            self.set_snowflakes_enabled(should_enable_snowflakes)

            opacity_saved = get_window_opacity()
            log(f"🔮 Инициализация: opacity={opacity_saved}%", "DEBUG")
            self.set_window_opacity(opacity_saved)

            if not get_animations_enabled():
                on_animations_changed(self, False)

        except Exception as e:
            log(f"❌ Ошибка загрузки состояния декораций: {e}", "ERROR")
            import traceback

            log(traceback.format_exc(), "DEBUG")
