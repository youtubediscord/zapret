from __future__ import annotations

from PyQt6.QtWidgets import QApplication

from log.log import log


class ApplicationLifecycle:
    """Исполняет выход из приложения; окно только передаёт сюда событие."""

    def __init__(
        self,
        *,
        window_port,
        close_state,
        runtime_feature,
        premium_feature,
        telegram_proxy_feature,
        tray_feature,
    ) -> None:
        self._window_port = window_port
        self._close_state = close_state
        self._runtime_feature = runtime_feature
        self._premium_feature = premium_feature
        self._telegram_proxy_feature = telegram_proxy_feature
        self._tray_feature = tray_feature

    def request_exit(self, *, stop_dpi: bool) -> None:
        if stop_dpi:
            self.exit_stop_dpi()
        else:
            self.exit_keep_dpi()

    def exit_keep_dpi(self) -> None:
        self._prepare_full_exit(stop_dpi=False)
        log("Запрошен выход: выйти без остановки DPI", "INFO")
        self._quit_application()

    def exit_stop_dpi(self) -> None:
        self._prepare_full_exit(stop_dpi=True)
        log("Запрошен выход: остановить DPI и выйти", "INFO")

        if self._start_async_stop_and_exit():
            return

        self._shutdown_dpi_before_exit_sync(reason="exit_stop_dpi")
        self._quit_application()

    def exit_for_windows_session_end(self) -> None:
        close_state = self._close_state
        if bool(getattr(close_state, "windows_session_ending", False)):
            return

        close_state.windows_session_ending = True
        close_state.is_exiting = True
        close_state.closing_completely = True
        close_state.stop_dpi_on_exit = False

        log("Windows завершает сеанс: закрываем GUI без диалога", "INFO")
        self._window_port.persist_geometry(context="windows_session_end", level="DEBUG")
        self._tray_feature.hide_icon_for_exit()
        self._try_fast_dpi_stop_for_windows_session_end()
        self._quit_application()

    def close_to_tray(self) -> bool:
        try:
            return bool(self._tray_feature.hide_to_tray(show_hint=True))
        except Exception as e:
            log(f"Ошибка сценария сворачивания в трей: {e}", "WARNING")

        return False

    def run_final_close_cleanup(self) -> None:
        from main.window_lifecycle_cleanup import detach_global_error_notifier

        detach_global_error_notifier()
        self._window_port.persist_geometry(context="закрытии", level="❌ ERROR")

        self._cleanup_before_close()
        self._finish_dpi_for_final_close()
        self._tray_feature.cleanup()

    def _prepare_full_exit(self, *, stop_dpi: bool) -> None:
        self._close_state.stop_dpi_on_exit = bool(stop_dpi)
        self._close_state.closing_completely = True

        self._window_port.persist_geometry(context="request_exit", level="DEBUG")
        self._tray_feature.hide_icon_for_exit()

    def _start_async_stop_and_exit(self) -> bool:
        try:
            return bool(self._runtime_feature.stop_and_exit())
        except Exception as e:
            log(f"stop_and_exit_async не удалось: {e}", "WARNING")
            return False

    def _shutdown_dpi_before_exit_sync(self, *, reason: str) -> None:
        try:
            self._runtime_feature.shutdown_sync(reason=reason, include_cleanup=True)
        except Exception as e:
            log(f"Ошибка остановки DPI перед выходом: {e}", "WARNING")

    def _try_fast_dpi_stop_for_windows_session_end(self) -> None:
        try:
            self._runtime_feature.shutdown_sync(
                reason="windows_session_end",
                include_cleanup=False,
                cleanup_services=False,
                update_runtime_state=False,
            )
        except Exception as e:
            log(f"Быстрая остановка DPI при завершении Windows не удалась: {e}", "WARNING")

    def _quit_application(self) -> None:
        QApplication.closeAllWindows()
        QApplication.quit()

    def _cleanup_before_close(self) -> None:
        from main.window_lifecycle_cleanup import (
            cleanup_process_monitor_for_close,
            cleanup_runtime_threads_for_close,
            cleanup_subscription_for_close,
        )

        cleanup_process_monitor_for_close(self._runtime_feature)
        cleanup_subscription_for_close(self._premium_feature)
        self._window_port.cleanup_theme()
        self._window_port.cleanup_threaded_pages()
        self._window_port.cleanup_visual_and_proxy_resources(
            telegram_proxy_feature=self._telegram_proxy_feature,
        )
        cleanup_runtime_threads_for_close(self._runtime_feature)

    def _finish_dpi_for_final_close(self) -> None:
        if not self._close_state.stop_dpi_on_exit:
            log("Выход без остановки DPI: winws не трогаем", "DEBUG")
            return

        try:
            result = self._runtime_feature.shutdown_sync(
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


__all__ = ["ApplicationLifecycle"]
