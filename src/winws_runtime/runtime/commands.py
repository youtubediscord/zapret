from __future__ import annotations

from typing import Any


def get_current_strategy_runner():
    from winws_runtime.runners.runner_factory import get_current_runner

    return get_current_runner()


def is_dpi_running(*, runtime_feature: Any) -> bool:
    runtime_owner = runtime_feature.objects.launch_runtime
    if runtime_owner is None:
        return False
    try:
        return bool(runtime_owner.is_running())
    except Exception:
        return False


def init_launch_runtime_api(*, runtime_feature: Any) -> None:
    from winws_runtime.runtime.startup import init_launch_runtime_api as _init_launch_runtime_api

    return _init_launch_runtime_api(runtime_feature=runtime_feature)


def init_launch_runtime(*, runtime_feature: Any, runtime_api: Any, notify) -> None:
    from winws_runtime.runtime.startup import init_launch_runtime as _init_launch_runtime

    return _init_launch_runtime(
        runtime_feature=runtime_feature,
        runtime_api=runtime_api,
        notify=notify,
    )


def init_process_monitor(
    *,
    process_monitor_manager: Any = None,
    runtime_api: Any = None,
    runtime_service: Any = None,
) -> None:
    from winws_runtime.runtime.startup import init_process_monitor as _init_process_monitor

    _init_process_monitor(
        process_monitor_manager=process_monitor_manager,
        runtime_api=runtime_api,
        runtime_service=runtime_service,
    )


def init_core_startup() -> None:
    from winws_runtime.runtime.startup import init_core_startup as _init_core_startup

    _init_core_startup()


def start_dpi_async(
    *,
    runtime_feature: Any,
    selected_mode: Any = None,
    launch_method: Any = None,
    skip_conflict_prompt: bool = False,
    startup_autostart: bool = False,
) -> bool:
    runtime_owner = runtime_feature.objects.launch_runtime
    if runtime_owner is None:
        return False
    runtime_owner.start_dpi_async(
        selected_mode=selected_mode,
        launch_method=launch_method,
        _skip_conflict_prompt=bool(skip_conflict_prompt),
        _startup_autostart=bool(startup_autostart),
    )
    return True


def stop_dpi_async(
    *,
    runtime_feature: Any,
    force_cleanup: bool = False,
    cleanup_services: bool = False,
) -> bool:
    runtime_owner = runtime_feature.objects.launch_runtime
    if runtime_owner is None:
        return False
    runtime_owner.stop_dpi_async(
        force_cleanup=bool(force_cleanup),
        cleanup_services=bool(cleanup_services),
    )
    return True


def restart_dpi_async(*, runtime_feature: Any, force_full_stop: bool = False) -> bool:
    runtime_owner = runtime_feature.objects.launch_runtime
    if runtime_owner is None:
        return False
    runtime_owner.restart_dpi_async(force_full_stop=bool(force_full_stop))
    return True


def switch_presets_async(*, runtime_feature: Any, method: str | None = None) -> bool:
    runtime_owner = runtime_feature.objects.launch_runtime
    if runtime_owner is None:
        return False
    runtime_owner.switch_presets_async(method)
    return True


def request_selected_source_preset_apply(
    *,
    runtime_feature: Any,
    launch_method: str,
    reason: str,
    preset_file_name: str = "",
) -> bool:
    from winws_runtime.flow.preset_switch_policy import request_selected_source_preset_apply

    return bool(
        request_selected_source_preset_apply(
            runtime_feature=runtime_feature,
            launch_method=launch_method,
            reason=reason,
            preset_file_name=preset_file_name,
        )
    )


def request_preset_runtime_content_apply(
    *,
    runtime_feature: Any,
    launch_method: str,
    reason: str,
    profile_key: str | None = None,
) -> bool:
    from winws_runtime.flow.apply_policy import request_preset_runtime_content_apply

    return bool(
        request_preset_runtime_content_apply(
            runtime_feature=runtime_feature,
            launch_method=launch_method,
            reason=reason,
            profile_key=profile_key,
        )
    )


