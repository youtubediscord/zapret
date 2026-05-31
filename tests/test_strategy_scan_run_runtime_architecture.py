import inspect
import unittest

from blockcheck import strategy_scan_run_workflow
from blockcheck.ui.strategy_scan_page import StrategyScanPage


class StrategyScanRunRuntimeArchitectureTest(unittest.TestCase):
    def test_strategy_scan_run_worker_starts_through_shared_runtime(self) -> None:
        page_source = inspect.getsource(StrategyScanPage)
        start_source = inspect.getsource(StrategyScanPage._on_start)
        cleanup_source = inspect.getsource(StrategyScanPage.cleanup)
        workflow_source = inspect.getsource(strategy_scan_run_workflow.start_strategy_scan_worker)

        self.assertIn("_strategy_scan_run_runtime = OneShotWorkerRuntime()", page_source)
        self.assertIn("run_runtime=self._strategy_scan_run_runtime", start_source)
        self.assertIn("_strategy_scan_run_runtime.stop", cleanup_source)
        self.assertIn("run_runtime.start_qthread_worker", workflow_source)
        self.assertNotIn("worker.start()", workflow_source)


if __name__ == "__main__":
    unittest.main()
