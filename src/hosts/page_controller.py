"""Контроллер Hosts page без привязки к QWidget."""

from __future__ import annotations


class HostsPageController:
    """Единая точка доступа страницы Hosts к hosts feature."""

    def __init__(self, hosts_feature) -> None:
        self._hosts = hosts_feature

    def create_selection_save_worker(self, request_id: int, selection: dict[str, str], parent=None):
        return self._hosts.create_selection_save_worker(request_id, selection, parent=parent)

    def create_selection_load_worker(self, request_id: int, parent=None):
        return self._hosts.create_selection_load_worker(request_id, parent=parent)

    def create_state_load_worker(self, request_id: int, hosts_runtime, parent=None):
        return self._hosts.create_state_load_worker(request_id, hosts_runtime, parent=parent)

    def create_open_hosts_file_worker(self, request_id: int, parent=None):
        return self._hosts.create_open_hosts_file_worker(request_id, parent=parent)

    def create_permission_restore_worker(self, request_id: int, parent=None):
        return self._hosts.create_permission_restore_worker(request_id, parent=parent)

    def create_operation_worker(self, *, hosts_runtime, operation: str, payload=None):
        return self._hosts.create_operation_worker(
            hosts_runtime=hosts_runtime,
            operation=operation,
            payload=payload,
        )

    def create_hosts_runtime(self, *, status_callback=None):
        return self._hosts.create_hosts_runtime(status_callback=status_callback)

    def get_hosts_path_str(self) -> str:
        return self._hosts.get_hosts_path_str()

    def create_services_catalog_worker(self, **kwargs):
        return self._hosts.create_services_catalog_worker(**kwargs)

    def create_catalog_refresh_worker(self, request_id: int, *, trigger: str, parent=None):
        return self._hosts.create_catalog_refresh_worker(request_id, trigger=trigger, parent=parent)

    def invalidate_catalog_cache(self) -> None:
        self._hosts.invalidate_catalog_cache()
