from __future__ import annotations

from typing import Any


def resolve_launch_controller(host: Any):
    """Возвращает launch controller для внешних слоёв.

    UI и main не должны напрямую знать, где именно окно хранит controller.
    """
    if host is None:
        return None
    return getattr(host, "launch_controller", None)


def is_runtime_available(host: Any) -> bool:
    return resolve_launch_controller(host) is not None


def is_dpi_running(host: Any) -> bool:
    controller = resolve_launch_controller(host)
    if controller is None:
        return False
    try:
        return bool(controller.is_running())
    except Exception:
        return False


def init_launch_runtime_api(host: Any) -> None:
    from winws_runtime.runtime.startup import init_launch_runtime_api as _init_launch_runtime_api

    _init_launch_runtime_api(host)


def init_launch_controller(host: Any) -> None:
    from winws_runtime.runtime.startup import init_launch_controller as _init_launch_controller

    _init_launch_controller(host)


def init_process_monitor(host: Any) -> None:
    from winws_runtime.runtime.startup import init_process_monitor as _init_process_monitor

    _init_process_monitor(host)


def init_core_startup(host: Any) -> None:
    from winws_runtime.runtime.startup import init_core_startup as _init_core_startup

    _init_core_startup(host)


def start_dpi_async(
    host: Any,
    selected_mode: Any = None,
    launch_method: Any = None,
    *,
    skip_conflict_prompt: bool = False,
    startup_autostart: bool = False,
) -> bool:
    controller = resolve_launch_controller(host)
    if controller is None:
        return False
    controller.start_dpi_async(
        selected_mode=selected_mode,
        launch_method=launch_method,
        _skip_conflict_prompt=bool(skip_conflict_prompt),
        _startup_autostart=bool(startup_autostart),
    )
    return True


def stop_dpi_async(
    host: Any,
    *,
    force_cleanup: bool = False,
    cleanup_services: bool = False,
) -> bool:
    controller = resolve_launch_controller(host)
    if controller is None:
        return False
    controller.stop_dpi_async(
        force_cleanup=bool(force_cleanup),
        cleanup_services=bool(cleanup_services),
    )
    return True


def restart_dpi_async(host: Any, *, force_full_stop: bool = False) -> bool:
    controller = resolve_launch_controller(host)
    if controller is None:
        return False
    controller.restart_dpi_async(force_full_stop=bool(force_full_stop))
    return True


def switch_presets_async(host: Any, method: str | None = None) -> bool:
    controller = resolve_launch_controller(host)
    if controller is None:
        return False
    controller.switch_presets_async(method)
    return True


def request_selected_source_preset_apply(
    host: Any,
    *,
    launch_method: str,
    reason: str,
    preset_file_name: str = "",
) -> bool:
    from winws_runtime.flow.preset_switch_policy import request_selected_source_preset_apply

    return bool(
        request_selected_source_preset_apply(
            host,
            launch_method=launch_method,
            reason=reason,
            preset_file_name=preset_file_name,
        )
    )


def request_preset_runtime_content_apply(
    host: Any,
    *,
    launch_method: str,
    reason: str,
    profile_key: str | None = None,
) -> bool:
    from winws_runtime.flow.apply_policy import request_preset_runtime_content_apply

    return bool(
        request_preset_runtime_content_apply(
            host,
            launch_method=launch_method,
            reason=reason,
            profile_key=profile_key,
        )
    )


def stop_and_exit_async(host: Any) -> bool:
    controller = resolve_launch_controller(host)
    if controller is None:
        return False
    try:
        host._closing_completely = True
    except Exception:
        pass
    controller.stop_and_exit_async()
    return True


def cleanup_launch_threads(host: Any) -> bool:
    controller = resolve_launch_controller(host)
    if controller is None:
        return False
    controller.cleanup_threads()
    return True


def create_preset_runtime_coordinator(
    host: Any,
    *,
    app_context,
    ui_state_store,
    get_launch_method,
    get_active_preset_path,
    refresh_after_switch,
):
    from core.runtime.preset_runtime_coordinator import PresetRuntimeCoordinator

    return PresetRuntimeCoordinator(
        host,
        app_context=app_context,
        ui_state_store=ui_state_store,
        get_launch_method=get_launch_method,
        get_active_preset_path=get_active_preset_path,
        is_dpi_running=lambda: is_dpi_running(host),
        restart_dpi_async=lambda: restart_dpi_async(host),
        switch_presets_async=lambda method: switch_presets_async(host, method),
        refresh_after_switch=refresh_after_switch,
        request_runtime_content_apply=lambda launch_method, reason, preset_file_name: request_selected_source_preset_apply(
            host,
            launch_method=launch_method,
            reason=reason,
            preset_file_name=preset_file_name,
        ),
    )


def handle_launch_method_changed(host: Any, method: str):
    from winws_runtime.runtime.method_switch_flow import handle_launch_method_changed_runtime

    return handle_launch_method_changed_runtime(host, method)


def start_dpi_autostart(host: Any, launch_method: str | None = None) -> bool:
    from winws_runtime.runtime.autostart import start_dpi_autostart as _start_dpi_autostart

    _start_dpi_autostart(host, launch_method=launch_method)
    return True


def shutdown_runtime_sync(
    *,
    host: Any = None,
    reason: str = "",
    include_cleanup: bool = True,
    cleanup_services: bool = True,
    update_runtime_state: bool = True,
):
    from winws_runtime.runtime.sync_shutdown import shutdown_runtime_sync as _shutdown_runtime_sync

    return _shutdown_runtime_sync(
        window=host,
        reason=reason,
        include_cleanup=bool(include_cleanup),
        cleanup_services=bool(cleanup_services),
        update_runtime_state=bool(update_runtime_state),
    )


def is_any_runtime_running_sync(*, host: Any = None) -> bool:
    from winws_runtime.runtime.sync_shutdown import is_any_runtime_running_sync as _is_any_runtime_running_sync

    return bool(_is_any_runtime_running_sync(window=host))


def resume_start_after_conflict_resolution(
    host: Any,
    request_id: int,
    *,
    close_conflicts: bool,
) -> bool:
    controller = resolve_launch_controller(host)
    if controller is None:
        return False

    from winws_runtime.runtime.conflict_flow import resume_start_after_conflict_resolution

    resume_start_after_conflict_resolution(
        controller,
        int(request_id or 0),
        close_conflicts=bool(close_conflicts),
    )
    return True


def cancel_start_after_conflict_prompt(host: Any, request_id: int) -> bool:
    controller = resolve_launch_controller(host)
    if controller is None:
        return False

    from winws_runtime.runtime.conflict_flow import cancel_start_after_conflict_prompt

    cancel_start_after_conflict_prompt(controller, int(request_id or 0))
    return True
