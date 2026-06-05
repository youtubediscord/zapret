from __future__ import annotations

import unittest
from unittest.mock import Mock, patch

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
    def test_profile_context_action_queues_pending_actions_while_worker_runs(self) -> None:
        page = PresetSetupPageBase.__new__(PresetSetupPageBase)
        page.launch_method = "zapret2_mode"
        page._profile_context_action_runtime = _Runtime(running=True)
        page._pending_profile_context_actions = []

        PresetSetupPageBase._request_profile_context_action(
            page,
            "set_enabled",
            "profile-a",
            enabled=False,
        )
        PresetSetupPageBase._request_profile_context_action(
            page,
            "duplicate",
            "profile-b",
        )

        self.assertEqual(
            page._pending_profile_context_actions,
            [
                {
                    "action": "set_enabled",
                    "profile_key": "profile-a",
                    "enabled": False,
                },
                {
                    "action": "duplicate",
                    "profile_key": "profile-b",
                    "enabled": None,
                },
            ],
        )

    def test_profile_enabled_context_queue_keeps_latest_state_for_same_profile(self) -> None:
        page = PresetSetupPageBase.__new__(PresetSetupPageBase)
        page.launch_method = "zapret2_mode"
        page._profile_context_action_runtime = _Runtime(running=True)
        page._pending_profile_preset_write_operations = []
        page._pending_profile_context_actions = []

        PresetSetupPageBase._request_profile_context_action(
            page,
            "set_enabled",
            "profile-a",
            enabled=False,
        )
        PresetSetupPageBase._request_profile_context_action(
            page,
            "set_enabled",
            "profile-a",
            enabled=True,
        )

        self.assertEqual(
            page._pending_profile_context_actions,
            [
                {
                    "action": "set_enabled",
                    "profile_key": "profile-a",
                    "enabled": True,
                }
            ],
        )
        self.assertEqual(
            [
                (operation["kind"], operation["action"], operation["profile_key"], operation["enabled"])
                for operation in page._pending_profile_preset_write_operations
            ],
            [("context", "set_enabled", "profile-a", True)],
        )

    def test_profile_context_action_worker_finished_starts_next_pending_action(self) -> None:
        page = PresetSetupPageBase.__new__(PresetSetupPageBase)
        page.launch_method = "zapret2_mode"
        page._cleanup_in_progress = False
        old_worker = _Worker(running=False)
        next_worker = _Worker(running=False)
        page._profile_context_action_worker = old_worker
        page._profile_context_action_request_id = 0
        page._create_profile_context_action_worker = Mock(return_value=next_worker)
        page._profile_context_action_enabled_by_request = {}
        page._pending_profile_context_actions = [
            {
                "action": "duplicate",
                "profile_key": "profile-a",
                "enabled": None,
            },
            {
                "action": "delete",
                "profile_key": "profile-b",
                "enabled": None,
            },
        ]
        callbacks = []

        with patch(
            "profile.ui.preset_setup_page.QTimer.singleShot",
            side_effect=lambda _delay, callback: callbacks.append(callback),
        ):
            PresetSetupPageBase._on_profile_context_action_worker_finished(page, old_worker)

        page._create_profile_context_action_worker.assert_not_called()
        next_worker.start.assert_not_called()
        self.assertEqual(len(callbacks), 1)

        callbacks[0]()

        page._create_profile_context_action_worker.assert_called_once_with(
            1,
            "zapret2_mode",
            action="duplicate",
            profile_key="profile-a",
            enabled=None,
            parent=page,
        )
        next_worker.start.assert_called_once_with()
        self.assertEqual(
            page._pending_profile_context_actions,
            [
                {
                    "action": "delete",
                    "profile_key": "profile-b",
                    "enabled": None,
                }
            ],
        )

    def test_profile_context_action_error_ignored_when_next_action_is_pending(self) -> None:
        page = PresetSetupPageBase.__new__(PresetSetupPageBase)
        page._profile_context_action_request_id = 3
        page._profile_context_action_enabled_by_request = {3: True}
        page._pending_profile_preset_write_operations = [
            {
                "kind": "context",
                "action": "set_enabled",
                "profile_key": "profile-a",
                "enabled": False,
                "source_profile_key": "",
                "destination_profile_key": "",
                "destination_group_key": "",
            }
        ]
        page._pending_profile_context_actions = [
            {
                "action": "set_enabled",
                "profile_key": "profile-a",
                "enabled": False,
            }
        ]
        page._pending_profile_moves = []
        page._pending_user_profile_operations = []
        page.window = Mock(return_value=None)

        with (
            patch("profile.ui.preset_setup_page.InfoBar.error") as error,
            patch("profile.ui.preset_setup_page.log") as log_mock,
        ):
            PresetSetupPageBase._on_profile_context_action_failed(page, 3, "old error")

        error.assert_not_called()
        log_mock.assert_not_called()
        self.assertNotIn(3, page._profile_context_action_enabled_by_request)


if __name__ == "__main__":
    unittest.main()
