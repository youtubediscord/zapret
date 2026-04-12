from __future__ import annotations

import os

from log import log
from main.runtime_state import startup_elapsed_ms
from ui.main_window_appearance_flow import on_animations_changed
from ui.holiday_effects import HolidayEffectsManager
from app_state.main_window_state import AppUiState


class WindowStateSyncMixin:
    @staticmethod
    def _build_initial_ui_state() -> AppUiState:
        """Честное стартовое состояние UI до реальной проверки и автозапуска."""
        try:
            from config import get_dpi_autostart, get_winws_exe_for_method
            from strategy_menu import get_strategy_launch_method

            autostart_enabled = bool(get_dpi_autostart())
            launch_method = str(get_strategy_launch_method() or "").strip().lower()
            expected_process = ""
            if launch_method and launch_method != "orchestra":
                expected_process = os.path.basename(get_winws_exe_for_method(launch_method)).strip().lower()

            autostart_pending_methods = {
                "direct_zapret2",
                "direct_zapret1",
                "orchestra",
            }

            if autostart_enabled and launch_method in autostart_pending_methods:
                return AppUiState(
                    launch_phase="autostart_pending",
                    launch_running=False,
                    launch_expected_process=expected_process,
                    autostart_enabled=autostart_enabled,
                )

            return AppUiState(
                launch_phase="stopped",
                launch_running=False,
                launch_expected_process=expected_process,
                autostart_enabled=autostart_enabled,
            )
        except Exception:
            return AppUiState()

    def _apply_runner_failure_update(self, payload: object) -> None:
        if not isinstance(payload, dict):
            return

        runtime_service = getattr(self, "launch_runtime_service", None)
        if runtime_service is None:
            return

        launch_method = str(payload.get("launch_method") or "").strip().lower()
        if launch_method not in {"direct_zapret1", "direct_zapret2"}:
            return

        snapshot = runtime_service.snapshot()
        current_method = str(snapshot.launch_method or "").strip().lower()
        if current_method and current_method != launch_method and snapshot.phase in {"starting", "running", "autostart_pending"}:
            return

        error_text = str(payload.get("error") or "").strip()

        runtime_service.mark_start_failed(
            error_text or "Запуск завершился ошибкой",
        )

    def _apply_active_preset_content_changed(self, path: str) -> None:
        normalized_path = os.path.normcase(str(path or "").strip())
        if not normalized_path:
            return

        now_ms = startup_elapsed_ms()
        if (
            normalized_path == str(getattr(self, "_last_active_preset_content_path", "") or "")
            and max(0, now_ms - int(getattr(self, "_last_active_preset_content_ms", 0) or 0)) < 500
        ):
            return

        self._last_active_preset_content_path = normalized_path
        self._last_active_preset_content_ms = now_ms

        store = getattr(self, "ui_state_store", None)
        if store is None:
            return
        try:
            store.bump_preset_content_revision()
        except Exception:
            pass

    def set_garland_enabled(self, enabled: bool) -> None:
        """Enable/disable top garland overlay in FluentWindow shell."""
        try:
            store = getattr(self, "ui_state_store", None)
            if store is not None:
                snapshot = store.snapshot()
                store.set_holiday_overlays(bool(enabled), snapshot.snowflakes_enabled)

            effects = getattr(self, "_holiday_effects", None)
            if effects is None:
                effects = HolidayEffectsManager(self)
                self._holiday_effects = effects
            effects.set_garland_enabled(bool(enabled))
        except Exception as e:
            log(f"❌ Ошибка переключения гирлянды: {e}", "ERROR")

    def set_snowflakes_enabled(self, enabled: bool) -> None:
        """Enable/disable snow overlay in FluentWindow shell."""
        try:
            store = getattr(self, "ui_state_store", None)
            if store is not None:
                snapshot = store.snapshot()
                store.set_holiday_overlays(snapshot.garland_enabled, bool(enabled))

            effects = getattr(self, "_holiday_effects", None)
            if effects is None:
                effects = HolidayEffectsManager(self)
                self._holiday_effects = effects
            effects.set_snowflakes_enabled(bool(enabled))
        except Exception as e:
            log(f"❌ Ошибка переключения снежинок: {e}", "ERROR")

    def set_window_opacity(self, value: int) -> None:
        """Устанавливает прозрачность фона окна (0–100%).

        Win11: обновляет тинт-оверлей поверх Mica (apply_aero_effect fast path).
        Win10: применяет setWindowOpacity через apply_aero_effect.
        """
        try:
            store = getattr(self, "ui_state_store", None)
            if store is not None:
                store.set_window_opacity_value(value)

            from config.reg import get_background_preset

            if get_background_preset() != "standard":
                log("Transparent effect проигнорирован (не standard пресет)", "DEBUG")
                return

            from ui.theme import apply_aero_effect

            apply_aero_effect(self, value)
            log(f"Прозрачность обновлена: {value}%", "DEBUG")
        except Exception as e:
            log(f"❌ Ошибка при установке прозрачности окна: {e}", "ERROR")

    def _init_garland_from_registry(self) -> None:
        """Загружает состояние гирлянды и снежинок из реестра при старте."""
        try:
            from config.reg import get_animations_enabled, get_garland_enabled, get_snowflakes_enabled, get_window_opacity

            garland_saved = get_garland_enabled()
            snowflakes_saved = get_snowflakes_enabled()
            log(f"🎄 Инициализация: гирлянда={garland_saved}, снежинки={snowflakes_saved}", "DEBUG")

            is_premium = False
            if hasattr(self, "donate_checker") and self.donate_checker:
                try:
                    sub_info = self.donate_checker.get_full_subscription_info(use_cache=True)
                    is_premium = bool(sub_info.get("is_premium"))
                    log(f"🎄 Премиум статус: {is_premium}", "DEBUG")
                except Exception as e:
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
