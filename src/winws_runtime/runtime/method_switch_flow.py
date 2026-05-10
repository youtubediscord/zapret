from __future__ import annotations

import os
from dataclasses import dataclass

from PyQt6.QtCore import QTimer

from log.log import log
from presets.public import get_launch_snapshot
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


def handle_launch_method_changed_runtime(window, method: str) -> MethodSwitchRuntimePlan:
    log(f"Метод запуска изменён на: {method}", "INFO")

    try:
        controller = getattr(window, "launch_controller", None)
        if controller is not None:
            controller._dpi_start_verify_generation += 1
            controller._pending_launch_warnings = []
    except Exception:
        pass

    try:
        store = getattr(window, "ui_state_store", None)
        if store is not None:
            store.bump_mode_revision()
    except Exception:
        pass

    plan = build_method_switch_runtime_plan(window, method)
    apply_method_switch_runtime_plan(window, plan)

    try:
        window._preset_runtime_coordinator.setup_active_preset_file_watcher()
    except Exception:
        pass

    try:
        store = getattr(window, "ui_state_store", None)
        if store is not None:
            store.bump_mode_revision()
    except Exception:
        pass

    return plan


def build_method_switch_runtime_plan(window, method: str) -> MethodSwitchRuntimePlan:
    from program_settings.public import is_auto_dpi_enabled

    normalized_method = normalize_launch_method(method, default="")
    expected_exe_path = ""
    expected_process_name = ""
    if normalized_method in ALL_LAUNCH_METHODS:
        expected_exe_path = str(exe_path_for_launch_method(normalized_method) or "").strip()
        expected_process_name = os.path.basename(expected_exe_path).strip().lower()

    residual_runtime_detected = False
    try:
        runtime_api = getattr(window, "launch_runtime_api", None)
        if runtime_api is not None:
            residual_runtime_detected = bool(runtime_api.has_residual_processes(silent=True))
    except Exception:
        residual_runtime_detected = False

    active_runtime_detected = bool(residual_runtime_detected)
    try:
        runtime_service = getattr(window, "launch_runtime_service", None)
        if runtime_service is not None:
            snapshot = runtime_service.snapshot()
            phase = str(getattr(snapshot, "phase", "") or "").strip().lower()
            active_runtime_detected = bool(
                active_runtime_detected
                or getattr(snapshot, "running", False)
                or phase in {"starting", "running", "stopping"}
            )
    except Exception:
        pass

    try:
        controller = getattr(window, "launch_controller", None)
        if controller is not None and controller.transition_pipeline_in_progress():
            active_runtime_detected = True
    except Exception:
        pass

    can_autostart = _can_autostart_for_method(window, normalized_method)
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


def apply_method_switch_runtime_plan(window, plan: MethodSwitchRuntimePlan) -> None:
    runtime_api = getattr(window, "launch_runtime_api", None)
    if runtime_api is not None:
        try:
            runtime_api.set_expected_exe_path(plan.expected_exe_path)
        except Exception:
            pass

    runtime_service = getattr(window, "launch_runtime_service", None)

    if runtime_service is not None:
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
        if runtime_service is not None:
            if plan.dispatch_action in {"restart", "stop"}:
                runtime_service.set_busy(True, "Переключаем режим запуска...")
            else:
                runtime_service.set_busy(False)
    except Exception:
        pass

    controller = getattr(window, "launch_controller", None)
    if controller is None:
        return

    if plan.dispatch_action == "restart":
        log(
            f"Смена метода '{plan.method}' передана в единый restart pipeline",
            "INFO",
        )
        QTimer.singleShot(
            0,
            lambda c=controller, force_stop=plan.requires_cleanup_stop: c.restart_dpi_async(
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
            lambda c=controller, force_cleanup=plan.requires_cleanup_stop: c.stop_dpi_async(
                force_cleanup=force_cleanup,
            ),
        )


def _can_autostart_for_method(window, method: str) -> bool:
    normalized_method = normalize_launch_method(method, default="")
    if is_orchestra_launch_method(normalized_method):
        return True
    if not is_preset_launch_method(normalized_method):
        try:
            window.set_status("Ошибка: выбран удалённый или неподдерживаемый режим запуска")
        except Exception:
            pass
        log(f"Удалённый или неподдерживаемый режим запуска: {normalized_method}", "ERROR")
        return False

    try:
        get_launch_snapshot(
            normalized_method,
            app_context=window.app_context,
            require_filters=False,
        )
        return True
    except Exception as e:
        if is_zapret2_launch_method(normalized_method):
            log(f"{ZAPRET2_MODE}: выбранный source-пресет не подготовлен", "ERROR")
            try:
                window.set_status("Ошибка: отсутствует Default v1 (game filter).txt (built-in пресет)")
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
