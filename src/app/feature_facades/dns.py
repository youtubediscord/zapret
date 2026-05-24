from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True, slots=True)
class DnsFeature:
    apply_dns_on_startup_async: Callable
    load_page_data: Callable
    warm_page_data_cache: Callable
    consume_warmed_page_data: Callable
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
    def _commands():
        from dns import commands as dns_commands

        return dns_commands

    def _public():
        from dns import public as dns_public

        return dns_public

    return DnsFeature(
        apply_dns_on_startup_async=lambda *args, **kwargs: _public().apply_dns_on_startup_async(*args, **kwargs),
        load_page_data=lambda *args, **kwargs: _public().load_page_data(*args, **kwargs),
        warm_page_data_cache=lambda *args, **kwargs: _public().warm_page_data_cache(*args, **kwargs),
        consume_warmed_page_data=lambda *args, **kwargs: _public().consume_warmed_page_data(*args, **kwargs),
        refresh_dns_info=lambda *args, **kwargs: _public().refresh_dns_info(*args, **kwargs),
        apply_auto_dns=lambda *args, **kwargs: _public().apply_auto_dns(*args, **kwargs),
        apply_provider_dns=lambda *args, **kwargs: _public().apply_provider_dns(*args, **kwargs),
        apply_custom_dns=lambda *args, **kwargs: _public().apply_custom_dns(*args, **kwargs),
        normalize_adapter_alias=lambda *args, **kwargs: _public().normalize_adapter_alias(*args, **kwargs),
        get_force_dns_status=lambda *args, **kwargs: _public().get_force_dns_status(*args, **kwargs),
        is_isp_dns_warning_shown=lambda *args, **kwargs: _public().is_isp_dns_warning_shown(*args, **kwargs),
        mark_isp_dns_warning_shown=lambda *args, **kwargs: _public().mark_isp_dns_warning_shown(*args, **kwargs),
        create_dns_check_worker=lambda *args, **kwargs: _commands().create_dns_check_worker(*args, **kwargs),
        enable_force_dns=lambda *args, **kwargs: _public().enable_force_dns(*args, **kwargs),
        disable_force_dns=lambda *args, **kwargs: _public().disable_force_dns(*args, **kwargs),
        flush_dns_cache=lambda *args, **kwargs: _public().flush_dns_cache(*args, **kwargs),
        run_connectivity_test=lambda *args, **kwargs: _public().run_connectivity_test(*args, **kwargs),
    )
