from __future__ import annotations

from dns.state import DnsCommandResult, DnsState


def apply_dns_on_startup_async(status_callback=None):
    from dns.dns_worker import apply_dns_on_startup_async as _apply_dns_on_startup_async

    return _apply_dns_on_startup_async(status_callback=status_callback)


def get_adapters_info_native():
    from dns.dns_core import get_adapters_info_native as _get_adapters_info_native

    return _get_adapters_info_native()


def get_force_dns_status() -> bool:
    from dns.network_page_controller import NetworkPageController

    return NetworkPageController.get_force_dns_status()


def check_ipv6_connectivity() -> bool:
    from dns.network_page_controller import NetworkPageController

    return NetworkPageController.detect_ipv6_availability()


def enable_force_dns(*, include_disconnected: bool = False) -> DnsCommandResult:
    from dns.network_page_controller import NetworkPageController

    success, ok_count, total, message = NetworkPageController.enable_force_dns(
        include_disconnected=include_disconnected,
    )
    return DnsCommandResult(
        success=bool(success),
        message=str(message or ""),
        affected_count=int(ok_count or 0),
        total_count=int(total or 0),
    )


def disable_force_dns(*, reset_to_auto: bool) -> DnsCommandResult:
    from dns.network_page_controller import NetworkPageController

    success, message = NetworkPageController.disable_force_dns(reset_to_auto=reset_to_auto)
    return DnsCommandResult(success=bool(success), message=str(message or ""))


def flush_dns_cache() -> DnsCommandResult:
    from dns.network_page_controller import NetworkPageController

    success, message = NetworkPageController.flush_dns_cache()
    return DnsCommandResult(success=bool(success), message=str(message or ""))


def get_dns_state() -> DnsState:
    from dns.network_page_controller import NetworkPageController

    data = NetworkPageController.load_page_data()
    return DnsState(
        adapters=tuple(data.adapters),
        dns_info=dict(data.dns_info),
        ipv6_available=bool(data.ipv6_available),
        force_dns_enabled=bool(data.force_dns_active),
    )


def load_page_data() -> DnsState:
    return get_dns_state()


def refresh_dns_info(adapter_names: list[str]) -> dict[str, dict[str, list[str]]]:
    from dns.network_page_controller import NetworkPageController

    return NetworkPageController.refresh_dns_info(adapter_names)


def apply_auto_dns(adapters: list[str]) -> DnsCommandResult:
    from dns.network_page_controller import NetworkPageController

    success_count = NetworkPageController.apply_auto_dns(adapters)
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
    from dns.network_page_controller import NetworkPageController

    success_count = NetworkPageController.apply_provider_dns(
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
    from dns.network_page_controller import NetworkPageController

    success_count = NetworkPageController.apply_custom_dns(adapters, primary, secondary)
    total = len(adapters or [])
    return DnsCommandResult(
        success=success_count > 0 or total == 0,
        affected_count=int(success_count or 0),
        total_count=total,
    )
