import os
import time
from typing import Optional, Callable

from log.log import log
from settings.mode import EXE_NAME_WINWS1, WINWS_ENGINE_FAMILY_LABEL

from .process_probe import (
    get_canonical_winws_process_pids,
    is_expected_winws_running,
)
from .system_ops import (
    cleanup_windivert_services_runtime,
    has_any_winws_process,
    restore_known_windivert_services_demand_start_runtime,
    stop_all_winws_processes,
)


class PresetLaunchRuntimeApi:
    """Низкоуровневый runtime-слой запуска: статус процесса, ожидаемый exe и очистка WinDivert."""

    def __init__(
        self,
        expected_exe_path: str,
        status_callback: Optional[Callable[[str], None]] = None,
    ):
        """
        Инициализирует PresetLaunchRuntimeApi.

        Args:
            expected_exe_path: Путь к ожидаемому winws.exe/winws2.exe
            status_callback: Функция обратного вызова для отображения статуса
        """
        self.expected_exe_path = expected_exe_path
        self.status_callback = status_callback

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
                log(f"{WINWS_ENGINE_FAMILY_LABEL} state → {is_running} (WinAPI canonical)", "DEBUG")
            return is_running
        except Exception as e:
            if not silent:
                log(f"WinAPI canonical check error: {e}", "DEBUG")
            return False

    def has_residual_processes(self, silent: bool = False) -> bool:
        """Проверка остаточных winws/winws2 процессов.

        Сначала используем канонический probe именно для процессов текущего проекта.
        Если он ничего не видит, дополнительно делаем fallback-проверку по имени
        процесса. Это нужно для stop/restart pipeline: очистка должна быть честной
        даже в моменты, когда канонический probe ещё не догнал переходное состояние.
        """
        canonical_running = bool(self.is_any_running(silent=True))
        if canonical_running:
            if not silent:
                log(f"Residual {WINWS_ENGINE_FAMILY_LABEL} detected via canonical probe", "DEBUG")
            return True

        try:
            residual_running = bool(has_any_winws_process())
            if not silent:
                log(
                    f"{WINWS_ENGINE_FAMILY_LABEL} residual state → {residual_running} (name fallback)",
                    "DEBUG",
                )
            return residual_running
        except Exception as e:
            if not silent:
                log(f"Residual process fallback error: {e}", "DEBUG")
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
                exe_name = os.path.basename(self.expected_exe_path) or EXE_NAME_WINWS1
                log(f"{exe_name} state → {is_running} (WinAPI canonical)", "DEBUG")
            return is_running
        except Exception as e:
            if not silent:
                log(f"Expected WinAPI canonical check error: {e}", "DEBUG")
            return False

    def cleanup_windivert_service(self) -> bool:
        """Мягкая stop-cleanup стадия для обычного stop/restart.

        Здесь нельзя деинсталлировать WinDivert из SCM на каждом обычном stop.
        Иначе следующий старт зависит от повторной авто-установки драйвера и
        начинает сам себе создавать плавающие 1060/1058 гонки.

        Также нельзя останавливать уже запущенную driver-service запись: на
        некоторых системах `Monkey` остаётся Running/Disabled, и после stop
        следующий WinDivertOpen получает 1058.
        """
        try:
            return bool(restore_known_windivert_services_demand_start_runtime())
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
        ok = not self.has_residual_processes(silent=True)
        log("Все процессы остановлены" if ok else f"{WINWS_ENGINE_FAMILY_LABEL} ещё работает",
            "✅ SUCCESS" if ok else "⚠ WARNING")
        return ok
