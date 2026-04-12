# utils/validators.py
"""
Utilities for network address validation
"""
import ipaddress
from typing import Tuple


class IPValidator:
    """IP address validator"""

    @staticmethod
    def is_valid_ipv4(address: str) -> bool:
        """
        Checks if the address is a valid IPv4 address

        Args:
            address: String with IP address

        Returns:
            True if valid IPv4, otherwise False
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
        Checks if the address is a valid IPv6 address

        Args:
            address: String with IP address

        Returns:
            True if valid IPv6, otherwise False
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
        Validates IP address of the specified family

        Args:
            address: String with IP address
            family: "IPv4" or "IPv6"

        Returns:
            True if valid IP address of the specified family
        """
        if family.lower() == "ipv6":
            return IPValidator.is_valid_ipv6(address)
        else:
            return IPValidator.is_valid_ipv4(address)


class DNSValidator:
    """DNS configuration validator"""

    @staticmethod
    def validate_dns_pair(
        primary: str,
        secondary: str = None,
        family: str = "IPv4"
    ) -> Tuple[bool, str]:
        """
        Validates a pair of DNS addresses

        Args:
            primary: Primary DNS
            secondary: Secondary DNS (optional)
            family: "IPv4" or "IPv6"

        Returns:
            Tuple (valid, error message)
        """
        if not primary or not primary.strip():
            return False, "Primary DNS not specified"

        primary = primary.strip()

        # Validate primary DNS
        if not IPValidator.is_valid_ip(primary, family):
            family_name = "IPv6" if family.lower() == "ipv6" else "IPv4"
            return False, f"Invalid {family_name} format: {primary}"

        # Validate secondary DNS (if specified)
        if secondary and secondary.strip():
            secondary = secondary.strip()
            if not IPValidator.is_valid_ip(secondary, family):
                family_name = "IPv6" if family.lower() == "ipv6" else "IPv4"
                return False, f"Invalid {family_name} format (secondary): {secondary}"

        return True, "OK"

    @staticmethod
    def validate_dual_stack_dns(
        ipv4_primary: str = None,
        ipv4_secondary: str = None,
        ipv6_primary: str = None,
        ipv6_secondary: str = None,
    ) -> Tuple[bool, str]:
        """
        Validates dual-stack DNS configuration (IPv4 + IPv6)

        Args:
            ipv4_primary: Primary IPv4 DNS
            ipv4_secondary: Secondary IPv4 DNS
            ipv6_primary: Primary IPv6 DNS
            ipv6_secondary: Secondary IPv6 DNS

        Returns:
            Tuple (valid, error message)
        """
        # Validate IPv4 (if specified)
        if ipv4_primary and ipv4_primary.strip():
            valid, msg = DNSValidator.validate_dns_pair(
                ipv4_primary, ipv4_secondary, "IPv4"
            )
            if not valid:
                return valid, msg

        # Validate IPv6 (if specified)
        if ipv6_primary and ipv6_primary.strip():
            valid, msg = DNSValidator.validate_dns_pair(
                ipv6_primary, ipv6_secondary, "IPv6"
            )
            if not valid:
                return valid, msg

        # Check that at least one family is specified
        if not ipv4_primary and not ipv4_secondary and not ipv6_primary and not ipv6_secondary:
            return False, "DNS servers not specified"

        return True, "OK"
