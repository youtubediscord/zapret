import os
import time
from typing import Optional, Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from main.window import LupiDPIApp

from log.log import log

from .process_probe import (
    get_canonical_winws_process_pids,
    is_expected_winws_running,
)
from .system_ops import cleanup_windivert_services_runtime, stop_all_winws_processes


class DirectLaunchRuntimeApi:
    """Низкоуровневый runtime-слой запуска: статус процесса, ожидаемый exe и очистка WinDivert."""

    def __init__(
        self,
        expected_exe_path: str,
        status_callback: Optional[Callable[[str], None]] = None,
        app_instance: Optional["LupiDPIApp"] = None,
    ):
        """
        Инициализирует DirectLaunchRuntimeApi.

        Args:
            expected_exe_path: Путь к ожидаемому winws.exe/winws2.exe
            status_callback: Функция обратного вызова для отображения статуса
            app_instance: Ссылка на главное приложение
        """
        self.expected_exe_path = expected_exe_path
        self.status_callback = status_callback
        self.app_instance = app_instance

    def _set_status(self, text: str) -> None:
        """Внутренний метод для установки статуса"""
        if self.status_callback:
            self.status_callback(text)

    def set_status(self, text: str) -> None:
        """Отображает статусное сообщение."""
        if self.status_callback:
            self.status_callback(text)
        else:
            print(text)

    def set_expected_exe_path(self, exe_path: str) -> None:
        self.expected_exe_path = str(exe_path or "").strip()

    def is_any_running(self, silent: bool = False) -> bool:
        """
        Проверка семейства winws через канонический WinAPI probe.

        Считает запущенными только процессы, чей полный путь совпадает
        с ожидаемыми `exe/winws.exe` и `exe/winws2.exe` этого проекта.
        """
        try:
            is_running = bool(get_canonical_winws_process_pids())
            if not silent:
                log(f"winws/winws2 state → {is_running} (WinAPI canonical)", "DEBUG")
            return is_running
        except Exception as e:
            if not silent:
                log(f"WinAPI canonical check error: {e}", "DEBUG")
            return False

    def is_expected_running(self, silent: bool = False) -> bool:
        """
        Проверка только текущего ожидаемого exe из `self.expected_exe_path`.

        Это нужно там, где нам важен именно активный режим запуска,
        а не любой процесс семейства winws.
        """
        try:
            is_running = bool(is_expected_winws_running(self.expected_exe_path))
            if not silent:
                exe_name = os.path.basename(self.expected_exe_path) or "winws.exe"
                log(f"{exe_name} state → {is_running} (WinAPI canonical)", "DEBUG")
            return is_running
        except Exception as e:
            if not silent:
                log(f"Expected WinAPI canonical check error: {e}", "DEBUG")
            return False

    def cleanup_windivert_service(self) -> bool:
        """Очистка служб WinDivert через internal runtime ops."""
        try:
            return bool(cleanup_windivert_services_runtime())
        except Exception as e:
            log(f"Ошибка очистки службы: {e}", "⚠ WARNING")
            return False

    def stop_all_processes(self) -> bool:
        """Останавливает все процессы DPI через Win API"""
        log("Останавливаем все процессы winws через Win API...", "INFO")

        try:
            stop_all_winws_processes()
        except Exception as e:
            log(f"Ошибка остановки через Win API: {e}", "⚠ WARNING")

        time.sleep(0.3)
        ok = not self.is_any_running(silent=True)
        log("Все процессы остановлены" if ok else "winws/winws2 ещё работает",
            "✅ SUCCESS" if ok else "⚠ WARNING")
        return ok
