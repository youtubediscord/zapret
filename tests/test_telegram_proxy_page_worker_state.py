from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from telegram_proxy.ui.worker_state import (
    TelegramProxyPageQueuedWorkerState,
    TelegramProxyPageWorkerState,
)
from ui.latest_value_worker_state import LatestValueWorkerState
from ui.queued_worker_state import QueuedWorkerState


class TelegramProxyPageWorkerStateTests(unittest.TestCase):
    def test_worker_state_uses_shared_latest_value_state(self) -> None:
        self.assertTrue(issubclass(TelegramProxyPageWorkerState, LatestValueWorkerState))

    def test_request_marks_pending_when_runtime_is_busy(self) -> None:
        state = TelegramProxyPageWorkerState(
            runtime=SimpleNamespace(is_running=Mock(return_value=True)),
        )
        start = Mock()

        started = state.start_or_mark_pending(start)

        self.assertFalse(started)
        self.assertTrue(state.pending)
        start.assert_not_called()

    def test_schedule_keeps_one_pending_request_until_timer_runs(self) -> None:
        state = TelegramProxyPageWorkerState(
            runtime=SimpleNamespace(is_running=Mock(return_value=False)),
        )
        single_shot = Mock(side_effect=lambda _delay, _callback: None)
        start = Mock()

        state.schedule_next(single_shot, start)
        state.schedule_next(single_shot, start)

        single_shot.assert_called_once()
        self.assertTrue(state.pending)
        start.assert_not_called()

        single_shot.call_args.args[1]()

        start.assert_called_once_with()
        self.assertFalse(state.pending)
        self.assertFalse(state.start_scheduled)

    def test_stale_finish_does_not_schedule_pending_request(self) -> None:
        current_worker = SimpleNamespace()
        state = TelegramProxyPageWorkerState(
            runtime=SimpleNamespace(worker=current_worker),
            pending=True,
        )
        schedule_next = Mock()

        state.schedule_after_finish(
            SimpleNamespace(),
            is_current_worker_finish=lambda _runtime, worker: worker is current_worker,
            schedule_next=schedule_next,
        )

        schedule_next.assert_not_called()
        self.assertTrue(state.pending)


class TelegramProxyPageQueuedWorkerStateTests(unittest.TestCase):
    def test_queued_state_uses_shared_ui_worker_state(self) -> None:
        self.assertIs(TelegramProxyPageQueuedWorkerState, QueuedWorkerState)

    def test_start_or_queue_adds_payload_when_runtime_is_busy(self) -> None:
        state = TelegramProxyPageQueuedWorkerState(
            runtime=SimpleNamespace(is_running=Mock(return_value=True)),
        )
        start = Mock()

        started = state.start_or_queue("next", start, state.append)

        self.assertFalse(started)
        self.assertEqual(state.pending, ["next"])
        start.assert_not_called()

    def test_append_unique_skips_existing_truthy_key(self) -> None:
        state = TelegramProxyPageQueuedWorkerState(runtime=SimpleNamespace())

        state.append_unique({"url": "tg://proxy"}, key=lambda item: item["url"])
        state.append_unique({"url": "tg://proxy"}, key=lambda item: item["url"])
        state.append_unique({"url": ""}, key=lambda item: item["url"])
        state.append_unique({"url": ""}, key=lambda item: item["url"])

        self.assertEqual(
            state.pending,
            [
                {"url": "tg://proxy"},
                {"url": ""},
                {"url": ""},
            ],
        )

    def test_replace_by_key_keeps_latest_payload_for_same_key(self) -> None:
        state = TelegramProxyPageQueuedWorkerState(runtime=SimpleNamespace())

        state.replace_by_key({"action": "host", "value": "old"}, key=lambda item: item["action"])
        state.replace_by_key({"action": "port", "value": 8080}, key=lambda item: item["action"])
        state.replace_by_key({"action": "host", "value": "new"}, key=lambda item: item["action"])

        self.assertEqual(
            state.pending,
            [
                {"action": "port", "value": 8080},
                {"action": "host", "value": "new"},
            ],
        )

    def test_schedule_start_queues_second_payload_until_timer_runs(self) -> None:
        state = TelegramProxyPageQueuedWorkerState(runtime=SimpleNamespace())
        start = Mock()
        single_shot = Mock(side_effect=lambda _delay, _callback: None)

        state.schedule_start(
            "old",
            single_shot,
            start,
            queue_item=state.append,
            is_cleanup_in_progress=lambda: False,
        )
        state.schedule_start(
            "new",
            single_shot,
            start,
            queue_item=state.append,
            is_cleanup_in_progress=lambda: False,
        )

        single_shot.assert_called_once()
        self.assertEqual(state.pending, ["new"])
        start.assert_not_called()

        single_shot.call_args.args[1]()

        start.assert_called_once_with("old")
        self.assertFalse(state.start_scheduled)
        self.assertEqual(state.pending, ["new"])

    def test_pop_next_after_finish_ignores_stale_worker(self) -> None:
        current_worker = SimpleNamespace()
        state = TelegramProxyPageQueuedWorkerState(
            runtime=SimpleNamespace(worker=current_worker),
            pending=["next"],
        )

        next_item = state.pop_next_after_finish(
            SimpleNamespace(),
            is_current_worker_finish=lambda _runtime, worker: worker is current_worker,
            cleanup_in_progress=False,
        )

        self.assertIsNone(next_item)
        self.assertEqual(state.pending, ["next"])


if __name__ == "__main__":
    unittest.main()
