# dns/dns_force.py
"""
Менеджер принудительной установки DNS (упрощенная версия на Win32 API)
"""
from __future__ import annotations

import winreg
import time
from typing import List, Tuple, Optional, Dict
import socket

from log import log
from config import REGISTRY_PATH
from .dns_core import DNSManager, DEFAULT_EXCLUSIONS, _normalize_alias

# ──────────────────────────────────────────────────────────────────────
#  DNSForceManager
# ──────────────────────────────────────────────────────────────────────

class DNSForceManager:
    """Менеджер принудительной установки DNS"""
    
    FORCE_DNS_KEY = "ForceDNS"
    
    # DNS серверы
    DNS_PRIMARY = "8.8.8.8"
    DNS_SECONDARY = "8.8.4.4"
    DNS_PRIMARY_V6 = "2001:4860:4860::8888"
    DNS_SECONDARY_V6 = "2001:4860:4860::8844"
    
    def __init__(self, status_callback=None):
        self.status_callback = status_callback
        self.dns_manager = DNSManager()
        self._ipv6_available = None
    
    def _set_status(self, text: str):
        """Обновляет статус"""
        if self.status_callback:
            self.status_callback(text)
        log(f"DNSForce: {text}", "DNS")
    
    @property
    def ipv6_available(self) -> bool:
        """Проверяет доступность IPv6 (с кешированием)"""
        if self._ipv6_available is None:
            self._ipv6_available = self.check_ipv6_connectivity()
        return self._ipv6_available
    
    @staticmethod
    def check_ipv6_connectivity() -> bool:
        """Быстрая проверка IPv6"""
        try:
            # Пробуем создать IPv6 сокет
            sock = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
            sock.settimeout(1)
            try:
                sock.connect(('2001:4860:4860::8888', 53))
                sock.close()
                return True
            except:
                sock.close()
                return False
        except:
            return False
    
    def is_force_dns_enabled(self) -> bool:
        """Проверяет, включен ли принудительный DNS"""
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REGISTRY_PATH) as key:
                value, _ = winreg.QueryValueEx(key, self.FORCE_DNS_KEY)
                return bool(value)
        except:
            return True  # По умолчанию включен
    
    def set_force_dns_enabled(self, enabled: bool):
        """Устанавливает состояние принудительного DNS"""
        try:
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, REGISTRY_PATH) as key:
                winreg.SetValueEx(key, self.FORCE_DNS_KEY, 0, winreg.REG_DWORD, int(enabled))
            log(f"ForceDNS = {enabled}", "DNS")
        except Exception as e:
            log(f"Error setting ForceDNS: {e}", "ERROR")
    
    def get_excluded_adapters(self) -> List[str]:
        """Возвращает список исключений"""
        return [x.lower() for x in DEFAULT_EXCLUSIONS]
    
    def is_adapter_excluded(self, adapter_name: str) -> bool:
        """Проверяет, исключен ли адаптер"""
        exclusions = self.get_excluded_adapters()
        adapter_lower = adapter_name.lower()
        
        for exclusion in exclusions:
            if exclusion in adapter_lower:
                return True
        return False
    
    def get_network_adapters(
        self,
        include_disconnected: bool = False,
        apply_exclusions: bool = False,
        use_cache: bool = True
    ) -> List[str]:
        """Получает список подходящих адаптеров (без VPN/виртуальных)"""
        pairs = self.dns_manager.get_network_adapters_fast(
            include_ignored=False,  # Исключает VPN, виртуальные адаптеры и т.д.
            include_disconnected=include_disconnected
        )
        
        adapters = []
        for name, desc in pairs:
            # apply_exclusions больше не применяется - используем только include_ignored
            adapters.append(name)
        
        return adapters
    
    def set_dns_for_adapter(
        self,
        adapter_name: str,
        primary_dns: str,
        secondary_dns: Optional[str] = None,
        ip_version: str = 'ipv4'
    ) -> bool:
        """Устанавливает DNS для адаптера"""
        try:
            family = "IPv4" if ip_version == 'ipv4' else "IPv6"
            
            success, msg = self.dns_manager.set_custom_dns(
                adapter_name,
                primary_dns,
                secondary_dns,
                family
            )
            
            if success:
                log(f"{family} DNS set for {adapter_name}: {primary_dns}", "DNS")
            else:
                log(f"Failed to set {family} DNS for {adapter_name}: {msg}", "ERROR")
            
            return success
            
        except Exception as e:
            log(f"Error setting DNS for {adapter_name}: {e}", "ERROR")
            return False
    
    def force_dns_on_all_adapters(
        self,
        include_disconnected: bool = True,
        enable_ipv6: bool = True
    ) -> Tuple[int, int]:
        """Применяет DNS ко всем адаптерам"""
        
        if not self.is_force_dns_enabled():
            log("Force DNS disabled", "DNS")
            return (0, 0)
        
        self._set_status("Getting adapters...")
        
        adapters = self.get_network_adapters(include_disconnected=include_disconnected)
        
        if not adapters:
            self._set_status("No adapters found")
            return (0, 0)
        
        # Проверяем IPv6
        if enable_ipv6 and not self.ipv6_available:
            log("IPv6 not available, skipping IPv6 DNS", "DEBUG")
            enable_ipv6 = False
        
        success_count = 0
        total = len(adapters)
        
        for i, adapter in enumerate(adapters):
            self._set_status(f"Setting DNS for {adapter} ({i+1}/{total})...")
            
            # IPv4
            ipv4_ok = self.set_dns_for_adapter(
                adapter,
                self.DNS_PRIMARY,
                self.DNS_SECONDARY,
                'ipv4'
            )
            
            # IPv6
            ipv6_ok = True
            if enable_ipv6:
                ipv6_ok = self.set_dns_for_adapter(
                    adapter,
                    self.DNS_PRIMARY_V6,
                    self.DNS_SECONDARY_V6,
                    'ipv6'
                )
            
            if ipv4_ok and ipv6_ok:
                success_count += 1
        
        # Очищаем кэш
        self.dns_manager.flush_dns_cache()
        
        msg = f"DNS set: {success_count}/{total}"
        if not enable_ipv6:
            msg += " (IPv6 skipped)"
        
        self._set_status(msg)
        return (success_count, total)
    
    def get_dns_for_adapter(self, adapter_name: str, ip_version: str = 'ipv4') -> List[str]:
        """Получает DNS адаптера"""
        family = "IPv4" if ip_version == 'ipv4' else "IPv6"
        return self.dns_manager.get_current_dns(adapter_name, family)
    
    def reset_dns_to_auto(self, adapter_name: str, ip_version: Optional[str] = None) -> bool:
        """Сбрасывает DNS на автоматический"""
        family = None if ip_version is None else ("IPv4" if ip_version == 'ipv4' else "IPv6")
        success, _ = self.dns_manager.set_auto_dns(adapter_name, family)
        return success
    
    def get_all_adapters_with_status(self) -> List[Dict]:
        """Возвращает список всех адаптеров со статусом"""
        all_adapters = []
        
        pairs = self.dns_manager.get_network_adapters_fast(
            include_ignored=True,
            include_disconnected=True
        )
        
        for name, desc in pairs:
            adapter_info = {
                'name': name,
                'description': desc,
                'excluded': self.is_adapter_excluded(name),
                'current_dns_v4': self.get_dns_for_adapter(name, 'ipv4'),
                'current_dns_v6': self.get_dns_for_adapter(name, 'ipv6') if self.ipv6_available else []
            }
            all_adapters.append(adapter_info)
        
        return all_adapters
    
    def enable_force_dns(self, include_disconnected: bool = True) -> Tuple[bool, int, int, str]:
        """
        Включает принудительный DNS
        
        Returns:
            Tuple[bool, int, int, str]: (успех, количество_успешных, всего_адаптеров, сообщение)
        """
        try:
            # Включаем опцию в реестре
            self.set_force_dns_enabled(True)
            
            # Применяем DNS
            log("Применение принудительного DNS...", "DNS")
            success, total = self.force_dns_on_all_adapters(
                include_disconnected=include_disconnected,
                enable_ipv6=self.ipv6_available
            )
            
            if success > 0:
                msg = (
                    f"DNS успешно установлен на {success} из {total} адаптеров.\n\n"
                    f"IPv4: {self.DNS_PRIMARY}\n"
                    f"IPv6: {self.DNS_PRIMARY_V6 if self.ipv6_available else 'не применён'}\n\n"
                    "Изменения вступили в силу немедленно."
                )
                log(f"Принудительный DNS включен: {success}/{total} адаптеров", "INFO")
                return (True, success, total, msg)
            else:
                msg = (
                    "Не удалось установить DNS ни на одном адаптере.\n"
                    "Возможно, требуются права администратора."
                )
                # Откатываем настройку
                self.set_force_dns_enabled(False)
                return (False, 0, total, msg)
                
        except Exception as e:
            log(f"Ошибка включения Force DNS: {e}", "ERROR")
            self.set_force_dns_enabled(False)
            return (False, 0, 0, str(e))
    
    def disable_force_dns(self) -> Tuple[bool, str]:
        """
        Отключает принудительный DNS и сбрасывает на автоматическое получение

        Returns:
            Tuple[bool, str]: (успех, сообщение)
        """
        try:
            # Отключаем опцию в реестре
            self.set_force_dns_enabled(False)

            # Сбрасываем на автоматическое получение
            return self._reset_to_auto()

        except Exception as e:
            log(f"Ошибка отключения Force DNS: {e}", "ERROR")
            return (False, str(e))
    
    def _reset_to_auto(self) -> Tuple[bool, str]:
        """Сбрасывает DNS на автоматическое получение на всех адаптерах"""
        log("Сброс DNS на автоматическое получение...", "DNS")
        
        adapters = self.get_network_adapters(include_disconnected=True)
        success_count = 0
        
        for adapter in adapters:
            # Сбрасываем IPv4
            if self.reset_dns_to_auto(adapter, 'ipv4'):
                success_count += 1
            
            # Сбрасываем IPv6 (если доступен)
            if self.ipv6_available:
                self.reset_dns_to_auto(adapter, 'ipv6')
        
        # Очищаем кэш DNS
        self.dns_manager.flush_dns_cache()
        
        if success_count > 0:
            msg = f"DNS сброшен на автоматическое получение на {success_count} из {len(adapters)} адаптеров."
            log(f"DNS сброшен на авто: {success_count}/{len(adapters)} адаптеров", "INFO")
            return (True, msg)
        else:
            msg = "Не удалось сбросить DNS ни на одном адаптере."
            return (False, msg)
        
# ──────────────────────────────────────────────────────────────────────
#  Утилиты
# ──────────────────────────────────────────────────────────────────────

def ensure_default_force_dns():
    """Создает ключ ForceDNS по умолчанию"""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REGISTRY_PATH):
            return
    except FileNotFoundError:
        try:
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, REGISTRY_PATH) as key:
                winreg.SetValueEx(key, DNSForceManager.FORCE_DNS_KEY, 0, winreg.REG_DWORD, 1)
            log("Created default ForceDNS=1", "DNS")
        except Exception as e:
            log(f"Error creating ForceDNS key: {e}", "ERROR")