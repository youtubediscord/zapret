from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True, slots=True)
class DnsFeature:
    load_page_data: Callable
    refresh_dns_info: Callable
    apply_auto_dns: Callable
    apply_provider_dns: Callable
    apply_custom_dns: Callable
    normalize_adapter_alias: Callable
    get_force_dns_status: Callable
    is_isp_dns_warning_shown: Callable
    mark_isp_dns_warning_shown: Callable
    create_dns_check_worker: Callable
    enable_force_dns: Callable
    disable_force_dns: Callable
    flush_dns_cache: Callable
    run_connectivity_test: Callable


def build_dns_feature() -> DnsFeature:
    from dns import commands as dns_commands
    from dns import public as dns_public

    return DnsFeature(
        load_page_data=dns_public.load_page_data,
        refresh_dns_info=dns_public.refresh_dns_info,
        apply_auto_dns=dns_public.apply_auto_dns,
        apply_provider_dns=dns_public.apply_provider_dns,
        apply_custom_dns=dns_public.apply_custom_dns,
        normalize_adapter_alias=dns_public.normalize_adapter_alias,
        get_force_dns_status=dns_public.get_force_dns_status,
        is_isp_dns_warning_shown=dns_public.is_isp_dns_warning_shown,
        mark_isp_dns_warning_shown=dns_public.mark_isp_dns_warning_shown,
        create_dns_check_worker=dns_commands.create_dns_check_worker,
        enable_force_dns=dns_public.enable_force_dns,
        disable_force_dns=dns_public.disable_force_dns,
        flush_dns_cache=dns_public.flush_dns_cache,
        run_connectivity_test=dns_public.run_connectivity_test,
    )
