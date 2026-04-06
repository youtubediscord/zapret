# dpi/bat_start.py
import os
import time
import psutil
from typing import Optional, Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from main import LupiDPIApp

from log import log
from utils import run_hidden, get_system32_path

class BatDPIStart:
    """Управляет процессом DPI: проверка состояния, остановка, очистка WinDivert"""

    def __init__(self, winws_exe: str, status_callback: Optional[Callable[[str], None]] = None,
                 app_instance: Optional['LupiDPIApp'] = None):
        """
        Инициализирует BatDPIStart.

        Args:
            winws_exe: Путь к исполняемому файлу winws.exe
            status_callback: Функция обратного вызова для отображения статуса
            app_instance: Ссылка на главное приложение
        """
        self.winws_exe = winws_exe
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

    def check_process_running_fast(self, silent: bool = False) -> bool:
        """
        БЫСТРАЯ проверка через psutil (~1-10ms вместо 100-2000ms у WMI)
        Основной метод проверки — используйте его везде!
        """
        try:
            for proc in psutil.process_iter(['name']):
                try:
                    proc_name = proc.info['name']
                    if proc_name and proc_name.lower() in ('winws.exe', 'winws2.exe'):
                        if not silent:
                            log(f"winws/winws2 state → True (psutil)", "DEBUG")
                        return True
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue
            if not silent:
                log(f"winws/winws2 state → False (psutil)", "DEBUG")
            return False
        except Exception as e:
            if not silent:
                log(f"psutil check error: {e}", "DEBUG")
            # psutil не работает - возвращаем False (процесс не найден)
            return False

    def check_process_running_wmi(self, silent: bool = False) -> bool:
        """
        Проверка процесса (теперь использует psutil, WMI как резерв)
        Оставлен для обратной совместимости — внутри вызывает check_process_running_fast()
        """
        return self.check_process_running_fast(silent)

    def check_process_running(self, silent: bool = False) -> bool:
        """
        Проверка процесса (теперь использует psutil)
        Оставлен для обратной совместимости — внутри вызывает check_process_running_fast()
        """
        return self.check_process_running_fast(silent)

    def cleanup_windivert_service(self) -> bool:
        """Очистка службы через PowerShell - без окон"""
        ps_script = """
        $service = Get-Service -Name windivert -ErrorAction SilentlyContinue
        if ($service) {
            Stop-Service -Name windivert -Force -ErrorAction SilentlyContinue
            Start-Sleep -Seconds 2
            sc.exe delete windivert | Out-Null
            Stop-Service -Name Monkey -Force -ErrorAction SilentlyContinue
            Start-Sleep -Seconds 2
            sc.exe delete Monkey | Out-Null
        }
        """

        try:
            ps_exe = os.path.join(get_system32_path(), 'WindowsPowerShell', 'v1.0', 'powershell.exe')
            run_hidden(
                [ps_exe, '-WindowStyle', 'Hidden', '-NoProfile', '-Command', ps_script],
                wait=True
            )
            return True
        except Exception as e:
            log(f"Ошибка очистки службы: {e}", "⚠ WARNING")
            return True

    def stop_all_processes(self) -> bool:
        """Останавливает все процессы DPI через Win API"""
        log("Останавливаем все процессы winws через Win API...", "INFO")

        try:
            from utils.process_killer import kill_winws_all
            kill_winws_all()
        except Exception as e:
            log(f"Ошибка остановки через Win API: {e}", "⚠ WARNING")

        time.sleep(0.3)
        ok = not self.check_process_running_wmi(silent=True)
        log("Все процессы остановлены" if ok else "winws/winws2 ещё работает",
            "✅ SUCCESS" if ok else "⚠ WARNING")
        return ok
