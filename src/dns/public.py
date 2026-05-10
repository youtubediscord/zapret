from __future__ import annotations

from typing import Any

__all__ = [
    "DNSCheckPage",
    "DNS_PROVIDERS",
    "DnsCommandResult",
    "DnsState",
    "apply_auto_dns",
    "apply_custom_dns",
    "apply_provider_dns",
    "check_ipv6_connectivity",
    "disable_force_dns",
    "enable_force_dns",
    "apply_dns_on_startup_async",
    "flush_dns_cache",
    "get_adapters_info_native",
    "get_dns_state",
    "get_force_dns_status",
    "load_page_data",
    "refresh_dns_info",
]


def __getattr__(name: str) -> Any:
    if name == "DNSCheckPage":
        from dns.ui.dns_check_page import DNSCheckPage

        return DNSCheckPage
    if name == "DNS_PROVIDERS":
        from dns.dns_providers import DNS_PROVIDERS

        return DNS_PROVIDERS
    if name == "DnsState":
        from dns.state import DnsState

        return DnsState
    if name == "DnsCommandResult":
        from dns.state import DnsCommandResult

        return DnsCommandResult
    if name == "apply_dns_on_startup_async":
        from dns.commands import apply_dns_on_startup_async

        return apply_dns_on_startup_async
    if name == "get_adapters_info_native":
        from dns.commands import get_adapters_info_native

        return get_adapters_info_native
    if name == "get_force_dns_status":
        from dns.commands import get_force_dns_status

        return get_force_dns_status
    if name == "check_ipv6_connectivity":
        from dns.commands import check_ipv6_connectivity

        return check_ipv6_connectivity
    if name == "get_dns_state":
        from dns.commands import get_dns_state

        return get_dns_state
    if name == "load_page_data":
        from dns.commands import load_page_data

        return load_page_data
    if name == "refresh_dns_info":
        from dns.commands import refresh_dns_info

        return refresh_dns_info
    if name == "apply_auto_dns":
        from dns.commands import apply_auto_dns

        return apply_auto_dns
    if name == "apply_provider_dns":
        from dns.commands import apply_provider_dns

        return apply_provider_dns
    if name == "apply_custom_dns":
        from dns.commands import apply_custom_dns

        return apply_custom_dns
    if name == "enable_force_dns":
        from dns.commands import enable_force_dns

        return enable_force_dns
    if name == "disable_force_dns":
        from dns.commands import disable_force_dns

        return disable_force_dns
    if name == "flush_dns_cache":
        from dns.commands import flush_dns_cache

        return flush_dns_cache
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
