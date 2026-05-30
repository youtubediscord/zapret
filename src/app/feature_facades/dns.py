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
    create_dns_check_save_worker: Callable
    create_dns_quick_check_worker: Callable
    create_page_load_worker: Callable
    create_connectivity_test_worker: Callable
    create_force_dns_action_worker: Callable
    create_dns_flush_cache_worker: Callable
    create_isp_dns_warning_worker: Callable
    create_dns_apply_worker: Callable
    enable_force_dns: Callable
    disable_force_dns: Callable
    flush_dns_cache: Callable
    run_connectivity_test: Callable
    run_dns_poisoning_check: Callable
    save_dns_check_results: Callable
    run_quick_dns_check: Callable


def build_dns_feature() -> DnsFeature:
    def _commands():
        from dns import commands as dns_commands

        return dns_commands

    def _public():
        from dns import public as dns_public

        return dns_public

    def _create_force_dns_action_worker(
        request_id: int,
        *,
        action: str,
        enabled=None,
        adapters=None,
        language: str = "ru",
        parent=None,
    ):
        from dns.page_workers import DnsForceDnsActionWorker

        return DnsForceDnsActionWorker(
            request_id,
            action=action,
            enabled=enabled,
            adapters=adapters,
            language=language,
            get_force_dns_status=feature.get_force_dns_status,
            enable_force_dns=feature.enable_force_dns,
            disable_force_dns=feature.disable_force_dns,
            refresh_dns_info=feature.refresh_dns_info,
            parent=parent,
        )

    def _create_dns_flush_cache_worker(
        request_id: int,
        *,
        language: str = "ru",
        parent=None,
    ):
        from dns.page_workers import DnsFlushCacheWorker

        return DnsFlushCacheWorker(
            request_id,
            language=language,
            flush_dns_cache=feature.flush_dns_cache,
            parent=parent,
        )

    def _create_isp_dns_warning_worker(
        request_id: int,
        *,
        adapters,
        dns_info: dict,
        force_dns_active: bool,
        language: str = "ru",
        parent=None,
    ):
        from dns.page_workers import DnsIspWarningWorker

        return DnsIspWarningWorker(
            request_id,
            adapters=adapters,
            dns_info=dns_info,
            force_dns_active=force_dns_active,
            language=language,
            is_isp_dns_warning_shown=feature.is_isp_dns_warning_shown,
            mark_isp_dns_warning_shown=feature.mark_isp_dns_warning_shown,
            normalize_adapter_alias=feature.normalize_adapter_alias,
            parent=parent,
        )

    def _create_dns_apply_worker(
        request_id: int,
        *,
        action: str,
        adapters,
        name: str = "",
        data=None,
        primary: str = "",
        secondary: str | None = None,
        ipv6_available: bool = False,
        parent=None,
    ):
        from dns.page_workers import DnsApplyWorker

        return DnsApplyWorker(
            request_id,
            action=action,
            adapters=adapters,
            name=name,
            data=data,
            primary=primary,
            secondary=secondary,
            ipv6_available=ipv6_available,
            apply_auto_dns=feature.apply_auto_dns,
            apply_provider_dns=feature.apply_provider_dns,
            apply_custom_dns=feature.apply_custom_dns,
            refresh_dns_info=feature.refresh_dns_info,
            parent=parent,
        )

    def _create_page_load_worker(request_id: int, *, parent=None):
        from dns.page_workers import DnsPageLoadWorker

        return DnsPageLoadWorker(request_id, feature.load_page_data, parent)

    def _create_connectivity_test_worker(request_id: int, *, test_hosts, parent=None):
        from dns.page_workers import DnsConnectivityTestWorker

        return DnsConnectivityTestWorker(
            request_id,
            feature.run_connectivity_test,
            test_hosts,
            parent,
        )

    def _create_dns_check_worker():
        from dns.dns_check_worker import DNSCheckWorker

        return DNSCheckWorker(
            run_dns_poisoning_check=feature.run_dns_poisoning_check,
        )

    def _create_dns_check_save_worker(request_id: int, *, file_path: str, plain_text: str, parent=None):
        from dns.dns_check_worker import DNSCheckSaveWorker

        return DNSCheckSaveWorker(
            request_id,
            file_path=file_path,
            plain_text=plain_text,
            save_dns_check_results=feature.save_dns_check_results,
            parent=parent,
        )

    def _create_dns_quick_check_worker(request_id: int, *, parent=None):
        from dns.dns_check_worker import DNSQuickCheckWorker

        return DNSQuickCheckWorker(
            request_id,
            run_quick_dns_check=feature.run_quick_dns_check,
            parent=parent,
        )

    feature = DnsFeature(
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
        create_dns_check_worker=_create_dns_check_worker,
        create_dns_check_save_worker=_create_dns_check_save_worker,
        create_dns_quick_check_worker=_create_dns_quick_check_worker,
        create_page_load_worker=_create_page_load_worker,
        create_connectivity_test_worker=_create_connectivity_test_worker,
        create_force_dns_action_worker=_create_force_dns_action_worker,
        create_dns_flush_cache_worker=_create_dns_flush_cache_worker,
        create_isp_dns_warning_worker=_create_isp_dns_warning_worker,
        create_dns_apply_worker=_create_dns_apply_worker,
        enable_force_dns=lambda *args, **kwargs: _public().enable_force_dns(*args, **kwargs),
        disable_force_dns=lambda *args, **kwargs: _public().disable_force_dns(*args, **kwargs),
        flush_dns_cache=lambda *args, **kwargs: _public().flush_dns_cache(*args, **kwargs),
        run_connectivity_test=lambda *args, **kwargs: _public().run_connectivity_test(*args, **kwargs),
        run_dns_poisoning_check=lambda *args, **kwargs: _commands().run_dns_poisoning_check(*args, **kwargs),
        save_dns_check_results=lambda *args, **kwargs: _commands().save_dns_check_results(*args, **kwargs),
        run_quick_dns_check=lambda *args, **kwargs: _commands().run_quick_dns_check(*args, **kwargs),
    )
    return feature
