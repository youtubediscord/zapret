import inspect
import unittest
from unittest.mock import Mock

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
        self.assertIn("run_runtime.start_qobject_worker", workflow_source)
        self.assertNotIn("self._worker", page_source)
        self.assertNotIn("worker.start()", workflow_source)

    def test_strategy_scan_page_leaves_run_worker_deletion_to_shared_runtime(self) -> None:
        finished_source = inspect.getsource(StrategyScanPage._on_finished)

        self.assertNotIn("delete_strategy_scan_worker_later", finished_source)
        self.assertNotIn("deleteLater", finished_source)

    def test_runtime_conflicting_stop_uses_strategy_scan_stop_path(self) -> None:
        page = StrategyScanPage.__new__(StrategyScanPage)
        page._strategy_scan_run_runtime = Mock()
        page._strategy_scan_run_runtime.is_running.return_value = True
        page._on_stop = Mock()

        stopped = StrategyScanPage.request_runtime_conflicting_stop(page)

        self.assertTrue(stopped)
        page._on_stop.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
