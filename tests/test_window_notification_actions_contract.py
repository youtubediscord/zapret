from __future__ import annotations

import inspect
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from main import window_notifications_setup
from ui.window_notification_actions import WindowNotificationActionHandler
from ui.window_notification_center import WindowNotificationCenter
from winws_runtime.runtime import conflict_flow


class WindowNotificationActionsContractTests(unittest.TestCase):
    def test_notification_open_url_action_runs_through_external_worker(self) -> None:
        handler_init_source = inspect.getsource(WindowNotificationActionHandler.__init__)
        handler_callback_source = inspect.getsource(WindowNotificationActionHandler.build_action_callback)
        center_source = inspect.getsource(WindowNotificationCenter)
        center_init_source = inspect.getsource(WindowNotificationCenter.__init__)
        setup_source = inspect.getsource(window_notifications_setup.attach_window_notifications)

        self.assertIn("open_url", handler_init_source)
        self.assertIn("_open_url", handler_callback_source)
        self.assertNotIn("webbrowser.open", handler_callback_source)
        self.assertIn("_external_open_url_runtime", center_source)
        self.assertIn("create_open_url_worker", center_source)
        self.assertIn("create_open_url_worker", center_init_source)
        self.assertNotIn("external_actions_feature", center_init_source)
        self.assertNotIn("self._external_actions", center_source)
        self.assertIn("features.external_actions", setup_source)

    def test_notification_open_url_pending_restarts_after_event_loop_turn(self) -> None:
        import ui.window_notification_center as notification_center

        center = WindowNotificationCenter.__new__(WindowNotificationCenter)
        center._external_open_url_pending = "https://example.org"
        center._start_external_open_url_worker = Mock()
        single_shot = Mock(side_effect=lambda _delay, _callback: None)

        with patch.object(notification_center, "QTimer", SimpleNamespace(singleShot=single_shot), create=True):
            WindowNotificationCenter._on_external_open_url_worker_finished(center, object())

        single_shot.assert_called_once()
        self.assertEqual(single_shot.call_args.args[0], 0)
        center._start_external_open_url_worker.assert_not_called()

        single_shot.call_args.args[1]()

        center._start_external_open_url_worker.assert_called_once_with("https://example.org")

    def test_notification_open_url_scheduled_start_keeps_latest_request(self) -> None:
        import ui.window_notification_center as notification_center

        center = WindowNotificationCenter.__new__(WindowNotificationCenter)
        center._external_open_url_pending = None
        center._external_open_url_start_scheduled = False
        center._start_external_open_url_worker = Mock()
        single_shot = Mock(side_effect=lambda _delay, _callback: None)

        with patch.object(notification_center, "QTimer", SimpleNamespace(singleShot=single_shot), create=True):
            WindowNotificationCenter._schedule_external_open_url_worker_start(center, "https://example.org/old")
            WindowNotificationCenter._schedule_external_open_url_worker_start(center, "https://example.org/new")

        single_shot.assert_called_once()

        single_shot.call_args.args[1]()

        center._start_external_open_url_worker.assert_called_once_with("https://example.org/new")

    def test_notification_system_actions_run_through_worker(self) -> None:
        from app.feature_facades.external import ExternalActionsFeature
        import app.external_workers as external_workers

        handler_source = inspect.getsource(WindowNotificationActionHandler)
        handler_callback_source = inspect.getsource(WindowNotificationActionHandler.build_action_callback)
        center_source = inspect.getsource(WindowNotificationCenter)
        feature_source = inspect.getsource(ExternalActionsFeature)

        self.assertTrue(hasattr(external_workers, "ExternalNotificationActionWorker"))
        worker_source = inspect.getsource(external_workers.ExternalNotificationActionWorker.run)
        self.assertIn("action_fn", worker_source)

        self.assertIn("_request_disable_proxy", handler_callback_source)
        self.assertIn("_request_disable_kaspersky_warning", handler_callback_source)
        self.assertIn("_request_disable_telega_warning", handler_callback_source)
        self.assertIn("_request_windivert_autofix", handler_callback_source)
        self.assertNotIn("from startup.check_start import _disable_proxy", handler_source)
        self.assertNotIn("disable_kaspersky_warning_forever()", handler_source)
        self.assertNotIn("disable_telega_warning_forever()", handler_source)
        self.assertNotIn("execute_windivert_autofix(", handler_source)

        self.assertIn("_notification_action_runtime", center_source)
        self.assertIn("create_notification_action_worker", center_source)
        self.assertIn("_run_notification_action_worker", center_source)
        self.assertIn("self._create_notification_action_worker", center_source)
        self.assertNotIn("self._external_actions.create_notification_action_worker", center_source)
        self.assertIn("ExternalNotificationActionWorker", feature_source)
        self.assertNotIn("ui.window_notification_action_workers", center_source)

    def test_notification_action_pending_restarts_after_event_loop_turn(self) -> None:
        import ui.window_notification_center as notification_center

        center = WindowNotificationCenter.__new__(WindowNotificationCenter)
        action_fn = Mock()
        bar = object()
        center._notification_action_pending = ("disable_proxy", action_fn, bar, {"reason": "test"})
        center._run_notification_action_worker = Mock()
        single_shot = Mock(side_effect=lambda _delay, _callback: None)

        with patch.object(notification_center, "QTimer", SimpleNamespace(singleShot=single_shot), create=True):
            WindowNotificationCenter._on_notification_action_worker_finished(center, object())

        single_shot.assert_called_once()
        self.assertEqual(single_shot.call_args.args[0], 0)
        center._run_notification_action_worker.assert_not_called()

        single_shot.call_args.args[1]()

        center._run_notification_action_worker.assert_called_once_with(
            "disable_proxy",
            action_fn,
            bar,
            {"reason": "test"},
        )

    def test_notification_action_scheduled_start_keeps_latest_request(self) -> None:
        import ui.window_notification_center as notification_center

        center = WindowNotificationCenter.__new__(WindowNotificationCenter)
        old_action_fn = Mock()
        new_action_fn = Mock()
        old_bar = object()
        new_bar = object()
        center._notification_action_pending = None
        center._notification_action_start_scheduled = False
        center._run_notification_action_worker = Mock()
        single_shot = Mock(side_effect=lambda _delay, _callback: None)

        with patch.object(notification_center, "QTimer", SimpleNamespace(singleShot=single_shot), create=True):
            WindowNotificationCenter._schedule_notification_action_worker_start(
                center,
                ("disable_proxy", old_action_fn, old_bar, {"reason": "old"}),
            )
            WindowNotificationCenter._schedule_notification_action_worker_start(
                center,
                ("disable_proxy", new_action_fn, new_bar, {"reason": "new"}),
            )

        single_shot.assert_called_once()

        single_shot.call_args.args[1]()

        center._run_notification_action_worker.assert_called_once_with(
            "disable_proxy",
            new_action_fn,
            new_bar,
            {"reason": "new"},
        )

    def test_launch_conflict_notification_action_runs_heavy_part_through_worker(self) -> None:
        handler_source = inspect.getsource(WindowNotificationActionHandler)
        center_source = inspect.getsource(WindowNotificationCenter)

        self.assertIn("_request_launch_conflict_action", handler_source)
        self.assertNotIn("resume_start_after_conflict_resolution(", handler_source)
        self.assertIn("prepare_launch_conflict_resolution", center_source)
        self.assertIn("continue_start_after_conflict_resolution", center_source)
        self.assertIn("launch_conflict_resume", center_source)
        self.assertIn("_notification_action_runtime", center_source)

    def test_notification_runtime_actions_are_narrow_instead_of_full_runtime_feature(self) -> None:
        handler_init_source = inspect.getsource(WindowNotificationActionHandler.__init__)
        handler_source = inspect.getsource(WindowNotificationActionHandler)
        center_init_source = inspect.getsource(WindowNotificationCenter.__init__)
        center_source = inspect.getsource(WindowNotificationCenter)
        setup_source = inspect.getsource(window_notifications_setup.attach_window_notifications)

        self.assertNotIn("runtime_feature", handler_init_source)
        self.assertNotIn("self._runtime =", handler_source)
        self.assertIn("runtime_actions", handler_init_source)
        self.assertIn("self._runtime_actions", handler_source)
        self.assertNotIn("runtime_feature", inspect.signature(WindowNotificationCenter.__init__).parameters)
        self.assertNotIn("self._runtime =", center_source)
        self.assertIn("runtime_actions", inspect.signature(WindowNotificationCenter.__init__).parameters)
        self.assertIn("WindowNotificationRuntimeActions", setup_source)

    def test_launch_conflict_prepare_does_not_start_dpi_from_worker_step(self) -> None:
        runtime_owner = SimpleNamespace(
            _pending_conflict_request_id=7,
            _pending_conflict_selected_mode="mode",
            _pending_conflict_launch_method="zapret2_mode",
            start_dpi_async=Mock(),
        )

        with (
            patch.object(conflict_flow, "try_kill_conflicting_processes", return_value=True) as kill_conflicts,
            patch.object(conflict_flow.time, "sleep") as sleep,
        ):
            ok, reason = conflict_flow.prepare_launch_conflict_resolution(
                runtime_owner,
                7,
                close_conflicts=True,
            )

        self.assertTrue(ok)
        self.assertEqual(reason, "")
        kill_conflicts.assert_called_once_with(auto_kill=True)
        sleep.assert_called_once_with(1)
        runtime_owner.start_dpi_async.assert_not_called()

        conflict_flow.continue_start_after_conflict_resolution(runtime_owner, 7)

        runtime_owner.start_dpi_async.assert_called_once_with(
            selected_mode="mode",
            launch_method="zapret2_mode",
            _skip_conflict_prompt=True,
        )


if __name__ == "__main__":
    unittest.main()
