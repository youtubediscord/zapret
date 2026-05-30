from __future__ import annotations

import inspect
import unittest

import hosts.commands as hosts_commands
import hosts.services_catalog_worker as services_catalog_worker
from hosts.page_controller import HostsPageController


class HostsServicesCatalogWorkerArchitectureTests(unittest.TestCase):
    def test_services_catalog_worker_receives_feature_actions_not_controller(self) -> None:
        self.assertTrue(hasattr(hosts_commands, "build_services_catalog_plan"))

        controller_source = inspect.getsource(HostsPageController.create_services_catalog_worker)
        worker_source = inspect.getsource(services_catalog_worker.HostsServicesCatalogWorker)
        command_source = inspect.getsource(hosts_commands.build_services_catalog_plan)

        self.assertNotIn("controller=self", controller_source)
        self.assertNotIn("self._controller", worker_source)
        self.assertIn("build_services_catalog_plan=self._hosts.build_services_catalog_plan", controller_source)
        self.assertIn("get_catalog_signature=self._hosts.get_catalog_signature", controller_source)
        self.assertIn("_build_services_catalog_plan", worker_source)
        self.assertIn("_get_catalog_signature", worker_source)
        self.assertNotIn("hosts.commands", worker_source)
        self.assertIn("read_active_domains_map", command_source)


if __name__ == "__main__":
    unittest.main()
