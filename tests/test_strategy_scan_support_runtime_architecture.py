import inspect
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from blockcheck.ui.strategy_scan_page import StrategyScanPage


class StrategyScanSupportRuntimeArchitectureTests(unittest.TestCase):
    def test_support_prepare_uses_runtime_not_manual_page_worker(self) -> None:
        page_source = inspect.getsource(StrategyScanPage)
        request_source = "\n".join(
            (
                inspect.getsource(StrategyScanPage._request_support_prepare),
                inspect.getsource(StrategyScanPage._start_support_prepare_worker),
            )
        )
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

    def test_support_prepare_queues_latest_request_while_worker_runs(self) -> None:
        class _Runtime:
            def is_running(self) -> bool:
                return True

        page = StrategyScanPage.__new__(StrategyScanPage)
        page._support_prepare_runtime = _Runtime()
        page._support_prepare_pending = None
        page._support_prepare_start_scheduled = False
        page._set_support_status = Mock()
        page._prepare_support_btn = SimpleNamespace(setEnabled=Mock())

        StrategyScanPage._request_support_prepare(
            page,
            run_log_file="first.log",
            target="old.example",
            protocol_label="TCP",
            mode_label="Quick",
            scan_protocol="tcp",
        )
        StrategyScanPage._request_support_prepare(
            page,
            run_log_file="second.log",
            target="new.example",
            protocol_label="UDP",
            mode_label="Full",
            scan_protocol="udp",
        )

        self.assertEqual(
            page._support_prepare_pending,
            {
                "run_log_file": "second.log",
                "target": "new.example",
                "protocol_label": "UDP",
                "mode_label": "Full",
                "scan_protocol": "udp",
            },
        )
        page._prepare_support_btn.setEnabled.assert_not_called()

    def test_support_prepare_pending_restarts_after_event_loop_turn(self) -> None:
        import blockcheck.ui.strategy_scan_page as strategy_scan_page

        pending = {
            "run_log_file": "support.log",
            "target": "new.example",
            "protocol_label": "TCP",
            "mode_label": "Full",
            "scan_protocol": "tcp",
        }
        page = StrategyScanPage.__new__(StrategyScanPage)
        page._cleanup_in_progress = False
        page._support_prepare_pending = pending
        page._support_prepare_start_scheduled = False
        page._prepare_support_btn = SimpleNamespace(setEnabled=Mock())
        page._set_support_status = Mock()
        page._start_support_prepare_worker = Mock()
        single_shot = Mock(side_effect=lambda _delay, _callback: None)

        with patch.object(strategy_scan_page, "QTimer", SimpleNamespace(singleShot=single_shot), create=True):
            StrategyScanPage._on_support_prepare_runtime_finished(page, object())

        single_shot.assert_called_once()
        self.assertEqual(single_shot.call_args.args[0], 0)
        page._prepare_support_btn.setEnabled.assert_not_called()
        page._start_support_prepare_worker.assert_not_called()

        single_shot.call_args.args[1]()

        page._start_support_prepare_worker.assert_called_once_with(pending)
        self.assertIsNone(page._support_prepare_pending)

    def test_stale_support_prepare_runtime_finish_does_not_restart_pending_prepare(self) -> None:
        pending = {
            "run_log_file": "support.log",
            "target": "new.example",
            "protocol_label": "TCP",
            "mode_label": "Full",
            "scan_protocol": "tcp",
        }
        page = StrategyScanPage.__new__(StrategyScanPage)
        page._support_prepare_runtime = SimpleNamespace(request_id=2)
        page._support_prepare_pending = pending
        page._schedule_support_prepare_worker_start = Mock()
        page._prepare_support_btn = SimpleNamespace(setEnabled=Mock())

        StrategyScanPage._on_support_prepare_runtime_finished(page, SimpleNamespace(_request_id=1))

        page._schedule_support_prepare_worker_start.assert_not_called()
        page._prepare_support_btn.setEnabled.assert_not_called()
        self.assertEqual(page._support_prepare_pending, pending)

    def test_support_prepare_result_is_ignored_when_new_prepare_is_pending(self) -> None:
        page = StrategyScanPage.__new__(StrategyScanPage)
        page._cleanup_in_progress = False
        page._support_prepare_pending = {
            "run_log_file": "new.log",
            "target": "new.example",
            "protocol_label": "TCP",
            "mode_label": "Full",
            "scan_protocol": "tcp",
        }
        page._support_prepare_runtime = Mock()
        page._support_prepare_runtime.is_current.return_value = True
        page._blockcheck = Mock()
        page._blockcheck.build_support_success_plan.return_value = SimpleNamespace(
            status_text="old status",
            title_key="old.title",
            title_default="Old",
            body_text="old body",
        )
        page._set_support_status = Mock()
        feedback = SimpleNamespace(result=SimpleNamespace(zip_path=None))

        StrategyScanPage._on_support_prepare_finished(page, 2, feedback)

        page._blockcheck.build_support_success_plan.assert_not_called()
        page._set_support_status.assert_not_called()

    def test_support_prepare_error_is_ignored_when_new_prepare_is_pending(self) -> None:
        page = StrategyScanPage.__new__(StrategyScanPage)
        page._cleanup_in_progress = False
        page._support_prepare_pending = {
            "run_log_file": "new.log",
            "target": "new.example",
            "protocol_label": "TCP",
            "mode_label": "Full",
            "scan_protocol": "tcp",
        }
        page._support_prepare_runtime = Mock()
        page._support_prepare_runtime.is_current.return_value = True
        page._blockcheck = Mock()
        page._blockcheck.build_support_error_plan.return_value = SimpleNamespace(
            status_text="old error status",
            title_key="old.error",
            title_default="Old error",
            body_text="old error body",
        )
        page._set_support_status = Mock()

        StrategyScanPage._on_support_prepare_failed(page, 2, "old error")

        page._blockcheck.build_support_error_plan.assert_not_called()
        page._set_support_status.assert_not_called()


if __name__ == "__main__":
    unittest.main()
