from __future__ import annotations

from PyQt6.QtCore import QTimer

from log import log
from ui.navigation.navigation_controller import ensure_navigation_controller
from ui.ui_workflows import ensure_ui_workflows


def handle_launch_method_changed(window, method: str) -> None:
    from utils.process_killer import kill_winws_all

    log(f"Метод запуска изменён на: {method}", "INFO")
    try:
        if getattr(window, "ui_state_store", None) is not None:
            window.ui_state_store.bump_mode_revision()
    except Exception:
        pass

    if hasattr(window, 'launch_runtime_api') and window.launch_runtime_api.is_any_running(silent=True):
        log("Останавливаем все процессы winws*.exe перед переключением режима...", "INFO")

        try:
            runtime_service = getattr(window, "launch_runtime_service", None)
            if runtime_service is not None:
                runtime_service.begin_stop()
            killed = kill_winws_all()
            if killed:
                log("Все процессы winws*.exe остановлены через Win API", "INFO")
            if hasattr(window, 'launch_runtime_api'):
                window.launch_runtime_api.cleanup_windivert_service()
            if runtime_service is not None:
                runtime_service.mark_stopped(clear_error=True)
            import time
            time.sleep(0.2)
        except Exception as e:
            log(f"Ошибка остановки через Win API: {e}", "WARNING")

    complete_launch_method_switch(window, method)


def complete_launch_method_switch(window, method: str) -> None:
    from config import get_winws_exe_for_method
    from direct_launch.runners import invalidate_strategy_runner
    from utils.service_manager import cleanup_windivert_services

    direct_flow_coordinator = window.app_context.direct_flow_coordinator

    try:
        cleanup_windivert_services()
    except Exception:
        pass

    if hasattr(window, 'launch_runtime_api'):
        window.launch_runtime_api.set_expected_exe_path(get_winws_exe_for_method(method))

    try:
        invalidate_strategy_runner()
    except Exception as e:
        log(f"Ошибка инвалидации StrategyRunner: {e}", "WARNING")

    can_autostart = True
    if method == "direct_zapret2":
        try:
            direct_flow_coordinator.get_startup_snapshot("direct_zapret2")
        except Exception:
            log("direct_zapret2: выбранный source-пресет не подготовлен", "ERROR")
            try:
                window.set_status("Ошибка: отсутствует Default.txt (built-in пресет)")
            except Exception:
                pass
            can_autostart = False

    elif method == "direct_zapret1":
        try:
            direct_flow_coordinator.get_startup_snapshot("direct_zapret1")
        except Exception as e:
            log(f"direct_zapret1: ошибка инициализации пресета: {e}", "WARNING")
            can_autostart = False
    elif method != "orchestra":
        log(f"Удалённый или неподдерживаемый режим запуска: {method}", "ERROR")
        try:
            window.set_status("Ошибка: выбран удалённый или неподдерживаемый режим запуска")
        except Exception:
            pass
        can_autostart = False

    try:
        window._preset_runtime_coordinator.setup_active_preset_file_watcher()
    except Exception:
        pass

    try:
        if getattr(window, "ui_state_store", None) is not None:
            window.ui_state_store.bump_mode_revision()
    except Exception:
        pass

    log(f"Переключение на режим '{method}' завершено", "INFO")

    try:
        ensure_navigation_controller(window).sync_nav_visibility(method)
    except Exception:
        pass

    if can_autostart:
        QTimer.singleShot(
            500,
            lambda: (
                not bool(getattr(window, "_is_exiting", False) or getattr(window, "_closing_completely", False))
            ) and auto_start_after_method_switch(window, method),
        )

    try:
        ensure_ui_workflows(window).redirect_to_strategies_page_for_method(method)
    except Exception:
        pass


def auto_start_after_method_switch(window, method: str) -> None:
    if bool(getattr(window, "_is_exiting", False) or getattr(window, "_closing_completely", False)):
        return
    try:
        if not hasattr(window, 'launch_controller') or not window.launch_controller:
            return

        if method == "orchestra":
            log("Автозапуск Оркестр", "INFO")
            window.launch_controller.start_dpi_async(selected_mode=None, launch_method="orchestra")

        elif method in {"direct_zapret2", "direct_zapret1"}:
            from config import get_dpi_autostart
            if not get_dpi_autostart():
                return
            log(f"Автозапуск после смены режима передан в единый DPI controller pipeline: {method}", "INFO")
            window.launch_controller.start_dpi_async(selected_mode=None, launch_method=method)

    except Exception as e:
        log(f"Ошибка автозапуска после переключения режима: {e}", "ERROR")


__all__ = [
    "auto_start_after_method_switch",
    "complete_launch_method_switch",
    "handle_launch_method_changed",
]
