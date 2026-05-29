from __future__ import annotations

import inspect
import unittest

from app.feature_facades.autostart import build_autostart_feature
import autostart.workers as autostart_workers


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
        self.assertIn("autostart_public.enable_gui_autostart", worker_source)
        self.assertIn("autostart_public.disable_gui_autostart", worker_source)
        self.assertIn("autostart_public.save_gui_autostart_enabled", worker_source)
        self.assertIn("autostart_public.get_current_launch_method", worker_source)


if __name__ == "__main__":
    unittest.main()
