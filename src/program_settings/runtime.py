from __future__ import annotations


def attach_program_settings_runtime(
    owner,
    *,
    app_context,
    apply_snapshot_fn,
    require_attr_name: str | None = None,
) -> None:
    if bool(getattr(owner, "_program_settings_runtime_attached", False)):
        return
    if require_attr_name is not None and getattr(owner, require_attr_name, None) is None:
        return
    service = getattr(app_context, "program_settings_runtime_service", None)
    if service is None:
        return
    owner._program_settings_runtime_attached = True
    owner._program_settings_runtime_unsubscribe = service.subscribe(
        apply_snapshot_fn,
        emit_initial=True,
    )


def refresh_program_settings_snapshot(app_context):
    service = getattr(app_context, "program_settings_runtime_service", None)
    if service is None:
        return None
    return service.refresh()

