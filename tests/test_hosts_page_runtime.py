from __future__ import annotations

import inspect
import sys
import unittest
from pathlib import Path


PROJECT_SRC = Path(__file__).resolve().parents[1] / "src"
if str(PROJECT_SRC) not in sys.path:
    sys.path.insert(0, str(PROJECT_SRC))


class HostsPageRuntimeTests(unittest.TestCase):
    def test_page_controller_passes_status_callback_to_hosts_runtime(self) -> None:
        from hosts.page_controller import HostsPageController
        from hosts.ui.page_runtime import create_page_hosts_runtime

        captured = {}

        class HostsFeature:
            def create_hosts_runtime(self, *, status_callback=None):
                captured["status_callback"] = status_callback
                return "runtime"

        controller = HostsPageController(HostsFeature())

        runtime = create_page_hosts_runtime(controller.create_hosts_runtime)

        self.assertEqual(runtime, "runtime")
        self.assertTrue(callable(captured["status_callback"]))

    def test_user_selection_save_runs_through_worker(self) -> None:
        from hosts.page_controller import HostsPageController
        from hosts.ui.page import HostsPage
        import hosts.commands as hosts_commands
        import hosts.selection_save_worker as selection_save_worker

        self.assertTrue(hasattr(selection_save_worker, "HostsSelectionSaveWorker"))
        worker_source = inspect.getsource(selection_save_worker.HostsSelectionSaveWorker.run)
        controller_source = inspect.getsource(HostsPageController)
        init_source = inspect.getsource(HostsPage.__init__)
        request_source = inspect.getsource(HostsPage._request_user_selection_save)
        finished_source = inspect.getsource(HostsPage._on_user_selection_save_worker_finished)

        self.assertIn("create_selection_save_worker", controller_source)
        self.assertIn("_selection_save_runtime", init_source)
        self.assertIn("start_qthread_worker", request_source)
        self.assertIn("_selection_save_pending", request_source)
        self.assertIn("_selection_save_pending", finished_source)
        self.assertIn("save_user_selection=self._hosts.save_user_selection", controller_source)
        self.assertIn("_save_user_selection", worker_source)
        self.assertNotIn("hosts.commands", worker_source)
        self.assertNotIn("self._controller", worker_source)
        self.assertIn("save_user_selection", inspect.getsource(hosts_commands.save_user_selection))

        for method_name in (
            "_bulk_apply_dns_profile",
            "_build_services_selectors",
            "_on_direct_toggle_changed",
            "_on_profile_changed",
            "_apply_current_selection",
            "_reset_all_service_profiles",
        ):
            source = inspect.getsource(getattr(HostsPage, method_name))
            self.assertIn("_request_user_selection_save", source)
            self.assertNotIn("_controller.save_user_selection", source)

    def test_catalog_refresh_signature_runs_through_worker(self) -> None:
        from hosts.page_controller import HostsPageController
        from hosts.ui.page import HostsPage
        import hosts.catalog_refresh_worker as catalog_refresh_worker

        controller_source = inspect.getsource(HostsPageController)
        page_init_source = inspect.getsource(HostsPage.__init__)
        refresh_source = inspect.getsource(HostsPage._refresh_catalog_if_needed)
        worker_source = inspect.getsource(catalog_refresh_worker.HostsCatalogRefreshWorker)

        self.assertIn("create_catalog_refresh_worker", controller_source)
        self.assertIn("_catalog_refresh_runtime", page_init_source)
        self.assertIn("start_qthread_worker", refresh_source)
        self.assertIn("create_catalog_refresh_worker", refresh_source)
        self.assertNotIn("get_catalog_signature_fn=self._controller.get_catalog_signature", refresh_source)
        self.assertIn("get_catalog_signature=self._hosts.get_catalog_signature", controller_source)
        self.assertIn("_get_catalog_signature", worker_source)
        self.assertNotIn("hosts.commands", worker_source)
        self.assertNotIn("self._controller", worker_source)

    def test_hosts_operation_worker_is_created_by_controller(self) -> None:
        from hosts.page_controller import HostsPageController
        from hosts.ui.page import HostsPage
        import hosts.operation_workflow as operation_workflow

        controller_source = inspect.getsource(HostsPageController)
        workflow_source = inspect.getsource(operation_workflow.start_hosts_operation)
        run_source = inspect.getsource(HostsPage._run_operation)

        self.assertIn("create_operation_worker", controller_source)
        self.assertIn("execute_hosts_operation_fn=self._hosts.execute_hosts_operation", controller_source)
        self.assertIn("create_operation_worker_fn", workflow_source)
        self.assertIn("create_operation_worker_fn(", workflow_source)
        self.assertIn("create_operation_worker_fn=self._controller.create_operation_worker", run_source)
        self.assertNotIn("execute_hosts_operation_fn=self._controller.execute_hosts_operation", run_source)


if __name__ == "__main__":
    unittest.main()
