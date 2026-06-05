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
    def test_hosts_page_uses_feature_without_page_controller_wrapper(self) -> None:
        from hosts.ui.page import HostsPage

        page_source = inspect.getsource(HostsPage)
        init_source = inspect.getsource(HostsPage.__init__)
        run_source = inspect.getsource(HostsPage._run_operation)

        self.assertIn("self._hosts = deps.hosts_feature", init_source)
        self.assertNotIn("HostsPageController", page_source)
        self.assertNotIn("self._controller", page_source)
        self.assertIn("create_operation_worker_fn=self._hosts.create_operation_worker", run_source)

    def test_hosts_feature_does_not_expose_heavy_direct_actions(self) -> None:
        from app.feature_facades.hosts import build_hosts_feature

        feature = build_hosts_feature()

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

    def test_page_feature_passes_status_callback_to_hosts_runtime(self) -> None:
        from hosts.ui.page_runtime import create_page_hosts_runtime

        captured = {}

        class HostsFeature:
            def create_hosts_runtime(self, *, status_callback=None):
                captured["status_callback"] = status_callback
                return "runtime"

        runtime = create_page_hosts_runtime(HostsFeature().create_hosts_runtime)

        self.assertEqual(runtime, "runtime")
        self.assertTrue(callable(captured["status_callback"]))

    def test_adobe_section_uses_cached_state_instead_of_reading_hosts_in_ui_thread(self) -> None:
        import hosts.ui.page as hosts_page
        from hosts.ui.page import HostsPage

        page = HostsPage.__new__(HostsPage)
        page.hosts_runtime = SimpleNamespace(is_adobe_domains_active=Mock(side_effect=AssertionError("sync hosts read")))
        page._adobe_active = True
        page.add_section_title = Mock()
        page.add_widget = Mock()
        page._tr = Mock(side_effect=lambda _key, default, **_kwargs: default)

        widgets = SimpleNamespace(description_label=object(), title_label=object(), switch=object(), card=object())
        with patch.object(hosts_page, "build_hosts_adobe_section", return_value=widgets) as build_section:
            HostsPage._build_adobe_section(page)

        page.hosts_runtime.is_adobe_domains_active.assert_not_called()
        build_section.assert_called_once()
        self.assertTrue(build_section.call_args.kwargs["adobe_active"])

    def test_user_selection_save_runs_through_worker(self) -> None:
        from hosts.ui.page import HostsPage
        import hosts.commands as hosts_commands
        import hosts.selection_save_worker as selection_save_worker

        self.assertTrue(hasattr(selection_save_worker, "HostsSelectionSaveWorker"))
        worker_source = inspect.getsource(selection_save_worker.HostsSelectionSaveWorker.run)
        init_source = inspect.getsource(HostsPage.__init__)
        request_source = inspect.getsource(HostsPage._request_user_selection_save)
        finished_source = inspect.getsource(HostsPage._on_user_selection_save_worker_finished)

        self.assertIn("self._hosts = deps.hosts_feature", init_source)
        self.assertIn("_selection_save_runtime", init_source)
        self.assertIn("start_qthread_worker", request_source)
        self.assertIn("_selection_save_pending", request_source)
        self.assertIn("_selection_save_pending", finished_source)
        self.assertIn("self._hosts.create_selection_save_worker", request_source)
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

    def test_stale_user_selection_save_worker_finished_does_not_restart_pending_save(self) -> None:
        import hosts.ui.page as hosts_page
        from hosts.ui.page import HostsPage

        page = HostsPage.__new__(HostsPage)
        page._cleanup_in_progress = False
        page._selection_save_runtime = SimpleNamespace(request_id=2)
        page._selection_save_pending = {"service": "profile"}
        page._request_user_selection_save = Mock()

        with patch.object(hosts_page, "QTimer", SimpleNamespace(singleShot=Mock()), create=True) as timer_mock:
            HostsPage._on_user_selection_save_worker_finished(page, SimpleNamespace(_request_id=1))

        timer_mock.singleShot.assert_not_called()
        page._request_user_selection_save.assert_not_called()
        self.assertEqual(page._selection_save_pending, {"service": "profile"})

    def test_stale_user_selection_save_worker_object_finished_does_not_restart_pending_save(self) -> None:
        import hosts.ui.page as hosts_page
        from hosts.ui.page import HostsPage

        page = HostsPage.__new__(HostsPage)
        page._cleanup_in_progress = False
        page._selection_save_runtime = SimpleNamespace(worker=object())
        page._selection_save_pending = {"service": "profile"}
        page._request_user_selection_save = Mock()

        with patch.object(hosts_page, "QTimer", SimpleNamespace(singleShot=Mock()), create=True) as timer_mock:
            HostsPage._on_user_selection_save_worker_finished(page, object())

        timer_mock.singleShot.assert_not_called()
        page._request_user_selection_save.assert_not_called()
        self.assertEqual(page._selection_save_pending, {"service": "profile"})

    def test_user_selection_save_request_waits_while_restart_is_scheduled(self) -> None:
        from hosts.ui.page import HostsPage

        page = HostsPage.__new__(HostsPage)
        page._selection_save_start_scheduled = True
        page._selection_save_pending = None
        page._selection_save_runtime = SimpleNamespace(is_running=Mock(return_value=False), start_qthread_worker=Mock())

        HostsPage._request_user_selection_save(page, {"service": "latest"})

        page._selection_save_runtime.start_qthread_worker.assert_not_called()
        self.assertEqual(page._selection_save_pending, {"service": "latest"})

    def test_user_selection_save_scheduled_start_uses_latest_pending_selection(self) -> None:
        import hosts.ui.page as hosts_page
        from hosts.ui.page import HostsPage

        page = HostsPage.__new__(HostsPage)
        page._cleanup_in_progress = False
        page._selection_save_pending = {"service": "old"}
        page._selection_save_start_scheduled = False
        page._selection_save_runtime = SimpleNamespace(is_running=Mock(return_value=False), start_qthread_worker=Mock())
        page._request_user_selection_save = Mock()
        single_shot = Mock(side_effect=lambda _delay, _callback: None)

        with patch.object(hosts_page, "QTimer", SimpleNamespace(singleShot=single_shot), create=True):
            HostsPage._on_user_selection_save_worker_finished(page, object())
            HostsPage._request_user_selection_save(page, {"service": "latest"})

        single_shot.call_args.args[1]()

        page._request_user_selection_save.assert_called_once_with({"service": "latest"})

    def test_user_selection_save_result_ignored_when_new_save_is_pending(self) -> None:
        import hosts.ui.page as hosts_page
        from hosts.ui.page import HostsPage

        page = HostsPage.__new__(HostsPage)
        page._cleanup_in_progress = False
        page._selection_save_runtime = Mock()
        page._selection_save_runtime.is_current.return_value = True
        page._selection_save_pending = {"service": "latest"}

        with patch.object(hosts_page, "log") as log_mock:
            HostsPage._on_user_selection_save_finished(page, 7, False)

        log_mock.assert_not_called()

    def test_user_selection_save_error_ignored_when_new_save_is_pending(self) -> None:
        import hosts.ui.page as hosts_page
        from hosts.ui.page import HostsPage

        page = HostsPage.__new__(HostsPage)
        page._cleanup_in_progress = False
        page._selection_save_runtime = Mock()
        page._selection_save_runtime.is_current.return_value = True
        page._selection_save_pending = {"service": "latest"}

        with patch.object(hosts_page, "log") as log_mock:
            HostsPage._on_user_selection_save_failed(page, 7, "old save failed")

        log_mock.assert_not_called()

    def test_user_selection_load_request_waits_while_worker_runs(self) -> None:
        from hosts.ui.page import HostsPage

        page = HostsPage.__new__(HostsPage)
        page._selection_load_runtime = SimpleNamespace(is_running=Mock(return_value=True), start_qthread_worker=Mock())
        page._selection_load_pending = False
        page._selection_load_show_access_errors = False

        HostsPage._start_user_selection_load_worker(page, show_access_errors=True)

        page._selection_load_runtime.start_qthread_worker.assert_not_called()
        self.assertTrue(page._selection_load_pending)
        self.assertTrue(page._selection_load_show_access_errors)

    def test_user_selection_load_pending_restarts_after_event_loop_turn(self) -> None:
        import hosts.ui.page as hosts_page
        from hosts.ui.page import HostsPage

        page = HostsPage.__new__(HostsPage)
        page._cleanup_in_progress = False
        page._selection_load_pending = True
        page._selection_load_start_scheduled = False
        page._selection_load_show_access_errors = True
        page._start_user_selection_load_worker = Mock()
        single_shot = Mock(side_effect=lambda _delay, _callback: None)

        with patch.object(hosts_page, "QTimer", SimpleNamespace(singleShot=single_shot), create=True):
            HostsPage._on_user_selection_load_worker_finished(page, object())

        single_shot.assert_called_once()
        self.assertEqual(single_shot.call_args.args[0], 0)
        page._start_user_selection_load_worker.assert_not_called()

        single_shot.call_args.args[1]()

        page._start_user_selection_load_worker.assert_called_once_with(show_access_errors=True)
        self.assertFalse(page._selection_load_pending)

    def test_stale_user_selection_load_worker_finished_does_not_restart_pending_load(self) -> None:
        import hosts.ui.page as hosts_page
        from hosts.ui.page import HostsPage

        page = HostsPage.__new__(HostsPage)
        page._cleanup_in_progress = False
        page._selection_load_runtime = SimpleNamespace(request_id=2)
        page._selection_load_pending = True
        page._selection_load_start_scheduled = False
        page._selection_load_show_access_errors = True
        page._start_user_selection_load_worker = Mock()

        with patch.object(hosts_page, "QTimer", SimpleNamespace(singleShot=Mock()), create=True) as timer_mock:
            HostsPage._on_user_selection_load_worker_finished(page, SimpleNamespace(_request_id=1))

        timer_mock.singleShot.assert_not_called()
        page._start_user_selection_load_worker.assert_not_called()
        self.assertTrue(page._selection_load_pending)

    def test_user_selection_load_result_ignored_when_new_load_is_pending(self) -> None:
        from hosts.ui.page import HostsPage

        page = HostsPage.__new__(HostsPage)
        page._cleanup_in_progress = False
        page._selection_load_runtime = Mock()
        page._selection_load_runtime.is_current.return_value = True
        page._selection_load_pending = True
        page._selection_load_show_access_errors = True
        page._service_dns_selection = {"service": "old"}
        page._finish_runtime_init_after_selection = Mock()

        HostsPage._on_user_selection_load_finished(page, 8, {"service": "stale"})

        self.assertEqual(page._service_dns_selection, {"service": "old"})
        self.assertTrue(page._selection_load_show_access_errors)
        page._finish_runtime_init_after_selection.assert_not_called()

    def test_user_selection_load_error_ignored_when_new_load_is_pending(self) -> None:
        from hosts.ui.page import HostsPage

        page = HostsPage.__new__(HostsPage)
        page._cleanup_in_progress = False
        page._selection_load_runtime = Mock()
        page._selection_load_runtime.is_current.return_value = True
        page._selection_load_pending = True
        page._selection_load_show_access_errors = True
        page._service_dns_selection = {"service": "old"}
        page._finish_runtime_init_after_selection = Mock()

        HostsPage._on_user_selection_load_failed(page, 8, "stale error")

        self.assertEqual(page._service_dns_selection, {"service": "old"})
        self.assertTrue(page._selection_load_show_access_errors)
        page._finish_runtime_init_after_selection.assert_not_called()

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

    def test_stale_catalog_refresh_worker_finished_does_not_restart_pending_refresh(self) -> None:
        import hosts.ui.page as hosts_page
        from hosts.ui.page import HostsPage

        page = HostsPage.__new__(HostsPage)
        page._cleanup_in_progress = False
        page._catalog_refresh_runtime = SimpleNamespace(request_id=2)
        page._catalog_refresh_pending_trigger = "watcher"
        page._refresh_catalog_if_needed = Mock()

        with patch.object(hosts_page, "QTimer", SimpleNamespace(singleShot=Mock()), create=True) as timer_mock:
            HostsPage._on_catalog_refresh_worker_finished(page, SimpleNamespace(_request_id=1))

        timer_mock.singleShot.assert_not_called()
        page._refresh_catalog_if_needed.assert_not_called()
        self.assertEqual(page._catalog_refresh_pending_trigger, "watcher")

    def test_catalog_refresh_request_waits_while_restart_is_scheduled(self) -> None:
        from hosts.ui.page import HostsPage

        page = HostsPage.__new__(HostsPage)
        page._catalog_refresh_start_scheduled = True
        page._catalog_refresh_pending_trigger = ""
        page._catalog_refresh_runtime = SimpleNamespace(is_running=Mock(return_value=False), start_qthread_worker=Mock())

        HostsPage._refresh_catalog_if_needed(page, "watcher")

        page._catalog_refresh_runtime.start_qthread_worker.assert_not_called()
        self.assertEqual(page._catalog_refresh_pending_trigger, "watcher")

    def test_catalog_refresh_scheduled_start_uses_latest_pending_trigger(self) -> None:
        import hosts.ui.page as hosts_page
        from hosts.ui.page import HostsPage

        page = HostsPage.__new__(HostsPage)
        page._cleanup_in_progress = False
        page._catalog_refresh_pending_trigger = "old"
        page._catalog_refresh_start_scheduled = False
        page._catalog_refresh_runtime = SimpleNamespace(is_running=Mock(return_value=False), start_qthread_worker=Mock())
        page._refresh_catalog_if_needed = Mock()
        single_shot = Mock(side_effect=lambda _delay, _callback: None)

        with patch.object(hosts_page, "QTimer", SimpleNamespace(singleShot=single_shot), create=True):
            HostsPage._on_catalog_refresh_worker_finished(page, object())
            HostsPage._refresh_catalog_if_needed(page, "watcher")

        single_shot.call_args.args[1]()

        page._refresh_catalog_if_needed.assert_called_once_with("watcher")

    def test_catalog_refresh_result_ignored_when_new_refresh_is_pending(self) -> None:
        import hosts.ui.page as hosts_page
        from hosts.ui.page import HostsPage

        page = HostsPage.__new__(HostsPage)
        page._cleanup_in_progress = False
        page._catalog_refresh_runtime = Mock()
        page._catalog_refresh_runtime.is_current.return_value = True
        page._catalog_refresh_pending_trigger = "watcher"
        page._catalog_sig = "old-signature"
        page._catalog_dirty = False
        page._services_layout = object()
        page._hosts = SimpleNamespace(invalidate_catalog_cache=Mock())
        page._rebuild_services_selectors = Mock()
        page.isVisible = Mock(return_value=True)

        with patch.object(hosts_page, "apply_catalog_refresh_signature") as apply_refresh:
            HostsPage._on_catalog_refresh_loaded(page, 4, "timer", "new-signature")

        apply_refresh.assert_not_called()
        self.assertEqual(page._catalog_sig, "old-signature")
        self.assertFalse(page._catalog_dirty)
        page._hosts.invalidate_catalog_cache.assert_not_called()
        page._rebuild_services_selectors.assert_not_called()

    def test_catalog_refresh_error_ignored_when_new_refresh_is_pending(self) -> None:
        import hosts.ui.page as hosts_page
        from hosts.ui.page import HostsPage

        page = HostsPage.__new__(HostsPage)
        page._cleanup_in_progress = False
        page._catalog_refresh_runtime = Mock()
        page._catalog_refresh_runtime.is_current.return_value = True
        page._catalog_refresh_pending_trigger = "watcher"

        with patch.object(hosts_page, "log") as log_mock:
            HostsPage._on_catalog_refresh_failed(page, 4, "timer", "old refresh failed")

        log_mock.assert_not_called()

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

    def test_stale_open_hosts_file_worker_finished_does_not_restart_pending_open(self) -> None:
        import hosts.ui.page as hosts_page
        from hosts.ui.page import HostsPage

        page = HostsPage.__new__(HostsPage)
        page._cleanup_in_progress = False
        page._open_file_runtime = SimpleNamespace(request_id=2)
        page._open_file_pending = True
        page._request_open_hosts_file = Mock()

        with patch.object(hosts_page, "QTimer", SimpleNamespace(singleShot=Mock()), create=True) as timer_mock:
            HostsPage._on_open_hosts_file_worker_finished(page, SimpleNamespace(_request_id=1))

        timer_mock.singleShot.assert_not_called()
        page._request_open_hosts_file.assert_not_called()
        self.assertTrue(page._open_file_pending)

    def test_open_hosts_file_request_waits_while_restart_is_scheduled(self) -> None:
        from hosts.ui.page import HostsPage

        page = HostsPage.__new__(HostsPage)
        page._open_file_start_scheduled = True
        page._open_file_pending = False
        page._open_file_runtime = SimpleNamespace(is_running=Mock(return_value=False), start_qthread_worker=Mock())

        HostsPage._request_open_hosts_file(page)

        page._open_file_runtime.start_qthread_worker.assert_not_called()
        self.assertTrue(page._open_file_pending)

    def test_open_hosts_file_scheduled_start_is_not_duplicated(self) -> None:
        import hosts.ui.page as hosts_page
        from hosts.ui.page import HostsPage

        page = HostsPage.__new__(HostsPage)
        page._cleanup_in_progress = False
        page._open_file_pending = False
        page._open_file_start_scheduled = False
        page._request_open_hosts_file = Mock()
        single_shot = Mock(side_effect=lambda _delay, _callback: None)

        with patch.object(hosts_page, "QTimer", SimpleNamespace(singleShot=single_shot), create=True):
            HostsPage._schedule_open_hosts_file_start(page)
            HostsPage._schedule_open_hosts_file_start(page)

        single_shot.assert_called_once()
        self.assertTrue(page._open_file_pending)
        page._request_open_hosts_file.assert_not_called()

        single_shot.call_args.args[1]()

        page._request_open_hosts_file.assert_called_once_with()

    def test_open_hosts_file_result_ignored_when_new_open_is_pending(self) -> None:
        from hosts.ui.page import HostsPage

        page = HostsPage.__new__(HostsPage)
        page._cleanup_in_progress = False
        page._open_file_pending = True
        page._open_file_runtime = Mock()
        page._open_file_runtime.is_current.return_value = True
        page._show_open_hosts_file_error = Mock()
        result = SimpleNamespace(success=False, message="stale error", error="")

        HostsPage._on_open_hosts_file_finished(page, 5, result)

        page._show_open_hosts_file_error.assert_not_called()

    def test_open_hosts_file_failure_ignored_when_new_open_is_pending(self) -> None:
        from hosts.ui.page import HostsPage

        page = HostsPage.__new__(HostsPage)
        page._cleanup_in_progress = False
        page._open_file_pending = True
        page._open_file_runtime = Mock()
        page._open_file_runtime.is_current.return_value = True
        page._show_open_hosts_file_error = Mock()

        HostsPage._on_open_hosts_file_failed(page, 5, "stale error")

        page._show_open_hosts_file_error.assert_not_called()

    def test_restore_permissions_pending_restarts_after_event_loop_turn(self) -> None:
        import hosts.ui.page as hosts_page
        from hosts.ui.page import HostsPage

        page = HostsPage.__new__(HostsPage)
        page._cleanup_in_progress = False
        page._permission_restore_pending = True
        page._request_restore_hosts_permissions = Mock()
        single_shot = Mock(side_effect=lambda _delay, _callback: None)

        with patch.object(hosts_page, "QTimer", SimpleNamespace(singleShot=single_shot), create=True):
            HostsPage._on_restore_hosts_permissions_worker_finished(page, object())

        single_shot.assert_called_once()
        self.assertEqual(single_shot.call_args.args[0], 0)
        page._request_restore_hosts_permissions.assert_not_called()

        single_shot.call_args.args[1]()

        page._request_restore_hosts_permissions.assert_called_once_with()

    def test_stale_restore_permissions_worker_finished_does_not_restart_pending_restore(self) -> None:
        import hosts.ui.page as hosts_page
        from hosts.ui.page import HostsPage

        page = HostsPage.__new__(HostsPage)
        page._cleanup_in_progress = False
        page._permission_restore_runtime = SimpleNamespace(request_id=2)
        page._permission_restore_pending = True
        page._request_restore_hosts_permissions = Mock()

        with patch.object(hosts_page, "QTimer", SimpleNamespace(singleShot=Mock()), create=True) as timer_mock:
            HostsPage._on_restore_hosts_permissions_worker_finished(page, SimpleNamespace(_request_id=1))

        timer_mock.singleShot.assert_not_called()
        page._request_restore_hosts_permissions.assert_not_called()
        self.assertTrue(page._permission_restore_pending)

    def test_restore_permissions_request_waits_while_restart_is_scheduled(self) -> None:
        from hosts.ui.page import HostsPage

        page = HostsPage.__new__(HostsPage)
        page._permission_restore_start_scheduled = True
        page._permission_restore_pending = False
        page._permission_restore_runtime = SimpleNamespace(is_running=Mock(return_value=False), start_qthread_worker=Mock())

        HostsPage._request_restore_hosts_permissions(page)

        page._permission_restore_runtime.start_qthread_worker.assert_not_called()
        self.assertTrue(page._permission_restore_pending)

    def test_restore_permissions_result_ignored_when_new_restore_is_pending(self) -> None:
        import hosts.ui.page as hosts_page
        from hosts.ui.page import HostsPage

        page = HostsPage.__new__(HostsPage)
        page._cleanup_in_progress = False
        page._permission_restore_pending = True
        page._permission_restore_runtime = Mock()
        page._permission_restore_runtime.is_current.return_value = True
        page._dismiss_hosts_error_bar = Mock()
        page._invalidate_cache = Mock()
        page._update_ui = Mock()
        page._show_error = Mock()
        page.window = Mock(return_value=object())

        with patch.object(hosts_page, "apply_restore_hosts_permissions_result_flow") as apply_result:
            HostsPage._on_restore_hosts_permissions_finished(page, 6, object())

        apply_result.assert_not_called()
        page._dismiss_hosts_error_bar.assert_not_called()
        page._invalidate_cache.assert_not_called()
        page._update_ui.assert_not_called()
        page._show_error.assert_not_called()

    def test_restore_permissions_failure_ignored_when_new_restore_is_pending(self) -> None:
        from hosts.ui.page import HostsPage

        page = HostsPage.__new__(HostsPage)
        page._cleanup_in_progress = False
        page._permission_restore_pending = True
        page._permission_restore_runtime = Mock()
        page._permission_restore_runtime.is_current.return_value = True
        page._dismiss_hosts_error_bar = Mock()
        page._show_error = Mock()

        HostsPage._on_restore_hosts_permissions_failed(page, 6, "stale error")

        page._dismiss_hosts_error_bar.assert_not_called()
        page._show_error.assert_not_called()

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

    def test_stale_hosts_state_worker_finished_does_not_restart_pending_load(self) -> None:
        import hosts.ui.page as hosts_page
        from hosts.ui.page import HostsPage

        page = HostsPage.__new__(HostsPage)
        page._cleanup_in_progress = False
        page._state_load_runtime = SimpleNamespace(request_id=2)
        page._state_load_pending = {"show_access_errors": True, "update_status": True}
        page._request_hosts_state_load = Mock()

        with patch.object(hosts_page, "QTimer", SimpleNamespace(singleShot=Mock()), create=True) as timer_mock:
            HostsPage._on_hosts_state_worker_finished(page, SimpleNamespace(_request_id=1))

        timer_mock.singleShot.assert_not_called()
        page._request_hosts_state_load.assert_not_called()
        self.assertEqual(page._state_load_pending, {"show_access_errors": True, "update_status": True})

    def test_hosts_state_result_ignored_when_new_state_load_is_pending(self) -> None:
        from hosts.ui.page import HostsPage

        page = HostsPage.__new__(HostsPage)
        page._cleanup_in_progress = False
        page._state_load_runtime = Mock()
        page._state_load_runtime.is_current.return_value = True
        page._state_load_pending = {"show_access_errors": False, "update_status": True}
        page._state_load_request_context = {"show_access_errors": True, "update_status": True}
        page._runtime_cache = SimpleNamespace(runtime_state="old", active_domains={"old.example"})
        page._apply_hosts_access_state = Mock()
        page._apply_hosts_runtime_state_to_ui = Mock()
        runtime_state = SimpleNamespace(active_domains={"new.example"})

        HostsPage._on_hosts_state_loaded(page, 7, runtime_state)

        self.assertEqual(page._runtime_cache.runtime_state, "old")
        self.assertEqual(page._runtime_cache.active_domains, {"old.example"})
        page._apply_hosts_access_state.assert_not_called()
        page._apply_hosts_runtime_state_to_ui.assert_not_called()

    def test_hosts_state_error_ignored_when_new_state_load_is_pending(self) -> None:
        import hosts.ui.page as hosts_page
        from hosts.ui.page import HostsPage

        page = HostsPage.__new__(HostsPage)
        page._cleanup_in_progress = False
        page._state_load_runtime = Mock()
        page._state_load_runtime.is_current.return_value = True
        page._state_load_pending = {"show_access_errors": False, "update_status": True}
        page._state_load_request_context = {"show_access_errors": True, "update_status": True}
        page._show_error = Mock()
        page._tr = Mock(side_effect=lambda _key, default, **kwargs: default.format(**kwargs))

        with patch.object(hosts_page, "log") as log_mock:
            HostsPage._on_hosts_state_failed(page, 7, "stale error")

        log_mock.assert_not_called()
        page._show_error.assert_not_called()

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

    def test_hosts_state_scheduled_start_merges_latest_pending_flags(self) -> None:
        import hosts.ui.page as hosts_page
        from hosts.ui.page import HostsPage

        page = HostsPage.__new__(HostsPage)
        page._cleanup_in_progress = False
        page._state_load_start_scheduled = False
        page._state_load_pending = {"show_access_errors": True, "update_status": False}
        page._state_load_runtime = SimpleNamespace(is_running=Mock(return_value=False), start_qthread_worker=Mock())
        page._request_hosts_state_load = Mock()
        single_shot = Mock(side_effect=lambda _delay, _callback: None)

        with patch.object(hosts_page, "QTimer", SimpleNamespace(singleShot=single_shot), create=True):
            HostsPage._on_hosts_state_worker_finished(page, object())
            HostsPage._request_hosts_state_load(
                page,
                show_access_errors=False,
                update_status=True,
            )

        single_shot.call_args.args[1]()

        page._request_hosts_state_load.assert_called_once_with(
            show_access_errors=True,
            update_status=True,
        )

    def test_catalog_refresh_signature_runs_through_worker(self) -> None:
        from hosts.ui.page import HostsPage
        import hosts.catalog_refresh_worker as catalog_refresh_worker

        page_init_source = inspect.getsource(HostsPage.__init__)
        refresh_source = inspect.getsource(HostsPage._refresh_catalog_if_needed)
        worker_source = inspect.getsource(catalog_refresh_worker.HostsCatalogRefreshWorker)

        self.assertIn("self._hosts = deps.hosts_feature", page_init_source)
        self.assertIn("_catalog_refresh_runtime", page_init_source)
        self.assertIn("start_qthread_worker", refresh_source)
        self.assertIn("create_catalog_refresh_worker", refresh_source)
        self.assertNotIn("get_catalog_signature_fn=self._controller.get_catalog_signature", refresh_source)
        self.assertIn("self._hosts.create_catalog_refresh_worker", refresh_source)
        self.assertIn("_get_catalog_signature", worker_source)
        self.assertNotIn("hosts.commands", worker_source)
        self.assertNotIn("self._controller", worker_source)

    def test_hosts_operation_worker_is_created_by_feature(self) -> None:
        from hosts.ui.page import HostsPage
        import hosts.operation_workflow as operation_workflow

        workflow_source = inspect.getsource(operation_workflow.start_hosts_operation)
        page_init_source = inspect.getsource(HostsPage.__init__)
        run_source = inspect.getsource(HostsPage._run_operation)
        cleanup_source = inspect.getsource(HostsPage.cleanup)

        self.assertIn("self._hosts = deps.hosts_feature", page_init_source)
        self.assertIn("_operation_runtime = OneShotWorkerRuntime()", page_init_source)
        self.assertIn("operation_runtime=self._operation_runtime", run_source)
        self.assertIn("start_qobject_worker", workflow_source)
        self.assertIn("create_operation_worker_fn", workflow_source)
        self.assertIn("create_operation_worker_fn(", workflow_source)
        self.assertIn("create_operation_worker_fn=self._hosts.create_operation_worker", run_source)
        self.assertIn("_operation_runtime.stop", cleanup_source)
        self.assertIn("_operation_runtime.cancel", cleanup_source)
        self.assertNotIn("QThread", workflow_source)
        self.assertNotIn("thread.start()", workflow_source)
        self.assertNotIn("moveToThread", workflow_source)
        self.assertNotIn("execute_hosts_operation_fn=self._controller.execute_hosts_operation", run_source)


if __name__ == "__main__":
    unittest.main()
