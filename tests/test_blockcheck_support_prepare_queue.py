from __future__ import annotations

import inspect
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from blockcheck.ui.page import BlockcheckPage


class BlockcheckSupportPrepareQueueTests(unittest.TestCase):
    def test_support_prepare_state_uses_shared_latest_value_helper(self) -> None:
        import blockcheck.ui.page as blockcheck_page
        from ui.latest_value_worker_state import LatestValueWorkerState

        init_source = inspect.getsource(BlockcheckPage.__init__)
        request_source = inspect.getsource(BlockcheckPage._request_support_prepare)
        finished_source = inspect.getsource(BlockcheckPage._on_support_prepare_runtime_finished)
        cleanup_source = inspect.getsource(BlockcheckPage.cleanup)

        self.assertTrue(hasattr(blockcheck_page, "LatestValueWorkerState"))
        self.assertIs(blockcheck_page.LatestValueWorkerState, LatestValueWorkerState)
        self.assertIn("_support_prepare_state = LatestValueWorkerState", init_source)
        self.assertIn("_support_prepare_state_obj()", request_source)
        self.assertIn("schedule_pending_after_finish", finished_source)
        self.assertIn("_support_prepare_state_obj().reset()", cleanup_source)

    def test_support_prepare_queues_latest_request_while_worker_runs(self) -> None:
        class _Runtime:
            def is_running(self) -> bool:
                return True

        page = BlockcheckPage.__new__(BlockcheckPage)
        page._support_prepare_runtime = _Runtime()
        page._support_prepare_pending = None
        page._support_prepare_start_scheduled = False
        page._set_support_status = Mock()
        page._prepare_support_btn = SimpleNamespace(setEnabled=Mock())

        BlockcheckPage._request_support_prepare(
            page,
            run_log_file="first.log",
            mode_label="Quick",
            extra_domains=["old.example"],
        )
        BlockcheckPage._request_support_prepare(
            page,
            run_log_file="second.log",
            mode_label="Full",
            extra_domains=["new.example"],
        )

        self.assertEqual(
            page._support_prepare_pending,
            {
                "run_log_file": "second.log",
                "mode_label": "Full",
                "extra_domains": ["new.example"],
            },
        )
        page._prepare_support_btn.setEnabled.assert_not_called()

    def test_support_prepare_pending_restarts_after_event_loop_turn(self) -> None:
        import blockcheck.ui.page as blockcheck_page

        pending = {
            "run_log_file": "support.log",
            "mode_label": "Full",
            "extra_domains": ["new.example"],
        }
        page = BlockcheckPage.__new__(BlockcheckPage)
        page._cleanup_in_progress = False
        page._support_prepare_pending = pending
        page._support_prepare_start_scheduled = False
        page._prepare_support_btn = SimpleNamespace(setEnabled=Mock())
        page._set_support_status = Mock()
        page._start_support_prepare_worker = Mock()
        single_shot = Mock(side_effect=lambda _delay, _callback: None)

        with patch.object(blockcheck_page, "QTimer", SimpleNamespace(singleShot=single_shot), create=True):
            BlockcheckPage._on_support_prepare_runtime_finished(page, object())

        single_shot.assert_called_once()
        self.assertEqual(single_shot.call_args.args[0], 0)
        page._prepare_support_btn.setEnabled.assert_not_called()
        page._start_support_prepare_worker.assert_not_called()

        single_shot.call_args.args[1]()

        page._start_support_prepare_worker.assert_called_once_with(pending)
        self.assertIsNone(page._support_prepare_pending)

    def test_stale_support_prepare_finish_does_not_restart_pending_prepare(self) -> None:
        pending = {
            "run_log_file": "support.log",
            "mode_label": "Full",
            "extra_domains": ["new.example"],
        }
        page = BlockcheckPage.__new__(BlockcheckPage)
        page._cleanup_in_progress = False
        page._support_prepare_runtime = SimpleNamespace(request_id=5)
        page._support_prepare_pending = pending
        page._prepare_support_btn = SimpleNamespace(setEnabled=Mock())
        page._schedule_support_prepare_worker_start = Mock()

        BlockcheckPage._on_support_prepare_runtime_finished(page, SimpleNamespace(_request_id=4))

        page._schedule_support_prepare_worker_start.assert_not_called()
        page._prepare_support_btn.setEnabled.assert_not_called()

    def test_stale_support_prepare_worker_object_finish_does_not_restart_pending_prepare(self) -> None:
        pending = {
            "run_log_file": "support.log",
            "mode_label": "Full",
            "extra_domains": ["new.example"],
        }
        page = BlockcheckPage.__new__(BlockcheckPage)
        page._cleanup_in_progress = False
        page._support_prepare_runtime = SimpleNamespace(worker=object())
        page._support_prepare_pending = pending
        page._prepare_support_btn = SimpleNamespace(setEnabled=Mock())
        page._schedule_support_prepare_worker_start = Mock()

        BlockcheckPage._on_support_prepare_runtime_finished(page, object())

        page._schedule_support_prepare_worker_start.assert_not_called()
        page._prepare_support_btn.setEnabled.assert_not_called()

    def test_support_prepare_result_is_ignored_when_new_prepare_is_pending(self) -> None:
        page = BlockcheckPage.__new__(BlockcheckPage)
        page._cleanup_in_progress = False
        page._support_prepare_pending = {
            "run_log_file": "new.log",
            "mode_label": "Full",
            "extra_domains": ["new.example"],
        }
        page._support_prepare_runtime = Mock()
        page._support_prepare_runtime.is_current.return_value = True
        page._set_support_status = Mock()
        feedback = SimpleNamespace(
            result=SimpleNamespace(zip_path=None),
            status_text="old status",
            info_text="old info",
        )

        BlockcheckPage._on_support_prepare_finished(page, 5, feedback)

        page._set_support_status.assert_not_called()

    def test_support_prepare_error_is_ignored_when_new_prepare_is_pending(self) -> None:
        page = BlockcheckPage.__new__(BlockcheckPage)
        page._cleanup_in_progress = False
        page._support_prepare_pending = {
            "run_log_file": "new.log",
            "mode_label": "Full",
            "extra_domains": ["new.example"],
        }
        page._support_prepare_runtime = Mock()
        page._support_prepare_runtime.is_current.return_value = True
        page._set_support_status = Mock()

        BlockcheckPage._on_support_prepare_failed(page, 5, "old error")

        page._set_support_status.assert_not_called()


if __name__ == "__main__":
    unittest.main()
