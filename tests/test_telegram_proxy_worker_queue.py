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


if __name__ == "__main__":
    unittest.main()
