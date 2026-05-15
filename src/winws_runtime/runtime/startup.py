from __future__ import annotations

import os
import time

from log.log import log
from settings.mode import (
    exe_name_for_launch_method,
    exe_path_for_launch_method,
    is_orchestra_launch_method,
    normalize_launch_method,
)
from winws_runtime.runtime.status_feedback import runtime_status_callback


def init_launch_runtime_api(*, runtime_feature):
    from settings.dpi.strategy_settings import get_strategy_launch_method
    from winws_runtime.runtime.runtime_api import PresetLaunchRuntimeApi

    launch_method = get_strategy_launch_method()
    winws_exe = exe_path_for_launch_method(launch_method)
    exe_name = exe_name_for_launch_method(launch_method)
    log(f"Используется {exe_name} для режима {launch_method}", "INFO")

    runtime_api = PresetLaunchRuntimeApi(
        expected_exe_path=winws_exe,
        status_callback=runtime_status_callback(runtime_feature),
    )
    log("Launch runtime API инициализирован", "INFO")
    return runtime_api


def init_launch_runtime(*, runtime_feature, runtime_api, notify) -> None:
    from winws_runtime.runtime.launch_runtime import PresetLaunchRuntime

    launch_runtime = PresetLaunchRuntime(
        runtime_feature=runtime_feature,
        runtime_api=runtime_api,
        notify=notify,
    )
    log("Launch runtime инициализирован", "INFO")
    return launch_runtime


def init_process_monitor(*, process_monitor_manager=None, runtime_api=None, runtime_service=None) -> None:
    started_at = time.perf_counter()

    manager = process_monitor_manager
    if manager is None:
        raise RuntimeError("Process monitor manager is required")
    manager.initialize_process_monitor()

    try:
        from settings.dpi.strategy_settings import get_strategy_launch_method

        launch_method = normalize_launch_method(get_strategy_launch_method())
        expected_process = ""
        target_exe = exe_path_for_launch_method(launch_method)
        if not is_orchestra_launch_method(launch_method):
            expected_process = os.path.basename(target_exe).strip().lower()

        if runtime_api is None:
            raise RuntimeError("Runtime API is required for process monitor")
        if runtime_service is None:
            raise RuntimeError("Runtime service is required for process monitor")
        runtime_api.set_expected_exe_path(target_exe)
        runtime_service.bootstrap_probe(
            runtime_api.is_expected_running(silent=True),
            launch_method=launch_method,
            expected_process=expected_process,
        )
    except Exception as exc:
        log(f"Ошибка начальной проверки process monitor: {exc}", "DEBUG")

    log(f"✅ Process monitor: {(time.perf_counter() - started_at) * 1000:.0f}ms", "DEBUG")


def init_core_startup() -> None:
    started_at = time.perf_counter()

    from lists.file_manager import ensure_required_files

    ensure_required_files()

    log(f"✅ Core startup: {(time.perf_counter() - started_at) * 1000:.0f}ms", "DEBUG")
