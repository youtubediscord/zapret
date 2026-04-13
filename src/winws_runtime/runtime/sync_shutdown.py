from __future__ import annotations

from dataclasses import dataclass

from log.log import log


@dataclass(frozen=True, slots=True)
class RuntimeShutdownResult:
    had_running_processes: bool
    stop_ok: bool
    cleanup_ok: bool
    still_running: bool


def _find_runtime_window():
    try:
        from ui.app_window_locator import find_app_window

        return find_app_window()
    except Exception:
        return None


def _resolve_launch_method(window=None) -> str:
    try:
        runtime_service = getattr(window, "launch_runtime_service", None) if window is not None else None
        if runtime_service is not None:
            snapshot = runtime_service.snapshot()
            method = str(getattr(snapshot, "launch_method", "") or "").strip().lower()
            if method:
                return method
    except Exception:
        pass

    try:
        from settings.dpi.strategy_settings import get_strategy_launch_method

        return str(get_strategy_launch_method() or "").strip().lower()
    except Exception:
        return "direct_zapret2"


def _resolve_runtime_api(window, launch_method: str):
    runtime_api = getattr(window, "launch_runtime_api", None) if window is not None else None
    if runtime_api is not None:
        return runtime_api

    try:
        from config.config import get_winws_exe_for_method
        from winws_runtime.runtime.runtime_api import DirectLaunchRuntimeApi

        method = "direct_zapret2" if str(launch_method or "").strip().lower() == "orchestra" else str(launch_method or "").strip().lower()
        expected_exe_path = get_winws_exe_for_method(method)
        return DirectLaunchRuntimeApi(expected_exe_path=expected_exe_path, app_instance=window)
    except Exception:
        return None


def is_any_runtime_running_sync(*, window=None) -> bool:
    target = window or _find_runtime_window()
    launch_method = _resolve_launch_method(target)
    runtime_api = _resolve_runtime_api(target, launch_method)
    if runtime_api is None:
        return False
    try:
        return bool(runtime_api.is_any_running(silent=True))
    except Exception:
        return False


def shutdown_runtime_sync(
    *,
    window=None,
    reason: str = "",
    include_cleanup: bool = True,
    update_runtime_state: bool = True,
) -> RuntimeShutdownResult:
    target = window or _find_runtime_window()
    launch_method = _resolve_launch_method(target)
    runtime_api = _resolve_runtime_api(target, launch_method)

    if runtime_api is None:
        return RuntimeShutdownResult(
            had_running_processes=False,
            stop_ok=False,
            cleanup_ok=False,
            still_running=False,
        )

    had_running_processes = bool(runtime_api.is_any_running(silent=True))
    stop_ok = True
    cleanup_ok = True

    if reason:
        log(f"Sync runtime shutdown requested: {reason}", "INFO")

    try:
        from winws_runtime.runners.runner_factory import get_current_runner, invalidate_strategy_runner

        runner = get_current_runner()
        if runner is not None:
            try:
                stop_ok = bool(runner.stop()) and stop_ok
            except Exception as e:
                stop_ok = False
                log(f"Ошибка остановки текущего runner в sync shutdown: {e}", "DEBUG")
            finally:
                try:
                    invalidate_strategy_runner()
                except Exception:
                    pass
    except Exception as e:
        stop_ok = False
        log(f"Ошибка доступа к runner в sync shutdown: {e}", "DEBUG")

    try:
        orchestra_runner = getattr(target, "orchestra_runner", None) if target is not None else None
        if orchestra_runner is not None:
            try:
                orchestra_runner.stop()
            except Exception as e:
                stop_ok = False
                log(f"Ошибка остановки orchestra_runner в sync shutdown: {e}", "DEBUG")
        orchestra_page = getattr(target, "orchestra_page", None) if target is not None else None
        if orchestra_page is not None and hasattr(orchestra_page, "stop_monitoring"):
            try:
                orchestra_page.stop_monitoring()
            except Exception:
                pass
    except Exception:
        pass

    try:
        stop_ok = bool(runtime_api.stop_all_processes()) and stop_ok
    except Exception as e:
        stop_ok = False
        log(f"Ошибка stop_all_processes в sync shutdown: {e}", "DEBUG")

    if include_cleanup:
        try:
            cleanup_ok = bool(runtime_api.cleanup_windivert_service())
        except Exception as e:
            cleanup_ok = False
            log(f"Ошибка cleanup_windivert_service в sync shutdown: {e}", "DEBUG")

    still_running = bool(runtime_api.is_any_running(silent=True))

    if update_runtime_state:
        try:
            runtime_service = getattr(target, "launch_runtime_service", None) if target is not None else None
            if runtime_service is not None:
                if still_running:
                    runtime_service.bootstrap_probe(True, launch_method=launch_method)
                else:
                    runtime_service.mark_stopped(clear_error=True)
        except Exception as e:
            log(f"Ошибка обновления runtime state в sync shutdown: {e}", "DEBUG")

    return RuntimeShutdownResult(
        had_running_processes=had_running_processes,
        stop_ok=stop_ok,
        cleanup_ok=cleanup_ok,
        still_running=still_running,
    )
