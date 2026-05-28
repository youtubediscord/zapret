from __future__ import annotations

import inspect
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


if __name__ == "__main__":
    unittest.main()
