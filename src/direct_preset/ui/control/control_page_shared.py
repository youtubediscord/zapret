from __future__ import annotations

from app_state.main_window_state import MainWindowStateStore
from direct_preset.ui.control.control_page_runtime_shared import set_toggle_checked
from ui.window_action_controller import (
    open_connection_test,
    open_folder,
    start_dpi,
    stop_and_exit,
    stop_dpi,
)


class ControlPageActionMixin:
    """Общие action-wrapper'ы для control-page слоёв."""

    def _start_dpi(self) -> None:
        start_dpi(self)

    def _stop_dpi(self) -> None:
        stop_dpi(self)

    def _stop_and_exit(self) -> None:
        stop_and_exit(self)

    def _open_connection_test(self) -> None:
        open_connection_test(self)

    def _open_folder(self) -> None:
        open_folder(self)

    def _set_toggle_checked(self, toggle, checked: bool) -> None:
        set_toggle_checked(toggle, checked)

    def _set_status(self, msg: str) -> None:
        try:
            status_setter = getattr(self, "set_status", None)
            if callable(status_setter):
                status_setter(msg)
        except Exception:
            pass


def attach_program_settings_runtime(
    owner,
    *,
    require_app_context_fn,
    apply_snapshot_fn,
    require_attr_name: str | None = None,
) -> None:
    if bool(getattr(owner, "_program_settings_runtime_attached", False)):
        return
    if require_attr_name is not None and getattr(owner, require_attr_name, None) is None:
        return
    owner._program_settings_runtime_attached = True
    owner._program_settings_runtime_unsubscribe = (
        require_app_context_fn().program_settings_runtime_service.subscribe(
            apply_snapshot_fn,
            emit_initial=True,
        )
    )


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
