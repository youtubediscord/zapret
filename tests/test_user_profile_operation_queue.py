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

    def test_user_profile_update_queue_keeps_latest_update_for_same_profile(self) -> None:
        page = PresetSetupPageBase.__new__(PresetSetupPageBase)
        page._user_profile_create_runtime = _Runtime(running=True)
        page._user_profile_update_runtime = _Runtime(running=False)
        page._user_profile_delete_runtime = _Runtime(running=False)
        page._pending_profile_preset_write_operations = []
        page._pending_user_profile_operations = []

        PresetSetupPageBase._request_user_profile_update(
            page,
            "user-1",
            name="Old",
            protocol="tcp",
            ports="443",
        )
        PresetSetupPageBase._request_user_profile_update(
            page,
            "user-1",
            name="Latest",
            protocol="udp",
            ports="443,500",
        )

        self.assertEqual(
            page._pending_user_profile_operations,
            [
                {
                    "action": "update",
                    "profile_id": "user-1",
                    "name": "Latest",
                    "protocol": "udp",
                    "ports": "443,500",
                }
            ],
        )
        self.assertEqual(
            [
                (
                    operation["kind"],
                    operation["action"],
                    operation["profile_id"],
                    operation["name"],
                    operation["protocol"],
                    operation["ports"],
                )
                for operation in page._pending_profile_preset_write_operations
            ],
            [("user_profile", "update", "user-1", "Latest", "udp", "443,500")],
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

    def test_user_profile_create_result_ignored_when_next_operation_is_pending(self) -> None:
        page = PresetSetupPageBase.__new__(PresetSetupPageBase)
        page._user_profile_create_request_id = 4
        page._pending_user_profile_operations = [
            {
                "action": "update",
                "profile_id": "user-1",
                "name": "Latest",
                "protocol": "tcp",
                "ports": "443",
            }
        ]
        page._profiles_list = Mock()
        page._profiles_list.add_profile_item.return_value = True
        page.refresh_from_preset_switch = Mock()
        page.window = Mock(return_value=None)

        with patch("profile.ui.preset_setup_page.InfoBar.success") as success:
            PresetSetupPageBase._on_user_profile_create_finished(page, 4, "user-2", object())

        success.assert_not_called()
        page._profiles_list.add_profile_item.assert_not_called()
        page.refresh_from_preset_switch.assert_not_called()

    def test_user_profile_update_result_ignored_when_next_operation_is_pending(self) -> None:
        page = PresetSetupPageBase.__new__(PresetSetupPageBase)
        page._user_profile_update_request_id = 5
        page._pending_user_profile_operations = [
            {
                "action": "delete",
                "profile_id": "user-1",
                "name": "",
                "protocol": "",
                "ports": "",
            }
        ]
        page._profiles_list = Mock()
        page._profiles_list.replace_user_profile_items.return_value = True
        page.refresh_from_preset_switch = Mock()
        page.window = Mock(return_value=None)

        with patch("profile.ui.preset_setup_page.InfoBar.success") as success:
            PresetSetupPageBase._on_user_profile_update_finished(page, 5, "user-1", 3, (object(),))

        success.assert_not_called()
        page._profiles_list.replace_user_profile_items.assert_not_called()
        page.refresh_from_preset_switch.assert_not_called()

    def test_user_profile_delete_result_ignored_when_next_operation_is_pending(self) -> None:
        page = PresetSetupPageBase.__new__(PresetSetupPageBase)
        page._user_profile_delete_request_id = 6
        page._pending_user_profile_operations = [
            {
                "action": "create",
                "profile_id": "",
                "name": "Next",
                "protocol": "tcp",
                "ports": "443",
            }
        ]
        page._profiles_list = Mock()
        page._profiles_list.remove_user_profile_items.return_value = True
        page.refresh_from_preset_switch = Mock()
        page.window = Mock(return_value=None)

        with patch("profile.ui.preset_setup_page.InfoBar.success") as success:
            PresetSetupPageBase._on_user_profile_delete_finished(page, 6, "user-1", 3)

        success.assert_not_called()
        page._profiles_list.remove_user_profile_items.assert_not_called()
        page.refresh_from_preset_switch.assert_not_called()

    def test_user_profile_operation_error_ignored_when_next_operation_is_pending(self) -> None:
        page = PresetSetupPageBase.__new__(PresetSetupPageBase)
        page._pending_user_profile_operations = [
            {
                "action": "update",
                "profile_id": "user-1",
                "name": "Latest",
                "protocol": "tcp",
                "ports": "443",
            }
        ]
        page._user_profile_create_request_id = 7
        page._user_profile_update_request_id = 8
        page._user_profile_delete_request_id = 9
        page.window = Mock(return_value=None)

        with patch("profile.ui.preset_setup_page.InfoBar.error") as error:
            PresetSetupPageBase._on_user_profile_create_failed(page, 7, "old create error")
            PresetSetupPageBase._on_user_profile_update_failed(page, 8, "old update error")
            PresetSetupPageBase._on_user_profile_delete_failed(page, 9, "old delete error")

        error.assert_not_called()


if __name__ == "__main__":
    unittest.main()
