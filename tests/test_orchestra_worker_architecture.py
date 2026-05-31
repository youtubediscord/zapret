from __future__ import annotations

import inspect
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from unittest.mock import Mock


class OrchestraWorkerArchitectureTests(unittest.TestCase):
    def test_orchestra_controller_receives_runtime_state_callable(self) -> None:
        from app.page_names import PageName
        from orchestra.page_controller import OrchestraPageController
        from ui.page_deps.system import build_orchestra_page_kwargs

        init_source = inspect.getsource(OrchestraPageController.__init__)
        controller_source = inspect.getsource(OrchestraPageController)
        running_source = inspect.getsource(OrchestraPageController.is_runtime_running)

        self.assertNotIn("runtime_feature", init_source)
        self.assertNotIn("self._runtime", controller_source)
        self.assertIn("is_runtime_running", init_source)
        self.assertIn("self._is_runtime_running", running_source)

        runtime_feature = Mock()
        runtime_feature.is_any_running.return_value = True
        kwargs = build_orchestra_page_kwargs(
            page_name=PageName.ORCHESTRA,
            orchestra_feature=Mock(),
            runtime_feature=runtime_feature,
        )

        controller = kwargs["controller"]
        self.assertTrue(controller.is_runtime_running())
        runtime_feature.is_any_running.assert_called_once_with(silent=True)

    def test_page_workers_receive_action_functions(self) -> None:
        from orchestra.page_workers import (
            OrchestraClearLearnedWorker,
            OrchestraLogContextActionWorker,
            OrchestraLogHistoryActionWorker,
            OrchestraLogHistoryLoadWorker,
        )

        clear_init = inspect.getsource(OrchestraClearLearnedWorker.__init__)
        clear_run = inspect.getsource(OrchestraClearLearnedWorker.run)
        history_init = inspect.getsource(OrchestraLogHistoryLoadWorker.__init__)
        history_run = inspect.getsource(OrchestraLogHistoryLoadWorker.run)
        history_action_init = inspect.getsource(OrchestraLogHistoryActionWorker.__init__)
        history_action_run = inspect.getsource(OrchestraLogHistoryActionWorker.run)
        context_action_init = inspect.getsource(OrchestraLogContextActionWorker.__init__)
        context_action_run = inspect.getsource(OrchestraLogContextActionWorker.run)

        self.assertIn("clear_learned_data", clear_init)
        self.assertIn("self._clear_learned_data", clear_init)
        self.assertNotIn("self._controller", clear_init)
        self.assertIn("self._clear_learned_data()", clear_run)
        self.assertNotIn("self._controller.clear_learned_data", clear_run)

        self.assertIn("load_log_history", history_init)
        self.assertIn("self._load_log_history", history_init)
        self.assertNotIn("self._controller", history_init)
        self.assertIn("self._load_log_history()", history_run)
        self.assertNotIn("self._controller.load_log_history", history_run)

        self.assertIn("run_action", history_action_init)
        self.assertIn("self._run_action", history_action_init)
        self.assertNotIn("self._controller", history_action_init)
        self.assertIn("self._run_action(action=self._action, log_id=self._log_id)", history_action_run)
        self.assertNotIn("self._controller.", history_action_run)

        self.assertIn("run_action", context_action_init)
        self.assertIn("self._run_action", context_action_init)
        self.assertNotIn("self._controller", context_action_init)
        self.assertIn("self._run_action(", context_action_run)
        self.assertIn("domain=self._domain", context_action_run)
        self.assertNotIn("self._controller.", context_action_run)

    def test_orchestra_log_history_actions_run_through_worker(self) -> None:
        from orchestra.page_controller import OrchestraPageController
        from orchestra.ui.page import OrchestraPage

        view_source = inspect.getsource(OrchestraPage._view_log_history)
        delete_source = inspect.getsource(OrchestraPage._delete_log_history)
        clear_source = inspect.getsource(OrchestraPage._clear_all_log_history)
        request_source = inspect.getsource(OrchestraPage._request_log_history_action)
        start_source = inspect.getsource(OrchestraPage._start_log_history_action_worker)
        page_source = inspect.getsource(OrchestraPage)
        controller_source = inspect.getsource(OrchestraPageController)

        for source in (view_source, delete_source, clear_source):
            self.assertIn("_request_log_history_action", source)
            self.assertNotIn("runner=", source)
            self.assertNotIn("log_history_workflow", source)

        self.assertIn("_log_history_action_runtime", page_source)
        self.assertIn("create_log_history_action_worker", page_source)
        self.assertIn("start_qthread_worker", start_source)
        self.assertIn("_log_history_action_pending", request_source)
        self.assertIn("create_log_history_action_worker", controller_source)
        self.assertIn("run_log_history_action", controller_source)

    def test_orchestra_log_history_pending_action_restarts_after_event_loop_turn(self) -> None:
        import orchestra.ui.page as orchestra_page
        from orchestra.ui.page import OrchestraPage

        page = OrchestraPage.__new__(OrchestraPage)
        page._cleanup_in_progress = False
        page._log_history_action_pending = [("delete", "log-1")]
        page._start_log_history_action_worker = Mock()
        single_shot = Mock(side_effect=lambda _delay, _callback: None)

        with patch.object(orchestra_page, "QTimer", SimpleNamespace(singleShot=single_shot), create=True):
            OrchestraPage._on_log_history_action_worker_finished(page, object())

        single_shot.assert_called_once()
        self.assertEqual(single_shot.call_args.args[0], 0)
        page._start_log_history_action_worker.assert_not_called()

        single_shot.call_args.args[1]()

        page._start_log_history_action_worker.assert_called_once_with(("delete", "log-1"))

    def test_orchestra_log_context_actions_run_through_worker(self) -> None:
        import orchestra.ui.page_log_context_workflow as log_context_workflow
        from orchestra.page_controller import OrchestraPageController
        from orchestra.ui.page import OrchestraPage

        lock_source = inspect.getsource(OrchestraPage._lock_strategy_from_log)
        block_source = inspect.getsource(OrchestraPage._block_strategy_from_log)
        unblock_source = inspect.getsource(OrchestraPage._unblock_strategy_from_log)
        whitelist_source = inspect.getsource(OrchestraPage._add_to_whitelist_from_log)
        request_source = inspect.getsource(OrchestraPage._request_log_context_action)
        start_source = inspect.getsource(OrchestraPage._start_log_context_action_worker)
        menu_source = inspect.getsource(log_context_workflow.show_log_context_menu)
        page_source = inspect.getsource(OrchestraPage)
        controller_source = inspect.getsource(OrchestraPageController)

        for source in (lock_source, block_source, unblock_source, whitelist_source):
            self.assertIn("_request_log_context_action", source)
            self.assertNotIn("runner=", source)
            self.assertNotIn("log_context_actions", source)

        self.assertNotIn("runner=", menu_source)
        self.assertIn("is_strategy_blocked_fn", menu_source)
        self.assertIn("_log_context_action_runtime", page_source)
        self.assertIn("create_log_context_action_worker", page_source)
        self.assertIn("start_qthread_worker", start_source)
        self.assertIn("_log_context_action_pending", request_source)
        self.assertIn("create_log_context_action_worker", controller_source)
        self.assertIn("run_log_context_action", controller_source)

    def test_orchestra_log_context_pending_action_restarts_after_event_loop_turn(self) -> None:
        import orchestra.ui.page as orchestra_page
        from orchestra.ui.page import OrchestraPage

        page = OrchestraPage.__new__(OrchestraPage)
        page._cleanup_in_progress = False
        page._log_context_action_pending = [("lock", "example.com", 7, "tcp")]
        page._start_log_context_action_worker = Mock()
        single_shot = Mock(side_effect=lambda _delay, _callback: None)

        with patch.object(orchestra_page, "QTimer", SimpleNamespace(singleShot=single_shot), create=True):
            OrchestraPage._on_log_context_action_worker_finished(page, object())

        single_shot.assert_called_once()
        self.assertEqual(single_shot.call_args.args[0], 0)
        page._start_log_context_action_worker.assert_not_called()

        single_shot.call_args.args[1]()

        page._start_log_context_action_worker.assert_called_once_with(("lock", "example.com", 7, "tcp"))

    def test_orchestra_main_page_does_not_read_learned_data_in_ui_thread(self) -> None:
        from orchestra.ui.page import OrchestraPage

        learned_source = inspect.getsource(OrchestraPage._update_learned_domains)

        self.assertNotIn("build_learned_data_plan_from_runner", learned_source)
        self.assertNotIn("get_learned_data", learned_source)
        self.assertNotIn("_get_runner", learned_source)

    def test_ratings_worker_receives_loader_function(self) -> None:
        from orchestra.ratings_worker import OrchestraRatingsStateLoadWorker

        init_source = inspect.getsource(OrchestraRatingsStateLoadWorker.__init__)
        run_source = inspect.getsource(OrchestraRatingsStateLoadWorker.run)

        self.assertIn("load_state", init_source)
        self.assertIn("self._load_state", init_source)
        self.assertNotIn("self._controller", init_source)
        self.assertIn("self._load_state()", run_source)
        self.assertNotIn("self._controller.load_state", run_source)

    def test_managed_workers_receive_action_functions(self) -> None:
        from orchestra.managed_lists_workers import (
            OrchestraManagedActionWorker,
            OrchestraManagedSnapshotLoadWorker,
        )

        snapshot_init = inspect.getsource(OrchestraManagedSnapshotLoadWorker.__init__)
        snapshot_run = inspect.getsource(OrchestraManagedSnapshotLoadWorker.run)
        action_init = inspect.getsource(OrchestraManagedActionWorker.__init__)
        action_run = inspect.getsource(OrchestraManagedActionWorker.run)

        self.assertIn("load_snapshot", snapshot_init)
        self.assertIn("self._load_snapshot", snapshot_init)
        self.assertNotIn("self._controller", snapshot_init)
        self.assertIn("self._load_snapshot()", snapshot_run)
        self.assertNotIn("self._controller.reload_snapshot", snapshot_run)

        for name in (
            "change_strategy",
            "remove_strategy",
            "add_strategy",
            "clear_user_strategies",
            "is_blocked_strategy",
            "current_strategy",
            "clear_strategies",
            "load_snapshot",
        ):
            self.assertIn(name, action_init)
        self.assertNotIn("self._controller", action_init)
        self.assertNotIn("self._controller.", action_run)

    def test_locked_managed_action_pending_restarts_after_event_loop_turn(self) -> None:
        import orchestra.ui.locked_page as locked_page
        from orchestra.ui.locked_page import OrchestraLockedPage

        page = OrchestraLockedPage.__new__(OrchestraLockedPage)
        page._cleanup_in_progress = False
        page._managed_action_runtime = SimpleNamespace(worker=object())
        page._managed_action_pending = [("locked_remove", {"domain": "example.org"})]
        page._start_managed_action = Mock()
        single_shot = Mock(side_effect=lambda _delay, _callback: None)

        with patch.object(locked_page, "QTimer", SimpleNamespace(singleShot=single_shot)):
            OrchestraLockedPage._on_managed_action_worker_finished(page, object())

        single_shot.assert_called_once()
        self.assertEqual(single_shot.call_args.args[0], 0)
        page._start_managed_action.assert_not_called()

        single_shot.call_args.args[1]()

        page._start_managed_action.assert_called_once_with(("locked_remove", {"domain": "example.org"}))

    def test_blocked_managed_action_pending_restarts_after_event_loop_turn(self) -> None:
        import orchestra.ui.blocked_page as blocked_page
        from orchestra.ui.blocked_page import OrchestraBlockedPage

        page = OrchestraBlockedPage.__new__(OrchestraBlockedPage)
        page._cleanup_in_progress = False
        page._managed_action_runtime = SimpleNamespace(worker=object())
        page._managed_action_pending = [("blocked_remove", {"domain": "example.org"})]
        page._start_managed_action = Mock()
        single_shot = Mock(side_effect=lambda _delay, _callback: None)

        with patch.object(blocked_page, "QTimer", SimpleNamespace(singleShot=single_shot)):
            OrchestraBlockedPage._on_managed_action_worker_finished(page, object())

        single_shot.assert_called_once()
        self.assertEqual(single_shot.call_args.args[0], 0)
        page._start_managed_action.assert_not_called()

        single_shot.call_args.args[1]()

        page._start_managed_action.assert_called_once_with(("blocked_remove", {"domain": "example.org"}))

    def test_whitelist_workers_receive_action_functions(self) -> None:
        from orchestra.managed_lists_workers import (
            OrchestraWhitelistActionWorker,
            OrchestraWhitelistSnapshotLoadWorker,
        )

        snapshot_init = inspect.getsource(OrchestraWhitelistSnapshotLoadWorker.__init__)
        snapshot_run = inspect.getsource(OrchestraWhitelistSnapshotLoadWorker.run)
        action_init = inspect.getsource(OrchestraWhitelistActionWorker.__init__)
        action_run = inspect.getsource(OrchestraWhitelistActionWorker.run)

        self.assertIn("load_snapshot", snapshot_init)
        self.assertIn("self._load_snapshot", snapshot_init)
        self.assertNotIn("self._controller", snapshot_init)
        self.assertIn("self._load_snapshot(refresh=self._refresh)", snapshot_run)
        self.assertNotIn("self._controller.snapshot", snapshot_run)

        for name in ("add_domain", "remove_domain", "clear_user_domains", "load_snapshot"):
            self.assertIn(name, action_init)
        self.assertNotIn("self._controller", action_init)
        self.assertNotIn("self._controller.", action_run)


if __name__ == "__main__":
    unittest.main()
