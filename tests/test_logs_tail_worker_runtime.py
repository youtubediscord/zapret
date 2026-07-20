import inspect
import unittest

import log.runtime_workflow as log_runtime_workflow
from app.feature_facades.logs import LogsFeature
from log.ui.page import LogsPage


class LogsTailWorkerRuntimeTest(unittest.TestCase):
    def test_old_log_reader_uses_shared_runtime_and_live_log_uses_bridge(self) -> None:
        page_source = inspect.getsource(LogsPage)
        start_source = inspect.getsource(LogsPage._start_log_source)
        stop_source = inspect.getsource(LogsPage._stop_log_source)
        runtime_start_source = inspect.getsource(log_runtime_workflow.start_log_file_reader)
        runtime_stop_source = inspect.getsource(log_runtime_workflow.stop_log_source)
        feature_source = inspect.getsource(LogsFeature)

        self.assertIn("_log_reader_runtime = OneShotWorkerRuntime()", page_source)
        self.assertIn("reader_runtime=self._log_reader_runtime", start_source)
        self.assertIn("stop_log_source", stop_source)
        self.assertIn("create_live_log_bridge", start_source)
        self.assertIn("start_qobject_worker", runtime_start_source)
        self.assertIn("reader_runtime.stop", runtime_stop_source)
        self.assertIn("def stop_log_source", feature_source)
        self.assertNotIn("QThread", page_source)
        self.assertNotIn("thread_cls", runtime_start_source)
        self.assertNotIn("thread.start()", runtime_start_source)
        self.assertNotIn("handle_thread_stop", page_source)
        self.assertNotIn("time.sleep", page_source)


if __name__ == "__main__":
    unittest.main()
