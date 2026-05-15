from __future__ import annotations

from app.state_store import MainWindowStateStore
from presets.ui.control.control_page_runtime_shared import set_toggle_checked


class ControlPageActionMixin:
    """Общие действия для страниц управления."""

    def _start_dpi(self) -> None:
        self._runtime_feature.start()

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
