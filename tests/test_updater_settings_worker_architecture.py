from __future__ import annotations

import inspect
import unittest

from app.feature_facades.updater import UpdaterFeature
import updater.settings_workers as settings_workers


class UpdaterSettingsWorkerArchitectureTests(unittest.TestCase):
    def test_auto_check_workers_receive_feature_action_callables(self) -> None:
        feature_source = inspect.getsource(UpdaterFeature)
        save_source = inspect.getsource(settings_workers.UpdaterAutoCheckSaveWorker)
        load_source = inspect.getsource(settings_workers.UpdaterAutoCheckLoadWorker)
        save_signature = inspect.signature(settings_workers.UpdaterAutoCheckSaveWorker.__init__)
        load_signature = inspect.signature(settings_workers.UpdaterAutoCheckLoadWorker.__init__)

        self.assertNotIn("updater_feature=self", feature_source)
        self.assertNotIn("self._updater", save_source)
        self.assertNotIn("self._updater", load_source)
        self.assertIn("set_auto_update_enabled=self.set_auto_update_enabled", feature_source)
        self.assertIn("is_auto_update_enabled=self.is_auto_update_enabled", feature_source)
        self.assertIn("set_auto_update_enabled", save_signature.parameters)
        self.assertIn("is_auto_update_enabled", load_signature.parameters)
        self.assertNotIn("updater_commands.set_auto_update_enabled", save_source)
        self.assertNotIn("updater_commands.is_auto_update_enabled", load_source)
        self.assertNotIn("import updater.commands", save_source)
        self.assertNotIn("import updater.commands", load_source)

    def test_channel_open_worker_receives_feature_action_callable(self) -> None:
        feature_source = inspect.getsource(UpdaterFeature)
        worker_source = inspect.getsource(settings_workers.UpdaterChannelOpenWorker)
        worker_signature = inspect.signature(settings_workers.UpdaterChannelOpenWorker.__init__)

        self.assertNotIn("updater_feature=self", feature_source)
        self.assertNotIn("self._updater", worker_source)
        self.assertIn("open_update_channel=self.open_update_channel", feature_source)
        self.assertIn("open_update_channel", worker_signature.parameters)
        self.assertNotIn("updater_commands.open_update_channel", worker_source)
        self.assertNotIn("import updater.commands", worker_source)


if __name__ == "__main__":
    unittest.main()
