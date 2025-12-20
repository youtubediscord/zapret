# autostart/registry_check.py

import winreg
from typing import Optional
from log import log
from config import REGISTRY_PATH_AUTOSTART
AUTOSTART_KEY = "AutostartEnabled"
AUTOSTART_METHOD_KEY = "AutostartMethod"  # Тип автозапуска: exe, task, service

class AutostartRegistryChecker:
    """Быстрая проверка автозапуска через реестр"""
    
    @staticmethod
    def is_autostart_enabled() -> bool:
        """
        Проверяет, включен ли автозапуск (по данным реестра).
        Это быстрая проверка без сканирования системы.
        """
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REGISTRY_PATH_AUTOSTART) as key:
                value, _ = winreg.QueryValueEx(key, AUTOSTART_KEY)
                return bool(value)
        except (FileNotFoundError, OSError):
            # Ключ не существует - автозапуск не настроен
            return False
        except Exception as e:
            log(f"Ошибка чтения статуса автозапуска из реестра: {e}", "❌ ERROR")
            return False
    
    @staticmethod
    def set_autostart_enabled(enabled: bool, method: Optional[str] = None):
        """
        Устанавливает флаг автозапуска в реестре.
        
        Args:
            enabled: True если автозапуск включен
            method: Метод автозапуска ('exe', 'task', 'service')
        """
        try:
            # Создаем ключ если его нет
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, REGISTRY_PATH_AUTOSTART) as key:
                # Сохраняем статус
                winreg.SetValueEx(key, AUTOSTART_KEY, 0, winreg.REG_DWORD, int(enabled))
                
                # Сохраняем метод автозапуска
                if enabled and method:
                    winreg.SetValueEx(key, AUTOSTART_METHOD_KEY, 0, winreg.REG_SZ, method)
                elif not enabled:
                    # Удаляем информацию о методе при отключении
                    try:
                        winreg.DeleteValue(key, AUTOSTART_METHOD_KEY)
                    except:
                        pass
                
                log(f"Статус автозапуска сохранен в реестр: {enabled} (метод: {method})", "INFO")
                
        except Exception as e:
            log(f"Ошибка записи статуса автозапуска в реестр: {e}", "❌ ERROR")
    
    @staticmethod
    def get_autostart_method() -> Optional[str]:
        """
        Возвращает метод автозапуска из реестра.
        
        Returns:
            'exe', 'task', 'service' или None
        """
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REGISTRY_PATH_AUTOSTART) as key:
                method, _ = winreg.QueryValueEx(key, AUTOSTART_METHOD_KEY)
                return method
        except:
            return None
    
    @staticmethod
    def verify_and_sync_status() -> bool:
        """
        Проверяет реальное состояние автозапуска и синхронизирует с реестром.
        Вызывается при старте программы для проверки целостности.
        
        Returns:
            True если автозапуск действительно включен
        """
        from autostart.checker import CheckerManager
        from config import WINWS_EXE
        
        try:
            # Полная проверка всех методов (медленная, но точная)
            checker = CheckerManager(WINWS_EXE, None, None)
            real_status = checker.check_autostart_exists()
            
            # Получаем статус из реестра
            registry_status = AutostartRegistryChecker.is_autostart_enabled()
            
            # Если статусы не совпадают - синхронизируем
            if real_status != registry_status:
                log(f"Несоответствие статуса автозапуска: реальный={real_status}, реестр={registry_status}", "⚠ WARNING")
                AutostartRegistryChecker.set_autostart_enabled(real_status)
            
            return real_status
            
        except Exception as e:
            log(f"Ошибка синхронизации статуса автозапуска: {e}", "❌ ERROR")
            return False

# Глобальные функции для удобства
def is_autostart_enabled() -> bool:
    """Быстрая проверка автозапуска через реестр"""
    return AutostartRegistryChecker.is_autostart_enabled()

def set_autostart_enabled(enabled: bool, method: Optional[str] = None):
    """Установка флага автозапуска в реестре"""
    AutostartRegistryChecker.set_autostart_enabled(enabled, method)

def verify_autostart_status() -> bool:
    """Полная проверка и синхронизация статуса"""
    return AutostartRegistryChecker.verify_and_sync_status()