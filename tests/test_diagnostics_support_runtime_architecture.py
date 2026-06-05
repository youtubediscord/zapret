from __future__ import annotations

import inspect
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from diagnostics.ui.page import ConnectionTestPage


class DiagnosticsSupportRuntimeArchitectureTests(unittest.TestCase):
    def test_support_prepare_queues_latest_request_while_worker_runs(self) -> None:
        class _Runtime:
            def is_running(self) -> bool:
                return True

        page = ConnectionTestPage.__new__(ConnectionTestPage)
        page._support_prepare_runtime = _Runtime()
        page._support_prepare_pending = None
        page._support_prepare_start_scheduled = False
        page.send_log_btn = SimpleNamespace(setEnabled=Mock())
        page._set_status = Mock()
        page.create_support_prepare_worker = Mock()

        ConnectionTestPage._request_support_prepare(page, selection="Discord")
        ConnectionTestPage._request_support_prepare(page, selection="YouTube")

        page.create_support_prepare_worker.assert_not_called()
        self.assertEqual(page._support_prepare_pending, {"selection": "YouTube"})
        page.send_log_btn.setEnabled.assert_not_called()

    def test_support_prepare_pending_restarts_after_event_loop_turn(self) -> None:
        import diagnostics.ui.page as diagnostics_page

        page = ConnectionTestPage.__new__(ConnectionTestPage)
        page._cleanup_in_progress = False
        page._support_prepare_pending = {"selection": "YouTube"}
        page._support_prepare_start_scheduled = False
        page.send_log_btn = SimpleNamespace(setEnabled=Mock())
        page._set_status = Mock()
        page._start_support_prepare_worker = Mock()
        single_shot = Mock(side_effect=lambda _delay, _callback: None)

        with patch.object(diagnostics_page, "QTimer", SimpleNamespace(singleShot=single_shot), create=True):
            ConnectionTestPage._on_support_prepare_worker_finished(page, object())

        single_shot.assert_called_once()
        self.assertEqual(single_shot.call_args.args[0], 0)
        page.send_log_btn.setEnabled.assert_not_called()
        page._start_support_prepare_worker.assert_not_called()

        single_shot.call_args.args[1]()

        page._start_support_prepare_worker.assert_called_once_with({"selection": "YouTube"})
        self.assertIsNone(page._support_prepare_pending)

    def test_stale_support_prepare_finish_does_not_restart_pending_prepare(self) -> None:
        page = ConnectionTestPage.__new__(ConnectionTestPage)
        page._cleanup_in_progress = False
        page._support_prepare_runtime = SimpleNamespace(request_id=3)
        page._support_prepare_pending = {"selection": "YouTube"}
        page.send_log_btn = SimpleNamespace(setEnabled=Mock())
        page._schedule_support_prepare_worker_start = Mock()

        ConnectionTestPage._on_support_prepare_worker_finished(page, SimpleNamespace(_request_id=2))

        page._schedule_support_prepare_worker_start.assert_not_called()
        page.send_log_btn.setEnabled.assert_not_called()

    def test_stale_support_prepare_worker_object_finish_does_not_restart_pending_prepare(self) -> None:
        old_worker = object()
        current_worker = object()
        page = ConnectionTestPage.__new__(ConnectionTestPage)
        page._cleanup_in_progress = False
        page._support_prepare_runtime = SimpleNamespace(request_id=3, worker=current_worker)
        page._support_prepare_pending = {"selection": "YouTube"}
        page.send_log_btn = SimpleNamespace(setEnabled=Mock())
        page._schedule_support_prepare_worker_start = Mock()

        ConnectionTestPage._on_support_prepare_worker_finished(page, old_worker)

        page._schedule_support_prepare_worker_start.assert_not_called()
        page.send_log_btn.setEnabled.assert_not_called()
        self.assertEqual(page._support_prepare_pending, {"selection": "YouTube"})

    def test_support_prepare_runtime_keeps_page_worker_boundary(self) -> None:
        page_source = inspect.getsource(ConnectionTestPage)
        request_source = "\n".join(
            (
                inspect.getsource(ConnectionTestPage._request_support_prepare),
                inspect.getsource(ConnectionTestPage._start_support_prepare_worker),
            )
        )
        finished_source = inspect.getsource(ConnectionTestPage._on_support_prepare_worker_finished)
        cleanup_source = inspect.getsource(ConnectionTestPage.cleanup)

        self.assertIn("_support_prepare_runtime = OneShotWorkerRuntime()", page_source)
        self.assertIn("_support_prepare_pending", page_source)
        self.assertIn("_support_prepare_start_scheduled", page_source)
        self.assertIn("start_qthread_worker", request_source)
        self.assertIn("create_support_prepare_worker", request_source)
        self.assertIn("_schedule_support_prepare_worker_start", finished_source)
        self.assertIn("_support_prepare_runtime.stop", cleanup_source)
        self.assertIn("_support_prepare_runtime.cancel", cleanup_source)
        self.assertNotIn("_support_prepare_worker =", page_source)


if __name__ == "__main__":
    unittest.main()
