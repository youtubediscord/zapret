from __future__ import annotations

import inspect
import importlib.util
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from app.feature_facades.premium import PremiumFeature
import donater.commands as premium_commands
import donater.open_bot_worker as open_bot_worker
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

    def test_subscription_manager_uses_shared_worker_runtime(self) -> None:
        manager_init_source = inspect.getsource(subscription_manager.SubscriptionManager.__init__)
        manager_start_source = inspect.getsource(subscription_manager.SubscriptionManager.initialize_async)
        manager_cleanup_source = inspect.getsource(subscription_manager.SubscriptionManager.cleanup)

        self.assertIn("_subscription_runtime = OneShotWorkerRuntime()", manager_init_source)
        self.assertIn("_subscription_runtime.start_qobject_worker", manager_start_source)
        self.assertIn("bind_worker=", manager_start_source)
        self.assertIn("_subscription_runtime.stop", manager_cleanup_source)
        self.assertNotIn("QThread(", manager_start_source)
        self.assertNotIn("moveToThread", manager_start_source)
        self.assertNotIn("self._subscription_thread.start()", manager_start_source)

    def test_subscription_manager_cleanup_does_not_wait_for_worker(self) -> None:
        manager = subscription_manager.SubscriptionManager.__new__(subscription_manager.SubscriptionManager)
        manager._cleanup_in_progress = False
        manager._subscription_runtime = SimpleNamespace(stop=Mock(), cancel=Mock())
        manager._subscription_worker = object()

        manager.cleanup()

        self.assertTrue(manager._cleanup_in_progress)
        manager._subscription_runtime.stop.assert_called_once_with(
            blocking=False,
            log_fn=subscription_manager.log,
            warning_prefix="Поток подписки",
        )
        manager._subscription_runtime.cancel.assert_called_once_with()
        self.assertIsNone(manager._subscription_worker)

    def test_premium_page_action_tasks_use_shared_worker_runtime(self) -> None:
        page_init_source = inspect.getsource(PremiumPage.__init__)
        start_source = inspect.getsource(PremiumPage._start_worker_thread)
        page_source = inspect.getsource(PremiumPage)
        lifecycle_source = inspect.getsource(__import__("donater.ui.page_lifecycle", fromlist=["cleanup_premium_page"]))

        self.assertIn("_premium_action_runtime = OneShotWorkerRuntime()", page_init_source)
        self.assertIn("_premium_action_runtime.start_qthread_worker", start_source)
        self.assertIn("loaded_signal_name=\"result_ready\"", start_source)
        self.assertIn("failed_signal_name=\"error_occurred\"", start_source)
        self.assertIn("_is_premium_action_running", page_source)
        self.assertIn("premium_action_runtime.stop", lifecycle_source)
        self.assertNotIn("start_premium_worker_task", page_source)
        self.assertNotIn("current_thread", page_source)
        self.assertNotIn("is_premium_task_running", page_source)
        self.assertIsNone(importlib.util.find_spec("donater.premium_page_tasks"))

    def test_pair_code_action_is_remembered_while_checker_initializes(self) -> None:
        page = PremiumPage.__new__(PremiumPage)
        page._premium_action_runtime = SimpleNamespace(is_running=Mock(return_value=False))
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

    def test_status_check_is_remembered_while_premium_action_runtime_runs(self) -> None:
        page = PremiumPage.__new__(PremiumPage)
        page._premium_action_runtime = SimpleNamespace(is_running=Mock(return_value=True))
        page._pending_premium_action = ""
        page._pending_premium_action_start_scheduled = False
        page._premium = SimpleNamespace(is_checker_ready=Mock(return_value=True))
        page._set_status_badge = Mock()

        PremiumPage._check_status(page)

        self.assertEqual(page._pending_premium_action, "check_status")
        page._set_status_badge.assert_not_called()

    def test_premium_worker_finished_replays_pending_action_later(self) -> None:
        import donater.ui.page as premium_page

        worker = object()
        page = PremiumPage.__new__(PremiumPage)
        page._cleanup_in_progress = False
        page._premium_action_runtime_worker = worker
        page._pending_premium_action = "test_connection"
        page._pending_premium_action_start_scheduled = False
        page._test_connection = Mock()
        single_shot = Mock(side_effect=lambda _delay, _callback: None)

        with patch.object(premium_page, "QTimer", SimpleNamespace(singleShot=single_shot), create=True):
            PremiumPage._on_worker_thread_finished(page, worker)

        single_shot.assert_called_once()
        page._test_connection.assert_not_called()

        single_shot.call_args.args[1]()

        page._test_connection.assert_called_once_with()
        self.assertEqual(page._pending_premium_action, "")

    def test_stale_premium_worker_finished_does_not_replay_pending_action(self) -> None:
        page = PremiumPage.__new__(PremiumPage)
        page._cleanup_in_progress = False
        page._premium_action_runtime_worker = object()
        page._pending_premium_action = "test_connection"
        page._schedule_pending_premium_action_start = Mock()

        PremiumPage._on_worker_thread_finished(page, object())

        page._schedule_pending_premium_action_start.assert_not_called()
        self.assertEqual(page._pending_premium_action, "test_connection")

    def test_stale_premium_action_result_is_ignored(self) -> None:
        worker = object()
        start_kwargs = {}
        result_handler = Mock()
        error_handler = Mock()
        runtime = SimpleNamespace(
            start_qthread_worker=Mock(side_effect=lambda **kwargs: start_kwargs.update(kwargs) or (2, worker)),
            is_current=Mock(return_value=False),
        )
        page = PremiumPage.__new__(PremiumPage)
        page._cleanup_in_progress = False
        page._premium_action_runtime = runtime
        page._premium = SimpleNamespace(
            create_premium_worker_thread=Mock(return_value=worker),
        )

        PremiumPage._start_worker_thread(page, Mock(), result_handler, error_handler)

        start_kwargs["on_loaded"](1, "old-result")
        start_kwargs["on_failed"](1, "old-error")

        result_handler.assert_not_called()
        error_handler.assert_not_called()
        runtime.is_current.assert_any_call(1, cleanup_in_progress=False)

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

    def test_stale_device_info_worker_finished_does_not_restart_pending_load(self) -> None:
        import donater.ui.page as premium_page

        page = PremiumPage.__new__(PremiumPage)
        page._device_info_runtime = SimpleNamespace(worker=object())
        page._device_info_pending = True
        page._cleanup_in_progress = False
        page._start_device_info_load_worker = Mock()
        single_shot = Mock()

        with patch.object(premium_page, "QTimer", SimpleNamespace(singleShot=single_shot), create=True):
            PremiumPage._on_device_info_worker_finished(page, object())

        single_shot.assert_not_called()
        page._start_device_info_load_worker.assert_not_called()
        self.assertTrue(page._device_info_pending)

    def test_device_info_result_is_ignored_when_new_load_is_pending(self) -> None:
        import donater.ui.page as premium_page

        page = PremiumPage.__new__(PremiumPage)
        page._cleanup_in_progress = False
        page._device_info_runtime = SimpleNamespace(is_current=Mock(return_value=True))
        page._device_info_pending = True
        page._set_pairing_autopoll_snapshot_from_device_info = Mock()
        page._tr = Mock(side_effect=lambda _key, default, **_kwargs: default)
        page.device_id_label = Mock()
        page.saved_key_label = Mock()
        page.last_check_label = Mock()

        with patch.object(premium_page, "apply_device_info_snapshot_labels") as apply_labels:
            PremiumPage._on_device_info_loaded(page, 4, {"device_id": "old"})

        page._set_pairing_autopoll_snapshot_from_device_info.assert_not_called()
        apply_labels.assert_not_called()

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

    def test_stale_open_bot_worker_finished_does_not_restart_pending_open(self) -> None:
        import donater.ui.page as premium_page

        page = PremiumPage.__new__(PremiumPage)
        page._open_bot_runtime = SimpleNamespace(worker=object())
        page._open_bot_pending = True
        page._cleanup_in_progress = False
        page._request_open_extend_bot = Mock()
        single_shot = Mock()

        with patch.object(premium_page, "QTimer", SimpleNamespace(singleShot=single_shot), create=True):
            PremiumPage._on_open_extend_bot_worker_finished(page, object())

        single_shot.assert_not_called()
        page._request_open_extend_bot.assert_not_called()
        self.assertTrue(page._open_bot_pending)

    def test_open_bot_result_is_ignored_when_new_open_is_pending(self) -> None:
        page = PremiumPage.__new__(PremiumPage)
        page._cleanup_in_progress = False
        page._open_bot_runtime = SimpleNamespace(is_current=Mock(return_value=True))
        page._open_bot_pending = True
        page._show_open_extend_bot_error = Mock()

        PremiumPage._on_open_extend_bot_finished(
            page,
            4,
            SimpleNamespace(ok=False, message="old error"),
        )

        page._show_open_extend_bot_error.assert_not_called()

    def test_open_bot_error_is_ignored_when_new_open_is_pending(self) -> None:
        page = PremiumPage.__new__(PremiumPage)
        page._cleanup_in_progress = False
        page._open_bot_runtime = SimpleNamespace(is_current=Mock(return_value=True))
        page._open_bot_pending = True
        page._show_open_extend_bot_error = Mock()

        PremiumPage._on_open_extend_bot_failed(page, 4, "old error")

        page._show_open_extend_bot_error.assert_not_called()

    def test_cleanup_stops_open_bot_worker_without_blocking_gui(self) -> None:
        page = PremiumPage.__new__(PremiumPage)
        page._cleanup_in_progress = False
        page._stop_pairing_status_autopoll = Mock()
        page._premium_action_runtime = Mock()
        page._open_bot_runtime = Mock()
        page._device_info_runtime = Mock()
        page._reset_storage_runtime = Mock()
        page._open_bot_pending = True
        page._open_bot_start_scheduled = True
        page._device_info_pending = True
        page._device_info_start_scheduled = True
        page._reset_storage_pending = True
        page._reset_storage_start_scheduled = True
        page._premium_action_runtime_worker = object()
        page._pending_premium_action = "activate"
        page._pending_premium_action_start_scheduled = True

        PremiumPage.cleanup(page)

        self.assertTrue(page._cleanup_in_progress)
        self.assertFalse(page._open_bot_pending)
        self.assertFalse(page._open_bot_start_scheduled)
        self.assertFalse(page._device_info_pending)
        self.assertFalse(page._device_info_start_scheduled)
        page._open_bot_runtime.stop.assert_called_once_with(
            blocking=False,
            warning_prefix="Premium open bot worker",
        )
        page._open_bot_runtime.cancel.assert_called_once()
        page._device_info_runtime.stop.assert_called_once_with(
            blocking=False,
            warning_prefix="Premium device info worker",
        )
        page._device_info_runtime.cancel.assert_called_once()
        page._premium_action_runtime.stop.assert_called_once_with(
            blocking=False,
            wait_timeout_ms=1000,
            warning_prefix="Premium action worker",
        )
        page._reset_storage_runtime.stop.assert_called_once_with(
            blocking=False,
            warning_prefix="Premium reset storage worker",
        )

    def test_close_event_stops_premium_action_worker_without_blocking_gui(self) -> None:
        from donater.ui.page_lifecycle import close_premium_page

        runtime = SimpleNamespace(is_running=Mock(return_value=True), stop=Mock())
        event = SimpleNamespace(accept=Mock())
        cleanup_values = []
        stop_autopoll = Mock()

        close_premium_page(
            set_cleanup_in_progress_fn=cleanup_values.append,
            build_close_plan_fn=Mock(
                return_value=SimpleNamespace(
                    stop_autopoll=True,
                    should_quit_thread=True,
                    wait_timeout_ms=750,
                )
            ),
            premium_action_runtime=runtime,
            stop_pairing_status_autopoll_fn=stop_autopoll,
            event=event,
        )

        self.assertEqual(cleanup_values, [True])
        stop_autopoll.assert_called_once_with()
        runtime.stop.assert_called_once_with(
            blocking=False,
            wait_timeout_ms=750,
            warning_prefix="Premium action worker",
        )
        event.accept.assert_called_once_with()

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

    def test_reset_storage_request_is_remembered_while_worker_runs(self) -> None:
        page = PremiumPage.__new__(PremiumPage)
        page._reset_storage_runtime = SimpleNamespace(is_running=Mock(return_value=True), start_qthread_worker=Mock())
        page._reset_storage_pending = False
        page._reset_storage_start_scheduled = False

        PremiumPage._request_reset_storage(page)

        page._reset_storage_runtime.start_qthread_worker.assert_not_called()
        self.assertTrue(page._reset_storage_pending)

    def test_reset_storage_pending_restarts_after_event_loop_turn(self) -> None:
        import donater.ui.page as premium_page

        page = PremiumPage.__new__(PremiumPage)
        page._cleanup_in_progress = False
        page._reset_storage_pending = True
        page._reset_storage_start_scheduled = False
        page._start_reset_storage_worker = Mock()
        single_shot = Mock(side_effect=lambda _delay, _callback: None)

        with patch.object(premium_page, "QTimer", SimpleNamespace(singleShot=single_shot), create=True):
            PremiumPage._on_reset_storage_worker_finished(page, object())

        single_shot.assert_called_once()
        self.assertEqual(single_shot.call_args.args[0], 0)
        page._start_reset_storage_worker.assert_not_called()

        single_shot.call_args.args[1]()

        page._start_reset_storage_worker.assert_called_once_with()
        self.assertFalse(page._reset_storage_pending)

    def test_stale_reset_storage_worker_finished_does_not_restart_pending_reset(self) -> None:
        import donater.ui.page as premium_page

        page = PremiumPage.__new__(PremiumPage)
        page._reset_storage_runtime = SimpleNamespace(worker=object())
        page._cleanup_in_progress = False
        page._reset_storage_pending = True
        page._reset_storage_start_scheduled = False
        page._start_reset_storage_worker = Mock()
        single_shot = Mock()

        with patch.object(premium_page, "QTimer", SimpleNamespace(singleShot=single_shot), create=True):
            PremiumPage._on_reset_storage_worker_finished(page, object())

        single_shot.assert_not_called()
        page._start_reset_storage_worker.assert_not_called()
        self.assertTrue(page._reset_storage_pending)

    def test_reset_storage_result_is_ignored_when_new_reset_is_pending(self) -> None:
        import donater.ui.page as premium_page

        page = PremiumPage.__new__(PremiumPage)
        page._cleanup_in_progress = False
        page._reset_storage_runtime = SimpleNamespace(is_current=Mock(return_value=True))
        page._reset_storage_pending = True
        page.key_input = Mock()
        page._set_activation_status = Mock()
        page._update_device_info = Mock()
        page._set_status_badge = Mock()
        page._render_days_label = Mock()
        page._set_activation_section_visible = Mock()
        page._stop_pairing_status_autopoll = Mock()
        page._apply_subscription_state = Mock()

        with patch.object(premium_page, "apply_reset_plan_ui", return_value=("idle", "")) as apply_reset:
            PremiumPage._on_reset_storage_finished(page, 4, object())

        apply_reset.assert_not_called()
        page._render_days_label.assert_not_called()

    def test_reset_storage_error_is_ignored_when_new_reset_is_pending(self) -> None:
        import donater.ui.page as premium_page

        page = PremiumPage.__new__(PremiumPage)
        page._cleanup_in_progress = False
        page._reset_storage_runtime = SimpleNamespace(is_current=Mock(return_value=True))
        page._reset_storage_pending = True
        page._tr = Mock(side_effect=lambda _key, default, **kwargs: default.format(**kwargs) if kwargs else default)
        page.window = Mock(return_value=object())

        with patch.object(premium_page.InfoBar, "warning") as warning:
            PremiumPage._on_reset_storage_failed(page, 4, "old error")

        warning.assert_not_called()


if __name__ == "__main__":
    unittest.main()
