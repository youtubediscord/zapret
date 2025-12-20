# donater/donate.py

import requests, winreg, hashlib, platform, logging
from datetime import datetime
from typing import Optional, Dict, Tuple
from dataclasses import dataclass

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Константы
from config import REGISTRY_PATH_GUI
DEVICE_ID_VALUE = "DeviceID"
KEY_VALUE = "ActivationKey"
LAST_CHECK_VALUE = "LastCheck"

API_BASE_URL = "http://84.54.30.233:6666/api"
REQUEST_TIMEOUT = 10

# ============== DATA CLASSES ==============

@dataclass
class ActivationStatus:
    """Статус активации"""
    is_activated: bool
    days_remaining: Optional[int]
    expires_at: Optional[str]
    status_message: str
    subscription_level: str = "–"
    
    def get_formatted_expiry(self) -> str:
        """Форматированная информация об истечении"""
        if not self.is_activated:
            return "Не активировано"
        
        if self.days_remaining is not None:
            if self.days_remaining == 0:
                return "Истекает сегодня"
            elif self.days_remaining == 1:
                return "1 день"
            else:
                return f"{self.days_remaining} дн."
        
        return "Активировано"


# ============== REGISTRY MANAGER ==============

class RegistryManager:
    """Работа с реестром Windows"""
    
    @staticmethod
    def get_device_id() -> str:
        """Получить или создать Device ID"""
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REGISTRY_PATH_GUI) as key:
                device_id, _ = winreg.QueryValueEx(key, DEVICE_ID_VALUE)
                return device_id
        except:
            pass
        
        # Генерируем новый
        machine_info = f"{platform.machine()}-{platform.processor()}-{platform.node()}"
        device_id = hashlib.md5(machine_info.encode()).hexdigest()
        
        try:
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, REGISTRY_PATH_GUI) as key:
                winreg.SetValueEx(key, DEVICE_ID_VALUE, 0, winreg.REG_SZ, device_id)
            logger.info(f"Created Device ID: {device_id[:8]}...")
        except Exception as e:
            logger.error(f"Error saving device_id: {e}")
        
        return device_id
    
    @staticmethod
    def save_key(key: str) -> bool:
        """Сохранить ключ"""
        try:
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, REGISTRY_PATH_GUI) as reg_key:
                winreg.SetValueEx(reg_key, KEY_VALUE, 0, winreg.REG_SZ, key)
            logger.info(f"Key saved: {key[:4]}****")
            return True
        except Exception as e:
            logger.error(f"Error saving key: {e}")
            return False
    
    @staticmethod
    def get_key() -> Optional[str]:
        """Получить сохраненный ключ"""
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REGISTRY_PATH_GUI) as key:
                value, _ = winreg.QueryValueEx(key, KEY_VALUE)
                return value
        except:
            return None
    
    @staticmethod
    def delete_key() -> bool:
        """Удалить ключ"""
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REGISTRY_PATH_GUI, 0, winreg.KEY_SET_VALUE) as key:
                winreg.DeleteValue(key, KEY_VALUE)
            logger.info("Key deleted")
            return True
        except:
            return True
    
    @staticmethod
    def save_last_check() -> bool:
        """Сохранить время последней проверки"""
        try:
            timestamp = datetime.now().isoformat()
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, REGISTRY_PATH_GUI) as reg_key:
                winreg.SetValueEx(reg_key, LAST_CHECK_VALUE, 0, winreg.REG_SZ, timestamp)
            logger.debug(f"Last check saved: {timestamp}")
            return True
        except Exception as e:
            logger.error(f"Error saving last_check: {e}")
            return False
    
    @staticmethod
    def get_last_check() -> Optional[datetime]:
        """Получить время последней проверки"""
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REGISTRY_PATH_GUI) as key:
                timestamp_str, _ = winreg.QueryValueEx(key, LAST_CHECK_VALUE)
                return datetime.fromisoformat(timestamp_str)
        except:
            return None


# ============== API CLIENT ==============

