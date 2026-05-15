from __future__ import annotations

from dns.state import DnsCommandResult, DnsState


def apply_dns_on_startup_async(status_callback=None):
    from dns.dns_worker import apply_dns_on_startup_async as _apply_dns_on_startup_async

    return _apply_dns_on_startup_async(status_callback=status_callback)


def get_adapters_info_native():
    from dns.dns_core import get_adapters_info_native as _get_adapters_info_native

    return _get_adapters_info_native()


def normalize_adapter_alias(alias: str) -> str:
    from dns.dns_core import _normalize_alias

    return _normalize_alias(alias)


def get_force_dns_status() -> bool:
    from dns.runtime import get_force_dns_status as _get_force_dns_status

    return _get_force_dns_status()


def is_isp_dns_warning_shown() -> bool:
    from settings.store import get_isp_dns_info_shown

    return bool(get_isp_dns_info_shown())


def mark_isp_dns_warning_shown() -> bool:
    from settings.store import set_isp_dns_info_shown

    return bool(set_isp_dns_info_shown(True))


def create_dns_check_worker():
    from dns.dns_check_worker import DNSCheckWorker

    return DNSCheckWorker()


def check_ipv6_connectivity() -> bool:
    from dns.runtime import detect_ipv6_availability

    return detect_ipv6_availability()


def enable_force_dns(*, include_disconnected: bool = False) -> DnsCommandResult:
    from dns.runtime import enable_force_dns as _enable_force_dns

    success, ok_count, total, message = _enable_force_dns(
        include_disconnected=include_disconnected,
    )
    return DnsCommandResult(
        success=bool(success),
        message=str(message or ""),
        affected_count=int(ok_count or 0),
        total_count=int(total or 0),
    )


def disable_force_dns(*, reset_to_auto: bool) -> DnsCommandResult:
    from dns.runtime import disable_force_dns as _disable_force_dns

    success, message = _disable_force_dns(reset_to_auto=reset_to_auto)
    return DnsCommandResult(success=bool(success), message=str(message or ""))


def flush_dns_cache() -> DnsCommandResult:
    from dns.runtime import flush_dns_cache as _flush_dns_cache

    success, message = _flush_dns_cache()
    return DnsCommandResult(success=bool(success), message=str(message or ""))


def get_dns_state() -> DnsState:
    from dns.runtime import load_page_data as _load_page_data

    data = _load_page_data()
    return DnsState(
        adapters=tuple(data.adapters),
        dns_info=dict(data.dns_info),
        ipv6_available=bool(data.ipv6_available),
        force_dns_enabled=bool(data.force_dns_active),
    )


def load_page_data() -> DnsState:
    return get_dns_state()


def refresh_dns_info(adapter_names: list[str]) -> dict[str, dict[str, list[str]]]:
    from dns.runtime import refresh_dns_info as _refresh_dns_info

    return _refresh_dns_info(adapter_names)


def apply_auto_dns(adapters: list[str]) -> DnsCommandResult:
    from dns.runtime import apply_auto_dns as _apply_auto_dns

    success_count = _apply_auto_dns(adapters)
    total = len(adapters or [])
    return DnsCommandResult(
        success=success_count > 0 or total == 0,
        affected_count=int(success_count or 0),
        total_count=total,
    )


def apply_provider_dns(
    adapters: list[str],
    ipv4: list[str],
    ipv6: list[str],
    *,
    ipv6_available: bool,
) -> DnsCommandResult:
    from dns.runtime import apply_provider_dns as _apply_provider_dns

    success_count = _apply_provider_dns(
        adapters,
        ipv4,
        ipv6,
        ipv6_available=ipv6_available,
    )
    total = len(adapters or [])
    return DnsCommandResult(
        success=success_count > 0 or total == 0,
        affected_count=int(success_count or 0),
        total_count=total,
    )


def apply_custom_dns(adapters: list[str], primary: str, secondary: str | None) -> DnsCommandResult:
    from dns.runtime import apply_custom_dns as _apply_custom_dns

    success_count = _apply_custom_dns(adapters, primary, secondary)
    total = len(adapters or [])
    return DnsCommandResult(
        success=success_count > 0 or total == 0,
        affected_count=int(success_count or 0),
        total_count=total,
    )


def run_connectivity_test(test_hosts: list[tuple[str, str]]) -> list[tuple[str, str, bool]]:
    from utils.windows_icmp import ping_ipv4_host_winapi

    results: list[tuple[str, str, bool]] = []
    for name, host in test_hosts:
        try:
            ping_result = ping_ipv4_host_winapi(
                host,
                count=1,
                timeout_ms=2000,
            )
            results.append((name, host, ping_result.ok))
        except Exception:
            results.append((name, host, False))
    return results
