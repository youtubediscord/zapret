from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import telegram_proxy.ui.page as telegram_proxy_page
from telegram_proxy.ui.page import TelegramProxyPage
from telegram_proxy.ui.worker_state import (
    TelegramProxyPageQueuedWorkerState,
    TelegramProxyPageWorkerState,
)


def _set_state(page, name: str, *, runtime=None, pending: bool = False, start_scheduled: bool = False):
    runtime_attr = f"_{name}_runtime"
    state_attr = f"_{name}_state"
    if runtime is None:
        runtime = page.__dict__.get(runtime_attr, SimpleNamespace(is_running=Mock(return_value=False)))
    setattr(page, runtime_attr, runtime)
    state = TelegramProxyPageWorkerState(
        runtime=runtime,
        pending=bool(pending),
        start_scheduled=bool(start_scheduled),
    )
    setattr(page, state_attr, state)
    return state


def _set_queue_state(page, name: str, *, runtime=None, pending=None, start_scheduled: bool = False):
    runtime_attr = f"_{name}_runtime"
    state_attr = f"_{name}_state"
    if runtime is None:
        runtime = page.__dict__.get(runtime_attr, SimpleNamespace(is_running=Mock(return_value=False)))
    setattr(page, runtime_attr, runtime)
    state = TelegramProxyPageQueuedWorkerState(
        runtime=runtime,
        pending=list(pending or []),
        start_scheduled=bool(start_scheduled),
    )
    setattr(page, state_attr, state)
    return state


