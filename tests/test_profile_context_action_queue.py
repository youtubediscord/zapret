from __future__ import annotations

import unittest
from unittest.mock import Mock

from profile.ui.preset_setup_page import PresetSetupPageBase


class _Signal:
    def connect(self, _callback) -> None:
        return None


class _Worker:
    finished_action = _Signal()
    failed = _Signal()
    finished = _Signal()

    def __init__(self, *, running: bool = False) -> None:
        self._running = running
        self.start = Mock()
        self.deleteLater = Mock()

    def isRunning(self) -> bool:  # noqa: N802
        return self._running


class _Runtime:
    def __init__(self, *, running: bool = False) -> None:
        self._running = running

    def is_running(self) -> bool:
        return self._running


class ProfileContextActionQueueTests(unittest.TestCase):
    def test_profile_context_action_keeps_latest_pending_action_while_worker_runs(self) -> None:
        page = PresetSetupPageBase.__new__(PresetSetupPageBase)
        page.launch_method = "zapret2_mode"
        page._profile_context_action_runtime = _Runtime(running=True)
        page._pending_profile_context_action = None

        PresetSetupPageBase._request_profile_context_action(
            page,
            "set_enabled",
            "profile-a",
            enabled=False,
        )

        self.assertEqual(
            page._pending_profile_context_action,
            {
                "action": "set_enabled",
                "profile_key": "profile-a",
                "enabled": False,
            },
        )

    def test_profile_context_action_worker_finished_starts_pending_action(self) -> None:
        page = PresetSetupPageBase.__new__(PresetSetupPageBase)
        page.launch_method = "zapret2_mode"
        old_worker = _Worker(running=False)
        next_worker = _Worker(running=False)
        page._profile_context_action_worker = old_worker
        page._profile_context_action_request_id = 0
        page._create_profile_context_action_worker = Mock(return_value=next_worker)
        page._profile_context_action_enabled_by_request = {}
        page._pending_profile_context_action = {
            "action": "duplicate",
            "profile_key": "profile-a",
            "enabled": None,
        }

        PresetSetupPageBase._on_profile_context_action_worker_finished(page, old_worker)

        page._create_profile_context_action_worker.assert_called_once_with(
            1,
            "zapret2_mode",
            action="duplicate",
            profile_key="profile-a",
            enabled=None,
            parent=page,
        )
        next_worker.start.assert_called_once_with()
        self.assertIsNone(page._pending_profile_context_action)


if __name__ == "__main__":
    unittest.main()
