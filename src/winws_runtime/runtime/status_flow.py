from __future__ import annotations

import os

from settings.mode import is_preset_launch_method, normalize_launch_method


def transition_pipeline_in_progress(runtime_owner, launch_method: str | None = None) -> bool:
    method = normalize_launch_method(launch_method, default="")

    try:
        if runtime_owner._dpi_start_thread and runtime_owner._dpi_start_thread.isRunning():
            return True
    except RuntimeError:
        runtime_owner._dpi_start_thread = None

    try:
        if runtime_owner._dpi_stop_thread and runtime_owner._dpi_stop_thread.isRunning():
            return True
    except RuntimeError:
        runtime_owner._dpi_stop_thread = None

    try:
        if runtime_owner._presets_switch_thread and runtime_owner._presets_switch_thread.isRunning():
            if not method or is_preset_launch_method(method):
                return True
    except RuntimeError:
        runtime_owner._presets_switch_thread = None

    if int(runtime_owner._restart_request_generation or 0) > int(runtime_owner._restart_completed_generation or 0):
        return True
    if int(runtime_owner._restart_active_start_generation or 0) > 0:
        return True
    if int(runtime_owner._restart_pending_stop_generation or 0) > 0:
        return True
    if int(runtime_owner._presets_switch_requested_generation or 0) > int(runtime_owner._presets_switch_completed_generation or 0):
        if not method or is_preset_launch_method(method):
            return True

    return False


def is_runner_transition_state(state_value: object) -> bool:
    return str(state_value or "").strip().lower() in {"starting", "stopping"}


def runner_transition_in_progress(runtime_owner, *, launch_method: str | None = None) -> bool:
    try:
        from winws_runtime.runners.runner_factory import get_current_runner

        runner = get_current_runner()
        if runner is None:
            return False

        if launch_method:
            try:
                from settings.mode import exe_name_for_launch_method

                expected_name = exe_name_for_launch_method(launch_method).strip().lower()
                runner_name = os.path.basename(str(getattr(runner, "winws_exe", "") or "")).strip().lower()
                if expected_name and runner_name and expected_name != runner_name:
                    return False
            except Exception:
                pass

        snapshot_getter = getattr(runner, "get_runner_state_snapshot", None)
        if not callable(snapshot_getter):
            return False

        snapshot = snapshot_getter()
        return is_runner_transition_state(getattr(snapshot, "state", ""))
    except Exception:
        return False


def is_running(runtime_owner) -> bool:
    try:
        snapshot = runtime_owner._runtime_service().snapshot()
        phase = str(snapshot.phase or "").strip().lower()
        if bool(snapshot.running) and phase == "running":
            return True
    except Exception:
        pass

    try:
        from winws_runtime.runners.runner_factory import get_current_runner

        runner = get_current_runner()
        if runner is not None:
            snapshot_getter = getattr(runner, "get_runner_state_snapshot", None)
            if callable(snapshot_getter):
                snapshot = snapshot_getter()
                state_value = str(getattr(snapshot, "state", "") or "").strip().lower()
                if state_value == "running":
                    return True

            is_runner_running = getattr(runner, "is_running", None)
            if callable(is_runner_running) and bool(is_runner_running()):
                return True
    except Exception:
        pass

    return bool(runtime_owner._runtime_api().is_any_running(silent=True))
