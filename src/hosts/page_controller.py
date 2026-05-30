"""Контроллер Hosts page без привязки к QWidget."""

from __future__ import annotations


class HostsPageController:
    """Единая точка доступа страницы Hosts к hosts feature."""

    def __init__(self, hosts_feature) -> None:
        self._hosts = hosts_feature

    def load_user_selection(self) -> dict[str, str]:
        return self._hosts.load_user_selection()

    def save_user_selection(self, selection: dict[str, str]) -> bool:
        return bool(self._hosts.save_user_selection(selection))

    def create_selection_save_worker(self, request_id: int, selection: dict[str, str], parent=None):
        from hosts.selection_save_worker import HostsSelectionSaveWorker

        return HostsSelectionSaveWorker(
            request_id,
            selection,
            save_user_selection=self._hosts.save_user_selection,
            parent=parent,
        )

    def create_selection_load_worker(self, request_id: int, parent=None):
        from hosts.selection_load_worker import HostsSelectionLoadWorker

        return HostsSelectionLoadWorker(
            request_id,
            load_user_selection=self._hosts.load_user_selection,
            parent=parent,
        )

    def create_state_load_worker(self, request_id: int, hosts_runtime, parent=None):
        from hosts.state_load_worker import HostsStateLoadWorker

        return HostsStateLoadWorker(
            request_id,
            hosts_runtime,
            get_hosts_state=self._hosts.get_hosts_state,
            parent=parent,
        )

    def create_open_hosts_file_worker(self, request_id: int, parent=None):
        from hosts.open_file_worker import HostsOpenFileWorker

        return HostsOpenFileWorker(
            request_id,
            open_hosts_file=self._hosts.open_hosts_file,
            parent=parent,
        )

    def create_permission_restore_worker(self, request_id: int, parent=None):
        from hosts.permission_restore_worker import HostsPermissionRestoreWorker

        return HostsPermissionRestoreWorker(
            request_id,
            restore_hosts_permissions=self._hosts.restore_hosts_permissions,
            parent=parent,
        )

    def create_operation_worker(self, *, hosts_runtime, operation: str, payload=None):
        from hosts.operation_worker import HostsOperationWorker

        return HostsOperationWorker(
            hosts_runtime,
            operation,
            payload,
            execute_hosts_operation_fn=self._hosts.execute_hosts_operation,
        )

    def create_hosts_runtime(self, *, status_callback=None):
        return self._hosts.create_hosts_runtime(status_callback=status_callback)

    def get_hosts_state(self, hosts_runtime):
        return self._hosts.get_hosts_state(hosts_runtime)

    def get_hosts_path_str(self) -> str:
        return self._hosts.get_hosts_path_str()

    def read_active_domains_map(self, hosts_runtime) -> dict[str, str]:
        return self._hosts.read_active_domains_map(hosts_runtime)

    def create_services_catalog_worker(self, **kwargs):
        from hosts.services_catalog_worker import HostsServicesCatalogWorker

        return HostsServicesCatalogWorker(
            build_services_catalog_plan=self._hosts.build_services_catalog_plan,
            get_catalog_signature=self._hosts.get_catalog_signature,
            **kwargs,
        )

    def create_catalog_refresh_worker(self, request_id: int, *, trigger: str, parent=None):
        from hosts.catalog_refresh_worker import HostsCatalogRefreshWorker

        return HostsCatalogRefreshWorker(
            request_id,
            trigger,
            get_catalog_signature=self._hosts.get_catalog_signature,
            parent=parent,
        )

    def get_catalog_signature(self):
        return self._hosts.get_catalog_signature()

    def invalidate_catalog_cache(self) -> None:
        self._hosts.invalidate_catalog_cache()

    def restore_hosts_permissions(self):
        return self._hosts.restore_hosts_permissions()

    def open_hosts_file(self):
        return self._hosts.open_hosts_file()
