import inspect
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from blockcheck.ui.page import BlockcheckPage


class BlockcheckUserDomainRuntimeArchitectureTests(unittest.TestCase):
    def test_user_domain_actions_use_runtime_not_manual_page_worker(self) -> None:
        page_source = inspect.getsource(BlockcheckPage)
        request_source = inspect.getsource(BlockcheckPage._request_user_domain_action)
        start_source = inspect.getsource(BlockcheckPage._start_user_domain_action_worker)
        finished_source = inspect.getsource(BlockcheckPage._on_user_domain_action_finished)
        failed_source = inspect.getsource(BlockcheckPage._on_user_domain_action_failed)
        cleanup_source = inspect.getsource(BlockcheckPage.cleanup)

        self.assertIn("_user_domain_action_runtime = OneShotWorkerRuntime()", page_source)
        self.assertIn("_user_domain_action_runtime.is_running()", request_source)
        self.assertIn("start_qthread_worker", start_source)
        self.assertIn("bind_worker", start_source)
        self.assertIn("_on_user_domain_action_runtime_finished", start_source)
        self.assertIn("_user_domain_action_runtime.is_current", finished_source)
        self.assertIn("_user_domain_action_runtime.is_current", failed_source)
        self.assertIn("_user_domain_action_runtime.stop", cleanup_source)
        self.assertIn("_user_domain_action_runtime.cancel", cleanup_source)
        self.assertNotIn("_user_domain_action_worker =", page_source)
        self.assertNotIn("_user_domain_action_request_id", page_source)
        self.assertNotIn("worker.start()", start_source)

    def test_pending_user_domain_action_restarts_after_event_loop_turn(self) -> None:
        import blockcheck.ui.page as blockcheck_page

        page = BlockcheckPage.__new__(BlockcheckPage)
        page._cleanup_in_progress = False
        page._user_domain_action_pending = [{"action": "add", "domain": "example.com"}]
        page._start_user_domain_action_worker = Mock()
        single_shot = Mock(side_effect=lambda _delay, _callback: None)

        with patch.object(blockcheck_page, "QTimer", SimpleNamespace(singleShot=single_shot), create=True):
            BlockcheckPage._on_user_domain_action_runtime_finished(page, object())

        single_shot.assert_called_once()
        self.assertEqual(single_shot.call_args.args[0], 0)
        page._start_user_domain_action_worker.assert_not_called()

        single_shot.call_args.args[1]()

        page._start_user_domain_action_worker.assert_called_once_with({"action": "add", "domain": "example.com"})

    def test_stale_user_domain_action_finish_does_not_restart_pending_action(self) -> None:
        page = BlockcheckPage.__new__(BlockcheckPage)
        page._cleanup_in_progress = False
        page._user_domain_action_runtime = SimpleNamespace(request_id=3)
        page._user_domain_action_pending = [{"action": "add", "domain": "example.com"}]
        page._schedule_user_domain_action_worker_start = Mock()

        BlockcheckPage._on_user_domain_action_runtime_finished(page, SimpleNamespace(_request_id=2))

        page._schedule_user_domain_action_worker_start.assert_not_called()

    def test_scheduled_user_domain_action_queues_next_payload(self) -> None:
        import blockcheck.ui.page as blockcheck_page

        page = BlockcheckPage.__new__(BlockcheckPage)
        page._cleanup_in_progress = False
        page._user_domain_action_start_scheduled = False
        page._user_domain_action_pending = []
        page._start_user_domain_action_worker = Mock()
        single_shot = Mock(side_effect=lambda _delay, _callback: None)

        old_payload = {"action": "add", "domain": "old.example"}
        new_payload = {"action": "remove", "domain": "new.example"}
        with patch.object(blockcheck_page, "QTimer", SimpleNamespace(singleShot=single_shot), create=True):
            BlockcheckPage._schedule_user_domain_action_worker_start(page, old_payload)
            BlockcheckPage._schedule_user_domain_action_worker_start(page, new_payload)

        single_shot.assert_called_once()
        self.assertEqual(page._user_domain_action_pending, [new_payload])

        single_shot.call_args.args[1]()

        page._start_user_domain_action_worker.assert_called_once_with(old_payload)
        self.assertEqual(page._user_domain_action_pending, [new_payload])

    def test_running_user_domain_action_keeps_latest_payload_per_domain(self) -> None:
        page = BlockcheckPage.__new__(BlockcheckPage)
        page._cleanup_in_progress = False
        page._user_domain_action_start_scheduled = False
        page._user_domain_action_pending = []
        page._user_domain_action_runtime = SimpleNamespace(
            is_running=Mock(return_value=True),
            start_qthread_worker=Mock(),
        )
        page._start_user_domain_action_worker = Mock()

        BlockcheckPage._request_user_domain_action(page, "add", "one.example")
        BlockcheckPage._request_user_domain_action(page, "add", "two.example")
        BlockcheckPage._request_user_domain_action(page, "remove", "one.example")

        page._start_user_domain_action_worker.assert_not_called()
        page._user_domain_action_runtime.start_qthread_worker.assert_not_called()
        self.assertEqual(
            page._user_domain_action_pending,
            [
                {"action": "add", "domain": "two.example"},
                {"action": "remove", "domain": "one.example"},
            ],
        )

    def test_user_domain_add_result_ignored_when_same_domain_action_is_pending(self) -> None:
        page = BlockcheckPage.__new__(BlockcheckPage)
        page._cleanup_in_progress = False
        page._user_domain_action_pending = [{"action": "remove", "domain": "example.com"}]
        page._user_domain_action_runtime = SimpleNamespace(is_current=Mock(return_value=True))
        page._add_chip = Mock()
        page._domain_input = SimpleNamespace(clear=Mock())

        BlockcheckPage._on_user_domain_action_finished(
            page,
            5,
            "add",
            "example.com",
            {"domain": "example.com"},
        )

        page._add_chip.assert_not_called()
        page._domain_input.clear.assert_not_called()

    def test_user_domain_remove_result_ignored_when_same_domain_action_is_pending(self) -> None:
        page = BlockcheckPage.__new__(BlockcheckPage)
        page._cleanup_in_progress = False
        page._user_domain_action_pending = [{"action": "add", "domain": "example.com"}]
        page._user_domain_action_runtime = SimpleNamespace(is_current=Mock(return_value=True))
        page._domains_flow_layout = object()

        with patch("blockcheck.ui.page.remove_domain_chip") as remove_chip:
            BlockcheckPage._on_user_domain_action_finished(
                page,
                5,
                "remove",
                "example.com",
                {"domain": "example.com"},
            )

        remove_chip.assert_not_called()


if __name__ == "__main__":
    unittest.main()
