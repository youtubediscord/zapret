from __future__ import annotations

import inspect
import unittest

from app.feature_facades.autostart import build_autostart_feature
import autostart.workers as autostart_workers
from autostart.ui.page import AutostartPage


class AutostartWorkerArchitectureTests(unittest.TestCase):
    def test_autostart_workers_use_public_commands_not_feature_object(self) -> None:
        feature_source = inspect.getsource(build_autostart_feature)
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


if __name__ == "__main__":
    unittest.main()
