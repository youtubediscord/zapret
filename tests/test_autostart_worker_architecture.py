from __future__ import annotations

import inspect
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from app.feature_facades.autostart import build_autostart_feature
import autostart.workers as autostart_workers
import autostart.ui.page as autostart_page
from autostart.ui.page import AutostartPage


class AutostartWorkerArchitectureTests(unittest.TestCase):
    def test_autostart_workers_use_public_commands_not_feature_object(self) -> None:
        feature_source = inspect.getsource(build_autostart_feature)
        feature_cls_source = inspect.getsource(__import__("app.feature_facades.autostart", fromlist=["AutostartFeature"]).AutostartFeature)
        worker_source = "\n".join(
            (
                inspect.getsource(autostart_workers.AutostartActionWorker),
                inspect.getsource(autostart_workers.AutostartModeLoadWorker),
            )
        )

        self.assertNotIn("autostart_feature=feature", feature_source)
        self.assertNotIn("self._autostart", worker_source)
        self.assertIn("enable_gui_autostart=feature.enable_gui_autostart", feature_source)
        self.assertIn("disable_gui_autostart=feature.disable_gui_autostart", feature_source)
        self.assertIn("save_gui_autostart_enabled=feature.save_gui_autostart_enabled", feature_source)
        self.assertIn("get_current_launch_method=feature.get_current_launch_method", feature_source)
        self.assertIn("self._enable_gui_autostart", worker_source)
        self.assertIn("self._disable_gui_autostart", worker_source)
        self.assertIn("self._save_gui_autostart_enabled", worker_source)
        self.assertIn("self._get_current_launch_method", worker_source)
        self.assertNotIn("import autostart.public", worker_source)
        self.assertNotIn("set_autostart_enabled", feature_cls_source)
        self.assertNotIn("_set_autostart_enabled", feature_source)

    def test_autostart_page_uses_one_shot_runtime_for_workers(self) -> None:
        page_source = inspect.getsource(AutostartPage)
        action_start_source = inspect.getsource(AutostartPage._start_autostart_action_worker)
        mode_start_source = inspect.getsource(AutostartPage._start_mode_load_worker)
        cleanup_source = inspect.getsource(AutostartPage.cleanup)

        self.assertIn("OneShotWorkerRuntime", page_source)
        self.assertIn("_autostart_action_runtime", page_source)
        self.assertIn("_mode_load_runtime", page_source)
        self.assertIn("start_qthread_worker", action_start_source)
        self.assertIn("start_qthread_worker", mode_start_source)
        self.assertIn("_autostart_action_runtime.stop", cleanup_source)
        self.assertIn("_mode_load_runtime.stop", cleanup_source)
        self.assertNotIn("worker.start()", action_start_source)
        self.assertNotIn("worker.start()", mode_start_source)

    def test_autostart_action_pending_restarts_after_event_loop_turn(self) -> None:
        page = AutostartPage.__new__(AutostartPage)
        page._cleanup_in_progress = False
        page._autostart_action_pending = [("enable", True, "Strategy")]
        page._start_autostart_action_worker = Mock()
        single_shot = Mock(side_effect=lambda _delay, _callback: None)

        with patch.object(autostart_page, "QTimer", SimpleNamespace(singleShot=single_shot), create=True):
            AutostartPage._on_autostart_action_worker_finished(page, object())

        single_shot.assert_called_once()
        self.assertEqual(single_shot.call_args.args[0], 0)
        page._start_autostart_action_worker.assert_not_called()

        single_shot.call_args.args[1]()

        page._start_autostart_action_worker.assert_called_once_with(("enable", True, "Strategy"))

    def test_autostart_action_scheduled_start_queues_next_action(self) -> None:
        page = AutostartPage.__new__(AutostartPage)
        page._cleanup_in_progress = False
        page._autostart_action_start_scheduled = False
        page._autostart_action_pending = []
        page._start_autostart_action_worker = Mock()
        single_shot = Mock(side_effect=lambda _delay, _callback: None)

        old_payload = ("enable", True, "Old")
        new_payload = ("enable", True, "New")
        with patch.object(autostart_page, "QTimer", SimpleNamespace(singleShot=single_shot), create=True):
            AutostartPage._schedule_autostart_action_worker_start(page, old_payload)
            AutostartPage._schedule_autostart_action_worker_start(page, new_payload)

        single_shot.assert_called_once()
        self.assertEqual(page._autostart_action_pending, [new_payload])

        single_shot.call_args.args[1]()

        page._start_autostart_action_worker.assert_called_once_with(old_payload)
        self.assertEqual(page._autostart_action_pending, [new_payload])

    def test_mode_load_pending_restarts_after_event_loop_turn(self) -> None:
        page = AutostartPage.__new__(AutostartPage)
        page._cleanup_in_progress = False
        page._mode_load_pending = True
        page._start_mode_load_worker = Mock()
        single_shot = Mock(side_effect=lambda _delay, _callback: None)

        with patch.object(autostart_page, "QTimer", SimpleNamespace(singleShot=single_shot), create=True):
            AutostartPage._on_mode_load_worker_finished(page, object())

        single_shot.assert_called_once()
        self.assertEqual(single_shot.call_args.args[0], 0)
        page._start_mode_load_worker.assert_not_called()

        single_shot.call_args.args[1]()

        page._start_mode_load_worker.assert_called_once_with()

    def test_mode_load_scheduled_start_queues_next_refresh(self) -> None:
        page = AutostartPage.__new__(AutostartPage)
        page._cleanup_in_progress = False
        page._mode_load_start_scheduled = False
        page._mode_load_pending = False
        page._start_mode_load_worker = Mock()
        single_shot = Mock(side_effect=lambda _delay, _callback: None)

        with patch.object(autostart_page, "QTimer", SimpleNamespace(singleShot=single_shot), create=True):
            AutostartPage._schedule_mode_load_worker_start(page)
            AutostartPage._schedule_mode_load_worker_start(page)

        single_shot.assert_called_once()
        self.assertTrue(page._mode_load_pending)

        single_shot.call_args.args[1]()

        page._start_mode_load_worker.assert_called_once_with()
        self.assertTrue(page._mode_load_pending)


if __name__ == "__main__":
    unittest.main()