def stop_and_exit_async(*, runtime_feature: Any) -> bool:
    runtime_owner = runtime_feature.objects.launch_runtime
    if runtime_owner is None:
        return False
    runtime_owner.stop_and_exit_async()
    return True


def cleanup_launch_threads(*, runtime_feature: Any) -> bool:
    runtime_owner = runtime_feature.objects.launch_runtime
    if runtime_owner is None:
        return False
    runtime_owner.cleanup_threads()
    return True


def create_preset_runtime_coordinator(
    qt_parent: Any,
    *,
    runtime_feature,
    ui_state_store,
    get_launch_method,
    get_active_preset_path,
    refresh_after_switch,
):
    from core.runtime.preset_runtime_coordinator import PresetRuntimeCoordinator

    return PresetRuntimeCoordinator(
        qt_parent,
        presets_feature=runtime_feature.dependencies.presets_feature,
        ui_state_store=ui_state_store,
        get_launch_method=get_launch_method,
        get_active_preset_path=get_active_preset_path,
        refresh_after_switch=refresh_after_switch,
        request_runtime_content_apply=lambda launch_method, reason, preset_file_name: request_selected_source_preset_apply(
            runtime_feature=runtime_feature,
            launch_method=launch_method,
            reason=reason,
            preset_file_name=preset_file_name,
        ),
    )


def handle_launch_method_changed(
    method: str,
    *,
    runtime_feature: Any,
    ui_state: Any,
    set_status: Any = None,
):
    from winws_runtime.runtime.method_switch_flow import handle_launch_method_changed_runtime

    return handle_launch_method_changed_runtime(
        method,
        runtime_feature=runtime_feature,
        ui_state=ui_state,
        set_status=set_status,
    )


def start_dpi_autostart(
    startup_state: Any,
    *,
    runtime_feature: Any,
    ui_state: Any,
    launch_method: str | None = None,
) -> bool:
    from winws_runtime.runtime.autostart import start_dpi_autostart as _start_dpi_autostart

    _start_dpi_autostart(
        startup_state,
        runtime_feature=runtime_feature,
        ui_state=ui_state,
        launch_method=launch_method,
    )
    return True


def shutdown_runtime_sync(
    *,
    runtime_feature: Any = None,
    reason: str = "",
    include_cleanup: bool = True,
    cleanup_services: bool = True,
    update_runtime_state: bool = True,
):
    from winws_runtime.runtime.sync_shutdown import shutdown_runtime_sync as _shutdown_runtime_sync
    if runtime_feature is None:
        raise RuntimeError("RuntimeFeature is required for sync shutdown")

    return _shutdown_runtime_sync(
        runtime_feature=runtime_feature,
        reason=reason,
        include_cleanup=bool(include_cleanup),
        cleanup_services=bool(cleanup_services),
        update_runtime_state=bool(update_runtime_state),
    )


def resume_start_after_conflict_resolution(
    request_id: int,
    *,
    runtime_feature: Any,
    close_conflicts: bool,
) -> bool:
    runtime_owner = runtime_feature.objects.launch_runtime
    if runtime_owner is None:
        return False

    from winws_runtime.runtime.conflict_flow import resume_start_after_conflict_resolution

    resume_start_after_conflict_resolution(
        runtime_owner,
        int(request_id or 0),
        close_conflicts=bool(close_conflicts),
    )
    return True


def cancel_start_after_conflict_prompt(request_id: int, *, runtime_feature: Any) -> bool:
    runtime_owner = runtime_feature.objects.launch_runtime
    if runtime_owner is None:
        return False

    from winws_runtime.runtime.conflict_flow import cancel_start_after_conflict_prompt

    cancel_start_after_conflict_prompt(runtime_owner, int(request_id or 0))
    return True


def execute_windivert_autofix(action: str) -> tuple[bool, str]:
    from winws_runtime.health.process_health_check import execute_windivert_auto_fix

    ok, message = execute_windivert_auto_fix(str(action or ""))
    return bool(ok), str(message or "")
