from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from profile.ui.profile_setup_page import ProfileSetupPageBase


class _Signal:
    def connect(self, _callback) -> None:
        return None


class _Worker:
    saved = _Signal()
    failed = _Signal()
    finished = _Signal()

    def __init__(self, *, running: bool = False) -> None:
        self._running = running
        self.start = Mock()
        self.deleteLater = Mock()

    def isRunning(self) -> bool:  # noqa: N802
        return self._running


class ProfileEnabledSaveQueueTests(unittest.TestCase):
    def test_enabled_change_keeps_pending_final_state_while_worker_runs(self) -> None:
        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._loading = False
        page._profile_key = "profile-1"
        page._payload = SimpleNamespace(item=SimpleNamespace(enabled=False))
        page._enabled_save_worker = _Worker(running=True)
        page._enabled_save_worker_enabled = True
        page._pending_enabled_save = None

        ProfileSetupPageBase._on_enabled_changed(page, 0)

        self.assertIs(page._pending_enabled_save, False)

    def test_enabled_save_worker_finished_starts_pending_final_state(self) -> None:
        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        old_worker = _Worker(running=False)
        next_worker = _Worker(running=False)
        page._enabled_save_worker = old_worker
        page._enabled_save_worker_enabled = True
        page._pending_enabled_save = False
        page._enabled_save_request_id = 0
        page._profile_key = "profile-1"
        page._payload = SimpleNamespace(item=SimpleNamespace(enabled=True))
        page._enabled_checkbox = None
        page._current_filter_kind = Mock(return_value="hostlist")
        page._current_filter_value = Mock(return_value="example.com")
        page.create_profile_enabled_save_worker = Mock(return_value=next_worker)

        ProfileSetupPageBase._on_enabled_save_worker_finished(page, old_worker)

        page.create_profile_enabled_save_worker.assert_called_once_with(
            1,
            profile_key="profile-1",
            enabled=False,
            filter_kind="hostlist",
            filter_value="example.com",
            parent=page,
        )
        next_worker.start.assert_called_once_with()
        self.assertIsNone(page._pending_enabled_save)


if __name__ == "__main__":
    unittest.main()
