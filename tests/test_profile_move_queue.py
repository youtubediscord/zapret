from __future__ import annotations

import unittest
from unittest.mock import Mock

from profile.ui.preset_setup_page import PresetSetupPageBase


class _Signal:
    def connect(self, _callback) -> None:
        return None


class _Worker:
    moved = _Signal()
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


class ProfileMoveQueueTests(unittest.TestCase):
    def test_profile_move_request_keeps_latest_pending_move_while_worker_runs(self) -> None:
        page = PresetSetupPageBase.__new__(PresetSetupPageBase)
        page.launch_method = "zapret2_mode"
        page._profile_move_runtime = _Runtime(running=True)
        page._pending_profile_move = None

        PresetSetupPageBase._request_profile_move(
            page,
            "after",
            "profile-a",
            destination_profile_key="profile-b",
            destination_group_key="games",
        )

        self.assertEqual(
            page._pending_profile_move,
            {
                "action": "after",
                "source_profile_key": "profile-a",
                "destination_profile_key": "profile-b",
                "destination_group_key": "games",
            },
        )

    def test_profile_move_worker_finished_starts_pending_move(self) -> None:
        page = PresetSetupPageBase.__new__(PresetSetupPageBase)
        page.launch_method = "zapret2_mode"
        old_worker = _Worker(running=False)
        next_worker = _Worker(running=False)
        page._profile_move_worker = old_worker
        page._profile_move_request_id = 0
        page._create_profile_move_worker = Mock(return_value=next_worker)
        page._pending_profile_move = {
            "action": "folder",
            "source_profile_key": "profile-a",
            "destination_profile_key": "",
            "destination_group_key": "games",
        }

        PresetSetupPageBase._on_profile_move_worker_finished(page, old_worker)

        page._create_profile_move_worker.assert_called_once_with(
            1,
            "zapret2_mode",
            action="folder",
            source_profile_key="profile-a",
            destination_profile_key="",
            destination_group_key="games",
        )
        next_worker.start.assert_called_once_with()
        self.assertIsNone(page._pending_profile_move)


if __name__ == "__main__":
    unittest.main()