class TelegramProxyWorkerQueueTests(unittest.TestCase):
    def test_scheduled_log_line_start_queues_next_message(self) -> None:
        page = TelegramProxyPage.__new__(TelegramProxyPage)
        page._cleanup_in_progress = False
        state = _set_queue_state(page, "log_line")
        page._start_log_line_worker = Mock()
        single_shot = Mock(side_effect=lambda _delay, _callback: None)

        with patch.object(telegram_proxy_page, "QTimer", SimpleNamespace(singleShot=single_shot), create=True):
            TelegramProxyPage._schedule_log_line_worker_start(page, "old")
            TelegramProxyPage._schedule_log_line_worker_start(page, "new")

        single_shot.assert_called_once()
        self.assertEqual(state.pending, ["new"])

        single_shot.call_args.args[1]()

        page._start_log_line_worker.assert_called_once_with("old")
        self.assertEqual(state.pending, ["new"])

    def test_scheduled_open_log_file_start_queues_next_path(self) -> None:
        page = TelegramProxyPage.__new__(TelegramProxyPage)
        page._cleanup_in_progress = False
        state = _set_queue_state(page, "open_log_file")
        page._start_open_log_file_worker = Mock()
        single_shot = Mock(side_effect=lambda _delay, _callback: None)

        with patch.object(telegram_proxy_page, "QTimer", SimpleNamespace(singleShot=single_shot), create=True):
            TelegramProxyPage._schedule_open_log_file_worker_start(page, "old.log")
            TelegramProxyPage._schedule_open_log_file_worker_start(page, "new.log")

        single_shot.assert_called_once()
        self.assertEqual(state.pending, ["new.log"])

        single_shot.call_args.args[1]()

        page._start_open_log_file_worker.assert_called_once_with("old.log")
        self.assertEqual(state.pending, ["new.log"])

    def test_stale_open_log_file_worker_finished_does_not_restart_pending_open(self) -> None:
        page = TelegramProxyPage.__new__(TelegramProxyPage)
        page._cleanup_in_progress = False
        current_worker = SimpleNamespace()
        state = _set_queue_state(
            page,
            "open_log_file",
            runtime=SimpleNamespace(worker=current_worker),
            pending=["next.log"],
        )
        page._schedule_open_log_file_worker_start = Mock()

        TelegramProxyPage._on_open_log_file_worker_finished(page, SimpleNamespace())

        page._schedule_open_log_file_worker_start.assert_not_called()
        self.assertEqual(state.pending, ["next.log"])

    def test_scheduled_settings_save_start_queues_next_payload(self) -> None:
        page = TelegramProxyPage.__new__(TelegramProxyPage)
        page._cleanup_in_progress = False
        state = _set_queue_state(page, "settings_save")
        page._start_settings_save_worker = Mock()
        single_shot = Mock(side_effect=lambda _delay, _callback: None)

        old_payload = {"action": "host", "host": "old"}
        new_payload = {"action": "host", "host": "new"}
        with patch.object(telegram_proxy_page, "QTimer", SimpleNamespace(singleShot=single_shot), create=True):
            TelegramProxyPage._schedule_settings_save_worker_start(page, old_payload)
            TelegramProxyPage._schedule_settings_save_worker_start(page, new_payload)

        single_shot.assert_called_once()
        self.assertEqual(state.pending, [new_payload])

        single_shot.call_args.args[1]()

        page._start_settings_save_worker.assert_called_once_with(old_payload)
        self.assertEqual(state.pending, [new_payload])

    def test_settings_save_queue_replaces_pending_payload_for_same_action(self) -> None:
        page = TelegramProxyPage.__new__(TelegramProxyPage)
        state = _set_queue_state(
            page,
            "settings_save",
            runtime=SimpleNamespace(is_running=Mock(return_value=True)),
        )
        page._start_settings_save_worker = Mock()

        TelegramProxyPage._request_settings_save(page, "host", host="old.local")
        TelegramProxyPage._request_settings_save(page, "host", host="new.local")

        page._start_settings_save_worker.assert_not_called()
        self.assertEqual(
            state.pending,
            [
                {
                    "action": "host",
                    "host": "new.local",
                    "port": 0,
                    "user": "",
                    "password": "",
                    "enabled": False,
                    "context_extra": {
                        "restart": "",
                        "update_manual": False,
                    },
                }
            ],
        )

    def test_settings_save_queue_keeps_payloads_for_different_actions(self) -> None:
        page = TelegramProxyPage.__new__(TelegramProxyPage)
        state = _set_queue_state(
            page,
            "settings_save",
            runtime=SimpleNamespace(is_running=Mock(return_value=True)),
        )
        page._start_settings_save_worker = Mock()

        TelegramProxyPage._request_settings_save(page, "host", host="proxy.local")
        TelegramProxyPage._request_settings_save(page, "port", port=9090)

        self.assertEqual(
            [(payload["action"], payload["host"], payload["port"]) for payload in state.pending],
            [("host", "proxy.local", 0), ("port", "", 9090)],
        )

    def test_settings_save_failure_ignored_when_new_save_is_pending(self) -> None:
        page = TelegramProxyPage.__new__(TelegramProxyPage)
        page._cleanup_in_progress = False
        runtime = Mock()
        runtime.is_current.return_value = True
        page._settings_save_runtime = runtime
        _set_queue_state(page, "settings_save", runtime=runtime, pending=[{"action": "port", "port": 9090}])
        page._settings_save_restart_pending = "schedule"

        with patch.object(telegram_proxy_page, "log") as log_mock:
            TelegramProxyPage._on_settings_save_failed(page, 7, "host", "stale error", {})

        self.assertEqual(page._settings_save_restart_pending, "schedule")
        log_mock.assert_not_called()

    def test_scheduled_external_link_start_queues_next_link(self) -> None:
        page = TelegramProxyPage.__new__(TelegramProxyPage)
        page._cleanup_in_progress = False
        state = _set_queue_state(page, "external_link")
        page._start_external_link_worker = Mock()
        single_shot = Mock(side_effect=lambda _delay, _callback: None)

        old_payload = {"url": "https://old.example", "success_log": "old", "error_prefix": "old error"}
        new_payload = {"url": "https://new.example", "success_log": "new", "error_prefix": "new error"}
        with patch.object(telegram_proxy_page, "QTimer", SimpleNamespace(singleShot=single_shot), create=True):
            TelegramProxyPage._schedule_external_link_worker_start(page, old_payload)
            TelegramProxyPage._schedule_external_link_worker_start(page, new_payload)

        single_shot.assert_called_once()
        self.assertEqual(state.pending, [new_payload])

        single_shot.call_args.args[1]()

        page._start_external_link_worker.assert_called_once_with(
            "https://old.example",
            success_log="old",
            error_prefix="old error",
        )
        self.assertEqual(state.pending, [new_payload])

    def test_stale_external_link_worker_finished_does_not_restart_pending_open(self) -> None:
        page = TelegramProxyPage.__new__(TelegramProxyPage)
        page._cleanup_in_progress = False
        current_worker = SimpleNamespace()
        pending = {"url": "https://new.example", "success_log": "new", "error_prefix": "new error"}
        state = _set_queue_state(
            page,
            "external_link",
            runtime=SimpleNamespace(worker=current_worker),
            pending=[pending],
        )
        page._schedule_external_link_worker_start = Mock()

        TelegramProxyPage._on_external_link_worker_finished(page, SimpleNamespace())

        page._schedule_external_link_worker_start.assert_not_called()
        self.assertEqual(state.pending, [pending])

    def test_scheduled_ensure_hosts_start_coalesces_duplicate_request(self) -> None:
        page = TelegramProxyPage.__new__(TelegramProxyPage)
        page._cleanup_in_progress = False
        _set_state(page, "ensure_hosts")
        page._start_ensure_hosts_worker = Mock()
        single_shot = Mock(side_effect=lambda _delay, _callback: None)

        with patch.object(telegram_proxy_page, "QTimer", SimpleNamespace(singleShot=single_shot), create=True):
            TelegramProxyPage._schedule_ensure_hosts_worker_start(page)
            TelegramProxyPage._schedule_ensure_hosts_worker_start(page)

        single_shot.assert_called_once()
        self.assertTrue(page._ensure_hosts_state.pending)

        single_shot.call_args.args[1]()

        page._start_ensure_hosts_worker.assert_called_once_with()
        self.assertFalse(page._ensure_hosts_state.pending)

    def test_auto_deeplink_request_queues_while_worker_runs(self) -> None:
        page = TelegramProxyPage.__new__(TelegramProxyPage)
        _set_state(
            page,
            "auto_deeplink",
            runtime=SimpleNamespace(is_running=Mock(return_value=True), start_qthread_worker=Mock()),
        )

        TelegramProxyPage._request_auto_deeplink_check(page)

        page._auto_deeplink_runtime.start_qthread_worker.assert_not_called()
        self.assertTrue(page._auto_deeplink_state.pending)

    def test_auto_deeplink_pending_restarts_after_event_loop_turn(self) -> None:
        page = TelegramProxyPage.__new__(TelegramProxyPage)
        page._cleanup_in_progress = False
        _set_state(page, "auto_deeplink", pending=True)
        page._start_auto_deeplink_worker = Mock()
        single_shot = Mock(side_effect=lambda _delay, _callback: None)

        with patch.object(telegram_proxy_page, "QTimer", SimpleNamespace(singleShot=single_shot), create=True):
            TelegramProxyPage._on_auto_deeplink_worker_finished(page, object())

        single_shot.assert_called_once()
        self.assertEqual(single_shot.call_args.args[0], 0)
        page._start_auto_deeplink_worker.assert_not_called()

        single_shot.call_args.args[1]()

        page._start_auto_deeplink_worker.assert_called_once_with()
        self.assertFalse(page._auto_deeplink_state.pending)

    def test_stale_auto_deeplink_worker_finished_does_not_restart_pending_check(self) -> None:
        page = TelegramProxyPage.__new__(TelegramProxyPage)
        page._cleanup_in_progress = False
        _set_state(page, "auto_deeplink", runtime=SimpleNamespace(request_id=3), pending=True)
        page._schedule_auto_deeplink_worker_start = Mock()

        TelegramProxyPage._on_auto_deeplink_worker_finished(page, SimpleNamespace(_request_id=2))

        page._schedule_auto_deeplink_worker_start.assert_not_called()

    def test_scheduled_auto_deeplink_start_coalesces_duplicate_request(self) -> None:
        page = TelegramProxyPage.__new__(TelegramProxyPage)
        page._cleanup_in_progress = False
        _set_state(page, "auto_deeplink")
        page._start_auto_deeplink_worker = Mock()
        single_shot = Mock(side_effect=lambda _delay, _callback: None)

        with patch.object(telegram_proxy_page, "QTimer", SimpleNamespace(singleShot=single_shot), create=True):
            TelegramProxyPage._schedule_auto_deeplink_worker_start(page)
            TelegramProxyPage._schedule_auto_deeplink_worker_start(page)

        single_shot.assert_called_once()
        self.assertTrue(page._auto_deeplink_state.pending)

        single_shot.call_args.args[1]()

        page._start_auto_deeplink_worker.assert_called_once_with()
        self.assertFalse(page._auto_deeplink_state.pending)

    def test_restart_request_queues_while_restart_stop_worker_runs(self) -> None:
        page = TelegramProxyPage.__new__(TelegramProxyPage)
        page._cleanup_in_progress = False
        _set_state(
            page,
            "restart_stop",
            runtime=SimpleNamespace(is_running=Mock(return_value=True), start_qthread_worker=Mock()),
        )

        TelegramProxyPage._restart_if_running(page)

        page._restart_stop_runtime.start_qthread_worker.assert_not_called()
        self.assertTrue(page._restart_stop_state.pending)

    def test_restart_pending_restarts_after_event_loop_turn(self) -> None:
        page = TelegramProxyPage.__new__(TelegramProxyPage)
        page._cleanup_in_progress = False
        _set_state(page, "restart_stop", pending=True)
        page._restart_if_running = Mock()
        single_shot = Mock(side_effect=lambda _delay, _callback: None)

        with patch.object(telegram_proxy_page, "QTimer", SimpleNamespace(singleShot=single_shot), create=True):
            TelegramProxyPage._on_restart_stop_worker_finished(page, object())

        single_shot.assert_called_once()
        self.assertEqual(single_shot.call_args.args[0], 0)
        page._restart_if_running.assert_not_called()

        single_shot.call_args.args[1]()

        page._restart_if_running.assert_called_once_with()
        self.assertFalse(page._restart_stop_state.pending)

    def test_stale_restart_stop_worker_finished_does_not_restart_pending_stop(self) -> None:
        page = TelegramProxyPage.__new__(TelegramProxyPage)
        page._cleanup_in_progress = False
        current_worker = SimpleNamespace()
        _set_state(page, "restart_stop", runtime=SimpleNamespace(worker=current_worker), pending=True)
        page._schedule_restart_stop_worker_start = Mock()

        TelegramProxyPage._on_restart_stop_worker_finished(page, SimpleNamespace())

        page._schedule_restart_stop_worker_start.assert_not_called()
        self.assertTrue(page._restart_stop_state.pending)

    def test_stale_log_line_worker_finished_does_not_restart_pending_append(self) -> None:
        page = TelegramProxyPage.__new__(TelegramProxyPage)
        page._cleanup_in_progress = False
        _set_queue_state(page, "log_line", runtime=SimpleNamespace(request_id=5), pending=["new"])
        page._schedule_log_line_worker_start = Mock()

        TelegramProxyPage._on_log_line_worker_finished(page, SimpleNamespace(_request_id=4))

        page._schedule_log_line_worker_start.assert_not_called()

    def test_proxy_start_request_queues_while_start_worker_runs(self) -> None:
        page = TelegramProxyPage.__new__(TelegramProxyPage)
        page._cleanup_in_progress = False
        _set_state(page, "proxy_start", runtime=SimpleNamespace(is_running=Mock(return_value=True)))
        page._start_proxy_worker = Mock()

        TelegramProxyPage._request_proxy_start(page)

        page._start_proxy_worker.assert_not_called()
        self.assertTrue(page._proxy_start_state.pending)

    def test_proxy_start_pending_restarts_after_event_loop_turn(self) -> None:
        page = TelegramProxyPage.__new__(TelegramProxyPage)
        page._cleanup_in_progress = False
        _set_state(page, "proxy_start", pending=True)
        page._start_proxy_worker = Mock()
        single_shot = Mock(side_effect=lambda _delay, _callback: None)

        with patch.object(telegram_proxy_page, "QTimer", SimpleNamespace(singleShot=single_shot), create=True):
            TelegramProxyPage._on_proxy_start_worker_finished(page, object())

        single_shot.assert_called_once()
        self.assertEqual(single_shot.call_args.args[0], 0)
        page._start_proxy_worker.assert_not_called()

        single_shot.call_args.args[1]()

        page._start_proxy_worker.assert_called_once_with()
        self.assertFalse(page._proxy_start_state.pending)

    def test_stale_proxy_start_worker_finished_does_not_restart_pending_start(self) -> None:
        page = TelegramProxyPage.__new__(TelegramProxyPage)
        page._cleanup_in_progress = False
        current_worker = SimpleNamespace()
        _set_state(page, "proxy_start", runtime=SimpleNamespace(worker=current_worker), pending=True)
        page._schedule_proxy_start_worker_start = Mock()

        TelegramProxyPage._on_proxy_start_worker_finished(page, SimpleNamespace())

        page._schedule_proxy_start_worker_start.assert_not_called()
        self.assertTrue(page._proxy_start_state.pending)

    def test_stale_relay_check_worker_finished_does_not_restart_pending_check(self) -> None:
        page = TelegramProxyPage.__new__(TelegramProxyPage)
        page._cleanup_in_progress = False
        current_worker = SimpleNamespace()
        _set_state(page, "relay_check", runtime=SimpleNamespace(worker=current_worker), pending=True)
        page._schedule_relay_check_worker_start = Mock()

        TelegramProxyPage._on_relay_check_worker_finished(page, SimpleNamespace())

        page._schedule_relay_check_worker_start.assert_not_called()
        self.assertTrue(page._relay_check_state.pending)

    def test_proxy_stop_request_queues_while_stop_worker_runs(self) -> None:
        page = TelegramProxyPage.__new__(TelegramProxyPage)
        page._cleanup_in_progress = False
        _set_state(page, "proxy_stop", runtime=SimpleNamespace(is_running=Mock(return_value=True)))
        page._start_proxy_stop_worker = Mock()

        TelegramProxyPage._request_proxy_stop(page)

        page._start_proxy_stop_worker.assert_not_called()
        self.assertTrue(page._proxy_stop_state.pending)

    def test_proxy_stop_pending_restarts_after_event_loop_turn(self) -> None:
        page = TelegramProxyPage.__new__(TelegramProxyPage)
        page._cleanup_in_progress = False
        _set_state(page, "proxy_stop", pending=True)
        page._start_proxy_stop_worker = Mock()
        single_shot = Mock(side_effect=lambda _delay, _callback: None)

        with patch.object(telegram_proxy_page, "QTimer", SimpleNamespace(singleShot=single_shot), create=True):
            TelegramProxyPage._on_proxy_stop_worker_finished(page, object())

        single_shot.assert_called_once()
        self.assertEqual(single_shot.call_args.args[0], 0)
        page._start_proxy_stop_worker.assert_not_called()

        single_shot.call_args.args[1]()

        page._start_proxy_stop_worker.assert_called_once_with()
        self.assertFalse(page._proxy_stop_state.pending)

    def test_stale_proxy_stop_worker_finished_does_not_restart_pending_stop(self) -> None:
        page = TelegramProxyPage.__new__(TelegramProxyPage)
        page._cleanup_in_progress = False
        current_worker = SimpleNamespace()
        _set_state(page, "proxy_stop", runtime=SimpleNamespace(worker=current_worker), pending=True)
        page._schedule_proxy_stop_worker_start = Mock()

        TelegramProxyPage._on_proxy_stop_worker_finished(page, SimpleNamespace())

        page._schedule_proxy_stop_worker_start.assert_not_called()
        self.assertTrue(page._proxy_stop_state.pending)

    def test_stale_settings_save_worker_finished_does_not_restart_pending_save(self) -> None:
        page = TelegramProxyPage.__new__(TelegramProxyPage)
        page._cleanup_in_progress = False
        _set_queue_state(
            page,
            "settings_save",
            runtime=SimpleNamespace(request_id=7),
            pending=[{"action": "host", "host": "new"}],
        )
        page._schedule_settings_save_worker_start = Mock()

        TelegramProxyPage._on_settings_save_worker_finished(page, SimpleNamespace(_request_id=6))

        page._schedule_settings_save_worker_start.assert_not_called()

    def test_stale_ensure_hosts_worker_finished_does_not_restart_pending_ensure(self) -> None:
        page = TelegramProxyPage.__new__(TelegramProxyPage)
        page._cleanup_in_progress = False
        _set_state(page, "ensure_hosts", runtime=SimpleNamespace(request_id=9), pending=True)
        page._schedule_ensure_hosts_worker_start = Mock()

        TelegramProxyPage._on_ensure_hosts_worker_finished(page, SimpleNamespace(_request_id=8))

        page._schedule_ensure_hosts_worker_start.assert_not_called()


if __name__ == "__main__":
    unittest.main()
