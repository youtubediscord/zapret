from __future__ import annotations

import unittest
from unittest.mock import Mock, patch

from profile.ui.preset_setup_page import PresetSetupPageBase


class _Signal:
    def connect(self, _callback) -> None:
        return None


class _Worker:
    created = _Signal()
    updated = _Signal()
    deleted = _Signal()
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


class UserProfileOperationQueueTests(unittest.TestCase):
    def test_user_profile_operations_queue_while_worker_runs(self) -> None:
        page = PresetSetupPageBase.__new__(PresetSetupPageBase)
        page._user_profile_create_runtime = _Runtime(running=True)
        page._user_profile_update_runtime = _Runtime(running=False)
        page._user_profile_delete_runtime = _Runtime(running=False)
        page._pending_user_profile_operations = []

        PresetSetupPageBase._request_user_profile_update(
            page,
            "user-1",
            name="Updated",
            protocol="udp",
            ports="443",
        )
        PresetSetupPageBase._request_user_profile_delete(page, "user-2")

        self.assertEqual(
            page._pending_user_profile_operations,
            [
                {
                    "action": "update",
                    "profile_id": "user-1",
                    "name": "Updated",
                    "protocol": "udp",
                    "ports": "443",
                },
                {
                    "action": "delete",
                    "profile_id": "user-2",
                    "name": "",
                    "protocol": "",
                    "ports": "",
                },
            ],
        )

    def test_user_profile_worker_finished_starts_next_pending_operation(self) -> None:
        page = PresetSetupPageBase.__new__(PresetSetupPageBase)
        page._cleanup_in_progress = False
        page._user_profile_update_request_id = 0
        page._set_user_profile_actions_enabled = Mock()
        next_worker = _Worker(running=False)
        page._create_user_profile_update_worker = Mock(return_value=next_worker)
        page._pending_user_profile_operations = [
            {
                "action": "update",
                "profile_id": "user-1",
                "name": "Updated",
                "protocol": "udp",
                "ports": "443",
            },
            {
                "action": "delete",
                "profile_id": "user-2",
                "name": "",
                "protocol": "",
                "ports": "",
            },
        ]
        callbacks = []

        with patch(
            "profile.ui.preset_setup_page.QTimer.singleShot",
            side_effect=lambda _delay, callback: callbacks.append(callback),
        ):
            PresetSetupPageBase._on_user_profile_create_worker_finished(page, _Worker())

        page._create_user_profile_update_worker.assert_not_called()
        next_worker.start.assert_not_called()
        page._set_user_profile_actions_enabled.assert_not_called()
        self.assertEqual(len(callbacks), 1)

        callbacks[0]()

        page._create_user_profile_update_worker.assert_called_once_with(
            1,
            profile_id="user-1",
            name="Updated",
            protocol="udp",
            ports="443",
        )
        next_worker.start.assert_called_once_with()
        self.assertEqual(
            page._pending_user_profile_operations,
            [
                {
                    "action": "delete",
                    "profile_id": "user-2",
                    "name": "",
                    "protocol": "",
                    "ports": "",
                },
            ],
        )


if __name__ == "__main__":
    unittest.main()
