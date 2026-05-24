from __future__ import annotations

from PyQt6.QtCore import QTimer

from app.state_store import MainWindowStateStore
from presets.ui.control.control_page_runtime_shared import set_toggle_checked


RUNTIME_START_RETRY_MS = 250
RUNTIME_START_MAX_RETRIES = 24


class ControlPageActionMixin:
    """Общие действия для страниц управления."""

    def _start_dpi(self) -> None:
        if not self._runtime_start_available():
            self._queue_runtime_start_retry()
            return
        self._runtime_feature.start()

    def _runtime_start_available(self) -> bool:
        try:
            available = self._runtime_feature.is_available
        except AttributeError:
            return False
        if callable(available):
            try:
                return bool(available())
            except Exception:
                return False
        return False

    def _queue_runtime_start_retry(self) -> None:
        if bool(getattr(self, "_runtime_start_retry_pending", False)):
            return
        self._runtime_start_retry_pending = True
        self._runtime_start_retry_count = 0
        self._show_runtime_preparing_state()
        QTimer.singleShot(RUNTIME_START_RETRY_MS, self._retry_start_dpi_after_runtime_ready)

    def _show_runtime_preparing_state(self) -> None:
        message = "Подготовка запуска..."
        set_loading = getattr(self, "set_loading", None)
        if callable(set_loading):
            set_loading(True, message)
        set_status = getattr(self, "_set_status", None)
        if callable(set_status):
            set_status(message)

    def _retry_start_dpi_after_runtime_ready(self) -> None:
        if bool(getattr(self, "_cleanup_in_progress", False)):
            self._runtime_start_retry_pending = False
            return

        if self._runtime_start_available():
            self._runtime_start_retry_pending = False
            set_loading = getattr(self, "set_loading", None)
            if callable(set_loading):
                set_loading(False, "")
            self._runtime_feature.start()
            return

        retries = int(getattr(self, "_runtime_start_retry_count", 0)) + 1
        self._runtime_start_retry_count = retries
        if retries >= RUNTIME_START_MAX_RETRIES:
            self._runtime_start_retry_pending = False
            set_loading = getattr(self, "set_loading", None)
            if callable(set_loading):
                set_loading(False, "")
            set_status = getattr(self, "_set_status", None)
            if callable(set_status):
                set_status("Запуск ещё не готов. Попробуйте ещё раз через пару секунд.")
            return

        QTimer.singleShot(RUNTIME_START_RETRY_MS, self._retry_start_dpi_after_runtime_ready)

    def _stop_dpi(self) -> None:
        self._runtime_feature.stop()

    def _stop_and_exit(self) -> None:
        from log.log import log
        from PyQt6.QtWidgets import QApplication

        log("Остановка winws и закрытие программы...", "INFO")

        request_exit = getattr(self, "_request_exit_callback", None)
        if callable(request_exit):
            request_exit(stop_dpi=True)
            return

        if self._runtime_feature.stop_and_exit():
            return

        QApplication.quit()

    def _open_connection_test(self) -> None:
        handler = getattr(self, "_open_connection_test_callback", None)
        if callable(handler):
            handler()

    def _open_folder(self) -> None:
        handler = getattr(self, "_open_folder_callback", None)
        if callable(handler):
            handler()

    def _set_toggle_checked(self, toggle, checked: bool) -> None:
        set_toggle_checked(toggle, checked)

    def _set_status(self, msg: str) -> None:
        try:
            status_setter = getattr(self, "_set_status_callback", None)
            if callable(status_setter):
                status_setter(msg)
        except Exception:
            pass


def bind_control_ui_state_store(
    owner,
    store: MainWindowStateStore,
    *,
    callback,
    fields: set[str] | frozenset[str],
) -> None:
    if owner._ui_state_store is store:
        return

    unsubscribe = getattr(owner, "_ui_state_unsubscribe", None)
    if callable(unsubscribe):
        try:
            unsubscribe()
        except Exception:
            pass

    owner._ui_state_store = store
    owner._ui_state_unsubscribe = store.subscribe(
        callback,
        fields=set(fields),
        emit_initial=True,
    )


def cleanup_control_page_subscriptions(owner) -> None:
    unsubscribe = getattr(owner, "_ui_state_unsubscribe", None)
    if callable(unsubscribe):
        try:
            unsubscribe()
        except Exception:
            pass
    owner._ui_state_unsubscribe = None
    owner._ui_state_store = None

    unsubscribe_runtime = getattr(owner, "_program_settings_runtime_unsubscribe", None)
    if callable(unsubscribe_runtime):
        try:
            unsubscribe_runtime()
        except Exception:
            pass
    owner._program_settings_runtime_unsubscribe = None
