from __future__ import annotations

from PyQt6.QtCore import QEvent, QTimer
from PyQt6.QtWidgets import QApplication, QWidget

from log.log import log

from main.window_lifecycle_cleanup import (
    cleanup_runtime_threads_for_close,
    cleanup_support_managers_for_close,
    cleanup_threaded_pages_for_close,
    cleanup_tray_for_close,
    cleanup_visual_and_proxy_resources_for_close,
    detach_global_error_notifier,
    hide_tray_icon_for_exit,
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
        close_controller = getattr(self, "window_close_controller", None)
        if close_controller is not None:
            if not close_controller.should_continue_final_close(event):
                return

        self._is_exiting = True

        detach_global_error_notifier()
        persist_window_geometry(self, context="закрытии", level="❌ ERROR")

        self._cleanup_before_close()

        if getattr(self, "_stop_dpi_on_exit", False):
            try:
                from winws_runtime.runtime.sync_shutdown import shutdown_runtime_sync

                result = shutdown_runtime_sync(window=self, reason="close_event stop_dpi_on_exit", include_cleanup=True)
                log(
                    f"Процессы winws завершены при закрытии приложения "
                    f"(running={result.had_running_processes}, still_running={result.still_running})",
                    "DEBUG",
                )
            except Exception as e:
                log(f"Ошибка остановки winws при закрытии: {e}", "DEBUG")
        else:
            log("Выход без остановки DPI: winws не трогаем", "DEBUG")

        self._cleanup_tray_for_close()

        super().closeEvent(event)

    def _release_input_interaction_states(self) -> None:
        release_input_interaction_states(self)

    def request_exit(self, stop_dpi: bool) -> None:
        """Единая точка выхода из приложения.

        - stop_dpi=False: закрыть GUI, DPI оставить работать.
        - stop_dpi=True: остановить DPI и выйти.
        """
        self._stop_dpi_on_exit = bool(stop_dpi)
        self._closing_completely = True

        persist_window_geometry(self, context="request_exit", level="DEBUG")
        hide_tray_icon_for_exit(self)

        if stop_dpi:
            log("Запрошен выход: остановить DPI и выйти", "INFO")

            try:
                if hasattr(self, "launch_controller") and self.launch_controller:
                    self.launch_controller.stop_and_exit_async()
                    return
            except Exception as e:
                log(f"stop_and_exit_async не удалось: {e}", "WARNING")

            try:
                from winws_runtime.runtime.sync_shutdown import shutdown_runtime_sync

                shutdown_runtime_sync(window=self, reason="request_exit fallback", include_cleanup=True)
            except Exception as e:
                log(f"Ошибка остановки DPI перед выходом: {e}", "WARNING")

        else:
            log("Запрошен выход: выйти без остановки DPI", "INFO")

        QApplication.closeAllWindows()
        QApplication.processEvents()
        QApplication.quit()

    def ensure_tray_manager(self):
        """Возвращает tray manager, создавая его только как аварийный fallback."""
        tray_manager = getattr(self, "tray_manager", None)
        if tray_manager is not None:
            return tray_manager

        try:
            initialization_manager = getattr(self, "initialization_manager", None)
            if initialization_manager is not None:
                return initialization_manager.ensure_tray_initialized()
        except Exception as e:
            log(f"Не удалось инициализировать системный трей по требованию: {e}", "WARNING")

        return None

    def minimize_to_tray(self) -> bool:
        """Скрывает окно в трей (без выхода из GUI)."""
        try:
            tray_manager = self.ensure_tray_manager()
            if tray_manager is not None:
                return bool(tray_manager.hide_to_tray(show_hint=True))
        except Exception as e:
            log(f"Ошибка сценария сворачивания в трей: {e}", "WARNING")

        return False

    def _cleanup_before_close(self) -> None:
        self._cleanup_support_managers_for_close()
        self._cleanup_threaded_pages_for_close()
        self._cleanup_visual_and_proxy_resources_for_close()
        self._cleanup_runtime_threads_for_close()

    def setWindowTitle(self, title: str):
        """Override to update FluentWindow's built-in titlebar."""
        super().setWindowTitle(title)

    def changeEvent(self, event):
        if event.type() == QEvent.Type.ActivationChange:
            try:
                if not self.isActiveWindow():
                    self._release_input_interaction_states()
            except Exception:
                pass

        if event.type() == QEvent.Type.WindowStateChange:
            geometry_controller = getattr(self, "window_geometry_controller", None)
            if geometry_controller is not None:
                geometry_controller.on_window_state_change()

            try:
                effects = getattr(self, "_holiday_effects", None)
                if effects is not None:
                    QTimer.singleShot(0, effects.sync_geometry)
            except Exception:
                pass

        super().changeEvent(event)

    def hideEvent(self, event):
        try:
            self._release_input_interaction_states()
        except Exception:
            pass
        super().hideEvent(event)

    def moveEvent(self, event):
        super().moveEvent(event)
        geometry_controller = getattr(self, "window_geometry_controller", None)
        if geometry_controller is not None:
            geometry_controller.on_geometry_changed()

    def resizeEvent(self, event):
        """Обновляем геометрию при изменении размера окна."""
        super().resizeEvent(event)
        try:
            sync_titlebar_search_width(self)
        except Exception:
            pass
        geometry_controller = getattr(self, "window_geometry_controller", None)
        if geometry_controller is not None:
            geometry_controller.on_geometry_changed()
        try:
            effects = getattr(self, "_holiday_effects", None)
            if effects is not None:
                effects.sync_geometry()
        except Exception:
            pass

    def showEvent(self, event):
        """Первый показ окна."""
        super().showEvent(event)

        if not self._startup_ttff_logged:
            self._startup_ttff_logged = True
            self._startup_ttff_ms = startup_elapsed_ms()
            emit_startup_metric("TTFF", "first showEvent")

        geometry_controller = getattr(self, "window_geometry_controller", None)
        if geometry_controller is not None:
            geometry_controller.apply_saved_maximized_state_if_needed()
            QTimer.singleShot(350, geometry_controller.enable_persistence)

        try:
            effects = getattr(self, "_holiday_effects", None)
            if effects is not None:
                effects.sync_geometry()
                QTimer.singleShot(0, effects.sync_geometry)
        except Exception:
            pass

        notification_controller = getattr(self, "window_notification_controller", None)
        if notification_controller is not None:
            notification_controller.schedule_startup_notification_queue(0)

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

    def _cleanup_support_managers_for_close(self) -> None:
        cleanup_support_managers_for_close(self)

    def _cleanup_visual_and_proxy_resources_for_close(self) -> None:
        cleanup_visual_and_proxy_resources_for_close(self)

    def _cleanup_runtime_threads_for_close(self) -> None:
        cleanup_runtime_threads_for_close(self)

    def _cleanup_tray_for_close(self) -> None:
        cleanup_tray_for_close(self)
