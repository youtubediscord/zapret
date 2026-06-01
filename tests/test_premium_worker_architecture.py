from __future__ import annotations

import inspect
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from app.feature_facades.premium import PremiumFeature
import donater.commands as premium_commands
import donater.open_bot_worker as open_bot_worker
import donater.premium_page_tasks as premium_page_tasks
import donater.subscription_manager as subscription_manager
import donater.subscription_worker as subscription_worker
from donater.ui.page import PremiumPage


class PremiumWorkerArchitectureTests(unittest.TestCase):
    def test_open_bot_worker_receives_feature_action_not_feature_object(self) -> None:
        feature_source = inspect.getsource(PremiumFeature.create_open_extend_bot_worker)
        worker_source = inspect.getsource(open_bot_worker.PremiumOpenBotWorker)

        self.assertNotIn("premium_feature=self", feature_source)
        self.assertNotIn("self._premium", worker_source)
        self.assertIn("open_extend_bot=self.open_extend_bot", feature_source)
        self.assertIn("_open_extend_bot", worker_source)
        self.assertNotIn("premium_commands.open_extend_bot", worker_source)
        self.assertNotIn("import donater.commands", worker_source)
        self.assertIn("open_extend_bot", inspect.getsource(premium_commands.open_extend_bot))

    def test_subscription_worker_receives_command_actions_from_manager(self) -> None:
        command_source = inspect.getsource(premium_commands.create_subscription_manager)
        manager_init_source = inspect.getsource(subscription_manager.SubscriptionManager.__init__)
        manager_start_source = inspect.getsource(subscription_manager.SubscriptionManager.initialize_async)
        worker_source = inspect.getsource(subscription_worker.SubscriptionInitWorker)

        self.assertIn("get_premium_checker=get_premium_checker", command_source)
        self.assertIn("check_device_activation=check_device_activation", command_source)
        self.assertIn("_get_premium_checker", manager_init_source)
        self.assertIn("_check_device_activation", manager_init_source)
        self.assertIn("get_premium_checker=self._get_premium_checker", manager_start_source)
        self.assertIn("check_device_activation=self._check_device_activation", manager_start_source)
        self.assertIn("_get_premium_checker", worker_source)
        self.assertIn("_check_device_activation", worker_source)
        self.assertNotIn("import donater.commands", worker_source)

    def test_premium_page_action_tasks_use_shared_worker_runtime(self) -> None:
        page_init_source = inspect.getsource(PremiumPage.__init__)
        start_source = inspect.getsource(PremiumPage._start_worker_thread)
        page_source = inspect.getsource(PremiumPage)

        self.assertIn("_premium_action_runtime = OneShotWorkerRuntime()", page_init_source)
        self.assertIn("_premium_action_runtime.start_qthread_worker", start_source)
        self.assertIn("loaded_signal_name=\"result_ready\"", start_source)
        self.assertIn("failed_signal_name=\"error_occurred\"", start_source)
        self.assertNotIn("start_premium_worker_task", page_source)
        self.assertFalse(hasattr(premium_page_tasks, "start_premium_worker_task"))

    def test_pair_code_action_is_remembered_while_checker_initializes(self) -> None:
        page = PremiumPage.__new__(PremiumPage)
        page.current_thread = None
        page._premium = SimpleNamespace(is_checker_ready=Mock(return_value=False))
        page._pending_premium_action = ""
        page._pending_premium_action_start_scheduled = False
        page._start_premium_init_worker = Mock()
        page._set_activation_status = Mock()

        PremiumPage._create_pair_code(page)

        self.assertEqual(page._pending_premium_action, "pair_code")
        page._start_premium_init_worker.assert_called_once_with()

    def test_pending_premium_action_restarts_after_event_loop_turn(self) -> None:
        import donater.ui.page as premium_page

        page = PremiumPage.__new__(PremiumPage)
        page._cleanup_in_progress = False
        page._pending_premium_action = "check_status"
        page._pending_premium_action_start_scheduled = False
        page._check_status = Mock()
        single_shot = Mock(side_effect=lambda _delay, _callback: None)

        with patch.object(premium_page, "QTimer", SimpleNamespace(singleShot=single_shot), create=True):
            PremiumPage._schedule_pending_premium_action_start(page)

        single_shot.assert_called_once()
        self.assertEqual(single_shot.call_args.args[0], 0)
        page._check_status.assert_not_called()

        single_shot.call_args.args[1]()

        page._check_status.assert_called_once_with()
        self.assertEqual(page._pending_premium_action, "")

    def test_status_check_is_remembered_while_premium_worker_runs(self) -> None:
        running_worker = SimpleNamespace(isRunning=Mock(return_value=True))
        page = PremiumPage.__new__(PremiumPage)
        page.current_thread = running_worker
        page._pending_premium_action = ""
        page._pending_premium_action_start_scheduled = False
        page._premium = SimpleNamespace(is_checker_ready=Mock(return_value=True))
        page._set_status_badge = Mock()

        PremiumPage._check_status(page)

        self.assertEqual(page._pending_premium_action, "check_status")
        page._set_status_badge.assert_not_called()

    def test_premium_worker_finished_replays_pending_action_later(self) -> None:
        import donater.ui.page as premium_page

        page = PremiumPage.__new__(PremiumPage)
        page.current_thread = object()
        page._cleanup_in_progress = False
        page._pending_premium_action = "test_connection"
        page._pending_premium_action_start_scheduled = False
        page._test_connection = Mock()
        single_shot = Mock(side_effect=lambda _delay, _callback: None)

        with patch.object(premium_page, "QTimer", SimpleNamespace(singleShot=single_shot), create=True):
            PremiumPage._on_worker_thread_finished(page)

        self.assertIsNone(page.current_thread)
        single_shot.assert_called_once()
        page._test_connection.assert_not_called()

        single_shot.call_args.args[1]()

        page._test_connection.assert_called_once_with()
        self.assertEqual(page._pending_premium_action, "")

    def test_pending_premium_action_is_cleared_when_init_fails(self) -> None:
        page = PremiumPage.__new__(PremiumPage)
        page._cleanup_in_progress = False
        page._pending_premium_action = "pair_code"
        page._pending_premium_action_start_scheduled = True

        PremiumPage._on_premium_init_error(page, "boom")

        self.assertEqual(page._pending_premium_action, "")
        self.assertFalse(page._pending_premium_action_start_scheduled)

    def test_device_info_pending_restarts_after_event_loop_turn(self) -> None:
        import donater.ui.page as premium_page

        page = PremiumPage.__new__(PremiumPage)
        page._device_info_pending = True
        page._cleanup_in_progress = False
        page._start_device_info_load_worker = Mock()
        single_shot = Mock(side_effect=lambda _delay, _callback: None)

        with patch.object(premium_page, "QTimer", SimpleNamespace(singleShot=single_shot), create=True):
            PremiumPage._on_device_info_worker_finished(page, object())

        single_shot.assert_called_once()
        self.assertEqual(single_shot.call_args.args[0], 0)
        page._start_device_info_load_worker.assert_not_called()

        single_shot.call_args.args[1]()

        page._start_device_info_load_worker.assert_called_once_with()

    def test_open_bot_pending_restarts_after_event_loop_turn(self) -> None:
        import donater.ui.page as premium_page

        page = PremiumPage.__new__(PremiumPage)
        page._open_bot_pending = True
        page._cleanup_in_progress = False
        page._request_open_extend_bot = Mock()
        single_shot = Mock(side_effect=lambda _delay, _callback: None)

        with patch.object(premium_page, "QTimer", SimpleNamespace(singleShot=single_shot), create=True):
            PremiumPage._on_open_extend_bot_worker_finished(page, object())

        single_shot.assert_called_once()
        self.assertEqual(single_shot.call_args.args[0], 0)
        page._request_open_extend_bot.assert_not_called()

        single_shot.call_args.args[1]()

        page._request_open_extend_bot.assert_called_once_with()

    def test_device_info_pending_restart_is_coalesced_while_scheduled(self) -> None:
        import donater.ui.page as premium_page

        page = PremiumPage.__new__(PremiumPage)
        page._device_info_start_scheduled = False
        page._cleanup_in_progress = False
        page._device_info_pending = False
        page._start_device_info_load_worker = Mock()
        single_shot = Mock(side_effect=lambda _delay, _callback: None)

        with patch.object(premium_page, "QTimer", SimpleNamespace(singleShot=single_shot), create=True):
            PremiumPage._schedule_device_info_load_worker_start(page)
            PremiumPage._schedule_device_info_load_worker_start(page)

        single_shot.assert_called_once()
        self.assertTrue(page._device_info_pending)

        single_shot.call_args.args[1]()

        page._start_device_info_load_worker.assert_called_once_with()
        self.assertTrue(page._device_info_pending)

    def test_open_bot_pending_restart_is_coalesced_while_scheduled(self) -> None:
        import donater.ui.page as premium_page

        page = PremiumPage.__new__(PremiumPage)
        page._open_bot_start_scheduled = False
        page._cleanup_in_progress = False
        page._open_bot_pending = False
        page._request_open_extend_bot = Mock()
        single_shot = Mock(side_effect=lambda _delay, _callback: None)

        with patch.object(premium_page, "QTimer", SimpleNamespace(singleShot=single_shot), create=True):
            PremiumPage._schedule_open_extend_bot_worker_start(page)
            PremiumPage._schedule_open_extend_bot_worker_start(page)

        single_shot.assert_called_once()
        self.assertTrue(page._open_bot_pending)

        single_shot.call_args.args[1]()

        page._request_open_extend_bot.assert_called_once_with()
        self.assertTrue(page._open_bot_pending)


if __name__ == "__main__":
    unittest.main()
