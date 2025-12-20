import winreg
import time
import os
import hashlib
from log import log

class StartupCheckCache:
    """Кэширование результатов проверок запуска в реестре"""
    
    @property
    def REGISTRY_KEY(self):
        from config import REGISTRY_PATH
        return REGISTRY_PATH
    CACHE_EXPIRY_HOURS = 24  # Время жизни кэша в часах
    
    # Добавляем разные времена жизни для разных типов проверок
    CACHE_EXPIRY_OVERRIDE = {
        "mitmproxy_check": 0.083,  # 5 минут в часах (5/60)
        "goodbyedpi_check": 1,     # 1 час
        "system_commands": 6,      # 6 часов
        "bfe_check": 2,            # 2 часа
    }

    def __init__(self):
        self._ensure_registry_key()
    
    def _ensure_registry_key(self):
        """Создает ключ реестра если его нет"""
        try:
            winreg.CreateKey(winreg.HKEY_CURRENT_USER, self.REGISTRY_KEY)
        except Exception as e:
            log(f"Не удалось создать ключ реестра для кэша: {e}", "⚠ WARNING")
    
    def _get_cache_key(self, check_name: str, context: str = "") -> str:
        """Генерирует ключ для кэша с контекстом"""
        if context:
            # Хэшируем контекст для уникальности
            context_hash = hashlib.md5(context.encode()).hexdigest()[:8]
            return f"{check_name}_{context_hash}"
        return check_name
    
    def is_cached_and_valid(self, check_name: str, context: str = "") -> tuple[bool, bool]:
        """
        Проверяет наличие и валидность кэша
        Returns: (has_cache, cached_result)
        """
        try:
            cache_key = self._get_cache_key(check_name, context)
            
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.REGISTRY_KEY) as key:
                cached_result, _ = winreg.QueryValueEx(key, f"{cache_key}_result")
                cached_time, _ = winreg.QueryValueEx(key, f"{cache_key}_time")
                
                # Определяем время жизни для конкретной проверки
                expiry_hours = self.CACHE_EXPIRY_OVERRIDE.get(check_name, self.CACHE_EXPIRY_HOURS)
                
                # Проверяем не истек ли кэш
                current_time = time.time()
                if (current_time - cached_time) < (expiry_hours * 3600):
                    log(f"Используем кэшированный результат для {check_name}: {bool(cached_result)} (TTL: {expiry_hours}ч)", "DEBUG")
                    return True, bool(cached_result)
                else:
                    log(f"Кэш для {check_name} истек (TTL: {expiry_hours}ч)", "DEBUG")
                    return False, False
                    
        except FileNotFoundError:
            return False, False
        except Exception as e:
            log(f"Ошибка чтения кэша для {check_name}: {e}", "DEBUG")
            return False, False
    
    def cache_result(self, check_name: str, result: bool, context: str = ""):
        """Сохраняет результат проверки в кэш"""
        try:
            cache_key = self._get_cache_key(check_name, context)
            
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.REGISTRY_KEY, 0, 
                               winreg.KEY_SET_VALUE) as key:
                winreg.SetValueEx(key, f"{cache_key}_result", 0, winreg.REG_DWORD, int(result))
                winreg.SetValueEx(key, f"{cache_key}_time", 0, winreg.REG_QWORD, int(time.time()))
                
            log(f"Результат {check_name} сохранен в кэш: {result}", "DEBUG")
            
        except Exception as e:
            log(f"Не удалось сохранить кэш для {check_name}: {e}", "⚠ WARNING")
    
    def invalidate_cache(self, check_name: str = None):
        """Очищает кэш (конкретную проверку или весь)"""
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.REGISTRY_KEY, 0, 
                               winreg.KEY_ALL_ACCESS) as key:
                if check_name:
                    # Удаляем конкретную проверку
                    try:
                        winreg.DeleteValue(key, f"{check_name}_result")
                        winreg.DeleteValue(key, f"{check_name}_time")
                        log(f"Кэш для {check_name} очищен", "DEBUG")
                    except FileNotFoundError:
                        pass
                else:
                    # Очищаем весь кэш
                    i = 0
                    while True:
                        try:
                            value_name, _, _ = winreg.EnumValue(key, i)
                            winreg.DeleteValue(key, value_name)
                        except OSError:
                            break
                    log("Весь кэш проверок очищен", "INFO")
                    
        except Exception as e:
            log(f"Ошибка очистки кэша: {e}", "⚠ WARNING")

# Глобальный экземпляр кэша
startup_cache = StartupCheckCache()