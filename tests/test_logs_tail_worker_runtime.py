import inspect
import unittest

import log.runtime_workflow as log_runtime_workflow
from app.feature_facades.logs import LogsFeature
from log.ui.page import LogsPage


class LogsTailWorkerRuntimeTest(unittest.TestCase):
    def test_logs_tail_worker_uses_shared_runtime(self) -> None:
        page_source = inspect.getsource(LogsPage)
        start_source = inspect.getsource(LogsPage._start_tail_worker)
        stop_source = inspect.getsource(LogsPage._stop_tail_worker)
        runtime_start_source = inspect.getsource(log_runtime_workflow.start_tail_worker)
        runtime_stop_source = inspect.getsource(log_runtime_workflow.stop_tail_worker)
        feature_source = inspect.getsource(LogsFeature)

        self.assertIn("_tail_runtime = OneShotWorkerRuntime()", page_source)
        self.assertIn("tail_runtime=self._tail_runtime", start_source)
        self.assertIn("stop_tail_worker", stop_source)
        self.assertIn("start_qobject_worker", runtime_start_source)
        self.assertIn("tail_runtime.stop", runtime_stop_source)
        self.assertIn("def stop_tail_worker", feature_source)
        self.assertNotIn("QThread", page_source)
        self.assertNotIn("thread_cls", runtime_start_source)
        self.assertNotIn("thread.start()", runtime_start_source)
        self.assertNotIn("handle_thread_stop", page_source)
        self.assertNotIn("build_thread_stop_plan", feature_source)


if __name__ == "__main__":
    unittest.main()
