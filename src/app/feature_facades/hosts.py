from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True, slots=True)
class HostsFeature:
    load_user_selection: Callable
    warm_page_data_cache: Callable
    create_hosts_runtime: Callable
    get_hosts_state: Callable
    get_hosts_path_str: Callable
    read_active_domains_map: Callable
    save_user_selection: Callable
    get_catalog_signature: Callable
    build_services_catalog_plan: Callable
    invalidate_catalog_cache: Callable
    restore_hosts_permissions: Callable
    open_hosts_file: Callable
    execute_hosts_operation: Callable


def build_hosts_feature() -> HostsFeature:
    def _public():
        from hosts import public as hosts_public

        return hosts_public

    def _warm_page_data_cache() -> bool:
        public = _public()
        public.load_user_selection()
        public.get_catalog_signature()
        return True

    return HostsFeature(
        load_user_selection=lambda *args, **kwargs: _public().load_user_selection(*args, **kwargs),
        warm_page_data_cache=_warm_page_data_cache,
        create_hosts_runtime=lambda *args, **kwargs: _public().create_hosts_runtime(*args, **kwargs),
        get_hosts_state=lambda *args, **kwargs: _public().get_hosts_state(*args, **kwargs),
        get_hosts_path_str=lambda *args, **kwargs: _public().get_hosts_path_str(*args, **kwargs),
        read_active_domains_map=lambda *args, **kwargs: _public().read_active_domains_map(*args, **kwargs),
        save_user_selection=lambda *args, **kwargs: _public().save_user_selection(*args, **kwargs),
        get_catalog_signature=lambda *args, **kwargs: _public().get_catalog_signature(*args, **kwargs),
        build_services_catalog_plan=lambda *args, **kwargs: _public().build_services_catalog_plan(*args, **kwargs),
        invalidate_catalog_cache=lambda *args, **kwargs: _public().invalidate_catalog_cache(*args, **kwargs),
        restore_hosts_permissions=lambda *args, **kwargs: _public().restore_hosts_permissions(*args, **kwargs),
        open_hosts_file=lambda *args, **kwargs: _public().open_hosts_file(*args, **kwargs),
        execute_hosts_operation=lambda *args, **kwargs: _public().execute_hosts_operation(*args, **kwargs),
    )
