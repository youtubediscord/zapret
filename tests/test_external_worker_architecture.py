from __future__ import annotations

import inspect
import unittest

from app.feature_facades.external import ExternalActionsFeature
import app.external_workers as external_workers


class ExternalWorkerArchitectureTests(unittest.TestCase):
    def test_open_url_worker_uses_commands_not_feature_object(self) -> None:
        feature_source = inspect.getsource(ExternalActionsFeature)
        worker_source = inspect.getsource(external_workers.ExternalOpenUrlWorker)

        self.assertNotIn("external_actions_feature=self", feature_source)
        self.assertNotIn("self._external_actions", worker_source)
        self.assertIn("external_commands.open_url", worker_source)


if __name__ == "__main__":
    unittest.main()
