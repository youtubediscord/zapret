from __future__ import annotations

import os
from dataclasses import dataclass

from PyQt6.QtCore import QTimer

from log.log import log
from settings.mode import (
    ALL_LAUNCH_METHODS,
    ZAPRET1_MODE,
    ZAPRET2_MODE,
    exe_path_for_launch_method,
    is_orchestra_launch_method,
    is_preset_launch_method,
    is_zapret2_launch_method,
    normalize_launch_method,
)



@dataclass(frozen=True, slots=True)
class MethodSwitchRuntimePlan:
    method: str
    expected_exe_path: str
    expected_process_name: str
    autostart_enabled: bool
    can_autostart: bool
    dispatch_action: str
    requires_cleanup_stop: bool


def handle_launch_method_changed_runtime(
    method: str,
    *,
    runtime_feature,
    ui_state,
    set_status=None,
) -> MethodSwitchRuntimePlan:
    log(f"Метод запуска изменён на: {method}", "INFO")

    try:
        launch_runtime = runtime_feature.objects.launch_runtime
        if launch_runtime is not None:
            launch_runtime._dpi_start_verify_generation += 1
            launch_runtime._pending_launch_warnings = []
    except Exception:
        pass

    try:
        ui_state.bump_mode_revision()
    except Exception:
        pass

    plan = build_method_switch_runtime_plan(
        method,
        runtime_feature=runtime_feature,
        set_status=set_status,
    )
    apply_method_switch_runtime_plan(runtime_feature, plan)

    try:
        ui_state.bump_mode_revision()
    except Exception:
        pass

    return plan


def build_method_switch_runtime_plan(
    method: str,
    *,
    runtime_feature,
    set_status=None,
) -> MethodSwitchRuntimePlan:
    from program_settings.public import is_auto_dpi_enabled

    normalized_method = normalize_launch_method(method, default="")
    expected_exe_path = ""
    expected_process_name = ""
    if normalized_method in ALL_LAUNCH_METHODS:
        expected_exe_path = str(exe_path_for_launch_method(normalized_method) or "").strip()
        expected_process_name = os.path.basename(expected_exe_path).strip().lower()

    residual_runtime_detected = False
    try:
        runtime_api = runtime_feature.objects.launch_runtime_api
        if runtime_api is not None:
            residual_runtime_detected = bool(runtime_api.has_residual_processes(silent=True))
    except Exception:
        residual_runtime_detected = False

    active_runtime_detected = bool(residual_runtime_detected)
    try:
        snapshot = runtime_feature.objects.snapshot()
        phase = str(getattr(snapshot, "phase", "") or "").strip().lower()
        active_runtime_detected = bool(
            active_runtime_detected
            or getattr(snapshot, "running", False)
            or phase in {"starting", "running", "stopping"}
        )
    except Exception:
        pass

    try:
        launch_runtime = runtime_feature.objects.launch_runtime
        if launch_runtime is not None and launch_runtime.transition_pipeline_in_progress():
            active_runtime_detected = True
    except Exception:
        pass

    can_autostart = _can_autostart_for_method(
        normalized_method,
        runtime_feature=runtime_feature,
        set_status=set_status,
    )
    autostart_enabled = bool(is_auto_dpi_enabled())

    if active_runtime_detected:
        dispatch_action = "restart" if (autostart_enabled and can_autostart) else "stop"
    elif autostart_enabled and can_autostart:
        dispatch_action = "restart"
    else:
        dispatch_action = "none"

    requires_cleanup_stop = bool(
        active_runtime_detected and dispatch_action in {"restart", "stop"}
    )

    return MethodSwitchRuntimePlan(
        method=normalized_method,
        expected_exe_path=expected_exe_path,
        expected_process_name=expected_process_name,
        autostart_enabled=autostart_enabled,
        can_autostart=can_autostart,
        dispatch_action=dispatch_action,
        requires_cleanup_stop=requires_cleanup_stop,
    )


def apply_method_switch_runtime_plan(runtime_feature, plan: MethodSwitchRuntimePlan) -> None:
    runtime_api = runtime_feature.objects.launch_runtime_api
    if runtime_api is not None:
        try:
            runtime_api.set_expected_exe_path(plan.expected_exe_path)
        except Exception:
            pass

    runtime_service = runtime_feature.objects.runtime_service

    try:
        if plan.dispatch_action == "restart":
            if plan.requires_cleanup_stop:
                runtime_service.begin_stop()
            else:
                runtime_service.mark_autostart_pending(
                    launch_method=plan.method,
                    expected_process=plan.expected_process_name,
                )
        elif plan.dispatch_action == "stop":
            runtime_service.begin_stop()
        else:
            runtime_service.mark_stopped(clear_error=True)
            runtime_service.bootstrap_probe(
                False,
                launch_method=plan.method,
                expected_process="",
            )
    except Exception:
        pass

    try:
        if plan.dispatch_action in {"restart", "stop"}:
            runtime_service.set_busy(True, "Переключаем режим запуска...")
        else:
            runtime_service.set_busy(False)
    except Exception:
        pass

    launch_runtime = runtime_feature.objects.launch_runtime
    if launch_runtime is None:
        return

    if plan.dispatch_action == "restart":
        log(
            f"Смена метода '{plan.method}' передана в единый restart pipeline",
            "INFO",
        )
        QTimer.singleShot(
            0,
            lambda runtime=launch_runtime, force_stop=plan.requires_cleanup_stop: runtime.restart_dpi_async(
                force_full_stop=force_stop,
            ),
        )
        return

    if plan.dispatch_action == "stop":
        log(
            f"Смена метода '{plan.method}' требует остановки активного DPI через общий pipeline",
            "INFO",
        )
        QTimer.singleShot(
            0,
            lambda runtime=launch_runtime, force_cleanup=plan.requires_cleanup_stop: runtime.stop_dpi_async(
                force_cleanup=force_cleanup,
            ),
        )


def _set_status(set_status, text: str) -> None:
    if callable(set_status):
        set_status(text)


def _can_autostart_for_method(method: str, *, runtime_feature, set_status=None) -> bool:
    normalized_method = normalize_launch_method(method, default="")
    if is_orchestra_launch_method(normalized_method):
        return True
    if not is_preset_launch_method(normalized_method):
        try:
            _set_status(set_status, "Ошибка: выбран удалённый или неподдерживаемый режим запуска")
        except Exception:
            pass
        log(f"Удалённый или неподдерживаемый режим запуска: {normalized_method}", "ERROR")
        return False

    try:
        runtime_feature.dependencies.presets_feature.get_launch_snapshot(
            normalized_method,
            require_filters=False,
        )
        return True
    except Exception as e:
        if is_zapret2_launch_method(normalized_method):
            log(f"{ZAPRET2_MODE}: выбранный source-пресет не подготовлен", "ERROR")
            try:
                _set_status(set_status, "Ошибка: отсутствует Default v1 (game filter).txt (built-in пресет)")
            except Exception:
                pass
            return False

        log(f"{ZAPRET1_MODE}: ошибка инициализации пресета: {e}", "WARNING")
        return False


__all__ = [
    "MethodSwitchRuntimePlan",
    "apply_method_switch_runtime_plan",
    "build_method_switch_runtime_plan",
    "handle_launch_method_changed_runtime",
]
