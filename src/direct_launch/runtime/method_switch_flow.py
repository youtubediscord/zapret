from __future__ import annotations

import os
from dataclasses import dataclass

from PyQt6.QtCore import QTimer

from log import log


@dataclass(frozen=True, slots=True)
class MethodSwitchRuntimePlan:
    method: str
    expected_exe_path: str
    expected_process_name: str
    was_running: bool
    autostart_enabled: bool
    can_autostart: bool
    dispatch_action: str


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
    from config import get_dpi_autostart, get_winws_exe_for_method

    normalized_method = str(method or "").strip().lower()
    expected_exe_path = ""
    expected_process_name = ""
    if normalized_method in {"direct_zapret2", "direct_zapret1", "orchestra"}:
        expected_exe_path = str(get_winws_exe_for_method(normalized_method) or "").strip()
        expected_process_name = os.path.basename(expected_exe_path).strip().lower()

    was_running = False
    try:
        runtime_api = getattr(window, "launch_runtime_api", None)
        if runtime_api is not None:
            was_running = bool(runtime_api.is_any_running(silent=True))
    except Exception:
        was_running = False

    can_autostart = _can_autostart_for_method(window, normalized_method)
    autostart_enabled = bool(get_dpi_autostart())

    if was_running:
        dispatch_action = "restart" if (autostart_enabled and can_autostart) else "stop"
    elif autostart_enabled and can_autostart:
        dispatch_action = "restart"
    else:
        dispatch_action = "none"

    return MethodSwitchRuntimePlan(
        method=normalized_method,
        expected_exe_path=expected_exe_path,
        expected_process_name=expected_process_name,
        was_running=was_running,
        autostart_enabled=autostart_enabled,
        can_autostart=can_autostart,
        dispatch_action=dispatch_action,
    )


def apply_method_switch_runtime_plan(window, plan: MethodSwitchRuntimePlan) -> None:
    runtime_api = getattr(window, "launch_runtime_api", None)
    if runtime_api is not None:
        try:
            runtime_api.set_expected_exe_path(plan.expected_exe_path)
        except Exception:
            pass

    runtime_service = getattr(window, "launch_runtime_service", None)
    store = getattr(window, "ui_state_store", None)

    if runtime_service is not None:
        try:
            if plan.dispatch_action == "restart":
                if plan.was_running:
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
        if store is not None:
            if plan.dispatch_action in {"restart", "stop"}:
                store.set_launch_busy(True, "Переключаем режим запуска...")
            else:
                store.set_launch_busy(False)
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
        QTimer.singleShot(0, controller.restart_dpi_async)
        return

    if plan.dispatch_action == "stop":
        log(
            f"Смена метода '{plan.method}' требует остановки активного DPI через общий pipeline",
            "INFO",
        )
        QTimer.singleShot(0, controller.stop_dpi_async)


def _can_autostart_for_method(window, method: str) -> bool:
    normalized_method = str(method or "").strip().lower()
    if normalized_method == "orchestra":
        return True
    if normalized_method not in {"direct_zapret2", "direct_zapret1"}:
        try:
            window.set_status("Ошибка: выбран удалённый или неподдерживаемый режим запуска")
        except Exception:
            pass
        log(f"Удалённый или неподдерживаемый режим запуска: {normalized_method}", "ERROR")
        return False

    try:
        direct_flow_coordinator = window.app_context.direct_flow_coordinator
        direct_flow_coordinator.get_startup_snapshot(normalized_method)
        return True
    except Exception as e:
        if normalized_method == "direct_zapret2":
            log("direct_zapret2: выбранный source-пресет не подготовлен", "ERROR")
            try:
                window.set_status("Ошибка: отсутствует Default.txt (built-in пресет)")
            except Exception:
                pass
            return False

        log(f"direct_zapret1: ошибка инициализации пресета: {e}", "WARNING")
        return False


__all__ = [
    "MethodSwitchRuntimePlan",
    "apply_method_switch_runtime_plan",
    "build_method_switch_runtime_plan",
    "handle_launch_method_changed_runtime",
]
