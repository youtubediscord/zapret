import inspect
import unittest

from blockcheck.ui.strategy_scan_page import StrategyScanPage


class StrategyScanQuickTargetsRuntimeArchitectureTests(unittest.TestCase):
    def test_quick_targets_menu_uses_runtime_not_manual_page_worker(self) -> None:
        page_source = inspect.getsource(StrategyScanPage)
        request_source = inspect.getsource(StrategyScanPage._request_quick_targets_menu)
        loaded_source = inspect.getsource(StrategyScanPage._on_quick_targets_loaded)
        failed_source = inspect.getsource(StrategyScanPage._on_quick_targets_failed)
        cleanup_source = inspect.getsource(StrategyScanPage.cleanup)

        self.assertIn("_quick_targets_runtime = OneShotWorkerRuntime()", page_source)
        self.assertIn("_quick_targets_runtime.is_running()", request_source)
        self.assertIn("start_qthread_worker", request_source)
        self.assertIn("bind_worker", request_source)
        self.assertIn("_quick_targets_runtime.is_current", loaded_source)
        self.assertIn("_quick_targets_runtime.is_current", failed_source)
        self.assertIn("_quick_targets_runtime.stop", cleanup_source)
        self.assertIn("_quick_targets_runtime.cancel", cleanup_source)
        self.assertNotIn("_quick_targets_worker =", page_source)
        self.assertNotIn("_quick_targets_request_id", page_source)
        self.assertNotIn("worker.start()", request_source)


if __name__ == "__main__":
    unittest.main()
