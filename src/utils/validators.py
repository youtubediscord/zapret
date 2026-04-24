# utils/validators.py
"""
Утилиты для валидации сетевых адресов
"""
import ipaddress
from typing import Tuple


class IPValidator:
    """Валидатор IP-адресов"""
    
    @staticmethod
    def is_valid_ipv4(address: str) -> bool:
        """
        Проверяет, является ли адрес валидным IPv4
        
        Args:
            address: Строка с IP-адресом
            
        Returns:
            True если валидный IPv4, иначе False
        """
        if not address or not address.strip():
            return False
        try:
            ipaddress.IPv4Address(address.strip())
            return True
        except (ValueError, ipaddress.AddressValueError):
            return False
    
    @staticmethod
    def is_valid_ipv6(address: str) -> bool:
        """
        Проверяет, является ли адрес валидным IPv6
        
        Args:
            address: Строка с IP-адресом
            
        Returns:
            True если валидный IPv6, иначе False
        """
        if not address or not address.strip():
            return False
        try:
            ipaddress.IPv6Address(address.strip())
            return True
        except (ValueError, ipaddress.AddressValueError):
            return False
    
    @staticmethod
    def is_valid_ip(address: str, family: str = "IPv4") -> bool:
        """
        Проверяет валидность IP-адреса указанного семейства
        
        Args:
            address: Строка с IP-адресом
            family: "IPv4" или "IPv6"
            
        Returns:
            True если валидный адрес указанного семейства
        """
        if family.lower() == "ipv6":
            return IPValidator.is_valid_ipv6(address)
        else:
            return IPValidator.is_valid_ipv4(address)


class DNSValidator:
    """Валидатор DNS-конфигурации"""
    
    @staticmethod
    def validate_dns_pair(
        primary: str,
        secondary: str = None,
        family: str = "IPv4"
    ) -> Tuple[bool, str]:
        """
        Валидирует пару DNS-адресов
        
        Args:
            primary: Первичный DNS
            secondary: Вторичный DNS (опционально)
            family: "IPv4" или "IPv6"
            
        Returns:
            Кортеж (валидно, сообщение об ошибке)
        """
        if not primary or not primary.strip():
            return False, "Первичный DNS не указан"
        
        primary = primary.strip()
        
        # Валидация первичного DNS
        if not IPValidator.is_valid_ip(primary, family):
            family_name = "IPv6" if family.lower() == "ipv6" else "IPv4"
            return False, f"Неверный формат {family_name}: {primary}"
        
        # Валидация вторичного DNS (если указан)
        if secondary and secondary.strip():
            secondary = secondary.strip()
            if not IPValidator.is_valid_ip(secondary, family):
                family_name = "IPv6" if family.lower() == "ipv6" else "IPv4"
                return False, f"Неверный формат {family_name} (вторичный): {secondary}"
        
        return True, "OK"
    
    @staticmethod
    def validate_dual_stack_dns(
        ipv4_primary: str = None,
        ipv4_secondary: str = None,
        ipv6_primary: str = None,
        ipv6_secondary: str = None,
    ) -> Tuple[bool, str]:
        """
        Валидирует dual-stack DNS конфигурацию (IPv4 + IPv6)
        
        Args:
            ipv4_primary: Первичный IPv4 DNS
            ipv4_secondary: Вторичный IPv4 DNS
            ipv6_primary: Первичный IPv6 DNS
            ipv6_secondary: Вторичный IPv6 DNS
            
        Returns:
            Кортеж (валидно, сообщение об ошибке)
        """
        # Валидация IPv4 (если указан)
        if ipv4_primary and ipv4_primary.strip():
            valid, msg = DNSValidator.validate_dns_pair(
                ipv4_primary, ipv4_secondary, "IPv4"
            )
            if not valid:
                return valid, msg
        
        # Валидация IPv6 (если указан)
        if ipv6_primary and ipv6_primary.strip():
            valid, msg = DNSValidator.validate_dns_pair(
                ipv6_primary, ipv6_secondary, "IPv6"
            )
            if not valid:
                return valid, msg
        
        # Проверка что хотя бы одно семейство указано
        if not ipv4_primary and not ipv4_secondary and not ipv6_primary and not ipv6_secondary:
            return False, "Не указаны DNS-серверы"
        
        return True, "OK"
