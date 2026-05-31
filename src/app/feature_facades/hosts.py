from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True, slots=True)
class HostsFeature:
    warm_page_data_cache: Callable
    create_hosts_runtime: Callable
    get_hosts_path_str: Callable
    invalidate_catalog_cache: Callable
    create_selection_save_worker: Callable
    create_selection_load_worker: Callable
    create_state_load_worker: Callable
    create_open_hosts_file_worker: Callable
    create_permission_restore_worker: Callable
    create_operation_worker: Callable
    create_services_catalog_worker: Callable
    create_catalog_refresh_worker: Callable


def build_hosts_feature() -> HostsFeature:
    def _public():
        from hosts import public as hosts_public

        return hosts_public

    def _warm_page_data_cache() -> bool:
        public = _public()
        public.load_user_selection()
        public.get_catalog_signature()
        return True

    load_user_selection = lambda *args, **kwargs: _public().load_user_selection(*args, **kwargs)
    save_user_selection = lambda *args, **kwargs: _public().save_user_selection(*args, **kwargs)
    get_hosts_state = lambda *args, **kwargs: _public().get_hosts_state(*args, **kwargs)
    get_catalog_signature = lambda *args, **kwargs: _public().get_catalog_signature(*args, **kwargs)
    build_services_catalog_plan = lambda *args, **kwargs: _public().build_services_catalog_plan(*args, **kwargs)
    restore_hosts_permissions = lambda *args, **kwargs: _public().restore_hosts_permissions(*args, **kwargs)
    open_hosts_file = lambda *args, **kwargs: _public().open_hosts_file(*args, **kwargs)
    execute_hosts_operation = lambda *args, **kwargs: _public().execute_hosts_operation(*args, **kwargs)

    def _create_selection_save_worker(request_id: int, selection: dict[str, str], parent=None):
        from hosts.selection_save_worker import HostsSelectionSaveWorker

        return HostsSelectionSaveWorker(
            request_id,
            selection,
            save_user_selection=save_user_selection,
            parent=parent,
        )

    def _create_selection_load_worker(request_id: int, parent=None):
        from hosts.selection_load_worker import HostsSelectionLoadWorker

        return HostsSelectionLoadWorker(
            request_id,
            load_user_selection=load_user_selection,
            parent=parent,
        )

    def _create_state_load_worker(request_id: int, hosts_runtime, parent=None):
        from hosts.state_load_worker import HostsStateLoadWorker

        return HostsStateLoadWorker(
            request_id,
            hosts_runtime,
            get_hosts_state=get_hosts_state,
            parent=parent,
        )

    def _create_open_hosts_file_worker(request_id: int, parent=None):
        from hosts.open_file_worker import HostsOpenFileWorker

        return HostsOpenFileWorker(
            request_id,
            open_hosts_file=open_hosts_file,
            parent=parent,
        )

    def _create_permission_restore_worker(request_id: int, parent=None):
        from hosts.permission_restore_worker import HostsPermissionRestoreWorker

        return HostsPermissionRestoreWorker(
            request_id,
            restore_hosts_permissions=restore_hosts_permissions,
            parent=parent,
        )

    def _create_operation_worker(*, hosts_runtime, operation: str, payload=None):
        from hosts.operation_worker import HostsOperationWorker

        return HostsOperationWorker(
            hosts_runtime,
            operation,
            payload,
            execute_hosts_operation_fn=execute_hosts_operation,
        )

    def _create_services_catalog_worker(**kwargs):
        from hosts.services_catalog_worker import HostsServicesCatalogWorker

        return HostsServicesCatalogWorker(
            build_services_catalog_plan=build_services_catalog_plan,
            get_catalog_signature=get_catalog_signature,
            **kwargs,
        )

    def _create_catalog_refresh_worker(request_id: int, *, trigger: str, parent=None):
        from hosts.catalog_refresh_worker import HostsCatalogRefreshWorker

        return HostsCatalogRefreshWorker(
            request_id,
            trigger,
            get_catalog_signature=get_catalog_signature,
            parent=parent,
        )

    return HostsFeature(
        warm_page_data_cache=_warm_page_data_cache,
        create_hosts_runtime=lambda *args, **kwargs: _public().create_hosts_runtime(*args, **kwargs),
        get_hosts_path_str=lambda *args, **kwargs: _public().get_hosts_path_str(*args, **kwargs),
        invalidate_catalog_cache=lambda *args, **kwargs: _public().invalidate_catalog_cache(*args, **kwargs),
        create_selection_save_worker=_create_selection_save_worker,
        create_selection_load_worker=_create_selection_load_worker,
        create_state_load_worker=_create_state_load_worker,
        create_open_hosts_file_worker=_create_open_hosts_file_worker,
        create_permission_restore_worker=_create_permission_restore_worker,
        create_operation_worker=_create_operation_worker,
        create_services_catalog_worker=_create_services_catalog_worker,
        create_catalog_refresh_worker=_create_catalog_refresh_worker,
    )
