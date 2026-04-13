from __future__ import annotations

from PyQt6.QtCore import QEvent, QTimer
from PyQt6.QtWidgets import QApplication, QWidget

from log.log import global_logger, log

from main.runtime_state import (
    log_startup_metric as emit_startup_metric,
    startup_elapsed_ms,
)
from ui.navigation.schema import iter_page_names_for_cleanup
from ui.page_names import PageName
from ui.window_adapter import sync_titlebar_search_width


class WindowLifecycleMixin:
    def closeEvent(self, event):
        """Обрабатывает событие закрытия окна."""
        close_controller = getattr(self, "window_close_controller", None)
        if close_controller is not None:
            if not close_controller.should_continue_final_close(event):
                return

        self._is_exiting = True

        try:
            if hasattr(global_logger, "set_ui_error_notifier"):
                global_logger.set_ui_error_notifier(None)
        except Exception:
            pass

        try:
            geometry_controller = getattr(self, "window_geometry_controller", None)
            if geometry_controller is not None:
                geometry_controller.persist_now(force=True)
        except Exception as e:
            log(f"Ошибка сохранения геометрии окна при закрытии: {e}", "❌ ERROR")

        self._cleanup_support_managers_for_close()
        self._cleanup_threaded_pages_for_close()
        self._cleanup_visual_and_proxy_resources_for_close()
        self._cleanup_runtime_threads_for_close()

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
        """Сбрасывает drag/resize состояния при скрытии/потере фокуса окна."""
        try:
            if bool(getattr(self, "_is_resizing", False)) and hasattr(self, "_end_resize"):
                self._end_resize()
            else:
                self._is_resizing = False
                self._resize_edge = None
                self._resize_start_pos = None
                self._resize_start_geometry = None
                self.unsetCursor()
        except Exception:
            pass

        try:
            self._is_dragging = False
            self._drag_start_pos = None
            self._drag_window_pos = None
        except Exception:
            pass

        try:
            title_bar = getattr(self, "title_bar", None)
            if title_bar is not None:
                title_bar._is_moving = False
                title_bar._is_system_moving = False
                title_bar._drag_pos = None
                title_bar._window_pos = None
        except Exception:
            pass

    def request_exit(self, stop_dpi: bool) -> None:
        """Единая точка выхода из приложения.

        - stop_dpi=False: закрыть GUI, DPI оставить работать.
        - stop_dpi=True: остановить DPI и выйти.
        """
        self._stop_dpi_on_exit = bool(stop_dpi)
        self._closing_completely = True

        try:
            geometry_controller = getattr(self, "window_geometry_controller", None)
            if geometry_controller is not None:
                geometry_controller.persist_now(force=True)
        except Exception as e:
            log(f"Ошибка сохранения геометрии окна при request_exit: {e}", "DEBUG")

        try:
            if hasattr(self, "tray_manager") and self.tray_manager:
                self.tray_manager.hide_icon()
        except Exception:
            pass

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

    def _iter_loaded_pages_for_close(self):
        loaded_pages = getattr(self, "pages", {}) or {}
        for page_name, page in loaded_pages.items():
            if page is None:
                continue
            yield page_name, page

    def _cleanup_threaded_pages_for_close(self) -> None:
        try:
            loaded_pages = list(self._iter_loaded_pages_for_close())
            page_order = iter_page_names_for_cleanup(
                page_name for page_name, _page in loaded_pages
            )
            pages_by_name = {
                page_name: page
                for page_name, page in loaded_pages
            }

            for page_name in page_order:
                page = pages_by_name.get(page_name)
                if page is None or not hasattr(page, "cleanup"):
                    continue
                try:
                    page.cleanup()
                except Exception as e:
                    log(f"Ошибка при очистке страницы {page_name}: {e}", "DEBUG")
        except Exception as e:
            log(f"Ошибка при очистке страниц: {e}", "DEBUG")

    def _cleanup_support_managers_for_close(self) -> None:
        try:
            process_monitor_manager = getattr(self, "process_monitor_manager", None)
            if process_monitor_manager is not None:
                process_monitor_manager.stop_monitoring()
        except Exception as e:
            log(f"Ошибка остановки process_monitor_manager: {e}", "DEBUG")

        try:
            subscription_manager = getattr(self, "subscription_manager", None)
            if subscription_manager is not None:
                subscription_manager.cleanup()
        except Exception as e:
            log(f"Ошибка очистки subscription_manager: {e}", "DEBUG")

        try:
            dns_ui_manager = getattr(self, "dns_ui_manager", None)
            if dns_ui_manager is not None:
                dns_ui_manager.cleanup()
        except Exception as e:
            log(f"Ошибка при очистке dns_ui_manager: {e}", "DEBUG")

        try:
            theme_manager = getattr(self, "theme_manager", None)
            if theme_manager is not None:
                theme_manager.cleanup()
        except Exception as e:
            log(f"Ошибка при очистке theme_manager: {e}", "DEBUG")

    def _cleanup_visual_and_proxy_resources_for_close(self) -> None:
        try:
            app = QApplication.instance()
            closer = getattr(app, "_zapret_global_combo_popup_closer", None) if app is not None else None
            if closer is not None and hasattr(closer, "cleanup"):
                closer.cleanup()
        except Exception:
            pass

        try:
            from telegram_proxy.ui.page import _get_proxy_manager

            _get_proxy_manager().cleanup()
        except Exception:
            pass

        try:
            effects = getattr(self, "_holiday_effects", None)
            if effects is not None:
                effects.cleanup()
                self._holiday_effects = None
        except Exception as e:
            log(f"Ошибка очистки праздничных эффектов: {e}", "DEBUG")

    def _cleanup_runtime_threads_for_close(self) -> None:
        try:
            launch_controller = getattr(self, "launch_controller", None)
            if launch_controller is not None:
                launch_controller.cleanup_threads()
        except Exception as e:
            log(f"Ошибка очистки DPI controller threads: {e}", "DEBUG")

        try:
            if hasattr(self, "_dpi_start_thread") and self._dpi_start_thread:
                try:
                    if self._dpi_start_thread.isRunning():
                        self._dpi_start_thread.quit()
                        self._dpi_start_thread.wait(1000)
                except RuntimeError:
                    pass

            if hasattr(self, "_dpi_stop_thread") and self._dpi_stop_thread:
                try:
                    if self._dpi_stop_thread.isRunning():
                        self._dpi_stop_thread.quit()
                        self._dpi_stop_thread.wait(1000)
                except RuntimeError:
                    pass
        except Exception as e:
            log(f"Ошибка при очистке потоков: {e}", "❌ ERROR")

    def _cleanup_tray_for_close(self) -> None:
        try:
            tray_manager = getattr(self, "tray_manager", None)
            if tray_manager is not None:
                tray_manager.cleanup()
                self.tray_manager = None
        except Exception as e:
            log(f"Ошибка очистки системного трея: {e}", "DEBUG")
