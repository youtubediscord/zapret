from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch


PROJECT_SRC = Path(__file__).resolve().parents[1] / "src"
if str(PROJECT_SRC) not in sys.path:
    sys.path.insert(0, str(PROJECT_SRC))


class UpdaterChangelogLinkQueueTests(unittest.TestCase):
    def test_changelog_link_pending_restarts_after_event_loop_turn(self) -> None:
        import updater.ui.page as updater_page
        from updater.ui.page import ServersPage

        page = ServersPage.__new__(ServersPage)
        page._cleanup_in_progress = False
        page._changelog_link_open_pending = "https://example.org"
        page._start_changelog_link_open_worker = Mock()
        single_shot = Mock(side_effect=lambda _delay, _callback: None)

        with patch.object(updater_page, "QTimer", SimpleNamespace(singleShot=single_shot)):
            ServersPage._on_changelog_link_open_worker_finished(page, object())

        single_shot.assert_called_once()
        self.assertEqual(single_shot.call_args.args[0], 0)
        page._start_changelog_link_open_worker.assert_not_called()

        single_shot.call_args.args[1]()

        page._start_changelog_link_open_worker.assert_called_once_with("https://example.org")

    def test_changelog_link_request_queues_while_start_is_scheduled(self) -> None:
        from updater.ui.page import ServersPage

        runtime = SimpleNamespace(is_running=Mock(return_value=False))
        page = ServersPage.__new__(ServersPage)
        page._changelog_link_open_runtime = runtime
        page._changelog_link_open_start_scheduled = True
        page._changelog_link_open_pending = None
        page._start_changelog_link_open_worker = Mock()

        ServersPage._request_changelog_link_open(page, "https://example.org")

        page._start_changelog_link_open_worker.assert_not_called()
        self.assertEqual(page._changelog_link_open_pending, "https://example.org")

    def test_changelog_link_scheduled_start_uses_latest_pending_url(self) -> None:
        import updater.ui.page as updater_page
        from updater.ui.page import ServersPage

        runtime = SimpleNamespace(is_running=Mock(return_value=False))
        page = ServersPage.__new__(ServersPage)
        page._cleanup_in_progress = False
        page._changelog_link_open_runtime = runtime
        page._changelog_link_open_pending = "https://old.example.org"
        page._changelog_link_open_start_scheduled = False
        page._start_changelog_link_open_worker = Mock()
        single_shot = Mock(side_effect=lambda _delay, _callback: None)

        with patch.object(updater_page, "QTimer", SimpleNamespace(singleShot=single_shot)):
            ServersPage._on_changelog_link_open_worker_finished(page, object())
            ServersPage._request_changelog_link_open(page, "https://new.example.org")

        single_shot.call_args.args[1]()

        page._start_changelog_link_open_worker.assert_called_once_with("https://new.example.org")


if __name__ == "__main__":
    unittest.main()
