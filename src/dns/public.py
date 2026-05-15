from __future__ import annotations

from dns.commands import (
    apply_auto_dns,
    apply_custom_dns,
    apply_dns_on_startup_async,
    apply_provider_dns,
    check_ipv6_connectivity,
    disable_force_dns,
    enable_force_dns,
    flush_dns_cache,
    get_adapters_info_native,
    get_dns_state,
    get_force_dns_status,
    is_isp_dns_warning_shown,
    load_page_data,
    mark_isp_dns_warning_shown,
    normalize_adapter_alias,
    refresh_dns_info,
    run_connectivity_test,
)
from dns.dns_providers import DNS_PROVIDERS
from dns.state import DnsCommandResult, DnsState


__all__ = [
    "DNS_PROVIDERS",
    "DnsCommandResult",
    "DnsState",
    "apply_auto_dns",
    "apply_custom_dns",
    "apply_dns_on_startup_async",
    "apply_provider_dns",
    "check_ipv6_connectivity",
    "disable_force_dns",
    "enable_force_dns",
    "flush_dns_cache",
    "get_adapters_info_native",
    "get_dns_state",
    "get_force_dns_status",
    "is_isp_dns_warning_shown",
    "load_page_data",
    "mark_isp_dns_warning_shown",
    "normalize_adapter_alias",
    "refresh_dns_info",
    "run_connectivity_test",
]
