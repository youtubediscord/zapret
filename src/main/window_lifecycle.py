from __future__ import annotations

from PyQt6.QtCore import QEvent, QTimer
from PyQt6.QtWidgets import QApplication, QWidget

from log.log import log

from main.window_lifecycle_cleanup import (
    cleanup_process_monitor_for_close,
    cleanup_runtime_threads_for_close,
    cleanup_subscription_for_close,
    cleanup_theme_for_close,
    cleanup_threaded_pages_for_close,
    cleanup_visual_and_proxy_resources_for_close,
    detach_global_error_notifier,
    persist_window_geometry,
    release_input_interaction_states,
)
from main.runtime_state import (
    log_startup_metric as emit_startup_metric,
    startup_elapsed_ms,
)
from ui.window_adapter import sync_titlebar_search_width


class WindowLifecycleMixin:
    def closeEvent(self, event):
        """Обрабатывает событие закрытия окна."""
        if not self.window_close_flow.should_continue_final_close(event):
            return

        self.close_state.is_exiting = True
        self._run_final_close_cleanup()

        super().closeEvent(event)

    def release_input_interaction_states(self) -> None:
        release_input_interaction_states(self)

    def request_exit(self, stop_dpi: bool) -> None:
        """Общий вход для tray и adapter-слоя."""
        if stop_dpi:
            self.exit_stop_dpi()
        else:
            self.exit_keep_dpi()

    def exit_keep_dpi(self) -> None:
        """Полный выход из GUI без остановки DPI."""
        self._prepare_full_exit(stop_dpi=False)
        log("Запрошен выход: выйти без остановки DPI", "INFO")
        self._quit_application()

    def exit_stop_dpi(self) -> None:
        """Полный выход из GUI с остановкой DPI."""
        self._prepare_full_exit(stop_dpi=True)
        log("Запрошен выход: остановить DPI и выйти", "INFO")

        if self._start_async_stop_and_exit():
            return

        self._shutdown_dpi_before_exit_sync(reason="exit_stop_dpi")
        self._quit_application()

    def _prepare_full_exit(self, *, stop_dpi: bool) -> None:
        self.close_state.stop_dpi_on_exit = bool(stop_dpi)
        self.close_state.closing_completely = True

        persist_window_geometry(self, context="request_exit", level="DEBUG")
        self.app_runtime.features.tray.hide_icon_for_exit()

    def _start_async_stop_and_exit(self) -> bool:
        try:
            runtime_feature = self.app_runtime.features.runtime
            return bool(runtime_feature.stop_and_exit())
        except Exception as e:
            log(f"stop_and_exit_async не удалось: {e}", "WARNING")
            return False

    def _shutdown_dpi_before_exit_sync(self, *, reason: str) -> None:
        try:
            runtime_feature = self.app_runtime.features.runtime
            runtime_feature.shutdown_sync(reason=reason, include_cleanup=True)
        except Exception as e:
            log(f"Ошибка остановки DPI перед выходом: {e}", "WARNING")

    def _quit_application(self) -> None:
        QApplication.closeAllWindows()
        QApplication.processEvents()
        QApplication.quit()

    def close_to_tray(self) -> bool:
        """Скрывает окно в трей (без выхода из GUI)."""
        try:
            return bool(self.app_runtime.features.tray.hide_to_tray(show_hint=True))
        except Exception as e:
            log(f"Ошибка сценария сворачивания в трей: {e}", "WARNING")

        return False

    def _cleanup_before_close(self) -> None:
        features = self.app_runtime.features
        runtime_feature = features.runtime
        self._cleanup_process_monitor_for_close(runtime_feature)
        self._cleanup_subscription_for_close(features.premium)
        self._cleanup_theme_for_close()
        self._cleanup_threaded_pages_for_close()
        self._cleanup_visual_and_proxy_resources_for_close(
            telegram_proxy_feature=features.telegram_proxy,
        )
        self._cleanup_runtime_threads_for_close(runtime_feature)

    def _run_final_close_cleanup(self) -> None:
        detach_global_error_notifier()
        persist_window_geometry(self, context="закрытии", level="❌ ERROR")

        self._cleanup_before_close()
        self._finish_dpi_for_final_close()
        self._cleanup_tray_for_close()

    def _finish_dpi_for_final_close(self) -> None:
        if not self.close_state.stop_dpi_on_exit:
            log("Выход без остановки DPI: winws не трогаем", "DEBUG")
            return

        try:
            runtime_feature = self.app_runtime.features.runtime
            result = runtime_feature.shutdown_sync(
                reason="close_event exit_stop_dpi",
                include_cleanup=True,
            )
            log(
                f"Процессы winws завершены при закрытии приложения "
                f"(running={result.had_running_processes}, still_running={result.still_running})",
                "DEBUG",
            )
        except Exception as e:
            log(f"Ошибка остановки winws при закрытии: {e}", "DEBUG")

    def changeEvent(self, event):
        if event.type() == QEvent.Type.ActivationChange:
            try:
                if not self.isActiveWindow():
                    self.release_input_interaction_states()
            except Exception as e:
                log(f"Не удалось сбросить состояние ввода при смене активности окна: {e}", "DEBUG")

        if event.type() == QEvent.Type.WindowStateChange:
            self.window_geometry_runtime.on_window_state_change()

            try:
                effects = self.visual_state.holiday_effects
                if effects is not None:
                    QTimer.singleShot(0, effects.sync_geometry)
            except Exception as e:
                log(f"Не удалось синхронизировать визуальные эффекты при смене состояния окна: {e}", "DEBUG")

        super().changeEvent(event)

    def hideEvent(self, event):
        try:
            self.release_input_interaction_states()
        except Exception as e:
            log(f"Не удалось сбросить состояние ввода при скрытии окна: {e}", "DEBUG")
        super().hideEvent(event)

    def moveEvent(self, event):
        super().moveEvent(event)
        self.window_geometry_runtime.on_geometry_changed()

    def resizeEvent(self, event):
        """Обновляем геометрию при изменении размера окна."""
        super().resizeEvent(event)
        try:
            sync_titlebar_search_width(self)
        except Exception as e:
            log(f"Не удалось синхронизировать ширину поиска в заголовке: {e}", "DEBUG")
        self.window_geometry_runtime.on_geometry_changed()
        try:
            effects = self.visual_state.holiday_effects
            if effects is not None:
                effects.sync_geometry()
        except Exception as e:
            log(f"Не удалось синхронизировать визуальные эффекты при изменении размера окна: {e}", "DEBUG")

    def showEvent(self, event):
        """Первый показ окна."""
        super().showEvent(event)

        startup_state = self.startup_state
        if not startup_state.ttff_logged:
            startup_state.ttff_logged = True
            startup_state.ttff_ms = startup_elapsed_ms()
            emit_startup_metric("StartupTTFF", "first showEvent")

        self.window_geometry_runtime.apply_saved_maximized_state_if_needed()
        QTimer.singleShot(350, self.window_geometry_runtime.enable_persistence)

        try:
            effects = self.visual_state.holiday_effects
            if effects is not None:
                effects.sync_geometry()
                QTimer.singleShot(0, effects.sync_geometry)
        except Exception as e:
            log(f"Не удалось синхронизировать визуальные эффекты при показе окна: {e}", "DEBUG")

        self.window_notification_center.schedule_startup_notification_queue(0)

    def _force_style_refresh(self) -> None:
        """Принудительно обновляет стили всех виджетов после показа окна."""
        try:
            for widget in self.findChildren(QWidget):
                widget.style().unpolish(widget)
                widget.style().polish(widget)

            log("🎨 Принудительное обновление стилей выполнено после показа окна", "DEBUG")
        except Exception as e:
            log(f"Ошибка обновления стилей: {e}", "DEBUG")

    def _cleanup_threaded_pages_for_close(self) -> None:
        cleanup_threaded_pages_for_close(self)

    def _cleanup_process_monitor_for_close(self, runtime_feature) -> None:
        cleanup_process_monitor_for_close(runtime_feature)

    def _cleanup_subscription_for_close(self, premium_feature) -> None:
        cleanup_subscription_for_close(premium_feature)

    def _cleanup_theme_for_close(self) -> None:
        cleanup_theme_for_close(self)

    def _cleanup_visual_and_proxy_resources_for_close(self, *, telegram_proxy_feature) -> None:
        cleanup_visual_and_proxy_resources_for_close(
            self,
            telegram_proxy_feature=telegram_proxy_feature,
        )

    def _cleanup_runtime_threads_for_close(self, runtime_feature) -> None:
        cleanup_runtime_threads_for_close(runtime_feature)

    def _cleanup_tray_for_close(self) -> None:
        self.app_runtime.features.tray.cleanup()
