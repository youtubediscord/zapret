import inspect
import unittest

from blockcheck.ui.strategy_scan_page import StrategyScanPage


class StrategyScanSupportRuntimeArchitectureTests(unittest.TestCase):
    def test_support_prepare_uses_runtime_not_manual_page_worker(self) -> None:
        page_source = inspect.getsource(StrategyScanPage)
        request_source = inspect.getsource(StrategyScanPage._request_support_prepare)
        finished_source = inspect.getsource(StrategyScanPage._on_support_prepare_finished)
        failed_source = inspect.getsource(StrategyScanPage._on_support_prepare_failed)
        cleanup_source = inspect.getsource(StrategyScanPage.cleanup)

        self.assertIn("_support_prepare_runtime = OneShotWorkerRuntime()", page_source)
        self.assertIn("_support_prepare_runtime.is_running()", request_source)
        self.assertIn("start_qthread_worker", request_source)
        self.assertIn("bind_worker", request_source)
        self.assertIn("_on_support_prepare_runtime_finished", request_source)
        self.assertIn("_support_prepare_runtime.is_current", finished_source)
        self.assertIn("_support_prepare_runtime.is_current", failed_source)
        self.assertIn("_support_prepare_runtime.stop", cleanup_source)
        self.assertIn("_support_prepare_runtime.cancel", cleanup_source)
        self.assertNotIn("_support_prepare_worker =", page_source)
        self.assertNotIn("_support_prepare_request_id", page_source)
        self.assertNotIn("worker.start()", request_source)


if __name__ == "__main__":
    unittest.main()
