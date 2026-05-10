from __future__ import annotations

from ui.state.main_window_state import MainWindowStateStore
from presets.ui.control.control_page_runtime_shared import set_toggle_checked
from winws_runtime.public import start_dpi_async, stop_dpi_async, stop_and_exit_async


def _resolve_control_window(source):
    try:
        window = source.window()
        if window is not None:
            return window
    except Exception:
        pass

    try:
        parent_app = getattr(source, "parent_app", None)
        if parent_app is not None:
            return parent_app
    except Exception:
        pass

    return source


class ControlPageActionMixin:
    """Общие action-wrapper'ы для control-page слоёв."""

    def _start_dpi(self) -> None:
        start_dpi_async(_resolve_control_window(self))

    def _stop_dpi(self) -> None:
        stop_dpi_async(_resolve_control_window(self))

    def _stop_and_exit(self) -> None:
        from log.log import log
        from PyQt6.QtWidgets import QApplication

        window = _resolve_control_window(self)
        log("Остановка winws и закрытие программы...", "INFO")

        if window is not None:
            request_exit = getattr(window, "request_exit", None)
            if callable(request_exit):
                request_exit(stop_dpi=True)
                return

            if stop_and_exit_async(window):
                return

        QApplication.quit()

    def _open_connection_test(self) -> None:
        window = _resolve_control_window(self)
        handler = getattr(window, "open_connection_test", None)
        if callable(handler):
            handler()

    def _open_folder(self) -> None:
        window = _resolve_control_window(self)
        handler = getattr(window, "open_folder", None)
        if callable(handler):
            handler()

    def _set_toggle_checked(self, toggle, checked: bool) -> None:
        set_toggle_checked(toggle, checked)

    def _set_status(self, msg: str) -> None:
        try:
            status_setter = getattr(self, "set_status", None)
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
    if getattr(owner, "_ui_state_store", None) is store:
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
