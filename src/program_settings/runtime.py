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
