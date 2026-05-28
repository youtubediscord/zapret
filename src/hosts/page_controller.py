"""Контроллер Hosts page без привязки к QWidget."""

from __future__ import annotations

import hosts.page_plans as hosts_page_plans


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

        return HostsSelectionSaveWorker(request_id, self, selection, parent)

    def create_selection_load_worker(self, request_id: int, parent=None):
        from hosts.selection_load_worker import HostsSelectionLoadWorker

        return HostsSelectionLoadWorker(request_id, self, parent)

    def create_state_load_worker(self, request_id: int, hosts_runtime, parent=None):
        from hosts.state_load_worker import HostsStateLoadWorker

        return HostsStateLoadWorker(request_id, self, hosts_runtime, parent)

    def create_hosts_runtime(self, *, status_callback=None):
        return self._hosts.create_hosts_runtime(status_callback=status_callback)

    def get_hosts_state(self, hosts_runtime):
        return self._hosts.get_hosts_state(hosts_runtime)

    def get_hosts_path_str(self) -> str:
        return self._hosts.get_hosts_path_str()

    def read_active_domains_map(self, hosts_runtime) -> dict[str, str]:
        return self._hosts.read_active_domains_map(hosts_runtime)

    def build_services_catalog_plan(
        self,
        *,
        hosts_runtime,
        current_selection: dict[str, str],
        direct_title: str,
        ai_title: str,
        other_title: str,
    ):
        active_domains_map = self.read_active_domains_map(hosts_runtime)
        return hosts_page_plans.build_services_catalog_plan(
            current_selection=current_selection,
            active_domains_map=active_domains_map,
            direct_title=direct_title,
            ai_title=ai_title,
            other_title=other_title,
        )

    def create_services_catalog_worker(self, **kwargs):
        from hosts.services_catalog_worker import HostsServicesCatalogWorker

        return HostsServicesCatalogWorker(controller=self, **kwargs)

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
