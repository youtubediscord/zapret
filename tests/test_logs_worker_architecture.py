from __future__ import annotations

import inspect
import unittest

from app.feature_facades.logs import LogsFeature
import log.open_folder_worker as open_folder_worker
import log.support_worker as support_worker


class LogsWorkerArchitectureTests(unittest.TestCase):
    def test_logs_workers_receive_feature_actions_not_feature_object(self) -> None:
        feature_source = inspect.getsource(LogsFeature)
        worker_source = "\n".join(
            (
                inspect.getsource(open_folder_worker.LogsOpenFolderWorker),
                inspect.getsource(support_worker.LogsSupportPrepareWorker),
            )
        )

        self.assertNotIn("logs_feature=self", feature_source)
        self.assertNotIn("self._logs", worker_source)
        self.assertIn("open_logs_folder=self.open_logs_folder", feature_source)
        self.assertIn("open_logs_folder", inspect.signature(open_folder_worker.LogsOpenFolderWorker.__init__).parameters)
        self.assertIn("self._open_logs_folder", inspect.getsource(open_folder_worker.LogsOpenFolderWorker.run))
        self.assertNotIn("import log.commands", inspect.getsource(open_folder_worker.LogsOpenFolderWorker.run))
        self.assertIn("prepare_support_bundle=self.prepare_support_bundle", feature_source)
        self.assertIn("_prepare_support_bundle", worker_source)
        self.assertNotIn("log_commands.prepare_support_bundle", worker_source)
        self.assertNotIn("import log.commands", inspect.getsource(support_worker.LogsSupportPrepareWorker.run))


if __name__ == "__main__":
    unittest.main()
