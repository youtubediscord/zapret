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

    def create_hosts_runtime(self, *, status_callback=None):
        return self._hosts.create_hosts_runtime(status_callback=status_callback)

    def get_hosts_state(self, hosts_runtime):
        return self._hosts.get_hosts_state(hosts_runtime)

    def get_hosts_path_str(self) -> str:
        return self._hosts.get_hosts_path_str()

    def read_active_domains_map(self, hosts_runtime) -> dict[str, str]:
        return self._hosts.read_active_domains_map(hosts_runtime)

    def get_catalog_signature(self):
        return self._hosts.get_catalog_signature()

    def invalidate_catalog_cache(self) -> None:
        self._hosts.invalidate_catalog_cache()

    def restore_hosts_permissions(self):
        return self._hosts.restore_hosts_permissions()

    def open_hosts_file(self):
        return self._hosts.open_hosts_file()

    def execute_hosts_operation(self, hosts_runtime, operation: str, payload):
        return self._hosts.execute_hosts_operation(hosts_runtime, operation, payload)
