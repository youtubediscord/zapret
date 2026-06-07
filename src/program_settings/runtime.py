from __future__ import annotations


def attach_program_settings_runtime(
    owner,
    *,
    runtime_service,
    apply_snapshot_fn,
) -> None:
    if bool(getattr(owner, "_program_settings_runtime_attached", False)):
        return
    owner._program_settings_runtime_attached = True
    owner._program_settings_runtime_unsubscribe = runtime_service.subscribe(
        apply_snapshot_fn,
        emit_initial=True,
    )


def refresh_program_settings_snapshot(runtime_service):
    return runtime_service.refresh()


def load_program_settings_snapshot(runtime_service):
    return runtime_service.refresh_fast()


def publish_program_settings_snapshot(runtime_service, snapshot) -> bool:
    return bool(runtime_service.publish_snapshot(snapshot))


def peek_hide_to_tray_on_minimize_close(runtime_service, *, default: bool = False) -> bool:
    return bool(runtime_service.peek_hide_to_tray_on_minimize_close(default=bool(default)))


def remember_hide_to_tray_on_minimize_close(runtime_service, enabled: bool) -> bool:
    return bool(runtime_service.remember_hide_to_tray_on_minimize_close(bool(enabled)))
