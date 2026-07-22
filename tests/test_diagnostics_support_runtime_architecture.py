from __future__ import annotations

import inspect
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from diagnostics.ui.page import ConnectionTestPage
import diagnostics.ui.runtime_helpers as diagnostics_runtime_helpers
from diagnostics.worker import ConnectionTestWorker


class DiagnosticsSupportRuntimeArchitectureTests(unittest.TestCase):
    def test_connection_worker_constructor_does_not_touch_log_file(self) -> None:
        constructor_source = inspect.getsource(ConnectionTestWorker.__init__)
        run_source = inspect.getsource(ConnectionTestWorker.run)
        stop_source = inspect.getsource(ConnectionTestWorker.stop_gracefully)

        self.assertNotIn("makedirs", constructor_source)
        self.assertNotIn("FileHandler", constructor_source)
        self.assertIn("self._open_logger()", run_source)
        self.assertNotIn("log_message", stop_source)

    def test_connection_cleanup_requests_stop_without_waiting_for_worker(self) -> None:
        worker = object()
        runtime = SimpleNamespace(
            worker=worker,
            is_running=Mock(return_value=True),
            stop=Mock(),
            cancel=Mock(),
        )

        with patch.object(diagnostics_runtime_helpers, "release_worker_resources") as release:
            state = diagnostics_runtime_helpers.cleanup_connection_runtime(
                cleanup_in_progress=False,
                finish_mode="completed",
                stop_check_timer=None,
                runtime=runtime,
                log_debug=Mock(),
                log_warning=Mock(),
            )

        runtime.stop.assert_called_once()
        self.assertIs(runtime.stop.call_args.kwargs["blocking"], False)
        release.assert_not_called()
        runtime.cancel.assert_called_once()
        self.assertFalse(state["is_testing"])

    def test_connection_worker_releases_resources_when_worker_finishes(self) -> None:
        class _Signal:
            def __init__(self) -> None:
                self._callbacks = []

            def connect(self, callback) -> None:
                self._callbacks.append(callback)

            def emit(self) -> None:
                for callback in list(self._callbacks):
                    callback()

        worker = SimpleNamespace(
            update_signal=_Signal(),
            finished_signal=_Signal(),
            finished=_Signal(),
        )
        page = ConnectionTestPage.__new__(ConnectionTestPage)
        page._on_worker_update = Mock()
        page._on_worker_finished = Mock()

        with patch("diagnostics.ui.page.release_worker_resources") as release:
            ConnectionTestPage._bind_connection_test_worker(page, worker)
            release.assert_not_called()

            worker.finished.emit()

        release.assert_called_once_with(worker)

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

    def test_support_prepare_result_is_ignored_when_new_prepare_is_pending(self) -> None:
        page = ConnectionTestPage.__new__(ConnectionTestPage)
        page._cleanup_in_progress = False
        page._support_prepare_pending = {"selection": "YouTube"}
        page._support_prepare_runtime = Mock()
        page._support_prepare_runtime.is_current.return_value = True
        page._append = Mock()
        page._set_status = Mock()
        plan = SimpleNamespace(
            log_lines=["old support line"],
            status_text="old status",
            status_tone="success",
        )

        ConnectionTestPage._on_support_prepare_finished(page, 7, plan)

        page._append.assert_not_called()
        page._set_status.assert_not_called()

    def test_support_prepare_error_is_ignored_when_new_prepare_is_pending(self) -> None:
        page = ConnectionTestPage.__new__(ConnectionTestPage)
        page._cleanup_in_progress = False
        page._support_prepare_pending = {"selection": "YouTube"}
        page._support_prepare_runtime = Mock()
        page._support_prepare_runtime.is_current.return_value = True
        page._append = Mock()
        page._set_status = Mock()

        ConnectionTestPage._on_support_prepare_failed(page, 7, "old error")

        page._append.assert_not_called()
        page._set_status.assert_not_called()

    def test_support_prepare_state_uses_shared_latest_value_helper(self) -> None:
        import diagnostics.ui.page as diagnostics_page
        from ui.latest_value_worker_state import LatestValueWorkerState

        init_source = inspect.getsource(ConnectionTestPage.__init__)
        request_source = inspect.getsource(ConnectionTestPage._request_support_prepare)
        finished_source = inspect.getsource(ConnectionTestPage._on_support_prepare_worker_finished)
        cleanup_source = inspect.getsource(ConnectionTestPage.cleanup)

        self.assertTrue(hasattr(diagnostics_page, "LatestValueWorkerState"))
        self.assertIs(diagnostics_page.LatestValueWorkerState, LatestValueWorkerState)
        self.assertIn("_support_prepare_state = LatestValueWorkerState", init_source)
        self.assertIn("_support_prepare_state_obj()", request_source)
        self.assertIn("schedule_pending_after_finish", finished_source)
        self.assertIn("_support_prepare_state_obj().reset()", cleanup_source)

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
        self.assertIn("_support_prepare_state = LatestValueWorkerState", page_source)
        self.assertIn("start_qthread_worker", request_source)
        self.assertIn("create_support_prepare_worker", request_source)
        self.assertIn("schedule_pending_after_finish", finished_source)
        self.assertIn("_support_prepare_runtime.stop", cleanup_source)
        self.assertIn("_support_prepare_runtime.cancel", cleanup_source)
        self.assertNotIn("_support_prepare_worker =", page_source)


if __name__ == "__main__":
    unittest.main()
