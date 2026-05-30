import inspect
import unittest

from blockcheck.ui.strategy_scan_page import StrategyScanPage


class StrategyScanFinalizeRuntimeArchitectureTests(unittest.TestCase):
    def test_finalize_uses_runtime_not_manual_page_worker(self) -> None:
        page_source = inspect.getsource(StrategyScanPage)
        request_source = inspect.getsource(StrategyScanPage._request_strategy_scan_finalize)
        finished_source = inspect.getsource(StrategyScanPage._on_strategy_scan_finalize_finished)
        failed_source = inspect.getsource(StrategyScanPage._on_strategy_scan_finalize_failed)
        cleanup_source = inspect.getsource(StrategyScanPage.cleanup)

        self.assertIn("_strategy_scan_finalize_runtime = OneShotWorkerRuntime()", page_source)
        self.assertIn("_strategy_scan_finalize_runtime.is_running()", request_source)
        self.assertIn("start_qthread_worker", request_source)
        self.assertIn("bind_worker", request_source)
        self.assertIn("_strategy_scan_finalize_runtime.is_current", finished_source)
        self.assertIn("_strategy_scan_finalize_runtime.is_current", failed_source)
        self.assertIn("_strategy_scan_finalize_runtime.stop", cleanup_source)
        self.assertIn("_strategy_scan_finalize_runtime.cancel", cleanup_source)
        self.assertNotIn("_strategy_scan_finalize_worker =", page_source)
        self.assertNotIn("_strategy_scan_finalize_request_id", page_source)
        self.assertNotIn("worker.start()", request_source)


if __name__ == "__main__":
    unittest.main()
