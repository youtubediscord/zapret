from __future__ import annotations

from PyQt6.QtCore import QEvent, QTimer
from PyQt6.QtWidgets import QWidget

from log.log import log

from main.window_lifecycle_cleanup import (
    release_input_interaction_states,
)
from main.window_native_commands import (
    handle_minimize_request,
    handle_native_minimize_command,
)
from main.runtime_state import (
    log_startup_metric as emit_startup_metric,
    startup_elapsed_ms,
)
from ui.window_adapter import sync_titlebar_search_width


class WindowLifecycleMixin:
    def _get_window_geometry_runtime(self):
        return getattr(self, "window_geometry_runtime", None)

    def _get_visual_state(self):
        return getattr(self, "visual_state", None)

    def _get_startup_state(self):
        return getattr(self, "startup_state", None)

    def _get_window_notification_center(self):
        return getattr(self, "window_notification_center", None)

    def _require_application_lifecycle(self):
        lifecycle = getattr(self, "application_lifecycle", None)
        if lifecycle is None:
            raise RuntimeError("ApplicationLifecycle ещё не подключён к окну")
        return lifecycle

    def closeEvent(self, event):
        """Обрабатывает событие закрытия окна."""
        close_flow = getattr(self, "window_close_flow", None)
        if close_flow is not None and not close_flow.should_continue_final_close(event):
            return

        close_state = getattr(self, "close_state", None)
        if close_state is not None:
            close_state.is_exiting = True
        lifecycle = getattr(self, "application_lifecycle", None)
        if lifecycle is not None:
            lifecycle.run_final_close_cleanup()

        super().closeEvent(event)

    def release_input_interaction_states(self) -> None:
        release_input_interaction_states(self)

    def request_exit(self, stop_dpi: bool) -> None:
        """Общий вход для tray и adapter-слоя."""
        self._require_application_lifecycle().request_exit(stop_dpi=bool(stop_dpi))

    def exit_keep_dpi(self) -> None:
        """Полный выход из GUI без остановки DPI."""
        self._require_application_lifecycle().exit_keep_dpi()

    def exit_stop_dpi(self) -> None:
        """Полный выход из GUI с остановкой DPI."""
        self._require_application_lifecycle().exit_stop_dpi()

    def exit_for_windows_session_end(self) -> None:
        """Быстрый выход, когда Windows завершает сеанс пользователя."""
        self._require_application_lifecycle().exit_for_windows_session_end()

    def close_to_tray(self) -> bool:
        """Скрывает окно в трей (без выхода из GUI)."""
        return self._require_application_lifecycle().close_to_tray()

    def nativeEvent(self, event_type, message):  # noqa: N802 (Qt override)
        if handle_native_minimize_command(self, message):
            return (True, 0)
        return super().nativeEvent(event_type, message)

    def showMinimized(self) -> None:  # noqa: N802 (Qt override)
        if handle_minimize_request(self):
            return
        super().showMinimized()

    def changeEvent(self, event):
        event_type = event.type()

        if event_type == QEvent.Type.ActivationChange:
            try:
                if not self.isActiveWindow():
                    self.release_input_interaction_states()
            except Exception as e:
                log(f"Не удалось сбросить состояние ввода при смене активности окна: {e}", "DEBUG")

        if event_type == QEvent.Type.WindowStateChange:
            geometry_runtime = self._get_window_geometry_runtime()
            if geometry_runtime is not None:
                geometry_runtime.on_window_state_change()

            try:
                visual_state = self._get_visual_state()
                effects = None if visual_state is None else visual_state.holiday_effects
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
        geometry_runtime = self._get_window_geometry_runtime()
        if geometry_runtime is not None:
            geometry_runtime.on_geometry_changed()

    def resizeEvent(self, event):
        """Обновляем геометрию при изменении размера окна."""
        super().resizeEvent(event)
        try:
            sync_titlebar_search_width(self)
        except Exception as e:
            log(f"Не удалось синхронизировать ширину поиска в заголовке: {e}", "DEBUG")
        geometry_runtime = self._get_window_geometry_runtime()
        if geometry_runtime is not None:
            geometry_runtime.on_geometry_changed()
        try:
            visual_state = self._get_visual_state()
            effects = None if visual_state is None else visual_state.holiday_effects
            if effects is not None:
                effects.sync_geometry()
        except Exception as e:
            log(f"Не удалось синхронизировать визуальные эффекты при изменении размера окна: {e}", "DEBUG")

    def showEvent(self, event):
        """Первый показ окна."""
        super().showEvent(event)

        startup_state = self._get_startup_state()
        if startup_state is not None and not startup_state.ttff_logged:
            startup_state.ttff_logged = True
            startup_state.ttff_ms = startup_elapsed_ms()
            emit_startup_metric("StartupTTFF", "first showEvent")

        geometry_runtime = self._get_window_geometry_runtime()
        if geometry_runtime is not None:
            geometry_runtime.apply_saved_maximized_state_if_needed()
            QTimer.singleShot(350, geometry_runtime.enable_persistence)

        try:
            visual_state = self._get_visual_state()
            effects = None if visual_state is None else visual_state.holiday_effects
            if effects is not None:
                effects.sync_geometry()
                QTimer.singleShot(0, effects.sync_geometry)
        except Exception as e:
            log(f"Не удалось синхронизировать визуальные эффекты при показе окна: {e}", "DEBUG")

        notification_center = self._get_window_notification_center()
        if notification_center is not None:
            notification_center.schedule_startup_notification_queue(0)

    def _force_style_refresh(self) -> None:
        """Принудительно обновляет стили всех виджетов после показа окна."""
        try:
            for widget in self.findChildren(QWidget):
                widget.style().unpolish(widget)
                widget.style().polish(widget)

            log("🎨 Принудительное обновление стилей выполнено после показа окна", "DEBUG")
        except Exception as e:
            log(f"Ошибка обновления стилей: {e}", "DEBUG")
