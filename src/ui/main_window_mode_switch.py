from __future__ import annotations

from PyQt6.QtCore import QTimer

from log import log


def handle_main_window_launch_method_changed(window, method: str) -> None:
    from utils.process_killer import kill_winws_all

    log(f"Метод запуска изменён на: {method}", "INFO")
    try:
        if getattr(window, "ui_state_store", None) is not None:
            window.ui_state_store.bump_mode_revision()
    except Exception:
        pass

    if hasattr(window, 'dpi_starter') and window.dpi_starter.check_process_running_wmi(silent=True):
        log("Останавливаем все процессы winws*.exe перед переключением режима...", "INFO")

        try:
            runtime_service = getattr(window, "dpi_runtime_service", None)
            if runtime_service is not None:
                runtime_service.begin_stop()
            killed = kill_winws_all()
            if killed:
                log("Все процессы winws*.exe остановлены через Win API", "INFO")
            if hasattr(window, 'dpi_starter'):
                window.dpi_starter.cleanup_windivert_service()
            if runtime_service is not None:
                runtime_service.mark_stopped(clear_error=True)
            import time
            time.sleep(0.2)
        except Exception as e:
            log(f"Ошибка остановки через Win API: {e}", "WARNING")

    complete_main_window_method_switch(window, method)


def complete_main_window_method_switch(window, method: str) -> None:
    from config import get_winws_exe_for_method
    from launcher_common import invalidate_strategy_runner
    from utils.service_manager import cleanup_windivert_services

    try:
        cleanup_windivert_services()
    except Exception:
        pass

    if hasattr(window, 'dpi_starter'):
        window.dpi_starter.winws_exe = get_winws_exe_for_method(method)

    try:
        invalidate_strategy_runner()
    except Exception as e:
        log(f"Ошибка инвалидации StrategyRunner: {e}", "WARNING")

    can_autostart = True
    if method == "direct_zapret2":
        from core.services import get_direct_flow_coordinator
        try:
            get_direct_flow_coordinator().ensure_launch_profile("direct_zapret2", require_filters=False)
        except Exception:
            log("direct_zapret2: выбранный source-пресет не подготовлен", "ERROR")
            try:
                window.set_status("Ошибка: отсутствует Default.txt (built-in пресет)")
            except Exception:
                pass
            can_autostart = False

    elif method == "direct_zapret2_orchestra":
        from preset_orchestra_zapret2 import ensure_default_preset_exists
        if not ensure_default_preset_exists():
            log("direct_zapret2_orchestra: preset-zapret2-orchestra.txt не создан", "ERROR")
            try:
                window.set_status("Ошибка: отсутствует orchestra Default.txt")
            except Exception:
                pass
            can_autostart = False

    elif method == "direct_zapret1":
        try:
            from core.services import get_direct_flow_coordinator

            get_direct_flow_coordinator().ensure_launch_profile("direct_zapret1", require_filters=False)
        except Exception as e:
            log(f"direct_zapret1: ошибка инициализации пресета: {e}", "WARNING")
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
        window._sync_nav_visibility(method)
    except Exception:
        pass

    if can_autostart:
        QTimer.singleShot(500, lambda: auto_start_after_main_window_method_switch(window, method))

    try:
        window._redirect_to_strategies_page_for_method(method)
    except Exception:
        pass


def auto_start_after_main_window_method_switch(window, method: str) -> None:
    try:
        if not hasattr(window, 'dpi_controller') or not window.dpi_controller:
            return

        if method == "orchestra":
            log("Автозапуск Оркестр", "INFO")
            window.dpi_controller.start_dpi_async(selected_mode=None, launch_method="orchestra")

        elif method == "direct_zapret2":
            from config import get_dpi_autostart
            if not get_dpi_autostart():
                return

            from core.services import get_direct_flow_coordinator

            try:
                profile = get_direct_flow_coordinator().ensure_launch_profile(
                    "direct_zapret2",
                    require_filters=False,
                )
            except Exception:
                return

            selected_mode = profile.to_selected_mode()
            window.dpi_controller.start_dpi_async(selected_mode=selected_mode, launch_method=method)

        elif method == "direct_zapret2_orchestra":
            from config import get_dpi_autostart
            if not get_dpi_autostart():
                return

            from preset_orchestra_zapret2 import (
                ensure_default_preset_exists,
                get_active_preset_path,
                get_active_preset_name,
            )

            if not ensure_default_preset_exists():
                return

            preset_path = get_active_preset_path()
            preset_name = get_active_preset_name() or "Default"

            if not preset_path.exists():
                return

            selected_mode = {
                'is_preset_file': True,
                'name': f"Пресет оркестра: {preset_name}",
                'preset_path': str(preset_path),
            }
            window.dpi_controller.start_dpi_async(selected_mode=selected_mode, launch_method=method)

        elif method == "direct_zapret1":
            from config import get_dpi_autostart
            if not get_dpi_autostart():
                return

            from core.services import get_direct_flow_coordinator

            try:
                profile = get_direct_flow_coordinator().ensure_launch_profile(
                    "direct_zapret1",
                    require_filters=False,
                )
            except Exception:
                return

            selected_mode = profile.to_selected_mode()
            window.dpi_controller.start_dpi_async(selected_mode=selected_mode, launch_method=method)

    except Exception as e:
        log(f"Ошибка автозапуска после переключения режима: {e}", "ERROR")
