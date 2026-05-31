from __future__ import annotations

import inspect
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch


PROJECT_SRC = Path(__file__).resolve().parents[1] / "src"
if str(PROJECT_SRC) not in sys.path:
    sys.path.insert(0, str(PROJECT_SRC))


class HostsPageRuntimeTests(unittest.TestCase):
    def test_hosts_feature_does_not_expose_heavy_direct_actions(self) -> None:
        from app.feature_facades.hosts import build_hosts_feature
        from hosts.page_controller import HostsPageController

        feature = build_hosts_feature()
        controller = HostsPageController(feature)

        for attr_name in (
            "load_user_selection",
            "save_user_selection",
            "get_hosts_state",
            "read_active_domains_map",
            "get_catalog_signature",
            "build_services_catalog_plan",
            "restore_hosts_permissions",
            "open_hosts_file",
            "execute_hosts_operation",
        ):
            self.assertFalse(hasattr(feature, attr_name), attr_name)
            self.assertFalse(hasattr(controller, attr_name), attr_name)

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
        self.assertIn("self._hosts.create_selection_save_worker", controller_source)
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

    def test_user_selection_save_pending_restarts_after_event_loop_turn(self) -> None:
        import hosts.ui.page as hosts_page
        from hosts.ui.page import HostsPage

        page = HostsPage.__new__(HostsPage)
        page._cleanup_in_progress = False
        page._selection_save_pending = {"service": "profile"}
        page._request_user_selection_save = Mock()
        single_shot = Mock(side_effect=lambda _delay, _callback: None)

        with patch.object(hosts_page, "QTimer", SimpleNamespace(singleShot=single_shot), create=True):
            HostsPage._on_user_selection_save_worker_finished(page, object())

        single_shot.assert_called_once()
        self.assertEqual(single_shot.call_args.args[0], 0)
        page._request_user_selection_save.assert_not_called()

        single_shot.call_args.args[1]()

        page._request_user_selection_save.assert_called_once_with({"service": "profile"})

    def test_user_selection_save_request_waits_while_restart_is_scheduled(self) -> None:
        from hosts.ui.page import HostsPage

        page = HostsPage.__new__(HostsPage)
        page._selection_save_start_scheduled = True
        page._selection_save_pending = None
        page._selection_save_runtime = SimpleNamespace(is_running=Mock(return_value=False), start_qthread_worker=Mock())

        HostsPage._request_user_selection_save(page, {"service": "latest"})

        page._selection_save_runtime.start_qthread_worker.assert_not_called()
        self.assertEqual(page._selection_save_pending, {"service": "latest"})

    def test_catalog_refresh_pending_restarts_after_event_loop_turn(self) -> None:
        import hosts.ui.page as hosts_page
        from hosts.ui.page import HostsPage

        page = HostsPage.__new__(HostsPage)
        page._cleanup_in_progress = False
        page._catalog_refresh_pending_trigger = "watcher"
        page._refresh_catalog_if_needed = Mock()
        single_shot = Mock(side_effect=lambda _delay, _callback: None)

        with patch.object(hosts_page, "QTimer", SimpleNamespace(singleShot=single_shot), create=True):
            HostsPage._on_catalog_refresh_worker_finished(page, object())

        single_shot.assert_called_once()
        self.assertEqual(single_shot.call_args.args[0], 0)
        page._refresh_catalog_if_needed.assert_not_called()

        single_shot.call_args.args[1]()

        page._refresh_catalog_if_needed.assert_called_once_with("watcher")

    def test_catalog_refresh_request_waits_while_restart_is_scheduled(self) -> None:
        from hosts.ui.page import HostsPage

        page = HostsPage.__new__(HostsPage)
        page._catalog_refresh_start_scheduled = True
        page._catalog_refresh_pending_trigger = ""
        page._catalog_refresh_runtime = SimpleNamespace(is_running=Mock(return_value=False), start_qthread_worker=Mock())

        HostsPage._refresh_catalog_if_needed(page, "watcher")

        page._catalog_refresh_runtime.start_qthread_worker.assert_not_called()
        self.assertEqual(page._catalog_refresh_pending_trigger, "watcher")

    def test_open_hosts_file_pending_restarts_after_event_loop_turn(self) -> None:
        import hosts.ui.page as hosts_page
        from hosts.ui.page import HostsPage

        page = HostsPage.__new__(HostsPage)
        page._cleanup_in_progress = False
        page._open_file_pending = True
        page._request_open_hosts_file = Mock()
        single_shot = Mock(side_effect=lambda _delay, _callback: None)

        with patch.object(hosts_page, "QTimer", SimpleNamespace(singleShot=single_shot), create=True):
            HostsPage._on_open_hosts_file_worker_finished(page, object())

        single_shot.assert_called_once()
        self.assertEqual(single_shot.call_args.args[0], 0)
        page._request_open_hosts_file.assert_not_called()

        single_shot.call_args.args[1]()

        page._request_open_hosts_file.assert_called_once_with()

    def test_open_hosts_file_request_waits_while_restart_is_scheduled(self) -> None:
        from hosts.ui.page import HostsPage

        page = HostsPage.__new__(HostsPage)
        page._open_file_start_scheduled = True
        page._open_file_pending = False
        page._open_file_runtime = SimpleNamespace(is_running=Mock(return_value=False), start_qthread_worker=Mock())

        HostsPage._request_open_hosts_file(page)

        page._open_file_runtime.start_qthread_worker.assert_not_called()
        self.assertTrue(page._open_file_pending)

    def test_hosts_state_pending_restarts_after_event_loop_turn(self) -> None:
        import hosts.ui.page as hosts_page
        from hosts.ui.page import HostsPage

        page = HostsPage.__new__(HostsPage)
        page._cleanup_in_progress = False
        page._state_load_pending = {"show_access_errors": True, "update_status": True}
        page._request_hosts_state_load = Mock()
        single_shot = Mock(side_effect=lambda _delay, _callback: None)

        with patch.object(hosts_page, "QTimer", SimpleNamespace(singleShot=single_shot), create=True):
            HostsPage._on_hosts_state_worker_finished(page, object())

        single_shot.assert_called_once()
        self.assertEqual(single_shot.call_args.args[0], 0)
        page._request_hosts_state_load.assert_not_called()

        single_shot.call_args.args[1]()

        page._request_hosts_state_load.assert_called_once_with(
            show_access_errors=True,
            update_status=True,
        )

    def test_hosts_state_request_waits_while_restart_is_scheduled(self) -> None:
        from hosts.ui.page import HostsPage

        page = HostsPage.__new__(HostsPage)
        page._cleanup_in_progress = False
        page._state_load_start_scheduled = True
        page._state_load_pending = {"show_access_errors": False, "update_status": False}
        page._state_load_runtime = SimpleNamespace(is_running=Mock(return_value=False), start_qthread_worker=Mock())

        HostsPage._request_hosts_state_load(
            page,
            show_access_errors=True,
            update_status=False,
        )

        page._state_load_runtime.start_qthread_worker.assert_not_called()
        self.assertEqual(page._state_load_pending, {"show_access_errors": True, "update_status": False})

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
        self.assertIn("self._hosts.create_catalog_refresh_worker", controller_source)
        self.assertIn("_get_catalog_signature", worker_source)
        self.assertNotIn("hosts.commands", worker_source)
        self.assertNotIn("self._controller", worker_source)

    def test_hosts_operation_worker_is_created_by_controller(self) -> None:
        from hosts.page_controller import HostsPageController
        from hosts.ui.page import HostsPage
        import hosts.operation_workflow as operation_workflow

        controller_source = inspect.getsource(HostsPageController)
        workflow_source = inspect.getsource(operation_workflow.start_hosts_operation)
        page_init_source = inspect.getsource(HostsPage.__init__)
        run_source = inspect.getsource(HostsPage._run_operation)
        cleanup_source = inspect.getsource(HostsPage.cleanup)

        self.assertIn("create_operation_worker", controller_source)
        self.assertIn("self._hosts.create_operation_worker", controller_source)
        self.assertIn("_operation_runtime = OneShotWorkerRuntime()", page_init_source)
        self.assertIn("operation_runtime=self._operation_runtime", run_source)
        self.assertIn("start_qobject_worker", workflow_source)
        self.assertIn("create_operation_worker_fn", workflow_source)
        self.assertIn("create_operation_worker_fn(", workflow_source)
        self.assertIn("create_operation_worker_fn=self._controller.create_operation_worker", run_source)
        self.assertIn("_operation_runtime.stop", cleanup_source)
        self.assertIn("_operation_runtime.cancel", cleanup_source)
        self.assertNotIn("QThread", workflow_source)
        self.assertNotIn("thread.start()", workflow_source)
        self.assertNotIn("moveToThread", workflow_source)
        self.assertNotIn("execute_hosts_operation_fn=self._controller.execute_hosts_operation", run_source)


if __name__ == "__main__":
    unittest.main()
