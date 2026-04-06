"""
Остановка DPI процессов через Windows API.
Быстрее и надёжнее чем taskkill и .bat файлы.
"""

import time
from typing import TYPE_CHECKING
from log import log

if TYPE_CHECKING:
    from main import LupiDPIApp


def _set_runtime_dpi_running(app: "LupiDPIApp", running: bool) -> None:
    runtime_service = getattr(app, "dpi_runtime_service", None)
    if runtime_service is None:
        return
    if running:
        runtime_service.mark_running()
    else:
        runtime_service.mark_stopped(clear_error=True)


def stop_dpi(app: "LupiDPIApp"):
    """Останавливает процесс winws*.exe через Win API"""
    try:
        log("======================== Stop DPI ========================", level="START")
        
        # Проверяем метод запуска
        from strategy_menu import get_strategy_launch_method
        launch_method = get_strategy_launch_method()
        
        if launch_method in ("direct_zapret2", "direct_zapret2_orchestra", "direct_zapret1"):
            # Используем новый метод остановки для прямого запуска
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
        runtime_service = getattr(app, "dpi_runtime_service", None)
        if runtime_service is not None:
            runtime_service.begin_stop()

        # Проверяем, запущен ли процесс
        if not app.dpi_starter.check_process_running_wmi(silent=True):
            log("Процесс winws не запущен", level="INFO")
            app.set_status("Zapret уже остановлен")
            _set_runtime_dpi_running(app, False)
            return True

        app.set_status("Останавливаю Zapret...")

        # 1. Останавливаем через StrategyRunner
        try:
            from launcher_common import get_strategy_runner
            from config.config import get_current_winws_exe

            # Используем единую функцию определения exe
            winws_exe = get_current_winws_exe()

            runner = get_strategy_runner(winws_exe)
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
            _set_runtime_dpi_running(app, True)
            return False
        else:
            log("Zapret успешно остановлен", level="✅ SUCCESS")
            _set_runtime_dpi_running(app, False)
            app.set_status("Zapret успешно остановлен")
            return True

    except Exception as e:
        log(f"Ошибка в stop_dpi_direct: {e}", level="❌ ERROR")
        return False


def stop_dpi_universal(app: "LupiDPIApp"):
    """Универсальная остановка DPI через Win API (для BAT режима)"""
    try:
        log("======================== Stop DPI (Universal Win API) ========================", level="START")
        runtime_service = getattr(app, "dpi_runtime_service", None)
        if runtime_service is not None:
            runtime_service.begin_stop()

        # Проверяем, запущен ли процесс
        if not app.dpi_starter.check_process_running_wmi(silent=True):
            log("Процесс winws не запущен", level="INFO")
            app.set_status("Zapret уже остановлен")
            _set_runtime_dpi_running(app, False)
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
            _set_runtime_dpi_running(app, True)
            return False
        else:
            log("Zapret успешно остановлен", level="✅ SUCCESS")
            _set_runtime_dpi_running(app, False)
            app.set_status("Zapret успешно остановлен")
            return True

    except Exception as e:
        log(f"Ошибка в stop_dpi_universal: {e}", level="❌ ERROR")
        app.set_status(f"Ошибка остановки: {e}")
        return False


# Алиас для совместимости
stop_dpi_bat = stop_dpi_universal
