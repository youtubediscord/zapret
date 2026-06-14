from __future__ import annotations

from dataclasses import dataclass
from threading import RLock

from log.log import log


@dataclass(slots=True)
class NetworkPageData:
    adapters: list[tuple[str, str]]
    dns_info: dict[str, dict[str, list[str]]]
    ipv6_available: bool
    force_dns_active: bool


_dns_manager_instance = None
_warmed_page_data_cache: NetworkPageData | None = None
_warmed_page_data_lock = RLock()


def _new_dns_manager():
    from dns.dns_core import DNSManager

    return DNSManager()


def _new_force_dns_manager():
    from dns.dns_force import DNSForceManager

    return DNSForceManager()


def _get_dns_manager():
    global _dns_manager_instance
    if _dns_manager_instance is None:
        _dns_manager_instance = _new_dns_manager()
    return _dns_manager_instance


def detect_ipv6_availability() -> bool:
    try:
        from dns.dns_force import DNSForceManager

        return bool(DNSForceManager.check_ipv6_connectivity())
    except Exception as exc:
        log(f"Ошибка проверки IPv6 у провайдера: {exc}", "DEBUG")
        return False


def load_page_data() -> NetworkPageData:
    ipv6_available = detect_ipv6_availability()

    from dns.dns_force import ensure_default_force_dns

    dns_manager = _get_dns_manager()
    adapters = dns_manager.get_network_adapters_fast(
        include_ignored=False,
        include_disconnected=True,
    )
    adapter_names = [name for name, _ in adapters]
    dns_info = dns_manager.get_all_dns_info_fast(adapter_names)

    ensure_default_force_dns()
    force_dns_active = _new_force_dns_manager().is_force_dns_enabled()

    return NetworkPageData(
        adapters=adapters,
        dns_info=dns_info,
        ipv6_available=ipv6_available,
        force_dns_active=force_dns_active,
    )


def store_warmed_page_data(state: NetworkPageData) -> NetworkPageData:
    global _warmed_page_data_cache
    with _warmed_page_data_lock:
        _warmed_page_data_cache = state
    return state


def clear_warmed_page_data_cache() -> None:
    global _warmed_page_data_cache
    with _warmed_page_data_lock:
        _warmed_page_data_cache = None


def consume_warmed_page_data() -> NetworkPageData | None:
    global _warmed_page_data_cache
    with _warmed_page_data_lock:
        state = _warmed_page_data_cache
        _warmed_page_data_cache = None
    return state


def warm_page_data_cache() -> NetworkPageData:
    return store_warmed_page_data(load_page_data())


def refresh_dns_info(adapter_names: list[str]) -> dict[str, dict[str, list[str]]]:
    return _get_dns_manager().get_all_dns_info_fast(adapter_names)


def apply_auto_dns(adapters: list[str]) -> int:
    dns_manager = _get_dns_manager()
    success_count = 0
    for adapter in adapters:
        ok_v4, _ = dns_manager.set_auto_dns(adapter, "IPv4")
        ok_v6, _ = dns_manager.set_auto_dns(adapter, "IPv6")
        if ok_v4 and ok_v6:
            success_count += 1
    dns_manager.flush_dns_cache()
    return success_count


def apply_provider_dns(
    adapters: list[str],
    ipv4: list[str],
    ipv6: list[str],
    *,
    ipv6_available: bool,
) -> int:
    dns_manager = _get_dns_manager()
    success_count = 0
    for adapter in adapters:
        ok_v4 = True
        if ipv4:
            ok_v4, _ = dns_manager.set_custom_dns(
                adapter,
                ipv4[0],
                ipv4[1] if len(ipv4) > 1 else None,
                "IPv4",
            )
        ok_v6 = True
        if ipv6_available and ipv6:
            ok_v6, _ = dns_manager.set_custom_dns(
                adapter,
                ipv6[0],
                ipv6[1] if len(ipv6) > 1 else None,
                "IPv6",
            )
        if ok_v4 and ok_v6:
            success_count += 1
    dns_manager.flush_dns_cache()
    return success_count


def apply_custom_dns(adapters: list[str], primary: str, secondary: str | None) -> int:
    dns_manager = _get_dns_manager()
    success_count = 0
    for adapter in adapters:
        ok, _ = dns_manager.set_custom_dns(adapter, primary, secondary, "IPv4")
        if ok:
            success_count += 1
    dns_manager.flush_dns_cache()
    return success_count


def get_force_dns_status() -> bool:
    return _new_force_dns_manager().is_force_dns_enabled()


def enable_force_dns(
    *,
    include_disconnected: bool = False,
    adapters: list[str] | None = None,
) -> tuple[bool, int, int, str]:
    return _new_force_dns_manager().enable_force_dns(
        include_disconnected=include_disconnected,
        adapters=adapters,
    )


def disable_force_dns(
    *,
    reset_to_auto: bool,
    adapters: list[str] | None = None,
) -> tuple[bool, str]:
    return _new_force_dns_manager().disable_force_dns(
        reset_to_auto=reset_to_auto,
        adapters=adapters,
    )


def flush_dns_cache() -> tuple[bool, str]:
    return _get_dns_manager().flush_dns_cache()
