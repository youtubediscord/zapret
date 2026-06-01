from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from blockcheck.ui.page import BlockcheckPage


class BlockcheckSupportPrepareQueueTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
