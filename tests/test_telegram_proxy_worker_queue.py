from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import telegram_proxy.ui.page as telegram_proxy_page
from telegram_proxy.ui.page import TelegramProxyPage


class TelegramProxyWorkerQueueTests(unittest.TestCase):
    def test_scheduled_log_line_start_queues_next_message(self) -> None:
        page = TelegramProxyPage.__new__(TelegramProxyPage)
        page._cleanup_in_progress = False
        page._log_line_start_scheduled = False
        page._log_line_pending = []
        page._start_log_line_worker = Mock()
        single_shot = Mock(side_effect=lambda _delay, _callback: None)

        with patch.object(telegram_proxy_page, "QTimer", SimpleNamespace(singleShot=single_shot), create=True):
            TelegramProxyPage._schedule_log_line_worker_start(page, "old")
            TelegramProxyPage._schedule_log_line_worker_start(page, "new")

        single_shot.assert_called_once()
        self.assertEqual(page._log_line_pending, ["new"])

        single_shot.call_args.args[1]()

        page._start_log_line_worker.assert_called_once_with("old")
        self.assertEqual(page._log_line_pending, ["new"])

    def test_scheduled_open_log_file_start_queues_next_path(self) -> None:
        page = TelegramProxyPage.__new__(TelegramProxyPage)
        page._cleanup_in_progress = False
        page._open_log_file_start_scheduled = False
        page._open_log_file_pending = []
        page._start_open_log_file_worker = Mock()
        single_shot = Mock(side_effect=lambda _delay, _callback: None)

        with patch.object(telegram_proxy_page, "QTimer", SimpleNamespace(singleShot=single_shot), create=True):
            TelegramProxyPage._schedule_open_log_file_worker_start(page, "old.log")
            TelegramProxyPage._schedule_open_log_file_worker_start(page, "new.log")

        single_shot.assert_called_once()
        self.assertEqual(page._open_log_file_pending, ["new.log"])

        single_shot.call_args.args[1]()

        page._start_open_log_file_worker.assert_called_once_with("old.log")
        self.assertEqual(page._open_log_file_pending, ["new.log"])

    def test_scheduled_settings_save_start_queues_next_payload(self) -> None:
        page = TelegramProxyPage.__new__(TelegramProxyPage)
        page._cleanup_in_progress = False
        page._settings_save_start_scheduled = False
        page._settings_save_pending = []
        page._start_settings_save_worker = Mock()
        single_shot = Mock(side_effect=lambda _delay, _callback: None)

        old_payload = {"action": "host", "host": "old"}
        new_payload = {"action": "host", "host": "new"}
        with patch.object(telegram_proxy_page, "QTimer", SimpleNamespace(singleShot=single_shot), create=True):
            TelegramProxyPage._schedule_settings_save_worker_start(page, old_payload)
            TelegramProxyPage._schedule_settings_save_worker_start(page, new_payload)

        single_shot.assert_called_once()
        self.assertEqual(page._settings_save_pending, [new_payload])

        single_shot.call_args.args[1]()

        page._start_settings_save_worker.assert_called_once_with(old_payload)
        self.assertEqual(page._settings_save_pending, [new_payload])

    def test_settings_save_queue_replaces_pending_payload_for_same_action(self) -> None:
        page = TelegramProxyPage.__new__(TelegramProxyPage)
        page._settings_save_runtime = SimpleNamespace(is_running=Mock(return_value=True))
        page._settings_save_start_scheduled = False
        page._settings_save_pending = []
        page._start_settings_save_worker = Mock()

        TelegramProxyPage._request_settings_save(page, "host", host="old.local")
        TelegramProxyPage._request_settings_save(page, "host", host="new.local")

        page._start_settings_save_worker.assert_not_called()
        self.assertEqual(
            page._settings_save_pending,
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
        page._settings_save_runtime = SimpleNamespace(is_running=Mock(return_value=True))
        page._settings_save_start_scheduled = False
        page._settings_save_pending = []
        page._start_settings_save_worker = Mock()

        TelegramProxyPage._request_settings_save(page, "host", host="proxy.local")
        TelegramProxyPage._request_settings_save(page, "port", port=9090)

        self.assertEqual(
            [(payload["action"], payload["host"], payload["port"]) for payload in page._settings_save_pending],
            [("host", "proxy.local", 0), ("port", "", 9090)],
        )

    def test_scheduled_external_link_start_queues_next_link(self) -> None:
        page = TelegramProxyPage.__new__(TelegramProxyPage)
        page._cleanup_in_progress = False
        page._external_link_start_scheduled = False
        page._external_link_pending = []
        page._start_external_link_worker = Mock()
        single_shot = Mock(side_effect=lambda _delay, _callback: None)

        old_payload = {"url": "https://old.example", "success_log": "old", "error_prefix": "old error"}
        new_payload = {"url": "https://new.example", "success_log": "new", "error_prefix": "new error"}
        with patch.object(telegram_proxy_page, "QTimer", SimpleNamespace(singleShot=single_shot), create=True):
            TelegramProxyPage._schedule_external_link_worker_start(page, old_payload)
            TelegramProxyPage._schedule_external_link_worker_start(page, new_payload)

        single_shot.assert_called_once()
        self.assertEqual(page._external_link_pending, [new_payload])

        single_shot.call_args.args[1]()

        page._start_external_link_worker.assert_called_once_with(
            "https://old.example",
            success_log="old",
            error_prefix="old error",
        )
        self.assertEqual(page._external_link_pending, [new_payload])

    def test_scheduled_ensure_hosts_start_coalesces_duplicate_request(self) -> None:
        page = TelegramProxyPage.__new__(TelegramProxyPage)
        page._cleanup_in_progress = False
        page._ensure_hosts_start_scheduled = False
        page._ensure_hosts_pending = False
        page._start_ensure_hosts_worker = Mock()
        single_shot = Mock(side_effect=lambda _delay, _callback: None)

        with patch.object(telegram_proxy_page, "QTimer", SimpleNamespace(singleShot=single_shot), create=True):
            TelegramProxyPage._schedule_ensure_hosts_worker_start(page)
            TelegramProxyPage._schedule_ensure_hosts_worker_start(page)

        single_shot.assert_called_once()
        self.assertTrue(page._ensure_hosts_pending)

        single_shot.call_args.args[1]()

        page._start_ensure_hosts_worker.assert_called_once_with()
        self.assertFalse(page._ensure_hosts_pending)

    def test_auto_deeplink_request_queues_while_worker_runs(self) -> None:
        page = TelegramProxyPage.__new__(TelegramProxyPage)
        page._auto_deeplink_runtime = SimpleNamespace(is_running=Mock(return_value=True), start_qthread_worker=Mock())
        page._auto_deeplink_pending = False
        page._auto_deeplink_start_scheduled = False

        TelegramProxyPage._request_auto_deeplink_check(page)

        page._auto_deeplink_runtime.start_qthread_worker.assert_not_called()
        self.assertTrue(page._auto_deeplink_pending)

    def test_auto_deeplink_pending_restarts_after_event_loop_turn(self) -> None:
        page = TelegramProxyPage.__new__(TelegramProxyPage)
        page._cleanup_in_progress = False
        page._auto_deeplink_pending = True
        page._auto_deeplink_start_scheduled = False
        page._start_auto_deeplink_worker = Mock()
        single_shot = Mock(side_effect=lambda _delay, _callback: None)

        with patch.object(telegram_proxy_page, "QTimer", SimpleNamespace(singleShot=single_shot), create=True):
            TelegramProxyPage._on_auto_deeplink_worker_finished(page, object())

        single_shot.assert_called_once()
        self.assertEqual(single_shot.call_args.args[0], 0)
        page._start_auto_deeplink_worker.assert_not_called()

        single_shot.call_args.args[1]()

        page._start_auto_deeplink_worker.assert_called_once_with()
        self.assertFalse(page._auto_deeplink_pending)

    def test_scheduled_auto_deeplink_start_coalesces_duplicate_request(self) -> None:
        page = TelegramProxyPage.__new__(TelegramProxyPage)
        page._cleanup_in_progress = False
        page._auto_deeplink_start_scheduled = False
        page._auto_deeplink_pending = False
        page._start_auto_deeplink_worker = Mock()
        single_shot = Mock(side_effect=lambda _delay, _callback: None)

        with patch.object(telegram_proxy_page, "QTimer", SimpleNamespace(singleShot=single_shot), create=True):
            TelegramProxyPage._schedule_auto_deeplink_worker_start(page)
            TelegramProxyPage._schedule_auto_deeplink_worker_start(page)

        single_shot.assert_called_once()
        self.assertTrue(page._auto_deeplink_pending)

        single_shot.call_args.args[1]()

        page._start_auto_deeplink_worker.assert_called_once_with()
        self.assertFalse(page._auto_deeplink_pending)

    def test_restart_request_queues_while_restart_stop_worker_runs(self) -> None:
        page = TelegramProxyPage.__new__(TelegramProxyPage)
        page._cleanup_in_progress = False
        page._restart_stop_pending = False
        page._restart_stop_start_scheduled = False
        page._restart_stop_runtime = SimpleNamespace(is_running=Mock(return_value=True), start_qthread_worker=Mock())

        TelegramProxyPage._restart_if_running(page)

        page._restart_stop_runtime.start_qthread_worker.assert_not_called()
        self.assertTrue(page._restart_stop_pending)

    def test_restart_pending_restarts_after_event_loop_turn(self) -> None:
        page = TelegramProxyPage.__new__(TelegramProxyPage)
        page._cleanup_in_progress = False
        page._restart_stop_pending = True
        page._restart_stop_start_scheduled = False
        page._restart_if_running = Mock()
        single_shot = Mock(side_effect=lambda _delay, _callback: None)

        with patch.object(telegram_proxy_page, "QTimer", SimpleNamespace(singleShot=single_shot), create=True):
            TelegramProxyPage._on_restart_stop_worker_finished(page, object())

        single_shot.assert_called_once()
        self.assertEqual(single_shot.call_args.args[0], 0)
        page._restart_if_running.assert_not_called()

        single_shot.call_args.args[1]()

        page._restart_if_running.assert_called_once_with()
        self.assertFalse(page._restart_stop_pending)

    def test_proxy_start_request_queues_while_start_worker_runs(self) -> None:
        page = TelegramProxyPage.__new__(TelegramProxyPage)
        page._cleanup_in_progress = False
        page._proxy_start_pending = False
        page._proxy_start_start_scheduled = False
        page._proxy_start_runtime = SimpleNamespace(is_running=Mock(return_value=True))
        page._start_proxy_worker = Mock()

        TelegramProxyPage._request_proxy_start(page)

        page._start_proxy_worker.assert_not_called()
        self.assertTrue(page._proxy_start_pending)

    def test_proxy_start_pending_restarts_after_event_loop_turn(self) -> None:
        page = TelegramProxyPage.__new__(TelegramProxyPage)
        page._cleanup_in_progress = False
        page._proxy_start_pending = True
        page._proxy_start_start_scheduled = False
        page._start_proxy_worker = Mock()
        single_shot = Mock(side_effect=lambda _delay, _callback: None)

        with patch.object(telegram_proxy_page, "QTimer", SimpleNamespace(singleShot=single_shot), create=True):
            TelegramProxyPage._on_proxy_start_worker_finished(page, object())

        single_shot.assert_called_once()
        self.assertEqual(single_shot.call_args.args[0], 0)
        page._start_proxy_worker.assert_not_called()

        single_shot.call_args.args[1]()

        page._start_proxy_worker.assert_called_once_with()
        self.assertFalse(page._proxy_start_pending)

    def test_proxy_stop_request_queues_while_stop_worker_runs(self) -> None:
        page = TelegramProxyPage.__new__(TelegramProxyPage)
        page._cleanup_in_progress = False
        page._proxy_stop_pending = False
        page._proxy_stop_start_scheduled = False
        page._proxy_stop_runtime = SimpleNamespace(is_running=Mock(return_value=True))
        page._start_proxy_stop_worker = Mock()

        TelegramProxyPage._request_proxy_stop(page)

        page._start_proxy_stop_worker.assert_not_called()
        self.assertTrue(page._proxy_stop_pending)

    def test_proxy_stop_pending_restarts_after_event_loop_turn(self) -> None:
        page = TelegramProxyPage.__new__(TelegramProxyPage)
        page._cleanup_in_progress = False
        page._proxy_stop_pending = True
        page._proxy_stop_start_scheduled = False
        page._start_proxy_stop_worker = Mock()
        single_shot = Mock(side_effect=lambda _delay, _callback: None)

        with patch.object(telegram_proxy_page, "QTimer", SimpleNamespace(singleShot=single_shot), create=True):
            TelegramProxyPage._on_proxy_stop_worker_finished(page, object())

        single_shot.assert_called_once()
        self.assertEqual(single_shot.call_args.args[0], 0)
        page._start_proxy_stop_worker.assert_not_called()

        single_shot.call_args.args[1]()

        page._start_proxy_stop_worker.assert_called_once_with()
        self.assertFalse(page._proxy_stop_pending)


if __name__ == "__main__":
    unittest.main()
