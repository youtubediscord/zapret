from __future__ import annotations

import unittest
from unittest.mock import Mock, patch

from profile.ui.preset_setup_page import PresetSetupPageBase


class _Signal:
    def connect(self, _callback) -> None:
        return None


class _ContextWorker:
    finished_action = _Signal()
    failed = _Signal()
    finished = _Signal()

    def __init__(self) -> None:
        self.start = Mock()
        self.deleteLater = Mock()


class _MoveWorker:
    moved = _Signal()
    failed = _Signal()
    finished = _Signal()

    def __init__(self) -> None:
        self.start = Mock()
        self.deleteLater = Mock()


class _UserProfileWorker:
    created = _Signal()
    updated = _Signal()
    deleted = _Signal()
    failed = _Signal()
    finished = _Signal()

    def __init__(self) -> None:
        self.start = Mock()
        self.deleteLater = Mock()


class _Runtime:
    def __init__(self, *, running: bool = False) -> None:
        self._running = running

    def is_running(self) -> bool:
        return self._running

    def start_qthread_worker(self, *, worker_factory, **_kwargs):
        worker = worker_factory(0)
        worker.start()
        return 0, worker


class ProfilePresetWriteSerializationTests(unittest.TestCase):
    def test_profile_move_waits_while_context_action_worker_runs(self) -> None:
        page = PresetSetupPageBase.__new__(PresetSetupPageBase)
        page.launch_method = "zapret2_mode"
        page._profile_context_action_runtime = _Runtime(running=True)
        page._profile_move_runtime = _Runtime(running=False)
        page._pending_profile_preset_write_operations = []
        page._pending_profile_moves = []
        page._profile_move_request_id = 0
        page._create_profile_move_worker = Mock(return_value=_MoveWorker())

        PresetSetupPageBase._request_profile_move(
            page,
            "after",
            "profile-a",
            destination_profile_key="profile-b",
            destination_group_key="games",
        )

        page._create_profile_move_worker.assert_not_called()
        self.assertEqual(
            page._pending_profile_preset_write_operations,
            [
                {
                    "kind": "move",
                    "action": "after",
                    "profile_key": "profile-a",
                    "enabled": None,
                    "source_profile_key": "profile-a",
                    "destination_profile_key": "profile-b",
                    "destination_group_key": "games",
                }
            ],
        )

    def test_profile_context_action_waits_while_move_worker_runs(self) -> None:
        page = PresetSetupPageBase.__new__(PresetSetupPageBase)
        page.launch_method = "zapret2_mode"
        page._profile_context_action_runtime = _Runtime(running=False)
        page._profile_move_runtime = _Runtime(running=True)
        page._pending_profile_preset_write_operations = []
        page._pending_profile_context_actions = []
        page._profile_context_action_request_id = 0
        page._profile_context_action_enabled_by_request = {}
        page._create_profile_context_action_worker = Mock(return_value=_ContextWorker())

        PresetSetupPageBase._request_profile_context_action(
            page,
            "set_enabled",
            "profile-a",
            enabled=False,
        )

        page._create_profile_context_action_worker.assert_not_called()
        self.assertEqual(
            page._pending_profile_preset_write_operations,
            [
                {
                    "kind": "context",
                    "action": "set_enabled",
                    "profile_key": "profile-a",
                    "enabled": False,
                    "source_profile_key": "",
                    "destination_profile_key": "",
                    "destination_group_key": "",
                }
            ],
        )

    def test_user_profile_update_waits_while_move_worker_runs(self) -> None:
        page = PresetSetupPageBase.__new__(PresetSetupPageBase)
        page.launch_method = "zapret2_mode"
        page._profile_context_action_runtime = _Runtime(running=False)
        page._profile_move_runtime = _Runtime(running=True)
        page._user_profile_create_runtime = _Runtime(running=False)
        page._user_profile_update_runtime = _Runtime(running=False)
        page._user_profile_delete_runtime = _Runtime(running=False)
        page._pending_profile_preset_write_operations = []
        page._pending_user_profile_operations = []
        page._user_profile_update_request_id = 0
        page._set_user_profile_actions_enabled = Mock()
        page._create_user_profile_update_worker = Mock(return_value=_UserProfileWorker())

        PresetSetupPageBase._request_user_profile_update(
            page,
            "user-profile-1",
            name="Game UDP",
            protocol="udp",
            ports="443",
        )

        page._create_user_profile_update_worker.assert_not_called()
        self.assertEqual(
            page._pending_profile_preset_write_operations,
            [
                {
                    "kind": "user_profile",
                    "action": "update",
                    "profile_key": "user-profile-1",
                    "enabled": None,
                    "source_profile_key": "",
                    "destination_profile_key": "",
                    "destination_group_key": "",
                    "profile_id": "user-profile-1",
                    "name": "Game UDP",
                    "protocol": "udp",
                    "ports": "443",
                }
            ],
        )
        self.assertEqual(
            page._pending_user_profile_operations,
            [
                {
                    "action": "update",
                    "profile_id": "user-profile-1",
                    "name": "Game UDP",
                    "protocol": "udp",
                    "ports": "443",
                }
            ],
        )

    def test_profile_context_action_waits_while_user_profile_worker_runs(self) -> None:
        page = PresetSetupPageBase.__new__(PresetSetupPageBase)
        page.launch_method = "zapret2_mode"
        page._profile_context_action_runtime = _Runtime(running=False)
        page._profile_move_runtime = _Runtime(running=False)
        page._user_profile_create_runtime = _Runtime(running=True)
        page._user_profile_update_runtime = _Runtime(running=False)
        page._user_profile_delete_runtime = _Runtime(running=False)
        page._pending_profile_preset_write_operations = []
        page._pending_profile_context_actions = []
        page._profile_context_action_request_id = 0
        page._profile_context_action_enabled_by_request = {}
        page._create_profile_context_action_worker = Mock(return_value=_ContextWorker())

        PresetSetupPageBase._request_profile_context_action(
            page,
            "set_enabled",
            "profile-a",
            enabled=False,
        )

        page._create_profile_context_action_worker.assert_not_called()
        self.assertEqual(
            page._pending_profile_preset_write_operations,
            [
                {
                    "kind": "context",
                    "action": "set_enabled",
                    "profile_key": "profile-a",
                    "enabled": False,
                    "source_profile_key": "",
                    "destination_profile_key": "",
                    "destination_group_key": "",
                }
            ],
        )

    def test_profile_move_error_ignored_when_next_write_is_pending(self) -> None:
        page = PresetSetupPageBase.__new__(PresetSetupPageBase)
        page._profile_move_request_id = 4
        page._pending_profile_preset_write_operations = [
            {
                "kind": "move",
                "action": "after",
                "profile_key": "profile-a",
                "enabled": None,
                "source_profile_key": "profile-a",
                "destination_profile_key": "profile-b",
                "destination_group_key": "games",
            }
        ]
        page._pending_profile_context_actions = []
        page._pending_profile_moves = [
            {
                "action": "after",
                "source_profile_key": "profile-a",
                "destination_profile_key": "profile-b",
                "destination_group_key": "games",
            }
        ]
        page._pending_user_profile_operations = []
        page.refresh_from_preset_switch = Mock()

        with patch("profile.ui.preset_setup_page.log") as log:
            PresetSetupPageBase._on_profile_move_failed(page, 4, "old error")

        log.assert_not_called()
        page.refresh_from_preset_switch.assert_not_called()

    def test_latest_profile_move_replaces_older_pending_move_for_same_profile(self) -> None:
        page = PresetSetupPageBase.__new__(PresetSetupPageBase)
        page._pending_profile_preset_write_operations = []
        page._pending_profile_context_actions = []
        page._pending_profile_moves = []
        page._pending_user_profile_operations = []

        PresetSetupPageBase._queue_profile_preset_write_operation(
            page,
            "move",
            action="before",
            source_profile_key="profile-a",
            destination_profile_key="profile-b",
            destination_group_key="games",
        )
        PresetSetupPageBase._queue_profile_preset_write_operation(
            page,
            "move",
            action="after",
            source_profile_key="profile-a",
            destination_profile_key="profile-c",
            destination_group_key="games",
        )

        self.assertEqual(
            page._pending_profile_preset_write_operations,
            [
                {
                    "kind": "move",
                    "action": "after",
                    "profile_key": "profile-a",
                    "enabled": None,
                    "source_profile_key": "profile-a",
                    "destination_profile_key": "profile-c",
                    "destination_group_key": "games",
                }
            ],
        )
        self.assertEqual(
            page._pending_profile_moves,
            [
                {
                    "action": "after",
                    "source_profile_key": "profile-a",
                    "destination_profile_key": "profile-c",
                    "destination_group_key": "games",
                }
            ],
        )

    def test_profile_move_queue_keeps_moves_for_different_profiles(self) -> None:
        page = PresetSetupPageBase.__new__(PresetSetupPageBase)
        page._pending_profile_preset_write_operations = []
        page._pending_profile_context_actions = []
        page._pending_profile_moves = []
        page._pending_user_profile_operations = []

        PresetSetupPageBase._queue_profile_preset_write_operation(
            page,
            "move",
            action="before",
            source_profile_key="profile-a",
            destination_profile_key="profile-b",
            destination_group_key="games",
        )
        PresetSetupPageBase._queue_profile_preset_write_operation(
            page,
            "move",
            action="after",
            source_profile_key="profile-c",
            destination_profile_key="profile-d",
            destination_group_key="games",
        )

        self.assertEqual(len(page._pending_profile_preset_write_operations), 2)
        self.assertEqual(len(page._pending_profile_moves), 2)


if __name__ == "__main__":
    unittest.main()
