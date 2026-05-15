from __future__ import annotations

from dataclasses import dataclass

from log.log import log


@dataclass(frozen=True, slots=True)
class RuntimeShutdownResult:
    had_running_processes: bool
    stop_ok: bool
    cleanup_ok: bool
    still_running: bool


def _resolve_launch_method(runtime_feature) -> str:
    try:
        runtime_service = runtime_feature.objects.runtime_service
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
        from settings.mode import DEFAULT_LAUNCH_METHOD

        return DEFAULT_LAUNCH_METHOD


def _resolve_runtime_api(runtime_feature, launch_method: str):
    _ = launch_method
    runtime_api = runtime_feature.objects.launch_runtime_api
    if runtime_api is not None:
        return runtime_api

    raise RuntimeError("Runtime API is not initialized")


def shutdown_runtime_sync(
    *,
    runtime_feature,
    reason: str = "",
    include_cleanup: bool = True,
    cleanup_services: bool = True,
    update_runtime_state: bool = True,
) -> RuntimeShutdownResult:
    launch_method = _resolve_launch_method(runtime_feature)
    runtime_api = _resolve_runtime_api(runtime_feature, launch_method)
    runtime_service = runtime_feature.objects.runtime_service

    had_running_processes = bool(runtime_api.has_residual_processes(silent=True))
    stop_ok = True
    cleanup_ok = True

    if reason:
        log(f"Sync runtime shutdown requested: {reason}", "INFO")

    try:
        from winws_runtime.runners.runner_factory import get_current_runner, invalidate_strategy_runner

        runner = get_current_runner()
        if runner is not None:
            try:
                stop_ok = bool(runner.stop(cleanup_services=cleanup_services)) and stop_ok
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
        orchestra_feature = runtime_feature.dependencies.orchestra_feature
        if orchestra_feature is not None:
            try:
                orchestra_feature.stop_runner()
            except Exception as e:
                stop_ok = False
                log(f"Ошибка остановки оркестратора при синхронном завершении: {e}", "DEBUG")
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

    still_running = bool(runtime_api.has_residual_processes(silent=True))

    if update_runtime_state:
        try:
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
