from __future__ import annotations

import inspect
import importlib
import importlib.util
import unittest

from main import window_notifications_setup
from ui.window_notification_actions import WindowNotificationActionHandler
from ui.window_notification_center import WindowNotificationCenter


class WindowNotificationActionsContractTests(unittest.TestCase):
    def test_notification_open_url_action_runs_through_external_worker(self) -> None:
        handler_init_source = inspect.getsource(WindowNotificationActionHandler.__init__)
        handler_callback_source = inspect.getsource(WindowNotificationActionHandler.build_action_callback)
        center_source = inspect.getsource(WindowNotificationCenter)
        setup_source = inspect.getsource(window_notifications_setup.attach_window_notifications)

        self.assertIn("open_url", handler_init_source)
        self.assertIn("_open_url", handler_callback_source)
        self.assertNotIn("webbrowser.open", handler_callback_source)
        self.assertIn("_external_open_url_runtime", center_source)
        self.assertIn("create_open_url_worker", center_source)
        self.assertIn("features.external_actions", setup_source)

    def test_notification_system_actions_run_through_worker(self) -> None:
        spec = importlib.util.find_spec("ui.window_notification_action_workers")
        self.assertIsNotNone(spec)
        action_workers = importlib.import_module("ui.window_notification_action_workers")

        handler_source = inspect.getsource(WindowNotificationActionHandler)
        handler_callback_source = inspect.getsource(WindowNotificationActionHandler.build_action_callback)
        center_source = inspect.getsource(WindowNotificationCenter)

        self.assertTrue(hasattr(action_workers, "NotificationActionWorker"))
        worker_source = inspect.getsource(action_workers.NotificationActionWorker.run)
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


if __name__ == "__main__":
    unittest.main()
