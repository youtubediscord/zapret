from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True, slots=True)
class HostsFeature:
    load_user_selection: Callable
    create_hosts_runtime: Callable
    get_hosts_state: Callable
    get_hosts_path_str: Callable
    read_active_domains_map: Callable
    save_user_selection: Callable
    ensure_ipv6_catalog_sections: Callable
    get_catalog_signature: Callable
    invalidate_catalog_cache: Callable
    restore_hosts_permissions: Callable
    open_hosts_file: Callable
    execute_hosts_operation: Callable


def build_hosts_feature() -> HostsFeature:
    from hosts import public as hosts_public

    return HostsFeature(
        load_user_selection=hosts_public.load_user_selection,
        create_hosts_runtime=hosts_public.create_hosts_runtime,
        get_hosts_state=hosts_public.get_hosts_state,
        get_hosts_path_str=hosts_public.get_hosts_path_str,
        read_active_domains_map=hosts_public.read_active_domains_map,
        save_user_selection=hosts_public.save_user_selection,
        ensure_ipv6_catalog_sections=hosts_public.ensure_ipv6_catalog_sections,
        get_catalog_signature=hosts_public.get_catalog_signature,
        invalidate_catalog_cache=hosts_public.invalidate_catalog_cache,
        restore_hosts_permissions=hosts_public.restore_hosts_permissions,
        open_hosts_file=hosts_public.open_hosts_file,
        execute_hosts_operation=hosts_public.execute_hosts_operation,
    )