class APIClient:
    """Клиент для API сервера"""
    
    def __init__(self, base_url: str = API_BASE_URL):
        self.base_url = base_url
        self.device_id = RegistryManager.get_device_id()
        logger.info(f"Device ID: {self.device_id[:8]}...")
    
    def _request(self, endpoint: str, method: str = "GET", data: Dict = None) -> Optional[Dict]:
        """Выполнить HTTP запрос"""
        url = f"{self.base_url}/{endpoint}"
        
        try:
            if method == "POST":
                response = requests.post(url, json=data, timeout=REQUEST_TIMEOUT)
            else:
                response = requests.get(url, timeout=REQUEST_TIMEOUT)
            
            # Пытаемся получить JSON даже при ошибке (сервер может вернуть описание ошибки)
            try:
                result = response.json()
            except:
                result = None
            
            if response.status_code == 200:
                return result
            else:
                logger.error(f"HTTP {response.status_code}: {endpoint}")
                # Возвращаем результат с ошибкой если он есть
                if result:
                    return result
                return {'success': False, 'error': f'Ошибка сервера: {response.status_code}'}
                
        except requests.exceptions.ConnectionError:
            logger.error(f"Connection error: {url}")
            return {'success': False, 'error': 'Нет подключения к серверу'}
        except requests.exceptions.Timeout:
            logger.error(f"Timeout: {url}")
            return {'success': False, 'error': 'Превышено время ожидания'}
        except Exception as e:
            logger.error(f"Request error: {e}")
            return {'success': False, 'error': f'Ошибка запроса: {e}'}
        
        return None
    
    def test_connection(self) -> Tuple[bool, str]:
        """Проверка соединения"""
        result = self._request("status")
        
        if result and result.get('success'):
            version = result.get('version', 'unknown')
            return True, f"API сервер доступен (v{version})"
        
        return False, "Сервер недоступен"
    
    def activate_key(self, key: str) -> Tuple[bool, str]:
        """Активация ключа"""
        logger.info(f"Activating key: {key[:4]}****")
        
        result = self._request("activate_key", "POST", {
            "key": key,
            "device_id": self.device_id
        })
        
        if result and result.get('success'):
            # Сохраняем ключ локально
            RegistryManager.save_key(key)
            # Сохраняем время проверки
            RegistryManager.save_last_check()
            
            message = result.get('message', 'Ключ активирован')
            logger.info(f"✅ Activation successful: {message}")
            return True, message
        
        error = result.get('error', 'Ошибка активации') if result else 'Сервер недоступен'
        logger.error(f"❌ Activation failed: {error}")
        return False, error
    
    def check_device_status(self) -> ActivationStatus:
        """Проверка статуса устройства"""
        # Пробуем API
        result = self._request("check_device", "POST", {"device_id": self.device_id})
        
        if result and result.get('success'):
            # Сохраняем время проверки при успешном ответе
            RegistryManager.save_last_check()
            
            if result.get('activated'):
                # Активировано
                return ActivationStatus(
                    is_activated=True,
                    days_remaining=result.get('days_remaining'),
                    expires_at=result.get('expires_at'),
                    status_message=result.get('message', 'Активировано'),
                    subscription_level=result.get('subscription_level', 'zapretik')
                )
            else:
                # Не активировано
                return ActivationStatus(
                    is_activated=False,
                    days_remaining=None,
                    expires_at=None,
                    status_message=result.get('message', 'Не активировано'),
                    subscription_level='–'
                )
        
        # API недоступен - offline режим
        logger.warning("API unavailable, using offline mode")
        
        saved_key = RegistryManager.get_key()
        if saved_key:
            # Если есть ключ - считаем что активировано
            return ActivationStatus(
                is_activated=True,
                days_remaining=None,
                expires_at=None,
                status_message='Активировано (offline)',
                subscription_level='zapretik'
            )
        
        # Нет ключа
        return ActivationStatus(
            is_activated=False,
            days_remaining=None,
            expires_at=None,
            status_message='Не активировано',
            subscription_level='–'
        )


# ============== MAIN CLASS ==============

class SimpleDonateChecker:
    """Главный класс (совместимость со старым кодом)"""
    
    def __init__(self):
        self.api_client = APIClient()
        self.device_id = self.api_client.device_id
    
    def activate(self, key: str) -> Tuple[bool, str]:
        """Активировать ключ"""
        return self.api_client.activate_key(key)
    
    def check_device_activation(self) -> Dict:
        """Проверить активацию устройства"""
        status = self.api_client.check_device_status()
        
        return {
            'found': RegistryManager.get_key() is not None,
            'activated': status.is_activated,
            'days_remaining': status.days_remaining,
            'status': status.status_message,
            'expires_at': status.expires_at,
            'level': 'Premium' if status.subscription_level != '–' else '–',
            'subscription_level': status.subscription_level
        }
    
    def get_full_subscription_info(self) -> Dict:
        """Полная информация о подписке"""
        info = self.check_device_activation()
        
        # ✅ Premium только если ЕСТЬ локальный ключ И сервер подтвердил активацию
        # Это синхронизирует логику с premium_page.py
        has_local_key = RegistryManager.get_key() is not None
        is_premium = info['activated'] and has_local_key
        
        # Если сервер говорит activated, но ключа нет локально - статус "требуется активация"
        if info['activated'] and not has_local_key:
            status_msg = "Требуется активация (введите ключ)"
        else:
            status_msg = info['status']
        
        return {
            'is_premium': is_premium,
            'status_msg': status_msg,
            'days_remaining': info['days_remaining'] if is_premium else None,
            'subscription_level': info['subscription_level'] if is_premium else '–'
        }
    
    # ✅ МЕТОД ДЛЯ ОБРАТНОЙ СОВМЕСТИМОСТИ
    def check_subscription_status(self, use_cache: bool = True) -> Tuple[bool, str, Optional[int]]:
        """
        Проверка статуса подписки (старый API для обратной совместимости)
        
        Args:
            use_cache: Игнорируется (для совместимости со старым API)
            
        Returns:
            Tuple[bool, str, Optional[int]]: (is_premium, status_message, days_remaining)
        """
        try:
            info = self.get_full_subscription_info()
            
            return (
                info['is_premium'],
                info['status_msg'],
                info['days_remaining']
            )
        except Exception as e:
            logger.error(f"Error in check_subscription_status: {e}")
            return (False, f"Ошибка проверки: {e}", None)
    
    def test_connection(self) -> Tuple[bool, str]:
        """Проверка соединения"""
        return self.api_client.test_connection()
    
    def clear_saved_key(self) -> bool:
        """Удалить сохраненный ключ"""
        return RegistryManager.delete_key()


# Алиас для совместимости
DonateChecker = SimpleDonateChecker