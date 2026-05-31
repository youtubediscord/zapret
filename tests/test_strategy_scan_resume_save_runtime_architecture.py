import inspect
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from blockcheck.ui.strategy_scan_page import StrategyScanPage


class StrategyScanResumeSaveRuntimeArchitectureTests(unittest.TestCase):
    def test_resume_save_uses_runtime_not_manual_page_worker(self) -> None:
        page_source = inspect.getsource(StrategyScanPage)
        request_source = inspect.getsource(StrategyScanPage._request_strategy_scan_resume_save)
        start_source = inspect.getsource(StrategyScanPage._start_strategy_scan_resume_save_worker)
        finished_source = inspect.getsource(StrategyScanPage._on_strategy_scan_resume_save_finished)
        failed_source = inspect.getsource(StrategyScanPage._on_strategy_scan_resume_save_failed)
        runtime_finished = getattr(
            StrategyScanPage,
            "_on_strategy_scan_resume_save_runtime_finished",
            None,
        )
        runtime_finished_source = inspect.getsource(runtime_finished) if runtime_finished else ""
        cleanup_source = inspect.getsource(StrategyScanPage.cleanup)

        self.assertIn("_strategy_scan_resume_save_runtime = OneShotWorkerRuntime()", page_source)
        self.assertIn("_strategy_scan_resume_save_runtime.is_running()", request_source)
        self.assertIn("start_qthread_worker", start_source)
        self.assertIn("bind_worker", start_source)
        self.assertIn("_on_strategy_scan_resume_save_runtime_finished", start_source)
        self.assertIn("_strategy_scan_resume_save_runtime.is_current", finished_source)
        self.assertIn("_strategy_scan_resume_save_runtime.is_current", failed_source)
        self.assertIn("_strategy_scan_resume_save_pending", runtime_finished_source)
        self.assertIn("_strategy_scan_resume_save_runtime.stop", cleanup_source)
        self.assertIn("_strategy_scan_resume_save_runtime.cancel", cleanup_source)
        self.assertNotIn("_strategy_scan_resume_save_worker =", page_source)
        self.assertNotIn("_strategy_scan_resume_save_request_id", page_source)
        self.assertNotIn("worker.start()", start_source)

    def test_pending_resume_save_restarts_after_event_loop_turn(self) -> None:
        import blockcheck.ui.strategy_scan_page as strategy_scan_page

        page = StrategyScanPage.__new__(StrategyScanPage)
        pending = {
            "scan_target": "example.org",
            "scan_protocol": "tcp_https",
            "udp_games_scope": "all",
            "next_index": 2,
        }
        page._strategy_scan_resume_save_pending = pending
        page._cleanup_in_progress = False
        page._start_strategy_scan_resume_save_worker = Mock()
        single_shot = Mock(side_effect=lambda _delay, _callback: None)

        with patch.object(strategy_scan_page, "QTimer", SimpleNamespace(singleShot=single_shot), create=True):
            StrategyScanPage._on_strategy_scan_resume_save_runtime_finished(page, object())

        single_shot.assert_called_once()
        self.assertEqual(single_shot.call_args.args[0], 0)
        page._start_strategy_scan_resume_save_worker.assert_not_called()

        single_shot.call_args.args[1]()

        page._start_strategy_scan_resume_save_worker.assert_called_once_with(pending)


if __name__ == "__main__":
    unittest.main()
