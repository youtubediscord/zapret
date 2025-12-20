"""
Остановка DPI процессов через Windows API.
Быстрее и надёжнее чем taskkill и .bat файлы.
"""

import time
from typing import TYPE_CHECKING
from log import log

if TYPE_CHECKING:
    from main import LupiDPIApp


def stop_dpi(app: "LupiDPIApp"):
    """Останавливает процесс winws*.exe через Win API"""
    try:
        log("======================== Stop DPI ========================", level="START")
        
        # Проверяем метод запуска
        from strategy_menu import get_strategy_launch_method
        launch_method = get_strategy_launch_method()
        
        if launch_method in ("direct", "direct_orchestra"):
            # Используем новый метод остановки для Zapret 2
            return stop_dpi_direct(app)
        else:
            # Используем универсальный метод через Win API
            return stop_dpi_universal(app)
            
    except Exception as e:
        log(f"Критическая ошибка в stop_dpi: {e}", level="❌ ERROR")
        app.set_status(f"Ошибка остановки: {e}")
        return False


def stop_dpi_direct(app: "LupiDPIApp"):
    """Останавливает DPI в Direct режиме через Win API"""
    try:
        # Проверяем, запущен ли процесс
        if not app.dpi_starter.check_process_running_wmi(silent=True):
            log("Процесс winws не запущен", level="INFO")
            app.set_status("Zapret уже остановлен")
            if hasattr(app, 'ui_manager'):
                app.ui_manager.update_ui_state(running=False)
            return True

        app.set_status("Останавливаю Zapret...")

        # 1. Останавливаем через StrategyRunner
        try:
            from strategy_menu.strategy_runner import get_strategy_runner
            runner = get_strategy_runner(app.dpi_starter.winws_exe)
            if runner.is_running():
                runner.stop()
                time.sleep(0.3)
        except Exception as e:
            log(f"Ошибка остановки через StrategyRunner: {e}", "DEBUG")

        # 2. Убиваем все процессы через Win API с агрессивным методом
        from utils.process_killer import kill_winws_force
        kill_winws_force()

        # 3. Очищаем службу WinDivert
        if hasattr(app.dpi_starter, 'cleanup_windivert_service'):
            app.dpi_starter.cleanup_windivert_service()

        # Проверяем результат
        time.sleep(0.3)

        if app.dpi_starter.check_process_running_wmi(silent=True):
            log("Процесс winws всё ещё работает", level="⚠ WARNING")
            app.set_status("Не удалось полностью остановить Zapret")
            if hasattr(app, 'process_monitor_manager'):
                app.process_monitor_manager.on_process_status_changed(True)
            return False
        else:
            log("Zapret успешно остановлен", level="✅ SUCCESS")
            if hasattr(app, 'ui_manager'):
                app.ui_manager.update_ui_state(running=False)
            app.set_status("Zapret успешно остановлен")
            if hasattr(app, 'process_monitor_manager'):
                app.process_monitor_manager.on_process_status_changed(False)
            return True

    except Exception as e:
        log(f"Ошибка в stop_dpi_direct: {e}", level="❌ ERROR")
        return False


def stop_dpi_universal(app: "LupiDPIApp"):
    """Универсальная остановка DPI через Win API (для BAT режима)"""
    try:
        log("======================== Stop DPI (Universal Win API) ========================", level="START")

        # Проверяем, запущен ли процесс
        if not app.dpi_starter.check_process_running_wmi(silent=True):
            log("Процесс winws не запущен", level="INFO")
            app.set_status("Zapret уже остановлен")
            if hasattr(app, 'ui_manager'):
                app.ui_manager.update_ui_state(running=False)
            return True

        app.set_status("Останавливаю Zapret...")

        # 1. Завершаем все процессы winws*.exe через агрессивный метод
        from utils.process_killer import kill_winws_force
        killed = kill_winws_force()

        if killed:
            log("✅ Процессы winws остановлены", "INFO")

        # 2. Очищаем службу WinDivert
        if hasattr(app.dpi_starter, 'cleanup_windivert_service'):
            app.dpi_starter.cleanup_windivert_service()

        # Проверяем результат
        time.sleep(0.3)

        if app.dpi_starter.check_process_running_wmi(silent=True):
            log("Процесс winws всё ещё работает", level="⚠ WARNING")
            app.set_status("Не удалось полностью остановить Zapret")
            if hasattr(app, 'process_monitor_manager'):
                app.process_monitor_manager.on_process_status_changed(True)
            return False
        else:
            log("Zapret успешно остановлен", level="✅ SUCCESS")
            if hasattr(app, 'ui_manager'):
                app.ui_manager.update_ui_state(running=False)
            app.set_status("Zapret успешно остановлен")
            if hasattr(app, 'process_monitor_manager'):
                app.process_monitor_manager.on_process_status_changed(False)
            return True

    except Exception as e:
        log(f"Ошибка в stop_dpi_universal: {e}", level="❌ ERROR")
        app.set_status(f"Ошибка остановки: {e}")
        return False


# Алиас для совместимости
stop_dpi_bat = stop_dpi_universal
