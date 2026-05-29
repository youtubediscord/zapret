from __future__ import annotations

import inspect
import unittest

from app.feature_facades.updater import UpdaterFeature
import updater.commands as updater_commands
import updater.settings_workers as settings_workers


class UpdaterSettingsWorkerArchitectureTests(unittest.TestCase):
    def test_auto_check_workers_use_commands_not_feature_object(self) -> None:
        feature_source = inspect.getsource(UpdaterFeature)
        save_source = inspect.getsource(settings_workers.UpdaterAutoCheckSaveWorker)
        load_source = inspect.getsource(settings_workers.UpdaterAutoCheckLoadWorker)

        self.assertNotIn("updater_feature=self", feature_source)
        self.assertNotIn("self._updater", save_source)
        self.assertNotIn("self._updater", load_source)
        self.assertIn("updater_commands.set_auto_update_enabled", save_source)
        self.assertIn("updater_commands.is_auto_update_enabled", load_source)
        self.assertIn("set_auto_update_enabled", inspect.getsource(updater_commands.set_auto_update_enabled))
        self.assertIn("is_auto_update_enabled", inspect.getsource(updater_commands.is_auto_update_enabled))

    def test_channel_open_worker_uses_commands_not_feature_object(self) -> None:
        feature_source = inspect.getsource(UpdaterFeature)
        worker_source = inspect.getsource(settings_workers.UpdaterChannelOpenWorker)

        self.assertNotIn("updater_feature=self", feature_source)
        self.assertNotIn("self._updater", worker_source)
        self.assertIn("updater_commands.open_update_channel", worker_source)
        self.assertIn("open_update_channel", inspect.getsource(updater_commands.open_update_channel))


if __name__ == "__main__":
    unittest.main()
