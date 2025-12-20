# autostart/checker.py
import subprocess
import winreg
from utils import run_hidden, get_system_exe
from .autostart_direct import check_direct_autostart_exists
from .registry_check import is_autostart_enabled as registry_is_enabled

class CheckerManager:
    def __init__(self, winws_exe, status_callback=None, ui_callback=None, service_name="ZapretCensorliber"):
        """
        Инициализирует менеджер служб.
        
        Args:
            winws_exe (str): Путь к исполняемому файлу winws.exe
            status_callback (callable): Функция обратного вызова для отображения статуса
            service_name (str): Имя службы
        """
        self.winws_exe = winws_exe
        self.status_callback = status_callback
        self.ui_callback = ui_callback
        self.service_name = service_name
    
    def set_status(self, text):
        """Отображает статусное сообщение"""
        if self.status_callback:
            self.status_callback(text)
        else:
            print(text)
    
    def check_service_exists(self):
        """
        Проверяет наличие автозапуска (обратная совместимость)
        
        Returns:
            bool: True если автозапуск настроен через любой метод, иначе False
        """
        # Просто делегируем вызов новому методу для обеспечения обратной совместимости
        return self.check_autostart_exists()
        
    def check_autostart_registry_exists(self):
        """
        Проверяет, настроен ли автозапуск приложения через реестр Windows
        
        Returns:
            bool: True если автозапуск настроен, иначе False
        """
        try:
            # Открываем ключ автозапуска в реестре
            key_path = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run"
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_READ) as key:
                # Пытаемся прочитать значение
                value, _ = winreg.QueryValueEx(key, "ZapretGUI")
                
                # Если значение существует и содержит путь к exe, автозапуск настроен
                return value and (".exe" in value.lower())
        
        except FileNotFoundError:
            # Ключ или значение не найдены
            return False
        except Exception as e:
            from log import log
            log(f"Ошибка при проверке автозапуска: {str(e)}", level="❌ ERROR")
            return False

    def check_autostart_exists(self) -> bool:
        """
        БЫСТРАЯ проверка автозапуска через реестр.
        Используется для большинства проверок в UI.
        
        Returns:
            bool: True если автозапуск включен (по данным реестра)
        """
        return registry_is_enabled()

    def check_autostart_exists_full(self) -> bool:
        """
        ПОЛНАЯ проверка всех механизмов автозапуска.
        Медленная, но точная. Используется при удалении и синхронизации.
        
        Returns:
            bool: True если хоть один механизм автозапуска найден
        """
        try:
            from pathlib import Path
            import os
            
            # Проверяем ярлыки
            startup_dir = (
                Path(os.environ["APPDATA"])
                / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
            )
            for lnk in ("ZapretGUI.lnk", "ZapretStrategy.lnk"):
                if (startup_dir / lnk).exists():
                    return True

            # Проверяем реестр
            if self.check_autostart_registry_exists():
                return True

            # Проверяем задачи планировщика
            if self.check_scheduler_task_exists():
                return True

            # Проверяем службы
            if self.check_windows_service_exists():
                return True
            
            # Проверяем Direct автозапуск
            if check_direct_autostart_exists():
                return True

            return False

        except Exception:
            from log import log
            log("check_autostart_exists_full: необработанная ошибка", level="❌ ERROR")
            return False
    
    def check_scheduler_task_exists(self) -> bool:
        """
        True, если в Планировщике есть хотя бы одна из наших задач
        """
        task_names = (
            "ZapretCensorliber", 
            "ZapretStrategy", 
            "ZapretGUI_AutoStart",
            "ZapretDirect",
            "ZapretDirect_AutoStart",
            "ZapretDirectBoot"
        )

        for tn in task_names:
            try:
                res = run_hidden(
                    [get_system_exe("schtasks.exe"), "/Query", "/TN", tn],
                    capture_output=True,
                    text=True,
                    encoding="cp866",
                    errors="ignore",
                )
                if res.returncode == 0:
                    return True
            except Exception:
                pass

        return False
            
    def check_windows_service_exists(self):
        """
        Проверяет наличие службы Windows
        """
        service_names = [
            self.service_name,
            "ZapretDirectService"  # Добавить
        ]
        
        for svc_name in service_names:
            try:
                service_result = run_hidden(
                    f'"{get_system_exe("sc.exe")}" query {svc_name}',
                    shell=True,
                    capture_output=True,
                    text=True,
                    encoding='cp866'
                )
                if service_result.returncode == 0 and "STATE" in service_result.stdout:
                    return True
            except:
                continue
        return False